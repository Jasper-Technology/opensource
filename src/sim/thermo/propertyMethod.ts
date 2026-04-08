/**
 * Property Method Dispatch
 *
 * Abstracts thermodynamic calculations behind a PropertyPackage interface.
 * Factory selects the appropriate package based on project settings.
 */

import {
  COMPONENT_DATABASE,
  vaporPressure,
  calculateKValues,
  rachfordRiceFlash,
  flashComposition,
  mixtureEnthalpy,
  density,
  idealGasEnthalpy,
  idealGasCp,
} from './properties';
import {
  prFlash,
  prMixtureEnthalpy,
  prMixtureEntropy,
  prMixtureParams,
  solveCubic,
  prDadT,
  prEnthalpyDeparture,
} from './pengRobinson';
import { nrtlGamma } from './nrtl';

const R = 8.314;

export interface FlashResult {
  V: number;
  K: Record<string, number>;
  x: Record<string, number>;
  y: Record<string, number>;
}

export interface PropertyPackage {
  name: string;

  /** K-values for VLE at T (K), P (Pa) */
  calculateKValues(components: string[], T: number, P_Pa: number): Record<string, number>;

  /** Flash calculation returning vapor fraction and phase compositions */
  flash(z: Record<string, number>, T: number, P_Pa: number, components: string[]): FlashResult;

  /** Liquid density (kg/m3) */
  liquidDensity(composition: Record<string, number>, T: number, P_Pa: number): number;

  /** Vapor density (kg/m3) */
  vaporDensity(composition: Record<string, number>, T: number, P_Pa: number): number;

  /** Mixture enthalpy (kJ/mol) */
  mixtureEnthalpy(composition: Record<string, number>, T: number, P_Pa: number, phase?: 'V' | 'L'): number;

  /** Mixture entropy (kJ/mol/K) */
  mixtureEntropy(composition: Record<string, number>, T: number, P_Pa: number, phase?: 'V' | 'L'): number;
}

// ---------------------------------------------------------------------------
// Ideal Property Package (Raoult's Law + Lee-Kesler Pvap)
// ---------------------------------------------------------------------------

export class IdealPropertyPackage implements PropertyPackage {
  name = 'Ideal';

  calculateKValues(components: string[], T: number, P_Pa: number): Record<string, number> {
    return calculateKValues(components, T, P_Pa);
  }

  flash(z: Record<string, number>, T: number, P_Pa: number, components: string[]): FlashResult {
    const K = this.calculateKValues(components, T, P_Pa);
    const V = rachfordRiceFlash(z, K);
    const { vapor, liquid } = flashComposition(z, K, V);
    return { V: Math.max(0, Math.min(1, V)), K, x: liquid, y: vapor };
  }

  liquidDensity(composition: Record<string, number>, T: number, P_Pa: number): number {
    return density(composition, T, P_Pa, 'L');
  }

  vaporDensity(composition: Record<string, number>, T: number, P_Pa: number): number {
    return density(composition, T, P_Pa, 'V');
  }

  mixtureEnthalpy(composition: Record<string, number>, T: number, P_Pa: number): number {
    return mixtureEnthalpy(composition, T, P_Pa);
  }

  mixtureEntropy(composition: Record<string, number>, T: number, P_Pa: number): number {
    // Ideal gas entropy (simplified)
    const components = Object.keys(composition);
    const T0 = 298.15;
    const P0 = 101325;
    let S = 0;
    for (const name of components) {
      const comp = COMPONENT_DATABASE[name];
      if (!comp) continue;
      const [a, b, c, d, e] = comp.Cp_coef;
      const integral = a * Math.log(T / T0) + b * (T - T0) + (c / 2) * (T * T - T0 * T0) + (d / 3) * (T ** 3 - T0 ** 3) + (e / 4) * (T ** 4 - T0 ** 4);
      S += composition[name] * integral;
    }
    S -= R * Math.log(P_Pa / P0);
    for (const name of components) {
      if (composition[name] > 1e-15) S -= R * composition[name] * Math.log(composition[name]);
    }
    return S / 1000; // J -> kJ
  }
}

