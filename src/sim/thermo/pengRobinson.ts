/**
 * Peng-Robinson Equation of State
 *
 * Covers hydrocarbons, gases, and high-pressure systems.
 * Provides fugacity coefficients, flash calculations, and departure functions.
 */

import { COMPONENT_DATABASE, type Component, idealGasCp, idealGasEnthalpy } from './properties';

const R = 8.314; // J/(mol·K)

/**
 * PR alpha function: alpha(T) = [1 + kappa*(1 - sqrt(Tr))]^2
 */
export function prAlpha(T: number, Tc: number, omega: number): number {
  if (!Number.isFinite(T) || T <= 0 || Tc <= 0) return 1;
  const Tr = T / Tc;
  const kappa = 0.37464 + 1.54226 * omega - 0.26992 * omega * omega;
  const sqrtAlpha = 1 + kappa * (1 - Math.sqrt(Tr));
  return sqrtAlpha * sqrtAlpha;
}

/**
 * Pure component a and b parameters
 */
function prPureParams(Tc: number, Pc_bar: number): { ac: number; b: number } {
  const Pc = Pc_bar * 1e5; // bar -> Pa
  const ac = 0.45724 * R * R * Tc * Tc / Pc;
  const b = 0.07780 * R * Tc / Pc;
  return { ac, b };
}

/**
 * Mixture parameters using van der Waals one-fluid mixing rules
 * Returns a_mix, b_mix, and per-component partial derivatives for fugacity
 */
export function prMixtureParams(
  T: number,
  components: string[],
  composition: number[],
): { a_mix: number; b_mix: number; a_i: number[]; } {
  const n = components.length;
  const a_pure: number[] = [];
  const b_pure: number[] = [];

  for (const compName of components) {
    const comp = COMPONENT_DATABASE[compName];
    if (!comp) {
      a_pure.push(0);
      b_pure.push(0);
      continue;
    }
    const { ac, b } = prPureParams(comp.Tc, comp.Pc);
    const alpha = prAlpha(T, comp.Tc, comp.omega);
    a_pure.push(ac * alpha);
    b_pure.push(b);
  }

  // a_mix = sum_i sum_j x_i x_j sqrt(a_i * a_j) * (1 - k_ij)
  // k_ij = 0 for now (no BIPs for PR)
  let a_mix = 0;
  const a_i: number[] = new Array(n).fill(0);

  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const a_ij = Math.sqrt(a_pure[i] * a_pure[j]);
      a_mix += composition[i] * composition[j] * a_ij;
      a_i[i] += composition[j] * a_ij;
    }
    a_i[i] *= 2; // d(a_mix)/d(x_i) = 2 * sum_j x_j * a_ij
  }

  let b_mix = 0;
  for (let i = 0; i < n; i++) {
    b_mix += composition[i] * b_pure[i];
  }

  return { a_mix, b_mix, a_i };
}

/**
 * Solve the PR cubic: Z^3 + c2*Z^2 + c1*Z + c0 = 0
 * Returns all real roots sorted ascending
 */
export function solveCubic(A: number, B: number): number[] {
  // Z^3 - (1-B)*Z^2 + (A - 3B^2 - 2B)*Z - (AB - B^2 - B^3) = 0
  const c2 = -(1 - B);
  const c1 = A - 3 * B * B - 2 * B;
  const c0 = -(A * B - B * B - B * B * B);

  // Cardano's method
  const p = c1 - c2 * c2 / 3;
  const q = c0 - c2 * c1 / 3 + 2 * c2 * c2 * c2 / 27;
  const disc = q * q / 4 + p * p * p / 27;

  const roots: number[] = [];
  const shift = -c2 / 3;

  if (disc > 1e-12) {
    // One real root
    const sqrtDisc = Math.sqrt(disc);
    const u = Math.cbrt(-q / 2 + sqrtDisc);
    const v = Math.cbrt(-q / 2 - sqrtDisc);
    roots.push(u + v + shift);
  } else {
    // Three real roots
    const r = Math.sqrt(-p * p * p / 27);
    const theta = Math.acos(Math.max(-1, Math.min(1, -q / (2 * r))));
    const m = 2 * Math.cbrt(r);
    roots.push(m * Math.cos(theta / 3) + shift);
    roots.push(m * Math.cos((theta + 2 * Math.PI) / 3) + shift);
    roots.push(m * Math.cos((theta + 4 * Math.PI) / 3) + shift);
  }

  const positiveRoots = roots.filter(z => z > 0 && Number.isFinite(z)).sort((a, b) => a - b);
  // Guarantee at least one root — fallback to ideal gas Z=1 if cubic has no positive real roots
  return positiveRoots.length > 0 ? positiveRoots : [1.0];
}

