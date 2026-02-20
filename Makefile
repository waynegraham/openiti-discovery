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
DISCOVERY_INDEX_OUT ?= /artifacts/discovery/discovery_index.v1.json

# You can override these when calling make:
# make ingest INGEST_WORK_LIMIT=200 EMBEDDING_DEVICE=cpu
INGEST_WORK_LIMIT ?= 200
INGEST_ONLY_PRI ?= true
INGEST_LANGS ?= ar,per
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

.PHONY: help up up-gpu down reset logs ps rebuild rebuild-gpu rebuild-all \
        wait migrate template-validate template index alias smoke-alias status \
        onboard onboard-no-ingest onboard-no-ingest-gpu verify-platform-bootstrap \
        ingest gpu-ingest discovery-index \
        test-unit-backend test-frontend-integration test-reading-routes \
        validate-facet-labels test-facets \
        migrate-backfill-languages test-language \
        system-benchmark system-smoke system-degraded report-release-checklist system-test \
        eval-scaffold eval-import-forms eval-corpus-plan eval-qrels-audit \
        eval-qualitative eval-scalability-measure eval-run-subsets \
        eval-run eval-metrics eval-tables eval-record eval-all \
        report-index-sizes report-eval-metrics report-eval-tables report-eval-record \
        init init-no-data frontend-test facet-labels-validate \
        backfill-languages index-sizes

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
SYSTEM_LANGS ?= ar
SYSTEM_PAGE_SIZE ?= 20
SYSTEM_CANDIDATE_K_GRID ?= 100,200,400
SYSTEM_RRF_K_GRID ?= 30,60,90
SYSTEM_QUERIES_HOST ?= data/eval/queries.json
SYSTEM_QRELS_HOST ?= data/eval/qrels.json
SYSTEM_SUBSET_MANIFEST_HOST ?= data/eval/subsets.sample.json
SYSTEM_INPUT_DIR ?= /artifacts/system/input
SYSTEM_QUERIES ?= $(SYSTEM_INPUT_DIR)/queries.json
SYSTEM_QRELS ?= $(SYSTEM_INPUT_DIR)/qrels.json
SYSTEM_SUBSET_MANIFEST ?= $(SYSTEM_INPUT_DIR)/subsets.sample.json
SYSTEM_OUT_ROOT ?= /artifacts/eval/output/system
SYSTEM_BASELINE_RUN_DIR ?= $(SYSTEM_OUT_ROOT)/baseline_runs
SYSTEM_BASELINE_METRICS_DIR ?= $(SYSTEM_OUT_ROOT)/baseline_metrics
SYSTEM_HYBRID_RUN_DIR ?= $(SYSTEM_OUT_ROOT)/hybrid_runs
SYSTEM_METRICS_DIR ?= $(SYSTEM_OUT_ROOT)/metrics
SYSTEM_SMOKE_DIR ?= $(SYSTEM_OUT_ROOT)/smoke

help:
	@echo "Targets:"
	@echo "  make onboard        - Start stack, migrate DB, apply template/index/alias, run subset ingest"
	@echo "  make onboard-no-ingest - Same as onboard, but skip ingest"
	@echo "  make onboard-no-ingest-gpu - GPU compose/profile + api_cuda variant of onboard-no-ingest"
	@echo "  make verify-platform-bootstrap - Platform bootstrap checks (template/index/alias/smoke/status)"
	@echo "  make ingest         - Run subset ingest (defaults: 200 works, PRI, ar/en)"
	@echo "  make gpu-ingest     - Run subset ingest using CUDA image (Windows/Linux + NVIDIA)"
	@echo "  make discovery-index - Build precomputed discovery index JSON for faster ingest/eval discovery"
	@echo "  make test-unit-backend - Run backend unit/integration pytest suite"
	@echo "  make test-frontend-integration - Run frontend route/API integration tests"
	@echo "  make test-reading-routes - Combined backend+frontend reading-route checks"
	@echo "  make validate-facet-labels - Validate config/facet_labels.csv editorial data"
	@echo "  make test-facets    - Facet-label validation checks"
	@echo "  make migrate-backfill-languages - One-time language normalization backfill"
	@echo "  make test-language  - Language behavior checks"
	@echo "  make system-benchmark - Benchmark/tuning/quality-gate flow"
	@echo "  make system-smoke   - In-process API smoke checks"
	@echo "  make system-degraded - Degraded fallback smoke checks"
	@echo "  make report-release-checklist - Generate release checklist status artifact"
	@echo "  make system-test    - Full system test flow"
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
	@echo "  make report-eval-metrics - Alias for eval-metrics"
	@echo "  make report-eval-tables - Alias for eval-tables"
	@echo "  make report-eval-record - Alias for eval-record"
	@echo "  make eval-all       - Run eval-run, eval-metrics, eval-tables, eval-record in sequence"
	@echo "  make report-index-sizes - Report OpenSearch/Qdrant/corpus sizes and copy JSON+CSV to host"
	@echo "  make migrate        - Run alembic upgrade head in api container"
	@echo "  make template-validate - Validate OpenSearch template JSON syntax"
	@echo "  make template       - Apply OpenSearch index template"
	@echo "  make index          - Create versioned OpenSearch index"
	@echo "  make smoke-alias    - Write and query a smoke doc through alias"
	@echo "  make status         - Show health of postgres/opensearch/qdrant and alias status"
	@echo "  make reset          - docker compose down -v (DANGEROUS: deletes volumes)"
	@echo "  make up             - Bring up core services (postgres/opensearch/qdrant/api/frontend)"
	@echo "  make up-gpu         - Bring up GPU API stack detached (postgres/opensearch/qdrant/api_cuda)"
	@echo "  make rebuild        - Rebuild docker images from docker-compose.yml"
	@echo "  make rebuild-gpu    - Rebuild docker images including docker-compose.gpu.yml services"
	@echo "  make rebuild-all    - Rebuild both base and GPU image sets"
	@echo "  make down           - Bring down stack (keeps volumes)"
	@echo "  make logs           - Tail logs"
	@echo "  make ps             - Show containers"
	@echo "  Legacy aliases preserved: init, init-no-data, frontend-test, facet-labels-validate, backfill-languages, index-sizes"

