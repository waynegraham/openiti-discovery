# Updates

1. Migrate DB `docker compose exec api alembic upgrade head`
2. Ensure OpenSearch index alias exists (`curl -X GET http://localhost:9200/_alias/openiti_chunks`)