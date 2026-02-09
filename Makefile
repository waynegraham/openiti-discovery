SHELL := /bin/bash

# ---- Config you might actually change ----
COMPOSE ?= docker compose
API_SERVICE ?= api
OS_URL ?= http://localhost:9200
OS_TEMPLATE_NAME ?= openiti_chunks_template_v1
OS_TEMPLATE_FILE ?= opensearch/templates/openiti_chunks_template.json
OS_INDEX ?= openiti_chunks_v1
OS_ALIAS ?= openiti_chunks
OS_SIZE_TARGET ?= $(OS_ALIAS)
QDRANT_SIZE_COLLECTION ?= openiti_chunks
CORPUS_SIZE_ROOT ?= /corpus/RELEASE
INDEX_SIZES_OUT_JSON ?= /app/data/eval/output/metrics/index_sizes_report.json
INDEX_SIZES_OUT_CSV ?= /app/data/eval/output/metrics/index_sizes_report.csv
INDEX_SIZES_LOCAL_DIR ?= data/eval/output/metrics

# You can override these when calling make:
# make ingest INGEST_WORK_LIMIT=200 EMBEDDING_DEVICE=cpu
INGEST_WORK_LIMIT ?= 200
INGEST_ONLY_PRI ?= true
INGEST_LANGS ?= ar,en
EMBEDDINGS_ENABLED ?= true
EMBEDDING_DEVICE ?= cpu

# ---- Internal helpers ----
define wait_http
	@echo "Waiting for $(1) ..."
	@for i in $$(seq 1 60); do \
		if curl -fsS "$(1)" >/dev/null 2>&1; then echo "OK: $(1)"; exit 0; fi; \
		sleep 2; \
	done; \
	echo "Timed out waiting for $(1)"; exit 1
endef

.PHONY: help up down reset logs ps \
        wait migrate template-validate template index alias smoke-alias status milestone-1 \
        init init-no-data ingest gpu-ingest frontend-test milestone-5 facet-labels-validate milestone-6 \
        backfill-languages milestone-7 \
        eval-scaffold eval-import-forms eval-corpus-plan eval-qrels-audit \
        eval-qualitative eval-scalability-measure eval-run-subsets \
        eval-run eval-metrics eval-tables eval-record eval-all \
        index-sizes

# ---- Evaluation config ----
EVAL_QUERIES ?= /app/data/eval/queries.json
EVAL_QRELS ?= /app/data/eval/qrels.json
EVAL_RUN_DIR ?= /app/data/eval/output/runs
EVAL_METRICS_DIR ?= /app/data/eval/output/metrics
EVAL_TABLES_DIR ?= /app/data/eval/output/tables
EVAL_SCALABILITY_MANIFEST ?= /app/data/eval/scalability.json
EVAL_CONFIGS ?= baseline,normalized,variant_aware,full_pipeline
EVAL_SIZE ?= 100
EVAL_LANGS ?= ar
EVAL_PRI_ONLY ?= true
EVAL_SCAFFOLD_PER_CATEGORY ?= 4
EVAL_FORMS_QUERIES_CSV ?= /app/data/eval/forms/queries_form.csv
EVAL_FORMS_QRELS_CSV ?= /app/data/eval/forms/qrels_form.csv
EVAL_TARGET_LINES ?= 1000000,5000000,20000000
EVAL_SUBSET_MANIFEST ?= /app/data/eval/subsets.sample.json