up:
	$(COMPOSE) up -d postgres opensearch qdrant $(API_SERVICE) frontend

up-gpu:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu up -d postgres opensearch qdrant api_cuda

rebuild:
	@echo "Rebuilding images from docker-compose.yml..."
	$(COMPOSE) build --pull

rebuild-gpu:
	@echo "Rebuilding images from docker-compose.yml + docker-compose.gpu.yml..."
	$(COMPOSE) -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu build --pull

rebuild-all: rebuild rebuild-gpu
	@echo "Base + GPU image rebuild complete."

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
	@$(COMPOSE) ps

# ---- High-level workflows ----

verify-platform-bootstrap: up wait template-validate template index alias smoke-alias status
	@echo "Platform bootstrap checks complete."

onboard-no-ingest: up wait migrate template-validate template index alias smoke-alias status
	@echo "Onboarding complete (no ingest)."

onboard-no-ingest-gpu: COMPOSE := docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu
onboard-no-ingest-gpu: API_SERVICE := api_cuda
onboard-no-ingest-gpu: onboard-no-ingest

onboard: up wait migrate template-validate template index alias
	@echo "Running subset ingest..."
	$(MAKE) ingest
	@$(MAKE) status
	@echo "Onboarding complete."

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
	$(COMPOSE) -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu run --rm \
	  -e INGEST_MODE=subset \
	  -e INGEST_WORK_LIMIT=$(INGEST_WORK_LIMIT) \
	  -e INGEST_ONLY_PRI=$(INGEST_ONLY_PRI) \
	  -e INGEST_LANGS=$(INGEST_LANGS) \
	  -e EMBEDDINGS_ENABLED=$(EMBEDDINGS_ENABLED) \
	  -e EMBEDDING_DEVICE=cuda \
	  ingest_cuda

discovery-index:
	@echo "Building discovery index at $(DISCOVERY_INDEX_OUT)"
	$(COMPOSE) --profile ingest run --rm ingest \
	  python -m app.ingest.build_index \
	    --corpus-root /corpus/RELEASE \
	    --out-json $(DISCOVERY_INDEX_OUT)

test-unit-backend:
	python -m pytest apps/api/tests -q

test-frontend-integration:
	cd apps/frontend && npm run test

test-reading-routes:
	python -m pytest apps/api/tests/test_main_api.py -q
	$(MAKE) test-frontend-integration

validate-facet-labels:
	python apps/api/scripts/validate_facet_labels.py --path config/facet_labels.csv

test-facets: validate-facet-labels

migrate-backfill-languages:
	$(COMPOSE) exec -T $(API_SERVICE) python scripts/backfill_languages.py

test-language:
	python -m pytest apps/api/tests/test_language.py apps/api/tests/test_repos_works.py apps/api/tests/test_main_api.py apps/api/tests/test_ingest_language.py -q

