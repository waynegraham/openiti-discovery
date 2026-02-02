"""update chunks updated_at trigger to use update_updated_at_column

Revision ID: 009_chunks_updated_at
Revises: 008_works_updated_at
Create Date: 2026-02-02
"""

from alembic import op

revision = "009_chunks_updated_at"
down_revision = "008_works_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_chunks_updated_at ON chunks;")
    op.execute(
        """
        CREATE TRIGGER trg_chunks_updated_at
        BEFORE UPDATE ON chunks
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_chunks_updated_at ON chunks;")
    op.execute(
        """
        CREATE TRIGGER trg_chunks_updated_at
        BEFORE UPDATE ON chunks
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )
