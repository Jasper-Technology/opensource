/**
 * Default sizing assumptions — validated, sourced, and overridable per unit.
 * See docs/sizing/methods.md. Sources: Towler & Sinnott (Chemical Engineering
 * Design, 2nd ed.), GPSA Engineering Data Book, Turton (4th ed.).
 *
 * Every assumption a sizing function uses is recorded in EquipmentSize.assumptions
 * so a number is never bare.
 */

/** Overall heat-transfer coefficient by service (W/m²·K). Towler Table 19.1. */
export const U_BY_SERVICE = {
  liquid_liquid: 300,
  gas_gas: 30,
  condenser: 700, // organic condensation
  reboiler: 800, // vaporizer / reboiler
  process_cooling_water: 600,
  process_steam: 850, // heater vs condensing steam
} as const;

export type HxService = keyof typeof U_BY_SERVICE;

/** Utility-side terminal temperatures (K) for one-sided LMTD. */
export const UTILITY_TEMPS = {
  cooling_water: { in: 303.15, out: 313.15 }, // 30 → 40 °C
  lp_steam: { in: 433.15, out: 433.15 }, // 160 °C condensing
  mp_steam: { in: 457.15, out: 457.15 }, // 184 °C condensing
  refrigerant: { in: 278.15, out: 278.15 }, // 5 °C
} as const;

/** Vessel / column heuristics. */
export const VESSEL = {
  soudersBrownK: 0.107, // m/s, vertical separator with mesh (GPSA / Towler)
  refluxHoldupMin: 5, // minutes liquid holdup (reflux/surge drums; range 5–10)
  fillFraction: 0.5, // liquid fraction of vessel volume for residence sizing
  aspectRatio: 3, // L/D for liquid drums
  vaporFractionThreshold: 0.05, // above this → Souders-Brown; below → residence-time
} as const;

export const COLUMN = {
  traySpacing: 0.6, // m (24 in)
  floodFraction: 0.8, // design at 80 % of flooding velocity
  heightAllowance: 1.15, // sumps + disengagement factor on (n_stages × spacing)
  // Shortcut/Quick fallback when no stage count is exposed: N_actual ≈ factor × N_min.
  fenskeActualFactor: 2.0,
} as const;

/**
 * Reactor residence times (s) by reactor class — the WEAKEST defaults; flagged
 * in assumptions and meant to be overridden per reaction (or by the agent's
 * custom-sizing layer for novel reactors).
 */
export const REACTOR_RESIDENCE_S = {
  liquid: 3600, // ~1 h liquid-phase CSTR/batch-equivalent
  gas: 10, // ~10 s gas-phase / PFR (space velocity ~360 h⁻¹)
  default: 3600,
} as const;
