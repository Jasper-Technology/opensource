/**
 * Mixer Block
 *
 * Combines multiple inlet streams.
 * Rigorous mass and energy balance with adiabatic mixing.
 * Uses enthalpy to solve for outlet temperature.
 * Determines outlet phase based on thermodynamic state.
 */

import type { BlockFunction } from '../../core/schema-v2';
import {
  mixtureEnthalpy,
  determinePhase,
  calculateVaporFraction,
} from '../thermo/properties';

export const mixerBlock: BlockFunction = (inputs, _params, _components) => {
  const streams = Object.values(inputs);

  if (streams.length === 0) {
    throw new Error('Mixer has no inlet streams');
  }

  if (streams.length === 1) {
    // Pass through if only one inlet
    return {
      outputs: {
        out: streams[0],
      },
    };
  }

  // Total flow
  const totalFlow = streams.reduce((sum, s) => sum + s.flow, 0);

  // Minimum pressure (pressure drop at mixing point)
  const P = Math.min(...streams.map((s) => s.P));

  // Mix compositions (molar-weighted)
  const composition: Record<string, number> = {};

  // Get all unique components from all streams
  const allComponents = new Set<string>();
  for (const stream of streams) {
    for (const comp of Object.keys(stream.composition)) {
      allComponents.add(comp);
    }
  }

  // Calculate mixed composition
  for (const comp of allComponents) {
    let weightedSum = 0;
    for (const stream of streams) {
      const fraction = stream.composition[comp] || 0;
      weightedSum += fraction * stream.flow;
    }
    composition[comp] = weightedSum / totalFlow;
  }

  // Normalize composition (should already be normalized, but ensure it)
  const sum = Object.values(composition).reduce((a, b) => a + b, 0);
  if (Math.abs(sum - 1.0) > 0.01) {
    for (const comp of Object.keys(composition)) {
      composition[comp] /= sum;
    }
  }

  // Rigorous energy balance: Total enthalpy in = Total enthalpy out
  // H_out * F_out = Σ(H_i * F_i)
  const totalEnthalpy = streams.reduce((sum, s) => {
    const H_i = s.H || mixtureEnthalpy(s.composition, s.T, s.P);
    return sum + H_i * s.flow;
  }, 0);
  const H_mix = totalEnthalpy / totalFlow; // Average molar enthalpy (kJ/mol)

  // Solve for outlet temperature using enthalpy
  // For ideal gas: H = f(T), so we need to iterate to find T such that H(T) = H_mix
  // Start with flow-weighted average as initial guess
  let T = streams.reduce((sum, s) => sum + s.T * s.flow, 0) / totalFlow;

  // Newton's method to solve H(T) = H_mix
  for (let iter = 0; iter < 20; iter++) {
    const H_calc = mixtureEnthalpy(composition, T, P);
    const error = H_calc - H_mix;

    if (Math.abs(error) < 0.001) break; // Converged (within 0.001 kJ/mol)

    // Numerical derivative dH/dT ≈ Cp
    const dT = 0.1;
    const H_plus = mixtureEnthalpy(composition, T + dT, P);
    const dHdT = (H_plus - H_calc) / dT;

    if (Math.abs(dHdT) < 1e-10) break; // Avoid division by zero

    // Newton step
    T = T - error / dHdT;

    // Keep T reasonable
    if (T < 100) T = 100;
    if (T > 1000) T = 1000;
  }

  // Determine output phase based on thermodynamic state at outlet conditions
  const phase = determinePhase(composition, T, P);
  const vaporFrac = calculateVaporFraction(composition, T, P);

  return {
    outputs: {
      out: {
        T,
        P,
        flow: totalFlow,
        composition,
        phase,
        vaporFrac,
        H: H_mix,
      },
    },
  };
};
