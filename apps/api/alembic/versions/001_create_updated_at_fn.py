"""create set_updated_at trigger function

Revision ID: 001_create_updated_at_fn
Revises: 
Create Date: 2026-01-25
"""

from alembic import op

revision = "001_create_updated_at_fn"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
