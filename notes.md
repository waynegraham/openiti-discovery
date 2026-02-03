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

docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu run --rm \
  -e INGEST_MODE=subset \
  -e INGEST_WORK_LIMIT=200 \
  -e INGEST_ONLY_PRI=true \
  -e INGEST_LANGS=ara \
  -e EMBEDDINGS_ENABLED=true \
  -e EMBEDDING_DEVICE=cuda \
  ingest_cuda