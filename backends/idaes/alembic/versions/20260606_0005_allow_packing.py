"""allow packing functional form (C5 packed columns)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-06
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_CK = "ck_equipment_correlations_functional_form_allowed"


def _set_allowed(values_sql: str) -> None:
    op.execute(f"ALTER TABLE equipment_correlations DROP CONSTRAINT IF EXISTS {_CK}")
    op.execute(
        f"ALTER TABLE equipment_correlations ADD CONSTRAINT {_CK} "
        f"CHECK (functional_form in ({values_sql}))"
    )


def upgrade() -> None:
    _set_allowed(
        "'turton_log10','sslw_ln','sslw_trays','sslw_vessel','sslw_pump','packing'"
    )


def downgrade() -> None:
    _set_allowed(
        "'turton_log10','sslw_ln','sslw_trays','sslw_vessel','sslw_pump'"
    )
