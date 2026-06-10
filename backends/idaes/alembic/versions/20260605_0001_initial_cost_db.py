"""initial cost-db schema + provenance foundation

Builds all core tables from app.tea.models (single source of truth), seeds the
`units` allowlist, and installs the append-only trigger on `overrides`.

Revision ID: 0001
Revises:
Create Date: 2026-06-05
"""
from alembic import op

from app.tea import models

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Create every table defined on the models' metadata (FK ordering handled).
    models.Base.metadata.create_all(bind=bind)
    # Seed the units allowlist so unit-bearing FKs have valid targets.
    op.bulk_insert(
        models.Unit.__table__,
        [
            {"symbol": s, "dimension": d, "description": desc}
            for (s, d, desc) in models.SEED_UNITS
        ],
    )
    # Enforce append-only on overrides at the DB layer (not by convention).
    op.execute(models.APPEND_ONLY_TRIGGER_SQL)


def downgrade() -> None:
    op.execute(models.DROP_APPEND_ONLY_TRIGGER_SQL)
    models.Base.metadata.drop_all(bind=op.get_bind())
