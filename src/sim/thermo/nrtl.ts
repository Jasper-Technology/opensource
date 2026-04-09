/**
 * NRTL (Non-Random Two-Liquid) Activity Coefficient Model
 *
 * Handles polar and non-ideal liquid mixtures.
 * Uses binary interaction parameters (BIPs) from bipDatabase.
 */

import { getBIP } from './bipDatabase';

const R = 8.314; // J/(mol·K)

/**
 * Calculate NRTL activity coefficients gamma_i for each component.
 *
 * tau_ij = a_ij + b_ij / T
 * G_ij = exp(-alpha_ij * tau_ij)
 *
 * ln(gamma_i) = (sum_j tau_ji * G_ji * x_j) / (sum_k G_ki * x_k)
 *             + sum_j [ x_j * G_ij / (sum_k G_kj * x_k) *
 *               (tau_ij - (sum_m x_m * tau_mj * G_mj) / (sum_k G_kj * x_k)) ]
 */
export function nrtlGamma(
  components: string[],
  composition: number[],
  T: number,
): number[] {
  const n = components.length;
  if (n === 0) return [];
  if (n === 1) return [1.0];
  if (!Number.isFinite(T) || T <= 0) return new Array(n).fill(1.0);

  // Build tau and G matrices
  const tau: number[][] = Array.from({ length: n }, () => new Array(n).fill(0));
  const G: number[][] = Array.from({ length: n }, () => new Array(n).fill(0));

  for (let i = 0; i < n; i++) {
    G[i][i] = 1.0;
    tau[i][i] = 0.0;
    for (let j = i + 1; j < n; j++) {
      const bip = getBIP(components[i], components[j]);
      if (bip) {
        tau[i][j] = bip.a12 + bip.b12 / T;
        tau[j][i] = bip.a21 + bip.b21 / T;
        const alpha = bip.alpha12;
        G[i][j] = Math.exp(-alpha * tau[i][j]);
        G[j][i] = Math.exp(-alpha * tau[j][i]);
      } else {
        // No BIP available - ideal behavior
        tau[i][j] = 0;
        tau[j][i] = 0;
        G[i][j] = 1;
        G[j][i] = 1;
      }
    }
  }

  const x = composition;
  const gamma: number[] = [];

  for (let i = 0; i < n; i++) {
    // Numerator and denominator of first term
    let num1 = 0;
    let den1 = 0;
    for (let j = 0; j < n; j++) {
      num1 += tau[j][i] * G[j][i] * x[j];
      den1 += G[j][i] * x[j];
    }

    // Guard against zero denominator (empty composition edge case)
    if (Math.abs(den1) < 1e-300) { gamma.push(1.0); continue; }
    let lnGamma = num1 / den1;

    // Second sum
    for (let j = 0; j < n; j++) {
      let denJ = 0;
      let numJ = 0;
      for (let k = 0; k < n; k++) {
        denJ += G[k][j] * x[k];
        numJ += x[k] * tau[k][j] * G[k][j];
      }
      if (Math.abs(denJ) < 1e-300) continue;
      lnGamma += (x[j] * G[i][j] / denJ) * (tau[i][j] - numJ / denJ);
    }

    gamma.push(Math.exp(lnGamma));
  }

  return gamma;
}
