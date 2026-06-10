"""allow sslw_vessel + sslw_pump functional forms (C4 multi-source)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-06

Raw SQL with the literal constraint name (op.drop_constraint mangles names under
the metadata naming convention).
"""
from alembic import op

revision = "0004"
down_revision = "0003"
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
        "'turton_log10','sslw_ln','sslw_trays','sslw_vessel','sslw_pump'"
    )


def downgrade() -> None:
    _set_allowed("'turton_log10','sslw_ln','sslw_trays'")
