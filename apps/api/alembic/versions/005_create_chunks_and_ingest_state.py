"""create chunks and ingest_state tables

Revision ID: 005_create_chunks_and_ingest_state
Revises: 004_create_versions
Create Date: 2026-01-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005_create_chunks_and_ingest_state"
down_revision = "004_create_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # chunks
    op.create_table(
        "chunks",
        sa.Column("chunk_id", sa.Text(), primary_key=True),

        sa.Column("version_id", sa.Text(), nullable=False),
        sa.Column("work_id", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Text(), nullable=False),

        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading_path", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("heading_text", sa.Text(), nullable=True),

        sa.Column("start_char_offset", sa.Integer(), nullable=True),
        sa.Column("end_char_offset", sa.Integer(), nullable=True),

        sa.Column("text_raw", sa.Text(), nullable=False),
        sa.Column("text_norm", sa.Text(), nullable=False),

        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),

        sa.Column("prev_chunk_id", sa.Text(), nullable=True),
        sa.Column("next_chunk_id", sa.Text(), nullable=True),

        sa.Column("metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),

        sa.ForeignKeyConstraint(["version_id"], ["versions.version_id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_id"], ["works.work_id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["author_id"], ["authors.author_id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["prev_chunk_id"], ["chunks.chunk_id"], onupdate="CASCADE", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["next_chunk_id"], ["chunks.chunk_id"], onupdate="CASCADE", ondelete="SET NULL"),
        sa.UniqueConstraint("version_id", "chunk_index", name="uq_chunks_version_chunk_index"),
        sa.CheckConstraint("chunk_index >= 0", name="ck_chunks_chunk_index_nonneg"),
    )

    op.create_index("idx_chunks_version_id", "chunks", ["version_id"])
    op.create_index("idx_chunks_work_id", "chunks", ["work_id"])
    op.create_index("idx_chunks_author_id", "chunks", ["author_id"])
    op.create_index("idx_chunks_version_chunk_index", "chunks", ["version_id", "chunk_index"])

    op.execute(
        """
        CREATE TRIGGER trg_chunks_updated_at
        BEFORE UPDATE ON chunks
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )

    # ingest_state
    op.create_table(
        "ingest_state",
        sa.Column("version_id", sa.Text(), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("last_step_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_chunk_index", sa.Integer(), nullable=True),
        sa.Column("opensearch_index", sa.Text(), nullable=True),
        sa.Column("qdrant_collection", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_context", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_by", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["version_id"], ["versions.version_id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_ingest_state_attempt_count_nonneg"),
    )

    op.create_index("idx_ingest_state_status", "ingest_state", ["status"])
    op.create_index("idx_ingest_state_locked_at", "ingest_state", ["locked_at"])

    op.execute(
        """
        CREATE TRIGGER trg_ingest_state_updated_at
        BEFORE UPDATE ON ingest_state
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_ingest_state_updated_at ON ingest_state;")
    op.drop_index("idx_ingest_state_locked_at", table_name="ingest_state")
    op.drop_index("idx_ingest_state_status", table_name="ingest_state")
    op.drop_table("ingest_state")

    op.execute("DROP TRIGGER IF EXISTS trg_chunks_updated_at ON chunks;")
    op.drop_index("idx_chunks_version_chunk_index", table_name="chunks")
    op.drop_index("idx_chunks_author_id", table_name="chunks")
    op.drop_index("idx_chunks_work_id", table_name="chunks")
    op.drop_index("idx_chunks_version_id", table_name="chunks")
    op.drop_table("chunks")