help:
	@echo "Targets:"
	@echo "  make init           - Start stack, run migrations, apply template, create index, run subset ingest"
	@echo "  make init-no-data   - Same as init, but skip ingest"
	@echo "  make ingest         - Run subset ingest (defaults: 200 works, PRI, ar/en)"
	@echo "  make gpu-ingest     - Run subset ingest using CUDA image (Windows/Linux + NVIDIA)"
	@echo "  make frontend-test  - Run lightweight frontend route/API integration tests"
	@echo "  make milestone-5    - Run backend API tests plus frontend integration tests for reading routes"
	@echo "  make facet-labels-validate - Validate config/facet_labels.csv editorial data"
	@echo "  make milestone-6    - Run local Milestone 6 checks (facet-label validation)"
	@echo "  make backfill-languages - One-time language normalization backfill (DB + OpenSearch + Qdrant)"
	@echo "  make milestone-7    - Run Milestone 7 backend checks"
	@echo "  make eval-scaffold  - Generate placeholder queries + qrels from paper query framework"
	@echo "  make eval-import-forms - Convert expert CSV forms into queries.json and qrels.json"
	@echo "  make eval-corpus-plan - Estimate INGEST_WORK_LIMIT for target corpus line counts"
	@echo "  make eval-qrels-audit - Validate qrels coverage and consistency"
	@echo "  make eval-qualitative - Build qualitative baseline vs full_pipeline comparison CSV"
	@echo "  make eval-scalability-measure - Build measured scalability CSV (avg/p50/p95 latency)"
	@echo "  make eval-run-subsets - Run ingest+eval across subset manifest definitions"
	@echo "  make eval-run       - Run retrieval experiments for all configurations"
	@echo "  make eval-metrics   - Compute Table X and Table Y CSVs from runs + qrels"
	@echo "  make eval-tables    - Render markdown tables + compute Table Z"
	@echo "  make eval-record    - Append experiment metadata + key metrics to experiment_runs.csv"
	@echo "  make eval-all       - Run eval-run, eval-metrics, eval-tables in sequence"
	@echo "  make index-sizes    - Report OpenSearch/Qdrant/corpus sizes and copy JSON+CSV to host"
	@echo "  make migrate        - Run alembic upgrade head in api container"
	@echo "  make template-validate - Validate OpenSearch template JSON syntax"
	@echo "  make template       - Apply OpenSearch index template"
	@echo "  make index          - Create versioned OpenSearch index"
	@echo "  make smoke-alias    - Write and query a smoke doc through alias"
	@echo "  make milestone-1    - Run Milestone 1 bootstrap validation sequence"
	@echo "  make status         - Show health of postgres/opensearch/qdrant and alias status"
	@echo "  make reset          - docker compose down -v (DANGEROUS: deletes volumes)"
	@echo "  make up             - Bring up core services (postgres/opensearch/qdrant/api/frontend)"
	@echo "  make down           - Bring down stack (keeps volumes)"
	@echo "  make logs           - Tail logs"
	@echo "  make ps             - Show containers"

up:
	$(COMPOSE) up -d postgres opensearch qdrant $(API_SERVICE) frontend

down:
	$(COMPOSE) down

reset:
	$(COMPOSE) down -v

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=200

