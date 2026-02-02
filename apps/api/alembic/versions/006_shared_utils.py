"""add shared postgres utilities (pg_trgm + updated_at trigger)

Revision ID: 006_shared_utils
Revises: 005_chunks_ingest
Create Date: 2026-02-02
"""

from typing import Optional

from alembic import op

revision = "006_shared_utils"
down_revision = "005_chunks_ingest"
branch_labels = None
depends_on = None


def apply_updated_at_trigger(table_name: str, trigger_name: Optional[str] = None) -> None:
    """Helper to apply/update the updated_at trigger for a table."""
    trigger = trigger_name or f"trg_{table_name}_updated_at"
    op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table_name};")
    op.execute(
        f"""
        CREATE TRIGGER {trigger}
        BEFORE UPDATE ON {table_name}
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
