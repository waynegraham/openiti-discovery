SHELL := /bin/bash

# ---- Config you might actually change ----
COMPOSE ?= docker compose
API_SERVICE ?= api
OS_URL ?= http://localhost:9200
OS_TEMPLATE_NAME ?= openiti_chunks_template_v1
OS_TEMPLATE_FILE ?= opensearch/templates/openiti_chunks_template.json
OS_INDEX ?= openiti_chunks_v1
OS_ALIAS ?= openiti_chunks

# You can override these when calling make:
# make ingest INGEST_WORK_LIMIT=200 EMBEDDING_DEVICE=cpu
INGEST_WORK_LIMIT ?= 200
INGEST_ONLY_PRI ?= true
INGEST_LANGS ?= ara
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
        wait migrate template index alias status \
        init init-no-data ingest gpu-ingest \
        eval-scaffold eval-import-forms eval-corpus-plan eval-qrels-audit \
        eval-qualitative eval-scalability-measure eval-run-subsets \
        eval-run eval-metrics eval-tables eval-record eval-all

# ---- Evaluation config ----
EVAL_QUERIES ?= /app/data/eval/queries.json
EVAL_QRELS ?= /app/data/eval/qrels.json
EVAL_RUN_DIR ?= /app/data/eval/output/runs
EVAL_METRICS_DIR ?= /app/data/eval/output/metrics
EVAL_TABLES_DIR ?= /app/data/eval/output/tables
EVAL_SCALABILITY_MANIFEST ?= /app/data/eval/scalability.json
EVAL_CONFIGS ?= baseline,normalized,variant_aware,full_pipeline
EVAL_SIZE ?= 100
EVAL_LANGS ?= ara
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
	@echo "  make ingest         - Run subset ingest (defaults: 200 works, PRI, ara)"
	@echo "  make gpu-ingest     - Run subset ingest using CUDA image (Windows/Linux + NVIDIA)"
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
	@echo "  make migrate        - Run alembic upgrade head in api container"
	@echo "  make template       - Apply OpenSearch index template"
	@echo "  make index          - Create versioned OpenSearch index (and alias if in template)"
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
	@echo "Ensuring alias exists: $(OS_ALIAS) -> $(OS_INDEX)"
	# If template already assigns alias at index creation, this is harmless.
	curl -fsS -X POST "$(OS_URL)/_aliases" \
	  -H "Content-Type: application/json" \
	  -d '{"actions":[{"add":{"index":"'"$(OS_INDEX)"'","alias":"'"$(OS_ALIAS)"'"}}]}' >/dev/null
	@echo "Alias ensured."

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

init-no-data: up wait migrate template index alias status
	@echo "Init complete (no ingest)."

init: up wait migrate template index alias
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
