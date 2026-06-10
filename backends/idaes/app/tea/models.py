"""
SQLAlchemy models for the Jasper TEA cost database.

Single source of truth for the schema. The initial Alembic migration builds
these tables, then adds the append-only trigger and seeds the `units`
allowlist (things create_all cannot express).

Design notes
------------
- ``Provenanced`` mixin puts ``source_id`` (FK, NOT NULL) and ``basis_date``
  (NOT NULL) on every fact table. Inserting an unsourced/undated value fails
  at the DB layer, not by convention.
- Unit-bearing columns FK to ``units.symbol`` so a typo'd or invented unit is
  rejected. Currencies live in ``units`` with ``dimension='currency'``.
- Equipment correlations carry a ``functional_form`` discriminator
  ('turton_log10' | 'sslw_ln') plus their native base index/year, because the
  two seed families use different math and different cost-index bases. The
  costing layer (A3) dispatches on ``functional_form``.
- Flexible coefficient payloads use JSONB; scalar facts use Numeric.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
    relationship,
)

# Stable naming convention so Alembic autogenerate produces deterministic,
# reviewable constraint names for future (Stage B) migrations.
_NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# The allowlist of functional forms a correlation may declare.
# sslw_trays is handled by costing.cost_trays (not compute_cost) — its coeff
# carries the full SSLW tray model (base/type/material/number factors).
FUNCTIONAL_FORMS = (
    "turton_log10", "sslw_ln", "sslw_trays", "sslw_vessel", "sslw_pump",
    "packing",
)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=_NAMING)


# --------------------------------------------------------------------------- #
# Provenance anchors
# --------------------------------------------------------------------------- #
class Source(Base):
    """Every fact-bearing row points here. No source row → no fact."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(Text)
    # open_source_code | public_api | public_dataset | textbook_via_oss |
    # user_override | estimated
    source_type: Mapped[str] = mapped_column(String(40))
    license: Mapped[str] = mapped_column(String(80))
    license_url: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(Text)
    reference_citation: Mapped[Optional[str]] = mapped_column(Text)
    accessed_on: Mapped[Optional[_dt.date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "source_type in ('open_source_code','public_api','public_dataset',"
            "'textbook_via_oss','user_override','estimated')",
            name="source_type_allowed",
        ),
    )


class Unit(Base):
    """Allowlist of unit symbols. Unit-bearing columns FK here."""

    __tablename__ = "units"

    symbol: Mapped[str] = mapped_column(String(24), primary_key=True)
    # length|area|volume|power|mass_flow|volumetric_flow|heat_duty|pressure|
    # currency|currency_per_mass|currency_per_energy|dimensionless|...
    dimension: Mapped[str] = mapped_column(String(40))
    description: Mapped[Optional[str]] = mapped_column(Text)


class Provenanced:
    """Mixin: every fact carries a source and a basis date, enforced NOT NULL."""

    @declared_attr
    def source_id(cls) -> Mapped[int]:  # noqa: N805
        return mapped_column(ForeignKey("sources.id"), nullable=False, index=True)

    @declared_attr
    def basis_date(cls) -> Mapped[_dt.date]:  # noqa: N805
        return mapped_column(Date, nullable=False)


# --------------------------------------------------------------------------- #
# Equipment cost correlations + factors
# --------------------------------------------------------------------------- #
class EquipmentCorrelation(Provenanced, Base):
    __tablename__ = "equipment_correlations"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_type: Mapped[str] = mapped_column(String(60), index=True)
    subtype: Mapped[str] = mapped_column(String(60))
    functional_form: Mapped[str] = mapped_column(String(20))
    size_quantity: Mapped[str] = mapped_column(String(30))
    size_unit: Mapped[str] = mapped_column(ForeignKey("units.symbol"))
    size_min: Mapped[Optional[float]] = mapped_column(Numeric)
    size_max: Mapped[Optional[float]] = mapped_column(Numeric)
    # form-specific: {"K":[k1,k2,k3]} (turton) | {"alpha":[a1,a2,a3],"sign":-1} (sslw)
    coeff: Mapped[dict[str, Any]] = mapped_column(JSONB)
    currency: Mapped[str] = mapped_column(ForeignKey("units.symbol"))
    base_index_name: Mapped[str] = mapped_column(String(30))   # CEPCI | CE
    base_index_value: Mapped[float] = mapped_column(Numeric)   # 397 | 500
    base_index_year: Mapped[int] = mapped_column(Integer)
    # bare-module: {"B1":..,"B2":..} (two-factor) | {"F_bare":..}
    bare_module: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    # pressure model (Turton piecewise ranges or SSLW quadratic), nullable
    pressure_model: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    source = relationship("Source")

    __table_args__ = (
        UniqueConstraint(
            "equipment_type", "subtype", "source_id",
            name="equipment_subtype_source",
        ),
        CheckConstraint(
            "functional_form in ('turton_log10','sslw_ln','sslw_trays',"
            "'sslw_vessel','sslw_pump','packing')",
            name="functional_form_allowed",
        ),
    )


