"""update works updated_at trigger to use update_updated_at_column

Revision ID: 008_works_updated_at
Revises: 007_authors_updated_at
Create Date: 2026-02-02
"""

from alembic import op

revision = "008_works_updated_at"
down_revision = "007_authors_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_works_updated_at ON works;")
    op.execute(
        """
        CREATE TRIGGER trg_works_updated_at
        BEFORE UPDATE ON works
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_works_updated_at ON works;")
    op.execute(
        """
        CREATE TRIGGER trg_works_updated_at
        BEFORE UPDATE ON works
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )
