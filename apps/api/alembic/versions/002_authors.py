"""create authors table

Revision ID: 002_authors
Revises: 001_create_updated_at_fn
Create Date: 2026-01-25
"""

from alembic import op
import sqlalchemy as sa

revision = "002_authors"
down_revision = "001_updated_at_fn"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "authors",
        sa.Column("author_id", sa.Text(), primary_key=True),
        sa.Column("name_ar", sa.Text(), nullable=True),
        sa.Column("name_latn", sa.Text(), nullable=True),
        sa.Column("kunya", sa.Text(), nullable=True),
        sa.Column("nisba", sa.Text(), nullable=True),
        sa.Column("death_year_ah", sa.Integer(), nullable=True),
        sa.Column("death_year_ce", sa.Integer(), nullable=True),
        sa.Column("birth_year_ah", sa.Integer(), nullable=True),
        sa.Column("birth_year_ce", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("idx_authors_death_year_ce", "authors", ["death_year_ce"])

    op.execute(
        """
        CREATE TRIGGER trg_authors_updated_at
        BEFORE UPDATE ON authors
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_authors_updated_at ON authors;")
    op.drop_index("idx_authors_death_year_ce", table_name="authors")
    op.drop_table("authors")