/**
 * Fugacity coefficients ln(phi_i) for each component in a phase
 */
export function prFugacityCoeff(
  T: number,
  P_Pa: number,
  Z: number,
  components: string[],
  composition: number[],
  a_mix: number,
  b_mix: number,
  a_i: number[],
): number[] {
  const n = components.length;
  const lnPhi: number[] = [];

  const b_pure: number[] = [];
  for (const compName of components) {
    const comp = COMPONENT_DATABASE[compName];
    if (!comp) { b_pure.push(0); continue; }
    const { b } = prPureParams(comp.Tc, comp.Pc);
    b_pure.push(b);
  }

  const A = a_mix * P_Pa / (R * R * T * T);
  const B = b_mix * P_Pa / (R * T);
  const sqrt2 = Math.SQRT2;
  const logTerm = Math.log((Z + (1 + sqrt2) * B) / (Z + (1 - sqrt2) * B));

  for (let i = 0; i < n; i++) {
    const bi = b_pure[i];
    const lnPhi_i =
      (bi / b_mix) * (Z - 1) -
      Math.log(Z - B) -
      (A / (2 * sqrt2 * B)) * (a_i[i] / a_mix - bi / b_mix) * logTerm;
    lnPhi.push(lnPhi_i);
  }

  return lnPhi;
}

/**
 * PR enthalpy departure (J/mol)
 */
export function prEnthalpyDeparture(
  T: number,
  P_Pa: number,
  Z: number,
  a_mix: number,
  b_mix: number,
  dadT_mix: number,
): number {
  const B = b_mix * P_Pa / (R * T);
  const sqrt2 = Math.SQRT2;
  const logTerm = Math.log((Z + (1 + sqrt2) * B) / (Z + (1 - sqrt2) * B));

  return R * T * (Z - 1) + (T * dadT_mix - a_mix) / (2 * sqrt2 * b_mix) * logTerm;
}

/**
 * PR entropy departure (J/mol/K)
 */
export function prEntropyDeparture(
  T: number,
  P_Pa: number,
  Z: number,
  b_mix: number,
  dadT_mix: number,
): number {
  const B = b_mix * P_Pa / (R * T);
  const sqrt2 = Math.SQRT2;
  const logTerm = Math.log((Z + (1 + sqrt2) * B) / (Z + (1 - sqrt2) * B));

  return R * Math.log(Z - B) + dadT_mix / (2 * sqrt2 * b_mix) * logTerm;
}

/**
 * Compute da_mix/dT for departure functions
 */
export function prDadT(T: number, components: string[], composition: number[]): number {
  const n = components.length;
  let dadT = 0;

  for (let i = 0; i < n; i++) {
    const ci = COMPONENT_DATABASE[components[i]];
    if (!ci) continue;
    const { ac: ac_i } = prPureParams(ci.Tc, ci.Pc);
    const kappa_i = 0.37464 + 1.54226 * ci.omega - 0.26992 * ci.omega * ci.omega;
    const alpha_i = prAlpha(T, ci.Tc, ci.omega);
    const dalphadT_i = -kappa_i * Math.sqrt(alpha_i) / (Math.sqrt(T / ci.Tc) * ci.Tc);

    for (let j = 0; j < n; j++) {
      const cj = COMPONENT_DATABASE[components[j]];
      if (!cj) continue;
      const { ac: ac_j } = prPureParams(cj.Tc, cj.Pc);
      const kappa_j = 0.37464 + 1.54226 * cj.omega - 0.26992 * cj.omega * cj.omega;
      const alpha_j = prAlpha(T, cj.Tc, cj.omega);
      const dalphadT_j = -kappa_j * Math.sqrt(alpha_j) / (Math.sqrt(T / cj.Tc) * cj.Tc);

      const a_ij = Math.sqrt(ac_i * ac_j);
      const sqrt_alpha_ij = Math.sqrt(alpha_i * alpha_j);
      if (sqrt_alpha_ij < 1e-30) continue;

      const da_ij_dT = a_ij * 0.5 * (dalphadT_i * alpha_j + alpha_i * dalphadT_j) / sqrt_alpha_ij;
      dadT += composition[i] * composition[j] * da_ij_dT;
    }
  }

  return dadT;
}