// ---------------------------------------------------------------------------
// Peng-Robinson Property Package
// ---------------------------------------------------------------------------

export class PRPropertyPackage implements PropertyPackage {
  name = 'PR';

  calculateKValues(components: string[], T: number, P_Pa: number): Record<string, number> {
    // Use Wilson K as starting estimate, then refine with PR flash
    const z: Record<string, number> = {};
    const frac = 1 / components.length;
    for (const c of components) z[c] = frac;
    const result = prFlash(z, T, P_Pa, components);
    return result.K;
  }

  flash(z: Record<string, number>, T: number, P_Pa: number, components: string[]): FlashResult {
    const result = prFlash(z, T, P_Pa, components);
    return { V: result.V, K: result.K, x: result.x, y: result.y };
  }

  liquidDensity(composition: Record<string, number>, T: number, P_Pa: number): number {
    // Use PR EOS Z for liquid
    const components = Object.keys(composition);
    const compArr = components.map(c => composition[c]);
    const { a_mix, b_mix } = prMixtureParams(T, components, compArr);
    const A = a_mix * P_Pa / (R * R * T * T);
    const B = b_mix * P_Pa / (R * T);
    const roots = solveCubic(A, B);
    const ZL = roots[0] ?? 0.05;
    let MW = 0;
    for (const [c, f] of Object.entries(composition)) MW += f * (COMPONENT_DATABASE[c]?.MW ?? 30);
    // rho = P * MW / (Z * R * T), units: Pa * g/mol / (- * J/(mol*K) * K) = g/m3
    return (P_Pa * MW) / (ZL * R * T * 1000); // kg/m3
  }

  vaporDensity(composition: Record<string, number>, T: number, P_Pa: number): number {
    const components = Object.keys(composition);
    const compArr = components.map(c => composition[c]);
    const { a_mix, b_mix } = prMixtureParams(T, components, compArr);
    const A = a_mix * P_Pa / (R * R * T * T);
    const B = b_mix * P_Pa / (R * T);
    const roots = solveCubic(A, B);
    const ZV = roots[roots.length - 1] ?? 1;
    let MW = 0;
    for (const [c, f] of Object.entries(composition)) MW += f * (COMPONENT_DATABASE[c]?.MW ?? 30);
    return (P_Pa * MW) / (ZV * R * T * 1000);
  }

  mixtureEnthalpy(composition: Record<string, number>, T: number, P_Pa: number, phase: 'V' | 'L' = 'V'): number {
    const components = Object.keys(composition);
    return prMixtureEnthalpy(components, composition, T, P_Pa, phase);
  }

  mixtureEntropy(composition: Record<string, number>, T: number, P_Pa: number, phase: 'V' | 'L' = 'V'): number {
    const components = Object.keys(composition);
    return prMixtureEntropy(components, composition, T, P_Pa, phase);
  }
}

// ---------------------------------------------------------------------------
// NRTL Property Package (gamma-phi: NRTL activity + ideal vapor)
// ---------------------------------------------------------------------------

export class NRTLPropertyPackage implements PropertyPackage {
  name = 'NRTL';

  calculateKValues(components: string[], T: number, P_Pa: number): Record<string, number> {
    const n = components.length;
    const composition = new Array(n).fill(1 / n); // equimolar for standalone K
    const gamma = nrtlGamma(components, composition, T);
    const K: Record<string, number> = {};
    for (let i = 0; i < n; i++) {
      const comp = COMPONENT_DATABASE[components[i]];
      if (!comp) { K[components[i]] = 1; continue; }
      const Psat = vaporPressure(comp, T); // Pa
      K[components[i]] = gamma[i] * Psat / P_Pa;
    }
    return K;
  }

