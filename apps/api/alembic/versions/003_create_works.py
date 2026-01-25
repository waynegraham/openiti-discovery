"""create works table

Revision ID: 003_create_works
Revises: 002_create_authors
Create Date: 2026-01-25
"""

from alembic import op
import sqlalchemy as sa

revision = "003_create_works"
down_revision = "002_create_authors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "works",
        sa.Column("work_id", sa.Text(), primary_key=True),
        sa.Column("author_id", sa.Text(), nullable=False),
        sa.Column("title_ar", sa.Text(), nullable=True),
        sa.Column("title_latn", sa.Text(), nullable=True),
        sa.Column("genre", sa.Text(), nullable=True),
        sa.Column("work_year_start_ce", sa.Integer(), nullable=True),
        sa.Column("work_year_end_ce", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["author_id"], ["authors.author_id"], onupdate="CASCADE", ondelete="RESTRICT"),
    )

    op.create_index("idx_works_author_id", "works", ["author_id"])

    op.execute(
        """
        CREATE TRIGGER trg_works_updated_at
        BEFORE UPDATE ON works
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_works_updated_at ON works;")
    op.drop_index("idx_works_author_id", table_name="works")
    op.drop_table("works")