class MaterialFactor(Provenanced, Base):
    __tablename__ = "material_factors"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_type: Mapped[str] = mapped_column(String(60), index=True)
    subtype: Mapped[str] = mapped_column(String(60))
    material: Mapped[str] = mapped_column(String(60))
    # {"kind":"scalar","value":2.7} | {"kind":"ab","A":2.70,"B":0.07}
    factor_model: Mapped[dict[str, Any]] = mapped_column(JSONB)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    source = relationship("Source")

    __table_args__ = (
        UniqueConstraint(
            "equipment_type", "subtype", "material", "source_id",
            name="equipment_subtype_material_source",
        ),
    )


# --------------------------------------------------------------------------- #
# Chemicals + prices
# --------------------------------------------------------------------------- #
class Chemical(Provenanced, Base):
    """Identity, linked to idaes-backend component_db by CAS where possible."""

    __tablename__ = "chemicals"

    id: Mapped[int] = mapped_column(primary_key=True)
    cas_number: Mapped[Optional[str]] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(Text)
    formula: Mapped[Optional[str]] = mapped_column(String(80))
    component_db_id: Mapped[Optional[str]] = mapped_column(String(80))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    source = relationship("Source")
    prices = relationship("ChemicalPrice", back_populates="chemical")


class ChemicalPrice(Provenanced, Base):
    __tablename__ = "chemical_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    chemical_id: Mapped[int] = mapped_column(
        ForeignKey("chemicals.id"), index=True
    )
    price: Mapped[float] = mapped_column(Numeric)
    currency: Mapped[str] = mapped_column(ForeignKey("units.symbol"))
    price_unit: Mapped[str] = mapped_column(ForeignKey("units.symbol"))  # USD/kg ...
    region: Mapped[Optional[str]] = mapped_column(String(20))
    price_type: Mapped[Optional[str]] = mapped_column(String(20))  # market|contract|list
    as_of_date: Mapped[Optional[_dt.date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    source = relationship("Source")
    chemical = relationship("Chemical", back_populates="prices")


class Utility(Provenanced, Base):
    __tablename__ = "utilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    utility_type: Mapped[str] = mapped_column(String(40), index=True)
    price: Mapped[float] = mapped_column(Numeric)
    currency: Mapped[str] = mapped_column(ForeignKey("units.symbol"))
    price_unit: Mapped[str] = mapped_column(ForeignKey("units.symbol"))  # USD/GJ ...
    region: Mapped[Optional[str]] = mapped_column(String(20))
    # two-factor model (B5): {"capital":..,"energy":..}; null in Stage A
    two_factor: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    fuel_chemical_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chemicals.id")
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    source = relationship("Source")


# --------------------------------------------------------------------------- #
# Location, economics, index
# --------------------------------------------------------------------------- #
class LocationDriver(Provenanced, Base):
    __tablename__ = "location_drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    region: Mapped[str] = mapped_column(String(20), index=True)
    # labor_rate|productivity|freight_duty|fx|material_index
    driver_type: Mapped[str] = mapped_column(String(40))
    value: Mapped[float] = mapped_column(Numeric)
    unit: Mapped[str] = mapped_column(ForeignKey("units.symbol"))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    source = relationship("Source")

    __table_args__ = (
        UniqueConstraint(
            "region", "driver_type", "source_id", "basis_date",
            name="region_driver_source_basis",
        ),
    )


class EconomicFactor(Provenanced, Base):
    __tablename__ = "economic_factors"

    id: Mapped[int] = mapped_column(primary_key=True)
    # contingency|lang_isbl|lang_osbl|tax_rate|discount_rate|...
    factor_type: Mapped[str] = mapped_column(String(40), index=True)
    aace_class: Mapped[Optional[int]] = mapped_column(Integer)
    value: Mapped[float] = mapped_column(Numeric)
    unit: Mapped[str] = mapped_column(ForeignKey("units.symbol"))  # fraction|dimensionless
    region: Mapped[Optional[str]] = mapped_column(String(20))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    source = relationship("Source")


class CostIndex(Provenanced, Base):
    """Escalation series. Stage A: a single placeholder row. B3: BLS-built series."""

    __tablename__ = "cost_index"

    id: Mapped[int] = mapped_column(primary_key=True)
    index_name: Mapped[str] = mapped_column(String(40), index=True)  # jasper|CE|...
    period: Mapped[_dt.date] = mapped_column(Date)  # month
    value: Mapped[float] = mapped_column(Numeric)
    component_weights: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    source = relationship("Source")

    __table_args__ = (
        UniqueConstraint(
            "index_name", "period", "source_id",
            name="index_period_source",
        ),
    )


# --------------------------------------------------------------------------- #
# Unit-type costing map — resolves a Jasper flowsheet unit type to a correlation
# --------------------------------------------------------------------------- #
class UnitCostMap(Provenanced, Base):
    """
    Maps a Jasper unit type (site/src/core/schema.ts UnitType) to the
    equipment correlation used to cost it. Makes the cost DB directly
    consumable by a flowsheet. cost_bearing=False marks connectors/non-physical
    units (Feed, Mixer, Splitter, Valve, Sink, TextBox) that carry no standalone
    equipment cost.
    """

    __tablename__ = "unit_cost_map"

    id: Mapped[int] = mapped_column(primary_key=True)
    jasper_unit_type: Mapped[str] = mapped_column(String(40), unique=True)
    cost_bearing: Mapped[bool] = mapped_column(default=True)
    equipment_type: Mapped[Optional[str]] = mapped_column(String(60))
    default_subtype: Mapped[Optional[str]] = mapped_column(String(60))
    default_material: Mapped[Optional[str]] = mapped_column(String(60))
    sizing_basis: Mapped[Optional[str]] = mapped_column(String(30))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    source = relationship("Source")


# --------------------------------------------------------------------------- #
# Overrides — append-only event log (UPDATE/DELETE blocked by trigger)
# --------------------------------------------------------------------------- #
class Override(Base):
    __tablename__ = "overrides"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    scope: Mapped[str] = mapped_column(String(20))  # global|project|scenario
    scope_ref: Mapped[Optional[str]] = mapped_column(String(120))
    target_table: Mapped[str] = mapped_column(String(60))
    target_key: Mapped[dict[str, Any]] = mapped_column(JSONB)
    field: Mapped[str] = mapped_column(String(60))
    old_value: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    new_value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    context: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    actor: Mapped[Optional[str]] = mapped_column(String(120))
    basis_date: Mapped[Optional[_dt.date]] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint(
            "scope in ('global','project','scenario')", name="scope_allowed"
        ),
    )


# Raw DDL the migration appends after create_all (create_all can't express these).
APPEND_ONLY_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION cost_db_block_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'overrides is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER overrides_no_update
    BEFORE UPDATE ON overrides
    FOR EACH ROW EXECUTE FUNCTION cost_db_block_mutation();

CREATE TRIGGER overrides_no_delete
    BEFORE DELETE ON overrides
    FOR EACH ROW EXECUTE FUNCTION cost_db_block_mutation();
"""

DROP_APPEND_ONLY_TRIGGER_SQL = """
DROP TRIGGER IF EXISTS overrides_no_update ON overrides;
DROP TRIGGER IF EXISTS overrides_no_delete ON overrides;
DROP FUNCTION IF EXISTS cost_db_block_mutation();
"""

# Allowlist seeded into `units` by the initial migration.
SEED_UNITS: tuple[tuple[str, str, str], ...] = (
    # symbol, dimension, description
    ("m2", "area", "square metre"),
    ("ft2", "area", "square foot"),
    ("m3", "volume", "cubic metre"),
    ("kW", "power", "kilowatt"),
    ("hp", "power", "horsepower"),
    ("MW", "power", "megawatt"),
    ("kg/s", "mass_flow", "kilogram per second"),
    ("m3/s", "volumetric_flow", "cubic metre per second"),
    ("BTU/hr", "heat_duty", "British thermal unit per hour"),
    ("barg", "pressure", "bar gauge"),
    ("psig", "pressure", "pound-force per square inch gauge"),
    ("USD", "currency", "US dollar"),
    ("EUR", "currency", "Euro"),
    ("USD/kg", "currency_per_mass", "US dollar per kilogram"),
    ("USD/tonne", "currency_per_mass", "US dollar per tonne"),
    ("USD/GJ", "currency_per_energy", "US dollar per gigajoule"),
    ("USD/kWh", "currency_per_energy", "US dollar per kilowatt-hour"),
    ("USD/hr", "currency_per_time", "US dollar per hour"),
    ("fraction", "dimensionless", "fraction in [0,1]"),
    ("dimensionless", "dimensionless", "dimensionless ratio"),
)