wait:
	# Postgres is checked via api migration step (psycopg connection), but we still ensure services are reachable
	$(call wait_http,$(OS_URL))
	$(call wait_http,http://localhost:6333/healthz)

migrate:
	@echo "Running Alembic migrations..."
	$(COMPOSE) exec -T $(API_SERVICE) alembic upgrade head

template-validate:
	@echo "Validating OpenSearch template JSON: $(OS_TEMPLATE_FILE)"
	@test -f "$(OS_TEMPLATE_FILE)" || (echo "Missing $(OS_TEMPLATE_FILE)"; exit 1)
	@python -m json.tool "$(OS_TEMPLATE_FILE)" >/dev/null
	@echo "Template JSON is valid."

template:
	@echo "Applying OpenSearch index template: $(OS_TEMPLATE_NAME)"
	@test -f "$(OS_TEMPLATE_FILE)" || (echo "Missing $(OS_TEMPLATE_FILE)"; exit 1)
	curl -fsS -X PUT "$(OS_URL)/_index_template/$(OS_TEMPLATE_NAME)" \
	  -H "Content-Type: application/json" \
	  --data-binary "@$(OS_TEMPLATE_FILE)" >/dev/null
	@echo "Template applied."

index:
	@echo "Creating OpenSearch index: $(OS_INDEX)"
	# Ignore error if index already exists
	@curl -fsS -X PUT "$(OS_URL)/$(OS_INDEX)" >/dev/null || true
	@echo "Index ensured."

alias:
	@echo "Ensuring alias write target: $(OS_ALIAS) -> $(OS_INDEX)"
	# Clear alias from previous versioned indices, then mark this one as the sole write index.
	curl -fsS -X POST "$(OS_URL)/_aliases" \
	  -H "Content-Type: application/json" \
	  -d '{"actions":[{"remove":{"index":"openiti_chunks_v*","alias":"'"$(OS_ALIAS)"'","must_exist":false}},{"add":{"index":"'"$(OS_INDEX)"'","alias":"'"$(OS_ALIAS)"'","is_write_index":true}}]}' >/dev/null
	@echo "Alias ensured."

smoke-alias:
	@echo "Writing smoke doc via alias: $(OS_ALIAS)"
	@SMOKE_ID="smoke-$$(date +%s)"; \
	curl -fsS -X POST "$(OS_URL)/$(OS_ALIAS)/_doc/$$SMOKE_ID?refresh=wait_for" \
	  -H "Content-Type: application/json" \
	  -d '{"chunk_id":"'"$$SMOKE_ID"'","work_id":"smoke_work","version_id":"smoke_version","author_id":"smoke_author","lang":"ar","is_pri":true,"author_name_ar":"smoke","author_name_lat":"smoke","work_title_ar":"smoke","work_title_lat":"smoke","date_ah":1,"date_ce":1,"period":"test","period_tag":"test","region":"test","tags":["smoke"],"version_label":"smoke","type":"passage","title":"smoke","content":"smoke"}' >/dev/null; \
	HTTP_CODE="$$(curl -s -o /dev/null -w "%{http_code}" -X GET "$(OS_URL)/$(OS_ALIAS)/_search" -H "Content-Type: application/json" -d '{"size":1,"query":{"term":{"chunk_id":"'"$$SMOKE_ID"'"}}}')"; \
	if [ "$$HTTP_CODE" != "200" ]; then echo "Alias smoke query failed with HTTP $$HTTP_CODE"; exit 1; fi; \
	curl -fsS -X DELETE "$(OS_URL)/$(OS_ALIAS)/_doc/$$SMOKE_ID?refresh=wait_for" >/dev/null || true
	@echo "Alias smoke write/query passed (HTTP 200)."

status:
	@echo "OpenSearch:"
	@curl -fsS "$(OS_URL)" | head -c 200 || true; echo
	@echo "Qdrant:"
	@curl -fsS "http://localhost:6333/healthz" || true; echo
	@echo "Alias ($(OS_ALIAS)):"
	@curl -fsS "$(OS_URL)/_alias/$(OS_ALIAS)" || echo "Alias missing"
	@echo
	@$(COMPOSE) ps

# ---- High-level workflows ----

milestone-1: up wait template-validate template index alias smoke-alias status
	@echo "Milestone 1 checks complete."

init-no-data: up wait migrate template-validate template index alias smoke-alias status
	@echo "Init complete (no ingest)."

init: up wait migrate template-validate template index alias
	@echo "Running subset ingest..."
	$(MAKE) ingest
	@$(MAKE) status
	@echo "Init complete."

ingest:
	@echo "Running ingest (subset) with:"
	@echo "  INGEST_WORK_LIMIT=$(INGEST_WORK_LIMIT)"
	@echo "  INGEST_ONLY_PRI=$(INGEST_ONLY_PRI)"
	@echo "  INGEST_LANGS=$(INGEST_LANGS)"
	@echo "  EMBEDDINGS_ENABLED=$(EMBEDDINGS_ENABLED)"
	@echo "  EMBEDDING_DEVICE=$(EMBEDDING_DEVICE)"
	$(COMPOSE) --profile ingest run --rm \
	  -e INGEST_MODE=subset \
	  -e INGEST_WORK_LIMIT=$(INGEST_WORK_LIMIT) \
	  -e INGEST_ONLY_PRI=$(INGEST_ONLY_PRI) \
	  -e INGEST_LANGS=$(INGEST_LANGS) \
	  -e EMBEDDINGS_ENABLED=$(EMBEDDINGS_ENABLED) \
	  -e EMBEDDING_DEVICE=$(EMBEDDING_DEVICE) \
	  ingest

gpu-ingest:
	@echo "Running GPU ingest (subset) with:"
	@echo "  INGEST_WORK_LIMIT=$(INGEST_WORK_LIMIT)"
	@echo "  INGEST_ONLY_PRI=$(INGEST_ONLY_PRI)"
	@echo "  INGEST_LANGS=$(INGEST_LANGS)"
	@echo "  EMBEDDINGS_ENABLED=$(EMBEDDINGS_ENABLED)"
	@echo "  EMBEDDING_DEVICE=cuda"
	$(COMPOSE) -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu run --rm --gpus all \
	  -e INGEST_MODE=subset \
	  -e INGEST_WORK_LIMIT=$(INGEST_WORK_LIMIT) \
	  -e INGEST_ONLY_PRI=$(INGEST_ONLY_PRI) \
	  -e INGEST_LANGS=$(INGEST_LANGS) \
	  -e EMBEDDINGS_ENABLED=$(EMBEDDINGS_ENABLED) \
	  -e EMBEDDING_DEVICE=cuda \
	  ingest_cuda

frontend-test:
	cd apps/frontend && npm run test

milestone-5:
	python -m pytest apps/api/tests/test_main_api.py -q
	$(MAKE) frontend-test

facet-labels-validate:
	python apps/api/scripts/validate_facet_labels.py --path config/facet_labels.csv

milestone-6: facet-labels-validate

backfill-languages:
	$(COMPOSE) exec -T $(API_SERVICE) python scripts/backfill_languages.py

milestone-7:
	python -m pytest apps/api/tests/test_language.py apps/api/tests/test_repos_works.py apps/api/tests/test_main_api.py apps/api/tests/test_ingest_language.py -q

eval-run:
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.runner \
	  --queries $(EVAL_QUERIES) \
	  --output-dir $(EVAL_RUN_DIR) \
	  --configs $(EVAL_CONFIGS) \
	  --size $(EVAL_SIZE) \
	  --langs $(EVAL_LANGS) \
	  $(if $(filter true,$(EVAL_PRI_ONLY)),--pri-only,)

eval-metrics:
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.metrics \
	  --run-dir $(EVAL_RUN_DIR) \
	  --qrels $(EVAL_QRELS) \
	  --out-dir $(EVAL_METRICS_DIR) \
	  --p-at 10 \
	  --recall-at 100 \
	  --success-at 10

eval-tables:
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.tables \
	  --metrics-dir $(EVAL_METRICS_DIR) \
	  --out-dir $(EVAL_TABLES_DIR) \
	  --scalability-manifest $(EVAL_SCALABILITY_MANIFEST)

eval-scaffold:
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.scaffold \
	  --out-queries /app/data/eval/queries.placeholder.json \
	  --out-qrels /app/data/eval/qrels.placeholder.json \
	  --per-category $(EVAL_SCAFFOLD_PER_CATEGORY)

eval-import-forms:
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.forms_import \
	  --queries-csv $(EVAL_FORMS_QUERIES_CSV) \
	  --qrels-csv $(EVAL_FORMS_QRELS_CSV) \
	  --out-queries /app/data/eval/queries.json \
	  --out-qrels /app/data/eval/qrels.json \
	  --strict

eval-corpus-plan:
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.corpus_plan \
	  --targets $(EVAL_TARGET_LINES) \
	  --out-json /app/data/eval/output/corpus_plan.json

eval-qrels-audit:
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.qrels_audit \
	  --queries $(EVAL_QUERIES) \
	  --qrels $(EVAL_QRELS) \
	  --out-dir /app/data/eval/output/audit

eval-qualitative:
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.qualitative_cases \
	  --run-dir $(EVAL_RUN_DIR) \
	  --qrels $(EVAL_QRELS) \
	  --out-csv /app/data/eval/output/qualitative_cases.csv \
	  --baseline-config baseline \
	  --full-config full_pipeline \
	  --granularity passage \
	  --top-k 10

eval-scalability-measure:
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.scalability_measure \
	  --manifest $(EVAL_SCALABILITY_MANIFEST) \
	  --out-csv /app/data/eval/output/metrics/table_z_scalability_measured.csv

index-sizes:
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.index_sizes \
	  --opensearch-target $(OS_SIZE_TARGET) \
	  --qdrant-collection $(QDRANT_SIZE_COLLECTION) \
	  --corpus-root $(CORPUS_SIZE_ROOT) \
	  --out-json $(INDEX_SIZES_OUT_JSON) \
	  --out-csv $(INDEX_SIZES_OUT_CSV)
	@python -c "from pathlib import Path; Path(r'$(INDEX_SIZES_LOCAL_DIR)').mkdir(parents=True, exist_ok=True)"
	$(COMPOSE) cp $(API_SERVICE):$(INDEX_SIZES_OUT_JSON) $(INDEX_SIZES_LOCAL_DIR)/
	$(COMPOSE) cp $(API_SERVICE):$(INDEX_SIZES_OUT_CSV) $(INDEX_SIZES_LOCAL_DIR)/
	@echo "Copied reports to $(INDEX_SIZES_LOCAL_DIR)"

eval-run-subsets:
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.subset_runner \
	  --subset-manifest $(EVAL_SUBSET_MANIFEST) \
	  --out-root /app/data/eval/output/subsets \
	  --queries $(EVAL_QUERIES) \
	  --qrels $(EVAL_QRELS) \
	  --configs $(EVAL_CONFIGS) \
	  --size $(EVAL_SIZE) \
	  --langs $(EVAL_LANGS) \
	  $(if $(filter true,$(EVAL_PRI_ONLY)),--pri-only,) \
	  --embeddings-enabled true \
	  --embedding-device $(EMBEDDING_DEVICE) \
	  --scalability-manifest $(EVAL_SCALABILITY_MANIFEST) \
	  --update-manifest $(EVAL_SCALABILITY_MANIFEST)

eval-record:
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.record \
	  --queries $(EVAL_QUERIES) \
	  --qrels $(EVAL_QRELS) \
	  --run-dir $(EVAL_RUN_DIR) \
	  --metrics-dir $(EVAL_METRICS_DIR) \
	  --tables-dir $(EVAL_TABLES_DIR) \
	  --out-csv /app/data/eval/output/experiment_runs.csv \
	  --append

eval-all:
	$(MAKE) eval-run
	$(MAKE) eval-metrics
	$(MAKE) eval-tables
	$(MAKE) eval-record