  flash(z: Record<string, number>, T: number, P_Pa: number, components: string[]): FlashResult {
    // Iterative flash with composition-dependent gamma
    const n = components.length;
    const zArr = components.map(c => z[c] ?? 0);

    // Initial K from equimolar gamma
    let K = components.map((name, i) => {
      const comp = COMPONENT_DATABASE[name];
      if (!comp) return 1;
      const Psat = vaporPressure(comp, T);
      return Psat / P_Pa; // Start with Raoult
    });

    let V = 0.5;

    for (let iter = 0; iter < 30; iter++) {
      // Rachford-Rice
      V = solveRR(zArr, K);

      // Liquid compositions
      const x: number[] = [];
      for (let i = 0; i < n; i++) {
        x.push(zArr[i] / (1 + V * (K[i] - 1)));
      }
      const sumX = x.reduce((a, b) => a + b, 0);
      for (let i = 0; i < n; i++) x[i] /= sumX;

      // Update gamma with actual liquid composition
      const gamma = nrtlGamma(components, x, T);

      // Update K-values
      let maxChange = 0;
      for (let i = 0; i < n; i++) {
        const comp = COMPONENT_DATABASE[components[i]];
        if (!comp) continue;
        const Psat = vaporPressure(comp, T);
        const Knew = gamma[i] * Psat / P_Pa;
        const change = Math.abs(Knew - K[i]) / (Math.abs(K[i]) + 1e-10);
        if (change > maxChange) maxChange = change;
        K[i] = Knew;
      }

      if (maxChange < 1e-6) break;
    }

    V = Math.max(0, Math.min(1, V));

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
      xOut[components[i]] = xFinal[i] / sumX;
      yOut[components[i]] = yFinal[i] / sumY;
      KOut[components[i]] = K[i];
    }
    return { V, K: KOut, x: xOut, y: yOut };
  }

  liquidDensity(composition: Record<string, number>, T: number, P_Pa: number): number {
    return density(composition, T, P_Pa, 'L'); // Uses Rackett from properties.ts
  }

  vaporDensity(composition: Record<string, number>, T: number, P_Pa: number): number {
    return density(composition, T, P_Pa, 'V');
  }

  mixtureEnthalpy(composition: Record<string, number>, T: number, P_Pa: number): number {
    return mixtureEnthalpy(composition, T, P_Pa);
  }

  mixtureEntropy(composition: Record<string, number>, T: number, P_Pa: number): number {
    const components = Object.keys(composition);
    const T0 = 298.15;
    const P0 = 101325;
    let S = 0;
    for (const name of components) {
      const comp = COMPONENT_DATABASE[name];
      if (!comp) continue;
      const [a, b, c, d, e] = comp.Cp_coef;
      const integral = a * Math.log(T / T0) + b * (T - T0) + (c / 2) * (T * T - T0 * T0) + (d / 3) * (T ** 3 - T0 ** 3) + (e / 4) * (T ** 4 - T0 ** 4);
      S += composition[name] * integral;
    }
    S -= R * Math.log(P_Pa / P0);
    for (const name of components) {
      if (composition[name] > 1e-15) S -= R * composition[name] * Math.log(composition[name]);
    }
    return S / 1000;
  }
}

function solveRR(z: number[], K: number[]): number {
  let V = 0.5;
  for (let iter = 0; iter < 50; iter++) {
    let f = 0, df = 0;
    for (let i = 0; i < z.length; i++) {
      const d = 1 + V * (K[i] - 1);
      f += z[i] * (K[i] - 1) / d;
      df -= z[i] * (K[i] - 1) ** 2 / (d * d);
    }
    if (Math.abs(f) < 1e-8) break;
    V = Math.max(0, Math.min(1, V - f / df));
  }
  return V;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/**
 * Get the appropriate property package for the given method string.
 * Falls back to Ideal if method is unrecognized.
 */
export function getPropertyPackage(method: string): PropertyPackage {
  switch (method.toUpperCase()) {
    case 'PR':
    case 'PENG-ROBINSON':
    case 'PENG_ROBINSON':
    case 'SRK': // SRK users get PR (close enough for student use)
      return new PRPropertyPackage();
    case 'NRTL':
    case 'NRTL-RK':
    case 'NRTL-HOC':
      return new NRTLPropertyPackage();
    case 'IDEAL':
    case 'RAOULT':
    default:
      return new IdealPropertyPackage();
  }
}
