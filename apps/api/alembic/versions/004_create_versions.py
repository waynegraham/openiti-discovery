"""create versions table

Revision ID: 004_create_versions
Revises: 003_create_works
Create Date: 2026-01-25
"""

from alembic import op
import sqlalchemy as sa

revision = "004_create_versions"
down_revision = "003_create_works"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "versions",
        sa.Column("version_id", sa.Text(), primary_key=True),
        sa.Column("work_id", sa.Text(), nullable=False),
        sa.Column("is_pri", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("lang", sa.Text(), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("repo_path", sa.Text(), nullable=False),
        sa.Column("checksum_sha256", sa.Text(), nullable=True),
        sa.Column("word_count", sa.BigInteger(), nullable=True),
        sa.Column("char_count", sa.BigInteger(), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["work_id"], ["works.work_id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.CheckConstraint("lang IN ('ara','fas','ota')", name="ck_versions_lang"),
        sa.UniqueConstraint("repo_path", name="uq_versions_repo_path"),
    )

    op.create_index("idx_versions_work_id", "versions", ["work_id"])
    op.create_index("idx_versions_is_pri", "versions", ["is_pri"])
    op.create_index("idx_versions_lang", "versions", ["lang"])
    op.create_index("idx_versions_repo_path", "versions", ["repo_path"])

    op.execute(
        """
        CREATE TRIGGER trg_versions_updated_at
        BEFORE UPDATE ON versions
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_versions_updated_at ON versions;")
    op.drop_index("idx_versions_repo_path", table_name="versions")
    op.drop_index("idx_versions_lang", table_name="versions")
    op.drop_index("idx_versions_is_pri", table_name="versions")
    op.drop_index("idx_versions_work_id", table_name="versions")
    op.drop_table("versions")
