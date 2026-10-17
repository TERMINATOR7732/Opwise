"""Add workspace index to import_jobs table.

Revision ID: 002_add_import_jobs_index
Revises: 001_initial_schema
Create Date: 2026-10-17 22:30:00.000000

Governed by DATA_AND_API.md Section 1.1 and ARCHITECTURE.md.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "002_add_import_jobs_index"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add index on workspace_id for import_jobs."""
    op.create_index(
        "ix_import_jobs_workspace_id",
        "import_jobs",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop index on workspace_id for import_jobs."""
    op.drop_index("ix_import_jobs_workspace_id", table_name="import_jobs")
