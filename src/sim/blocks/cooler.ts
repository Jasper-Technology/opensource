/**
 * Cooler Block
 *
 * Cools stream to specified outlet temperature.
 * Calculates cooling duty required using rigorous enthalpy.
 * Determines outlet phase based on thermodynamic state.
 */

import type { BlockFunction } from '../../core/schema-v2';
import {
  mixtureEnthalpy,
  determinePhase,
  calculateVaporFraction,
} from '../thermo/properties';

export const coolerBlock: BlockFunction = (inputs, params, _components) => {
  const inlet = inputs.in;

  if (!inlet) {
    throw new Error('Cooler has no inlet stream');
  }

  // Get outlet temperature
  const outletT = params.outletT as number;

  if (!outletT) {
    throw new Error('Cooler missing outlet temperature parameter');
  }

  if (outletT >= inlet.T) {
    throw new Error(
      `Cooler outlet temperature (${outletT} K) must be less than inlet (${inlet.T} K)`
    );
  }

  // Rigorous enthalpy calculations
  const H_in = inlet.H || mixtureEnthalpy(inlet.composition, inlet.T, inlet.P);
  const H_out = mixtureEnthalpy(inlet.composition, outletT, inlet.P);

  // Calculate duty (kW) - negative for cooling
  // Duty = Flow * (H_out - H_in)
  // Since H_out < H_in, this will be negative
  const duty = (inlet.flow * (H_out - H_in) * 1000) / 3600; // kW

  // Determine outlet phase based on thermodynamic state
  const phase = determinePhase(inlet.composition, outletT, inlet.P);
  const vaporFrac = calculateVaporFraction(inlet.composition, outletT, inlet.P);

  return {
    outputs: {
      out: {
        T: outletT,
        P: inlet.P,
        flow: inlet.flow,
        composition: inlet.composition,
        phase,
        vaporFrac,
        H: H_out,
      },
    },
    duty, // Negative value indicates cooling
  };
};
