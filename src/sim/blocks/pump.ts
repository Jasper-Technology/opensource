/**
 * Pump Block
 *
 * Increases pressure of liquid stream.
 * Calculates power consumption.
 * Pumps handle liquid streams - phase should remain liquid.
 */

import type { BlockFunction } from '../../core/schema-v2';
import { density, COMPONENT_DATABASE } from '../thermo/properties';

export const pumpBlock: BlockFunction = (inputs, params, _components) => {
  const inlet = inputs.in;

  if (!inlet) {
    throw new Error('Pump has no inlet stream');
  }

  // Get pressure rise
  const dP = params.dP as number;

  if (!dP || dP <= 0) {
    throw new Error('Pump missing or invalid pressure rise (dP must be > 0)');
  }

  // Calculate outlet pressure
  const outletP = inlet.P + dP;

  // Calculate density (kg/m³)
  const rho = density(inlet.composition, inlet.T, inlet.P, 'L');

  // Calculate average molecular weight (g/mol = kg/kmol)
  let MW = 0;
  for (const [compName, moleFrac] of Object.entries(inlet.composition)) {
    const comp = COMPONENT_DATABASE[compName];
    if (comp) {
      MW += moleFrac * comp.MW;
    }
  }
  // Default to 30 if no components found (shouldn't happen)
  if (MW === 0) MW = 30;

  // Calculate volumetric flow rate (m³/s)
  // flow [kmol/h] × MW [kg/kmol] = mass flow [kg/h]
  // mass flow [kg/h] / rho [kg/m³] = volumetric flow [m³/h]
  // / 3600 = volumetric flow [m³/s]
  const volumetricFlow = (inlet.flow * MW) / (rho * 3600); // m³/s

  // Calculate ideal pump work (kW)
  const idealWork = (volumetricFlow * dP) / 1000; // Pa * m³/s -> kW

  // Apply efficiency
  const efficiency = (params.efficiency as number) ?? 0.75;
  const actualPower = idealWork / efficiency;

  // Pump output is always liquid (pumps are for liquids)
  // Phase doesn't change significantly with pressure for liquids
  return {
    outputs: {
      out: {
        T: inlet.T,
        P: outletP,
        flow: inlet.flow,
        composition: inlet.composition,
        phase: 'L' as const, // Pump output is liquid
        vaporFrac: 0, // No vapor in pump output
        H: inlet.H, // Enthalpy doesn't change significantly for liquid compression
      },
    },
    power: actualPower,
  };
};
