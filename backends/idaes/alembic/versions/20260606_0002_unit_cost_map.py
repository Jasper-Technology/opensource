"""unit_cost_map: resolve Jasper unit types to correlations (B2)

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-06

checkfirst=True so this is a no-op on fresh DBs (0001's metadata create_all
already built the table) and creates it on existing A1 DBs.
"""
from alembic import op

from app.tea import models

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    models.UnitCostMap.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    models.UnitCostMap.__table__.drop(bind=op.get_bind(), checkfirst=True)
