/**
 * Heater Block
 *
 * Heats stream to specified outlet temperature.
 * Calculates heat duty required using rigorous enthalpy.
 * Determines outlet phase based on thermodynamic state.
 */

import type { BlockFunction } from '../../core/schema-v2';
import {
  mixtureEnthalpy,
  determinePhase,
  calculateVaporFraction,
} from '../thermo/properties';

export const heaterBlock: BlockFunction = (inputs, params, _components) => {
  const inlet = inputs.in;

  if (!inlet) {
    throw new Error('Heater has no inlet stream');
  }

  // Get outlet temperature
  const outletT = params.outletT as number;

  if (!outletT) {
    throw new Error('Heater missing outlet temperature parameter');
  }

  if (outletT <= inlet.T) {
    throw new Error(
      `Heater outlet temperature (${outletT} K) must be greater than inlet (${inlet.T} K)`
    );
  }

  // Rigorous enthalpy calculations
  const H_in = inlet.H || mixtureEnthalpy(inlet.composition, inlet.T, inlet.P);
  const H_out = mixtureEnthalpy(inlet.composition, outletT, inlet.P);

  // Calculate duty (kW)
  // Duty = Flow * (H_out - H_in)
  // Flow is in kmol/h, H is in kJ/mol, so multiply by 1000 / 3600 to get kW
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
    duty,
  };
};
