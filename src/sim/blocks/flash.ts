/**
 * Flash Block
 *
 * Performs vapor-liquid equilibrium separation.
 * Uses rigorous Rachford-Rice flash calculation.
 * Extracted from blockSolver.ts lines 211-278
 */

import type { BlockFunction, StreamData } from '../../core/schema-v2';
import {
  calculateKValues,
  rachfordRiceFlash,
  flashComposition,
  mixtureEnthalpy,
} from '../thermo/properties';

export const flashBlock: BlockFunction = (inputs, params, components) => {
  const inlet = inputs.in;

  if (!inlet) {
    throw new Error('Flash has no inlet stream');
  }

  // Get flash conditions
  const T = params.T as number;
  const P = params.P as number;

  // Check if T and P are defined (not undefined/null, but 0 is valid)
  if (T === undefined || T === null || P === undefined || P === null) {
    throw new Error(`Flash missing T or P parameter. Got T=${T}, P=${P}`);
  }

  // Calculate K-values for VLE
  const K = calculateKValues(components, T, P);

  // Perform Rachford-Rice flash
  const V = rachfordRiceFlash(inlet.composition, K);

  // Calculate phase compositions
  const { vapor: vaporComp, liquid: liquidComp } = flashComposition(
    inlet.composition,
    K,
    V
  );

  // Calculate phase flows
  const vaporFlow = inlet.flow * V;
  const liquidFlow = inlet.flow * (1 - V);

  // Calculate enthalpies for each phase
  const H_vapor = mixtureEnthalpy(vaporComp, T, P);
  const H_liquid = mixtureEnthalpy(liquidComp, T, P);

  // Create output streams
  const vapor: StreamData = {
    T,
    P,
    flow: vaporFlow,
    composition: vaporComp,
    phase: 'V',
    vaporFrac: 1.0,
    H: H_vapor,
  };

  const liquid: StreamData = {
    T,
    P,
    flow: liquidFlow,
    composition: liquidComp,
    phase: 'L',
    vaporFrac: 0.0,
    H: H_liquid,
  };

  // Handle edge cases
  if (V < 0.001) {
    // All liquid
    const H_all_liquid = mixtureEnthalpy(inlet.composition, T, P);
    return {
      outputs: {
        vapor: { ...liquid, flow: 0.001, phase: 'V', H: H_vapor }, // Tiny vapor for connectivity
        liquid: { ...inlet, T, P, phase: 'L', vaporFrac: 0.0, H: H_all_liquid },
      },
    };
  } else if (V > 0.999) {
    // All vapor
    const H_all_vapor = mixtureEnthalpy(inlet.composition, T, P);
    return {
      outputs: {
        vapor: { ...inlet, T, P, phase: 'V', vaporFrac: 1.0, H: H_all_vapor },
        liquid: { ...vapor, flow: 0.001, phase: 'L', H: H_liquid }, // Tiny liquid for connectivity
      },
    };
  }

  return {
    outputs: {
      vapor,
      liquid,
    },
    vaporFraction: V,
  };
};
