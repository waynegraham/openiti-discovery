"""update authors updated_at trigger to use update_updated_at_column

Revision ID: 007_authors_updated_at
Revises: 006_shared_utils
Create Date: 2026-02-02
"""

from alembic import op

revision = "007_authors_updated_at"
down_revision = "006_shared_utils"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_authors_updated_at ON authors;")
    op.execute(
        """
        CREATE TRIGGER trg_authors_updated_at
        BEFORE UPDATE ON authors
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_authors_updated_at ON authors;")
    op.execute(
        """
        CREATE TRIGGER trg_authors_updated_at
        BEFORE UPDATE ON authors
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )
