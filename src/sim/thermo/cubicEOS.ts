/**
 * Generic cubic equation-of-state helpers.
 *
 * Shared by the quick-mode cubic packages that are not specific to PR.
 */

import {
  COMPONENT_DATABASE,
  idealGasEnthalpy,
  type Component,
} from './properties';

const R = 8.314;

export type CubicModel = 'SRK' | 'RK';

interface CubicSpec {
  acFactor: number;
  bFactor: number;
  u: number;
  w: number;
  delta1: number;
  delta2: number;
}

const CUBIC_SPECS: Record<CubicModel, CubicSpec> = {
  SRK: { acFactor: 0.42747, bFactor: 0.08664, u: 1, w: 0, delta1: 1, delta2: 0 },
  RK: { acFactor: 0.42748, bFactor: 0.08664, u: 1, w: 0, delta1: 1, delta2: 0 },
};

interface PureParams {
  a: number;
  b: number;
  da_dT: number;
}

interface MixtureParams {
  a_mix: number;
  b_mix: number;
  a_i: number[];
  da_dT_mix: number;
}

function pureParams(model: CubicModel, comp: Component, T: number): PureParams {
  const spec = CUBIC_SPECS[model];
  const Pc = comp.Pc * 1e5;
  const b = spec.bFactor * R * comp.Tc / Pc;

  if (model === 'RK') {
    const a = spec.acFactor * R * R * comp.Tc * comp.Tc / Pc * Math.sqrt(comp.Tc / T);
    return { a, b, da_dT: -0.5 * a / T };
  }

  const m = 0.480 + 1.574 * comp.omega - 0.176 * comp.omega * comp.omega;
  const sqrtTr = Math.sqrt(T / comp.Tc);
  const alphaBase = 1 + m * (1 - sqrtTr);
  const alpha = alphaBase * alphaBase;
  const ac = spec.acFactor * R * R * comp.Tc * comp.Tc / Pc;
  const a = ac * alpha;
  const da_dT = ac * (-m * alphaBase / (sqrtTr * comp.Tc));
  return { a, b, da_dT };
}

function mixtureParams(model: CubicModel, T: number, components: string[], composition: number[]): MixtureParams {
  const n = components.length;
  const aPure: number[] = [];
  const bPure: number[] = [];
  const da_dT_pure: number[] = [];

  for (const compName of components) {
    const comp = COMPONENT_DATABASE[compName];
    if (!comp) {
      aPure.push(0);
      bPure.push(0);
      da_dT_pure.push(0);
      continue;
    }
    const params = pureParams(model, comp, T);
    aPure.push(params.a);
    bPure.push(params.b);
    da_dT_pure.push(params.da_dT);
  }

  let a_mix = 0;
  let da_dT_mix = 0;
  const a_i = new Array<number>(n).fill(0);

  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const a_ij = Math.sqrt(aPure[i] * aPure[j]);
      a_mix += composition[i] * composition[j] * a_ij;
      a_i[i] += composition[j] * a_ij;

      if (a_ij < 1e-30) continue;
      const termI = aPure[i] > 1e-30 ? da_dT_pure[i] / aPure[i] : 0;
      const termJ = aPure[j] > 1e-30 ? da_dT_pure[j] / aPure[j] : 0;
      const da_ij_dT = 0.5 * a_ij * (termI + termJ);
      da_dT_mix += composition[i] * composition[j] * da_ij_dT;
    }
    a_i[i] *= 2;
  }

  let b_mix = 0;
  for (let i = 0; i < n; i++) b_mix += composition[i] * bPure[i];

  return { a_mix, b_mix, a_i, da_dT_mix };
}

function solveCubic(A: number, B: number, u: number, w: number): number[] {
  const c2 = -(1 - B);
  const c1 = A - u * B - (u - w) * B * B;
  const c0 = -(A * B + w * B * B + w * B * B * B);

  const p = c1 - c2 * c2 / 3;
  const q = c0 - c2 * c1 / 3 + 2 * c2 * c2 * c2 / 27;
  const disc = q * q / 4 + p * p * p / 27;
  const roots: number[] = [];
  const shift = -c2 / 3;

  if (disc > 1e-12) {
    const sqrtDisc = Math.sqrt(disc);
    const uRoot = Math.cbrt(-q / 2 + sqrtDisc);
    const vRoot = Math.cbrt(-q / 2 - sqrtDisc);
    roots.push(uRoot + vRoot + shift);
  } else {
    const r = Math.sqrt(Math.max(-p * p * p / 27, 0));
    const theta = Math.acos(Math.max(-1, Math.min(1, r < 1e-30 ? 0 : -q / (2 * r))));
    const m = 2 * Math.cbrt(r);
    roots.push(m * Math.cos(theta / 3) + shift);
    roots.push(m * Math.cos((theta + 2 * Math.PI) / 3) + shift);
    roots.push(m * Math.cos((theta + 4 * Math.PI) / 3) + shift);
  }

  const positiveRoots = roots.filter((z) => z > 0 && Number.isFinite(z)).sort((a, b) => a - b);
  return positiveRoots.length > 0 ? positiveRoots : [1.0];
}

function fugacityCoefficients(
  model: CubicModel,
  T: number,
  P_Pa: number,
  Z: number,
  components: string[],
  composition: number[],
  a_mix: number,
  b_mix: number,
  a_i: number[],
): number[] {
  const spec = CUBIC_SPECS[model];
  const n = components.length;
  const lnPhi: number[] = [];
  const deltaDiff = spec.delta1 - spec.delta2 || 1;
  const B = b_mix * P_Pa / (R * T);
  const A = a_mix * P_Pa / (R * R * T * T);
  const logTerm = Math.log((Z + spec.delta1 * B) / (Z + spec.delta2 * B));

  const bPure: number[] = [];
  for (const compName of components) {
    const comp = COMPONENT_DATABASE[compName];
    if (!comp) {
      bPure.push(0);
      continue;
    }
    bPure.push(pureParams(model, comp, T).b);
  }

  for (let i = 0; i < n; i++) {
    const bi = bPure[i];
    const ratio = a_mix > 0 ? a_i[i] / a_mix : 0;
    const lnPhi_i =
      (bi / b_mix) * (Z - 1) -
      Math.log(Math.max(Z - B, 1e-300)) -
      (A / (B * deltaDiff)) * (ratio - bi / b_mix) * logTerm;
    lnPhi.push(lnPhi_i);
  }

  return lnPhi;
}

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
    V = Math.max(0, Math.min(1, V - f / df));
  }
  return V;
}

export function cubicFlash(
  model: CubicModel,
  z: Record<string, number>,
  T: number,
  P_Pa: number,
  componentNames: string[],
): { V: number; K: Record<string, number>; x: Record<string, number>; y: Record<string, number> } {
  if (!Number.isFinite(T) || T <= 0 || !Number.isFinite(P_Pa) || P_Pa <= 0) {
    const fallback: Record<string, number> = {};
    for (const c of componentNames) fallback[c] = z[c] ?? 0;
    return { V: 0, K: {}, x: fallback, y: fallback };
  }

  const n = componentNames.length;
  const zArr = componentNames.map((c) => z[c] ?? 0);
  const K = componentNames.map((name) => {
    const comp = COMPONENT_DATABASE[name];
    if (!comp) return 1;
    const Tr = T / comp.Tc;
    const Pr = P_Pa / (comp.Pc * 1e5);
    return Math.exp(5.373 * (1 + comp.omega) * (1 - 1 / Tr)) / Pr;
  });

  let V = 0.5;

  for (let iter = 0; iter < 50; iter++) {
    V = solveRachfordRice(zArr, K);

    const x: number[] = [];
    const y: number[] = [];
    for (let i = 0; i < n; i++) {
      const xi = zArr[i] / (1 + V * (K[i] - 1));
      x.push(xi);
      y.push(K[i] * xi);
    }

    const sumX = x.reduce((a, b) => a + b, 0);
    const sumY = y.reduce((a, b) => a + b, 0);
    for (let i = 0; i < n; i++) {
      x[i] /= sumX;
      y[i] /= sumY;
    }

    const liquid = mixtureParams(model, T, componentNames, x);
    const vapor = mixtureParams(model, T, componentNames, y);
    const spec = CUBIC_SPECS[model];

    const AL = liquid.a_mix * P_Pa / (R * R * T * T);
    const BL = liquid.b_mix * P_Pa / (R * T);
    const AV = vapor.a_mix * P_Pa / (R * R * T * T);
    const BV = vapor.b_mix * P_Pa / (R * T);
    const rootsL = solveCubic(AL, BL, spec.u, spec.w);
    const rootsV = solveCubic(AV, BV, spec.u, spec.w);
    const ZL = rootsL[0] ?? 0.01;
    const ZV = rootsV[rootsV.length - 1] ?? 1;

    const lnPhiL = fugacityCoefficients(model, T, P_Pa, ZL, componentNames, x, liquid.a_mix, liquid.b_mix, liquid.a_i);
    const lnPhiV = fugacityCoefficients(model, T, P_Pa, ZV, componentNames, y, vapor.a_mix, vapor.b_mix, vapor.a_i);

    let maxChange = 0;
    for (let i = 0; i < n; i++) {
      const Knew = Math.exp(lnPhiL[i] - lnPhiV[i]);
      const change = Math.abs(Knew - K[i]) / (Math.abs(K[i]) + 1e-10);
      if (change > maxChange) maxChange = change;
      K[i] = Knew;
    }

    if (maxChange < 1e-6) break;
  }

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

  return { V: Math.max(0, Math.min(1, V)), K: KOut, x: xOut, y: yOut };
}

export function cubicMixtureDensity(
  model: CubicModel,
  composition: Record<string, number>,
  T: number,
  P_Pa: number,
  phase: 'V' | 'L',
): number {
  const components = Object.keys(composition);
  const compArr = components.map((c) => composition[c] ?? 0);
  const params = mixtureParams(model, T, components, compArr);
  const spec = CUBIC_SPECS[model];
  const A = params.a_mix * P_Pa / (R * R * T * T);
  const B = params.b_mix * P_Pa / (R * T);
  const roots = solveCubic(A, B, spec.u, spec.w);
  const Z = phase === 'L' ? (roots[0] ?? 0.05) : (roots[roots.length - 1] ?? 1);

  let MW = 0;
  for (const [c, f] of Object.entries(composition)) MW += f * (COMPONENT_DATABASE[c]?.MW ?? 30);
  return (P_Pa * MW) / (Z * R * T * 1000);
}

export function cubicMixtureEnthalpy(
  model: CubicModel,
  components: string[],
  composition: Record<string, number>,
  T: number,
  P_Pa: number,
  phase: 'V' | 'L',
): number {
  const compArr = components.map((c) => composition[c] ?? 0);

  let H_ig = 0;
  for (let i = 0; i < components.length; i++) {
    const comp = COMPONENT_DATABASE[components[i]];
    if (comp) H_ig += compArr[i] * idealGasEnthalpy(comp, T);
  }

  const params = mixtureParams(model, T, components, compArr);
  const spec = CUBIC_SPECS[model];
  const A = params.a_mix * P_Pa / (R * R * T * T);
  const B = params.b_mix * P_Pa / (R * T);
  const roots = solveCubic(A, B, spec.u, spec.w);
  const Z = phase === 'L' ? (roots[0] ?? 0.05) : (roots[roots.length - 1] ?? 1);
  const deltaDiff = spec.delta1 - spec.delta2 || 1;
  const logTerm = Math.log((Z + spec.delta1 * B) / (Z + spec.delta2 * B));
  const Hdep = R * T * (Z - 1) + (T * params.da_dT_mix - params.a_mix) / (params.b_mix * deltaDiff) * logTerm;

  return H_ig + Hdep / 1000;
}

export function cubicMixtureEntropy(
  model: CubicModel,
  components: string[],
  composition: Record<string, number>,
  T: number,
  P_Pa: number,
  phase: 'V' | 'L',
): number {
  if (!Number.isFinite(T) || T <= 0 || !Number.isFinite(P_Pa) || P_Pa <= 0) return 0;

  const compArr = components.map((c) => composition[c] ?? 0);
  const T0 = 298.15;
  const P0 = 101325;

  let S_ig = 0;
  for (let i = 0; i < components.length; i++) {
    const comp = COMPONENT_DATABASE[components[i]];
    if (!comp) continue;
    const [a, b, c, d, e] = comp.Cp_coef;
    const CpOverT_integral =
      a * Math.log(T / T0) +
      b * (T - T0) +
      (c / 2) * (T * T - T0 * T0) +
      (d / 3) * (T ** 3 - T0 ** 3) +
      (e / 4) * (T ** 4 - T0 ** 4);
    S_ig += compArr[i] * CpOverT_integral;
  }
  S_ig -= R * Math.log(P_Pa / P0);
  for (let i = 0; i < components.length; i++) {
    if (compArr[i] > 1e-15) S_ig -= R * compArr[i] * Math.log(compArr[i]);
  }

  const params = mixtureParams(model, T, components, compArr);
  const spec = CUBIC_SPECS[model];
  const A = params.a_mix * P_Pa / (R * R * T * T);
  const B = params.b_mix * P_Pa / (R * T);
  const roots = solveCubic(A, B, spec.u, spec.w);
  const Z = phase === 'L' ? (roots[0] ?? 0.05) : (roots[roots.length - 1] ?? 1);
  const deltaDiff = spec.delta1 - spec.delta2 || 1;
  const logTerm = Math.log((Z + spec.delta1 * B) / (Z + spec.delta2 * B));
  const Sdep = R * Math.log(Math.max(Z - B, 1e-300)) + params.da_dT_mix / (params.b_mix * deltaDiff) * logTerm;

  return (S_ig + Sdep) / 1000;
}
