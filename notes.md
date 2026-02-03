# Updates

1. Migrate DB `docker compose exec api alembic upgrade head`
2. Create the index (`curl -X PUT "http://localhost:9200/openiti_chunks_v1"`)
2. Ensure OpenSearch index alias exists (`curl -X GET http://localhost:9200/_alias/openiti_chunks`)
3. Run ingest (200 works, PRI, Arabic)

docker compose --profile ingest run --rm ingest



docker compose --profile ingest run --rm \
  -e INGEST_WORK_LIMIT=1 \
  -e EMBEDDINGS_ENABLED=false \
  ingest