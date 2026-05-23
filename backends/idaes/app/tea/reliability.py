"""
Reliability + operating-mode adjustments.

Simple-project cash flow assumes 8000 h/yr of continuous revenue. Real
plants have downtime — planned turnarounds every few years, unplanned
outages every month. This module adjusts the effective operating
hours (and therefore revenue + utility OPEX) for realistic availability.

Two modes:
- Continuous (default) — availability applies to revenue + utilities.
- Batch — campaign-based with cycle time, batch size, changeover, and
  utilisation rate. Revenue scales with actual batches/year after
  changeovers.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class OperationMode(str, Enum):
    CONTINUOUS = "continuous"
    BATCH = "batch"


@dataclass(frozen=True)
class ReliabilityConfig:
    """Availability + optional batch scheduling parameters."""

    operation_mode: OperationMode = OperationMode.CONTINUOUS
    availability: float = 0.95                # fraction of nominal uptime (0..1)
    # Turnaround: every N years, M days of lost production
    turnaround_interval_years: int = 4
    turnaround_days: int = 14

    # Batch-specific (ignored in continuous mode)
    batch_cycle_hours: float = 24.0           # full batch including changeover
    batch_changeover_hours: float = 2.0        # non-productive fraction of cycle
    batches_per_campaign: int = 1             # back-to-back batches before longer changeover

    def effective_hours_per_year(self, nominal_hours: float) -> float:
        """Compute effective productive hours taking downtime + (batch)
        changeovers into account."""
        if nominal_hours <= 0:
            return 0.0

        # Turnaround drag averaged across a turnaround cycle
        if self.turnaround_interval_years > 0 and self.turnaround_days > 0:
            annualized_ta_days = self.turnaround_days / self.turnaround_interval_years
            ta_fraction = min(1.0, annualized_ta_days / 365.0)
        else:
            ta_fraction = 0.0

        # Availability already rolls in unplanned outages
        effective = nominal_hours * self.availability * (1 - ta_fraction)

        if self.operation_mode == OperationMode.BATCH:
            # Fraction of batch cycle that's actually productive
            cycle = max(1e-6, self.batch_cycle_hours)
            productive = max(0.0, cycle - self.batch_changeover_hours)
            if cycle > 0:
                effective *= productive / cycle

        return max(0.0, effective)

    def revenue_multiplier(self, nominal_hours: float) -> float:
        """Revenue scales linearly with effective hours vs nominal."""
        if nominal_hours <= 0:
            return 0.0
        return self.effective_hours_per_year(nominal_hours) / nominal_hours

    def utilities_multiplier(self, nominal_hours: float) -> float:
        """Utility OPEX also scales with effective operating time."""
        return self.revenue_multiplier(nominal_hours)


def apply_reliability_to_totals(
    totals: dict,
    *,
    nominal_hours: float,
    config: ReliabilityConfig,
) -> dict:
    """
    Return a copy of ``totals`` with revenue + utility/feedstock OPEX
    scaled by the reliability/mode multipliers. Labor + maintenance
    don't scale — they're fixed costs the plant pays whether it runs
    or not.
    """
    mult = config.revenue_multiplier(nominal_hours)
    if mult >= 1.0 and config.operation_mode == OperationMode.CONTINUOUS:
        return dict(totals)

    scaled = dict(totals)
    scaled["revenue_annual_usd"] = float(totals.get("revenue_annual_usd", 0)) * mult
    scaled["opex_utilities_usd"] = float(totals.get("opex_utilities_usd", 0)) * mult
    scaled["opex_feedstock_usd"] = float(totals.get("opex_feedstock_usd", 0)) * mult

    # Recompute total OPEX: scaled utilities + scaled feedstock + unchanged
    # labor + unchanged maintenance
    scaled["opex_annual_usd"] = (
        scaled["opex_utilities_usd"]
        + scaled["opex_feedstock_usd"]
        + float(totals.get("opex_labor_usd", 0))
        + float(totals.get("opex_maintenance_usd", 0))
    )
    return scaled