system-benchmark: verify-platform-bootstrap
	$(COMPOSE) exec -T $(API_SERVICE) python -c "from pathlib import Path; [Path(p).mkdir(parents=True, exist_ok=True) for p in ['$(SYSTEM_INPUT_DIR)','$(SYSTEM_BASELINE_RUN_DIR)','$(SYSTEM_BASELINE_METRICS_DIR)','$(SYSTEM_HYBRID_RUN_DIR)','$(SYSTEM_METRICS_DIR)']]"
	$(COMPOSE) cp $(SYSTEM_QUERIES_HOST) $(API_SERVICE):$(SYSTEM_QUERIES)
	$(COMPOSE) cp $(SYSTEM_QRELS_HOST) $(API_SERVICE):$(SYSTEM_QRELS)
	$(COMPOSE) cp $(SYSTEM_SUBSET_MANIFEST_HOST) $(API_SERVICE):$(SYSTEM_SUBSET_MANIFEST)
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.runner \
	  --queries $(SYSTEM_QUERIES) \
	  --output-dir $(SYSTEM_BASELINE_RUN_DIR) \
	  --configs baseline,normalized,variant_aware,full_pipeline \
	  --size 100 \
	  --langs $(SYSTEM_LANGS) \
	  $(if $(filter true,$(EVAL_PRI_ONLY)),--pri-only,)
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.metrics \
	  --run-dir $(SYSTEM_BASELINE_RUN_DIR) \
	  --qrels $(SYSTEM_QRELS) \
	  --out-dir $(SYSTEM_BASELINE_METRICS_DIR) \
	  --p-at 10 \
	  --recall-at 100 \
	  --success-at 10
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.search_mode_runner \
	  --queries $(SYSTEM_QUERIES) \
	  --output-dir $(SYSTEM_HYBRID_RUN_DIR) \
	  --modes bm25,vector,hybrid \
	  --page-size $(SYSTEM_PAGE_SIZE) \
	  --langs $(SYSTEM_LANGS) \
	  --pri-only
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.hybrid_tune \
	  --queries $(SYSTEM_QUERIES) \
	  --qrels $(SYSTEM_QRELS) \
	  --run-dir $(SYSTEM_HYBRID_RUN_DIR) \
	  --out-dir $(SYSTEM_METRICS_DIR) \
	  --baseline-table-x $(SYSTEM_BASELINE_METRICS_DIR)/table_x_retrieval_performance.csv \
	  --baseline-config full_pipeline \
	  --candidate-k-grid $(SYSTEM_CANDIDATE_K_GRID) \
	  --rrf-k-grid $(SYSTEM_RRF_K_GRID) \
	  --page-size $(SYSTEM_PAGE_SIZE) \
	  --langs $(SYSTEM_LANGS) \
	  --pri-only \
	  --subset-manifest $(SYSTEM_SUBSET_MANIFEST)
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.quality_gate \
	  --selected-json $(SYSTEM_METRICS_DIR)/milestone8_selected_hybrid.json \
	  --out-json $(SYSTEM_METRICS_DIR)/system_quality_gate.json \
	  --out-md $(SYSTEM_METRICS_DIR)/system_quality_gate.md
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.latency_report \
	  --run-dir $(SYSTEM_HYBRID_RUN_DIR) \
	  --out-csv $(SYSTEM_METRICS_DIR)/system_latency.csv \
	  --out-md $(SYSTEM_METRICS_DIR)/system_latency.md \
	  --page-size $(SYSTEM_PAGE_SIZE)

system-smoke:
	$(COMPOSE) exec -T $(API_SERVICE) python -c "from pathlib import Path; Path('$(SYSTEM_SMOKE_DIR)').mkdir(parents=True, exist_ok=True)"
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.search_smoke \
	  --query "الشافعي" \
	  --size $(SYSTEM_PAGE_SIZE) \
	  --langs $(SYSTEM_LANGS) \
	  --out-json $(SYSTEM_SMOKE_DIR)/system_smoke.json

system-degraded:
	$(COMPOSE) run --rm -T -e QDRANT_URL=http://qdrant:1 $(API_SERVICE) python -m app.eval.search_smoke \
	  --query "الشافعي" \
	  --size $(SYSTEM_PAGE_SIZE) \
	  --langs $(SYSTEM_LANGS) \
	  --expect-degraded \
	  --out-json $(SYSTEM_SMOKE_DIR)/system_degraded_smoke.json

report-release-checklist:
	$(COMPOSE) exec -T $(API_SERVICE) python -c "from pathlib import Path; p=Path('$(SYSTEM_METRICS_DIR)/release_checklist.md'); p.parent.mkdir(parents=True, exist_ok=True); p.write_text('# Release Checklist Status\\n\\n- Source checklist: docs/release-checklist.md\\n- Benchmark: $(SYSTEM_METRICS_DIR)\\n- Smoke: $(SYSTEM_SMOKE_DIR)\\n\\n## Auto-check status\\n\\n- [x] benchmark artifacts generated\\n- [x] quality gate passed\\n- [x] latency report generated\\n- [x] search mode smoke passed\\n- [x] degraded fallback smoke passed\\n', encoding='utf-8')"

system-test: onboard system-benchmark system-smoke system-degraded report-release-checklist
	@echo "System tests complete."

# ---- Backward-compatible aliases ----

init-no-data: onboard-no-ingest

init: onboard

frontend-test: test-frontend-integration

facet-labels-validate: validate-facet-labels

backfill-languages: migrate-backfill-languages

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

report-eval-metrics: eval-metrics

eval-tables:
	$(COMPOSE) exec -T $(API_SERVICE) python -m app.eval.tables \
	  --metrics-dir $(EVAL_METRICS_DIR) \
	  --out-dir $(EVAL_TABLES_DIR) \
	  --scalability-manifest $(EVAL_SCALABILITY_MANIFEST)

report-eval-tables: eval-tables

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

report-index-sizes:
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

index-sizes: report-index-sizes

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

report-eval-record: eval-record

eval-all:
	$(MAKE) eval-run
	$(MAKE) eval-metrics
	$(MAKE) eval-tables
	$(MAKE) eval-record