/**
 * PR phi-phi flash: iterates K-values from fugacity coefficient ratios.
 * Returns { V, K, converged }
 */
export function prFlash(
  z: Record<string, number>,
  T: number,
  P_Pa: number,
  componentNames: string[],
): { V: number; K: Record<string, number>; x: Record<string, number>; y: Record<string, number>; converged: boolean } {
  // Validate inputs
  if (!Number.isFinite(T) || T <= 0 || !Number.isFinite(P_Pa) || P_Pa <= 0) {
    const fallback: Record<string, number> = Object.create(null);
    for (const c of componentNames) { fallback[c] = z[c] ?? 0; }
    return { V: 0, K: Object.create(null), x: fallback, y: fallback, converged: false };
  }
  const n = componentNames.length;
  const zArr = componentNames.map(c => z[c] ?? 0);

  // Initial K from Wilson correlation
  const K: number[] = componentNames.map(name => {
    const comp = COMPONENT_DATABASE[name];
    if (!comp) return 1;
    const Tr = T / comp.Tc;
    const Pr = P_Pa / (comp.Pc * 1e5);
    return Math.exp(5.373 * (1 + comp.omega) * (1 - 1 / Tr)) / Pr;
  });

  let V = 0.5;
  let converged = false;

  for (let iter = 0; iter < 50; iter++) {
    // Rachford-Rice for V
    V = solveRachfordRice(zArr, K);

    // Phase compositions
    const x: number[] = [];
    const y: number[] = [];
    for (let i = 0; i < n; i++) {
      const xi = zArr[i] / (1 + V * (K[i] - 1));
      x.push(xi);
      y.push(K[i] * xi);
    }

    // Normalize
    const sumX = x.reduce((a, b) => a + b, 0);
    const sumY = y.reduce((a, b) => a + b, 0);
    for (let i = 0; i < n; i++) { x[i] /= sumX; y[i] /= sumY; }

    // Fugacity coefficients for liquid and vapor
    const { a_mix: aL, b_mix: bL, a_i: aiL } = prMixtureParams(T, componentNames, x);
    const AL = aL * P_Pa / (R * R * T * T);
    const BL = bL * P_Pa / (R * T);
    const rootsL = solveCubic(AL, BL);
    const ZL = rootsL[0] ?? 0.01; // smallest positive root for liquid

    const { a_mix: aV, b_mix: bV, a_i: aiV } = prMixtureParams(T, componentNames, y);
    const AV = aV * P_Pa / (R * R * T * T);
    const BV = bV * P_Pa / (R * T);
    const rootsV = solveCubic(AV, BV);
    const ZV = rootsV[rootsV.length - 1] ?? 1; // largest positive root for vapor

    const lnPhiL = prFugacityCoeff(T, P_Pa, ZL, componentNames, x, aL, bL, aiL);
    const lnPhiV = prFugacityCoeff(T, P_Pa, ZV, componentNames, y, aV, bV, aiV);

    // Update K-values: K_i = phi_L_i / phi_V_i
    let maxChange = 0;
    for (let i = 0; i < n; i++) {
      const Knew = Math.exp(lnPhiL[i] - lnPhiV[i]);
      const change = Math.abs(Knew - K[i]) / (Math.abs(K[i]) + 1e-10);
      if (change > maxChange) maxChange = change;
      K[i] = Knew;
    }

    if (maxChange < 1e-6) {
      converged = true;
      break;
    }
  }

  // Final compositions
  const xFinal: number[] = [];
  const yFinal: number[] = [];
  for (let i = 0; i < n; i++) {
    const xi = zArr[i] / (1 + V * (K[i] - 1));
    xFinal.push(xi);
    yFinal.push(K[i] * xi);
  }
  const sumX = xFinal.reduce((a, b) => a + b, 0);
  const sumY = yFinal.reduce((a, b) => a + b, 0);

  const xOut: Record<string, number> = {};
  const yOut: Record<string, number> = {};
  const KOut: Record<string, number> = {};
  for (let i = 0; i < n; i++) {
    xOut[componentNames[i]] = xFinal[i] / sumX;
    yOut[componentNames[i]] = yFinal[i] / sumY;
    KOut[componentNames[i]] = K[i];
  }

  return { V: Math.max(0, Math.min(1, V)), K: KOut, x: xOut, y: yOut, converged };
}

