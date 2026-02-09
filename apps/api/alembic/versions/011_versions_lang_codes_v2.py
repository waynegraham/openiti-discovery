"""expand versions.lang check constraint for canonical language codes

Revision ID: 011_versions_lang_codes_v2
Revises: 010_ingest_state_updated_at
Create Date: 2026-02-08
"""

from alembic import op

revision = "011_versions_lang_codes_v2"
down_revision = "010_ingest_state_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_versions_lang", "versions", type_="check")
    op.create_check_constraint(
        "ck_versions_lang",
        "versions",
        "lang IN ('ar','en','fa','unknown','ara','fas','ota')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_versions_lang", "versions", type_="check")
    op.create_check_constraint(
        "ck_versions_lang",
        "versions",
        "lang IN ('ara','fas','ota')",
    )
