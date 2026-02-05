# Updates

1. Migrate DB `docker compose exec api alembic upgrade head`
2. Create the index (`curl -X PUT "http://localhost:9200/openiti_chunks_v1"`)
2. Ensure OpenSearch index alias exists (`curl -X GET http://localhost:9200/_alias/openiti_chunks`)
3. Run ingest (200 works, PRI, Arabic)

docker compose --profile ingest run --rm ingest

docker compose --profile ingest run --rm \
  -e INGEST_WORK_LIMIT=500 \
  -e EMBEDDINGS_ENABLED=true \
  -e INGEST_MODE=subset \
  -e INGEST_ONLY_PRI=true  \
  -e EMBEDDING_DEVICE=cuda \
  ingest


docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu run --rm ingest_cuda



docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu run --rm \
  -e INGEST_MODE=subset \
  -e INGEST_WORK_LIMIT=200 \
  -e INGEST_ONLY_PRI=true \
  -e INGEST_LANGS=ara \
  -e EMBEDDINGS_ENABLED=true \
  -e EMBEDDING_DEVICE=cuda \
  ingest_cuda

## PowerShell

```
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu run --rm `
   -e INGEST_MODE=subset `
   -e INGEST_WORK_LIMIT=200 `
   -e INGEST_ONLY_PRI=true `
   -e INGEST_LANGS=ara `
   -e EMBEDDINGS_ENABLED=true `
   -e EMBEDDING_DEVICE=gpu `
   ingest_cuda
```

## Checks

# status counts
docker compose exec -T postgres psql -U openiti -d openiti \
  -c "select status, count(*) from ingest_state group by status order by count(*) desc;"

# recent updates (if updated_at exists)
docker compose exec -T postgres psql -U openiti -d openiti \
  -c "select version_id, status, last_chunk_index, updated_at from ingest_state order by updated_at desc limit 10;"

# basic row counts
docker compose exec -T postgres psql -U openiti -d openiti \
  -c "select 'authors' as table, count(*) from authors
      union all select 'works', count(*) from works
      union all select 'versions', count(*) from versions
      union all select 'chunks', count(*) from chunks;"

## OpenSearch

# 1) Apply template
curl -X PUT http://localhost:9200/_index_template/openiti_chunks_template_v1 \
  -H "Content-Type: application/json" \
  -d @opensearch/templates/openiti_chunks_template.json

# 2) Create new index (version bump)
curl -X PUT http://localhost:9200/openiti_chunks_v2