/**
 * Newton-Raphson Rachford-Rice solver (local, works with arrays)
 */
function solveRachfordRice(z: number[], K: number[]): number {
  let V = 0.5;
  for (let iter = 0; iter < 50; iter++) {
    let f = 0;
    let df = 0;
    for (let i = 0; i < z.length; i++) {
      const denom = 1 + V * (K[i] - 1);
      f += z[i] * (K[i] - 1) / denom;
      df -= z[i] * (K[i] - 1) ** 2 / (denom * denom);
    }
    if (Math.abs(f) < 1e-8) break;
    if (Math.abs(df) < 1e-30) break;
    const Vnew = V - f / df;
    V = Math.max(0, Math.min(1, Vnew));
  }
  return V;
}

/**
 * Compute PR mixture enthalpy (kJ/mol) = ideal + departure
 */
export function prMixtureEnthalpy(
  components: string[],
  composition: Record<string, number>,
  T: number,
  P_Pa: number,
  phase: 'V' | 'L',
): number {
  const compArr = components.map(c => composition[c] ?? 0);

  // Ideal gas enthalpy
  let H_ig = 0;
  for (let i = 0; i < components.length; i++) {
    const comp = COMPONENT_DATABASE[components[i]];
    if (comp) H_ig += compArr[i] * idealGasEnthalpy(comp, T);
  }

  // Departure
  const { a_mix, b_mix } = prMixtureParams(T, components, compArr);
  const A = a_mix * P_Pa / (R * R * T * T);
  const B = b_mix * P_Pa / (R * T);
  const roots = solveCubic(A, B);
  const Z = phase === 'L' ? (roots[0] ?? 0.01) : (roots[roots.length - 1] ?? 1);
  const dadT = prDadT(T, components, compArr);
  const Hdep = prEnthalpyDeparture(T, P_Pa, Z, a_mix, b_mix, dadT);

  return H_ig + Hdep / 1000; // J -> kJ
}

/**
 * Compute PR mixture entropy (kJ/mol/K) = ideal + departure
 */
export function prMixtureEntropy(
  components: string[],
  composition: Record<string, number>,
  T: number,
  P_Pa: number,
  phase: 'V' | 'L',
): number {
  if (!Number.isFinite(T) || T <= 0 || !Number.isFinite(P_Pa) || P_Pa <= 0) return 0;
  const compArr = components.map(c => composition[c] ?? 0);
  const T0 = 298.15;
  const P0 = 101325; // 1 atm

  // Ideal gas entropy
  let S_ig = 0;
  for (let i = 0; i < components.length; i++) {
    const comp = COMPONENT_DATABASE[components[i]];
    if (!comp) continue;
    const [a, b, c, d, e] = comp.Cp_coef;
    // S = S_ref + integral(Cp/T dT) - R*ln(P/P_ref) - R*sum(x_i*ln(x_i))
    const CpOverT_integral =
      a * Math.log(T / T0) +
      b * (T - T0) +
      (c / 2) * (T * T - T0 * T0) +
      (d / 3) * (T * T * T - T0 * T0 * T0) +
      (e / 4) * (T ** 4 - T0 ** 4);
    S_ig += compArr[i] * CpOverT_integral; // J/mol/K
  }
  S_ig -= R * Math.log(P_Pa / P0);
  // Mixing term
  for (let i = 0; i < components.length; i++) {
    if (compArr[i] > 1e-15) {
      S_ig -= R * compArr[i] * Math.log(compArr[i]);
    }
  }

  // Departure
  const { b_mix } = prMixtureParams(T, components, compArr);
  const dadT = prDadT(T, components, compArr);
  const A_param = prMixtureParams(T, components, compArr).a_mix * P_Pa / (R * R * T * T);
  const B_param = b_mix * P_Pa / (R * T);
  const roots = solveCubic(A_param, B_param);
  const Z = phase === 'L' ? (roots[0] ?? 0.01) : (roots[roots.length - 1] ?? 1);
  const Sdep = prEntropyDeparture(T, P_Pa, Z, b_mix, dadT);

  return (S_ig + Sdep) / 1000; // J -> kJ
}
