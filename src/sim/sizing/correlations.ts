/**
 * Pure sizing correlations — closed-form, no I/O, no solver. Inputs are plain
 * numbers (the dispatcher in index.ts resolves them from sim results). All SI.
 * See docs/sizing/methods.md for sources.
 */
import { COMPONENT_DATABASE } from '../thermo/componentDatabase';

/** Molecular weight of a mixture (kg/kmol ≡ g/mol) from a mole-fraction map. */
export function mixtureMW(composition: Record<string, number> | undefined): number {
  if (!composition) return 30; // fallback when composition is unavailable
  let mw = 0;
  let total = 0;
  for (const [comp, frac] of Object.entries(composition)) {
    if (!(frac > 0)) continue;
    mw += frac * (COMPONENT_DATABASE[comp]?.MW ?? 30);
    total += frac;
  }
  return total > 0 ? mw / total : 30;
}

/** Volumetric flow (m³/s) from molar flow (kmol/h), MW (kg/kmol), density (kg/m³). */
export function volFlowM3s(flowMol: number, mw: number, density: number): number {
  const massFlowKgS = (flowMol * mw) / 3600; // kmol/h · kg/kmol / 3600 = kg/s
  return density > 0 ? massFlowKgS / density : 0;
}

/** Log-mean temperature difference (K) from the four terminal temperatures. */
export function lmtd(thIn: number, thOut: number, tcIn: number, tcOut: number): number {
  const dt1 = thIn - tcOut; // hot end
  const dt2 = thOut - tcIn; // cold end
  if (dt1 <= 0 || dt2 <= 0) return 5; // temperature cross → minimum practical ΔT
  if (Math.abs(dt1 - dt2) < 1e-6) return dt1;
  return (dt1 - dt2) / Math.log(dt1 / dt2);
}

/** Heat-exchanger area (m²): A = Q / (U·LMTD). Q in kW, U in W/m²·K. */
export function hxArea(dutyKW: number, U: number, lmtdK: number): number {
  const Q = Math.abs(dutyKW) * 1000; // W
  return Q / (U * Math.max(lmtdK, 1e-3));
}

/** Souders-Brown maximum vapor velocity (m/s). */
export function soudersBrownVelocity(rhoL: number, rhoV: number, K: number): number {
  if (!(rhoV > 0) || rhoL <= rhoV) return NaN;
  return K * Math.sqrt((rhoL - rhoV) / rhoV);
}

/** Vessel diameter (m) from a vapor volumetric flow and a settling velocity. */
export function diameterFromVapor(vaporVolFlowM3s: number, velocityMS: number): number {
  if (!(velocityMS > 0)) return NaN;
  const area = vaporVolFlowM3s / velocityMS;
  return Math.sqrt((4 * area) / Math.PI);
}

/** Cylinder volume (m³). */
export function cylinderVolume(diameter: number, height: number): number {
  return (Math.PI / 4) * diameter * diameter * height;
}

/**
 * Tray-column flooding velocity (m/s), Towler & Sinnott eq. 17.34 (plate spacing
 * lt in m, valid 0.15–1.0 m; conservative, F_LV-independent — fine for Class 4-5).
 *   û_flood = (−0.171·lt² + 0.27·lt − 0.047) · √((ρ_L − ρ_V)/ρ_V)
 */
export function trayFloodVelocity(traySpacing: number, rhoL: number, rhoV: number): number {
  if (!(rhoV > 0) || rhoL <= rhoV) return NaN;
  const k = -0.171 * traySpacing * traySpacing + 0.27 * traySpacing - 0.047;
  return Math.max(k, 1e-3) * Math.sqrt((rhoL - rhoV) / rhoV);
}

/** Liquid flow parameter F_LV = (L/V)·√(ρ_V/ρ_L) (mass flows). Recorded, not gating. */
export function flowParameter(
  liqMassFlow: number,
  vapMassFlow: number,
  rhoL: number,
  rhoV: number,
): number {
  if (!(vapMassFlow > 0) || !(rhoL > 0)) return 0;
  return (liqMassFlow / vapMassFlow) * Math.sqrt(rhoV / rhoL);
}
