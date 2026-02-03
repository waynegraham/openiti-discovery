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
        init init-no-data ingest gpu-ingest

help:
	@echo "Targets:"
	@echo "  make init           - Start stack, run migrations, apply template, create index, run subset ingest"
	@echo "  make init-no-data   - Same as init, but skip ingest"
	@echo "  make ingest         - Run subset ingest (defaults: 200 works, PRI, ara)"
	@echo "  make gpu-ingest     - Run subset ingest using CUDA image (Windows/Linux + NVIDIA)"
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
	$(COMPOSE) -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu run --rm \
	  -e INGEST_MODE=subset \
	  -e INGEST_WORK_LIMIT=$(INGEST_WORK_LIMIT) \
	  -e INGEST_ONLY_PRI=$(INGEST_ONLY_PRI) \
	  -e INGEST_LANGS=$(INGEST_LANGS) \
	  -e EMBEDDINGS_ENABLED=$(EMBEDDINGS_ENABLED) \
	  -e EMBEDDING_DEVICE=cuda \
	  ingest_cuda
