# Database Migrations (Alembic)

This project uses Alembic to manage PostgreSQL schema migrations.

## Prerequisites

- Docker Compose stack is running (at least `postgres` and `api`)
- The `api` container has:
  - `alembic` installed
  - SQLAlchemy installed
  - psycopg3 installed (`psycopg[binary]` or equivalent)
- `DATABASE_URL` is set in the `api` container environment.

Example `DATABASE_URL`:

postgresql+psycopg://openiti:openiti@postgres:5432/openiti

## Run migrations

### 1) Start services

```bash
docker compose up -d postgres api
```
### 2) Upgrade to latest

Run from the host:

```bash
docker compose exec api alembic upgrade head
```

Or, if your working directory inside the container isn’t `apps/api`, specify the config:

```bash
docker compose exec -w /app/apps/api api alembic -c alembic.ini upgrade head
```

### Check current revision

```bash
docker compose exec api alembic current
```

### Show migration history

```bash
docker compose exec api alembic history
```

## Downgrade (use carefully)

Downgrade one revision:

```bash
docker compose exec api alembic downgrade -1
```

Downgrade to a specific revision:

```bash
docker compose exec api alembic downgrade 004_create_versions
```

## Notes

* Migrations are written to be deterministic and safe.
* Do not change existing migrations after they are merged; create a new revision.
* `updated_at` is maintained via PostgreSQL triggers created in migration `001_create_updated_at_fn`.

---

## 6) Make sure the API image can run Alembic

Your `apps/api/Dockerfile` needs to include alembic dependencies. In `requirements.txt` (or equivalent) you want:

```txt
alembic>=1.13
SQLAlchemy>=2.0
psycopg[binary]>=3.1
```

If you’re missing psycopg3, Alembic will fail in the container and you’ll get to learn what “driver not found” means in five different stack traces.

