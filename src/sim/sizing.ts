/**
 * Equipment Sizing and Capital Cost Estimation
 *
 * Implements Guthrie/Turton correlations for equipment cost estimation
 * from simulation results (duty, power, flow rates).
 *
 * Reference: Turton et al., "Analysis, Synthesis and Design of Chemical Processes"
 *
 * ============================================================================
 * INTEGRATION NOTE FOR engine-v2.ts
 * ============================================================================
 *
 * To integrate CAPEX calculation into the simulation engine, add the following
 * code in engine-v2.ts after the block results are built (around line 136):
 *
 * ```typescript
 * import { convertBlocksToResults, calculateEquipmentCAPEX } from './sizing';
 *
 * // ... inside simulateV2 function, after building blockResults ...
 *
 * // Calculate equipment sizing and CAPEX
 * const blockResultsForSizing = convertBlocksToResults(
 *   project.blocks.map(block => ({
 *     id: block.id,
 *     type: block.type,
 *     duty: block.duty,
 *     power: block.power,
 *     inputs: block.inputs,
 *     outputs: block.outputs,
 *   }))
 * );
 * const capexResult = calculateEquipmentCAPEX(blockResultsForSizing);
 *
 * // Add CAPEX to KPIs
 * kpis.equipmentCAPEX = capexResult.totalCAPEX;
 *
 * // Add equipment sizing to rawOutputs
 * rawOutputs.equipmentSizing = capexResult.equipment;
 *
 * // Log CAPEX summary
 * log.push('');
 * log.push('Equipment Sizing & CAPEX:');
 * for (const equip of capexResult.equipment) {
 *   log.push(`  ${equip.blockId}: ${equip.sizingParam} = ${equip.value.toFixed(2)} ${equip.unit}, Cost = $${equip.cost.toFixed(0)}`);
 * }
 * log.push(`  Total Equipment CAPEX: $${capexResult.totalCAPEX.toFixed(0)}`);
 * ```
 *
 * The integration point is in simulateV2() function between lines 136-138,
 * right after building blockResults and before the summary log output.
 * ============================================================================
 */

// ============================================================================
// TYPES
// ============================================================================

export interface EquipmentSize {
  blockId: string;
  blockType: string;
  sizingParam: string; // e.g., 'area', 'power', 'volume'
  value: number;
  unit: string;
  cost: number; // USD
}

export interface BlockResult {
  id: string;
  type: string;
  duty?: number; // kW
  power?: number; // kW
  inlet?: {
    T: number; // K
    P: number; // Pa
    flow: number; // kmol/h
    composition: Record<string, number>;
  };
  outlet?: {
    T: number; // K
    P: number; // Pa
    flow: number; // kmol/h
    composition: Record<string, number>;
  };
}

export interface CAPEXResult {
  equipment: EquipmentSize[];
  totalCAPEX: number; // USD
}

// ============================================================================
// CONSTANTS
// ============================================================================

// Overall heat transfer coefficient (W/m²K)
// Typical value for shell-and-tube exchangers with liquid on both sides
const U_DEFAULT = 500;

// Minimum equipment sizes to avoid unrealistic costs
const MIN_HX_AREA = 1; // m²
const MIN_PUMP_POWER = 0.1; // kW
const MIN_COMPRESSOR_POWER = 1; // kW
const MIN_VESSEL_VOLUME = 0.1; // m³

// ============================================================================
// HEAT EXCHANGER SIZING
// ============================================================================

/**
 * Size a heat exchanger from duty and temperature conditions
 *
 * Uses Log Mean Temperature Difference (LMTD) method:
 *   Q = U × A × LMTD
 *   A = Q / (U × LMTD)
 *
 * Cost correlation (Guthrie/Turton):
 *   Cost = 32800 × (A/100)^0.65
 *   where A is in m²
 *
 * @param duty - Heat duty in kW (positive for heating, negative for cooling)
 * @param Th_in - Hot side inlet temperature (K)
 * @param Th_out - Hot side outlet temperature (K)
 * @param Tc_in - Cold side inlet temperature (K)
 * @param Tc_out - Cold side outlet temperature (K)
 * @returns Object with area (m²) and cost (USD)
 */
export function sizeHeatExchanger(
  duty: number,
  Th_in: number,
  Th_out: number,
  Tc_in: number,
  Tc_out: number
): { area: number; cost: number } {
  // Use absolute duty (both heaters and coolers have positive area)
  const Q = Math.abs(duty) * 1000; // kW -> W

  // Calculate LMTD
  // For countercurrent flow:
  //   dT1 = Th_in - Tc_out (hot end)
  //   dT2 = Th_out - Tc_in (cold end)
  const dT1 = Th_in - Tc_out;
  const dT2 = Th_out - Tc_in;

  let LMTD: number;

  if (Math.abs(dT1 - dT2) < 0.1) {
    // Temperature differences nearly equal, use arithmetic mean
    LMTD = (dT1 + dT2) / 2;
  } else if (dT1 <= 0 || dT2 <= 0) {
    // Temperature cross - invalid heat exchanger design
    // Use a minimum approach temperature
    LMTD = 10; // K, minimum practical LMTD
  } else {
    // Standard LMTD formula
    LMTD = (dT1 - dT2) / Math.log(dT1 / dT2);
  }

  // Ensure LMTD is reasonable
  LMTD = Math.max(LMTD, 5); // Minimum 5 K approach

  // Calculate area: A = Q / (U × LMTD)
  let area = Q / (U_DEFAULT * LMTD);

  // Apply minimum size
  area = Math.max(area, MIN_HX_AREA);

  // Cost correlation: Cost = 32800 × (A/100)^0.65
  const cost = 32800 * Math.pow(area / 100, 0.65);

  return { area, cost };
}

// ============================================================================
// PUMP SIZING
// ============================================================================

/**
 * Size a pump from power consumption
 *
 * Cost correlation (Guthrie/Turton):
 *   Cost = 9840 × (P/10)^0.55
 *   where P is in kW
 *
 * @param power - Pump power consumption in kW
 * @returns Object with power (kW) and cost (USD)
 */
export function sizePump(power: number): { power: number; cost: number } {
  // Use absolute power and apply minimum
  const P = Math.max(Math.abs(power), MIN_PUMP_POWER);

  // Cost correlation: Cost = 9840 × (P/10)^0.55
  const cost = 9840 * Math.pow(P / 10, 0.55);

  return { power: P, cost };
}

// ============================================================================
// COMPRESSOR SIZING
// ============================================================================

/**
 * Size a compressor from power consumption
 *
 * Cost correlation (Guthrie/Turton):
 *   Cost = 98400 × (P/100)^0.46
 *   where P is in kW
 *
 * @param power - Compressor power consumption in kW
 * @returns Object with power (kW) and cost (USD)
 */
export function sizeCompressor(power: number): { power: number; cost: number } {
  // Use absolute power and apply minimum
  const P = Math.max(Math.abs(power), MIN_COMPRESSOR_POWER);

  // Cost correlation: Cost = 98400 × (P/100)^0.46
  const cost = 98400 * Math.pow(P / 100, 0.46);

  return { power: P, cost };
}

// ============================================================================
// VESSEL SIZING
// ============================================================================

/**
 * Size a vessel (flash drum, separator) from volume
 *
 * Cost correlation (Guthrie/Turton):
 *   Cost = 17640 × (V/1)^0.62
 *   where V is in m³
 *
 * @param volume - Vessel volume in m³
 * @returns Object with volume (m³) and cost (USD)
 */
export function sizeVessel(volume: number): { volume: number; cost: number } {
  // Apply minimum volume
  const V = Math.max(Math.abs(volume), MIN_VESSEL_VOLUME);

  // Cost correlation: Cost = 17640 × (V/1)^0.62
  const cost = 17640 * Math.pow(V / 1, 0.62);

  return { volume: V, cost };
}

/**
 * Estimate flash drum volume from flow rate
 *
 * Uses rule of thumb: 5 minutes liquid residence time
 * Assumes 50% liquid holdup
 *
 * @param liquidFlow - Liquid flow rate in m³/h
 * @returns Vessel volume in m³
 */
export function estimateFlashVolume(liquidFlow: number): number {
  // 5 minutes residence time, 50% liquid holdup
  const residenceTime = 5 / 60; // hours
  const liquidHoldup = 0.5;

  const liquidVolume = liquidFlow * residenceTime;
  const totalVolume = liquidVolume / liquidHoldup;

  return Math.max(totalVolume, MIN_VESSEL_VOLUME);
}

// ============================================================================
// CAPEX CALCULATION FROM BLOCK RESULTS
// ============================================================================

/**
 * Calculate total equipment CAPEX from simulation block results
 *
 * Processes all blocks and applies appropriate sizing correlations
 * based on block type and available data (duty, power, etc.)
 *
 * @param blockResults - Array of block results from simulation
 * @returns Object with individual equipment sizes and total CAPEX
 */
export function calculateEquipmentCAPEX(
  blockResults: BlockResult[]
): CAPEXResult {
  const equipment: EquipmentSize[] = [];
  let totalCAPEX = 0;

  for (const block of blockResults) {
    let sizing: EquipmentSize | null = null;

    switch (block.type) {
      case 'Heater':
      case 'Cooler':
      case 'HeatExchanger': {
        if (block.duty && block.inlet && block.outlet) {
          // Estimate utility side temperatures
          // For heater: steam at ~180°C (453 K) condensing
          // For cooler: cooling water 25-35°C (298-308 K)
          let Th_in: number, Th_out: number, Tc_in: number, Tc_out: number;

          if (block.duty > 0) {
            // Heating - process side is cold
            Th_in = 453; // Steam inlet
            Th_out = 453; // Steam outlet (condensing)
            Tc_in = block.inlet.T;
            Tc_out = block.outlet.T;
          } else {
            // Cooling - process side is hot
            Th_in = block.inlet.T;
            Th_out = block.outlet.T;
            Tc_in = 298; // Cooling water inlet (25°C)
            Tc_out = 308; // Cooling water outlet (35°C)
          }

          const hxSizing = sizeHeatExchanger(
            block.duty,
            Th_in,
            Th_out,
            Tc_in,
            Tc_out
          );

          sizing = {
            blockId: block.id,
            blockType: block.type,
            sizingParam: 'area',
            value: hxSizing.area,
            unit: 'm²',
            cost: hxSizing.cost,
          };
        }
        break;
      }

      case 'Pump': {
        if (block.power) {
          const pumpSizing = sizePump(block.power);

          sizing = {
            blockId: block.id,
            blockType: block.type,
            sizingParam: 'power',
            value: pumpSizing.power,
            unit: 'kW',
            cost: pumpSizing.cost,
          };
        }
        break;
      }

      case 'Compressor': {
        if (block.power) {
          const compSizing = sizeCompressor(block.power);

          sizing = {
            blockId: block.id,
            blockType: block.type,
            sizingParam: 'power',
            value: compSizing.power,
            unit: 'kW',
            cost: compSizing.cost,
          };
        }
        break;
      }

      case 'Flash':
      case 'Separator': {
        // Estimate volume from flow rate
        // Assume average liquid density ~800 kg/m³, MW ~50 kg/kmol
        if (block.inlet) {
          const molarFlow = block.inlet.flow; // kmol/h
          const avgMW = 50; // kg/kmol (rough estimate)
          const avgDensity = 800; // kg/m³
          const volumetricFlow = (molarFlow * avgMW) / avgDensity; // m³/h

          const volume = estimateFlashVolume(volumetricFlow);
          const vesselSizing = sizeVessel(volume);

          sizing = {
            blockId: block.id,
            blockType: block.type,
            sizingParam: 'volume',
            value: vesselSizing.volume,
            unit: 'm³',
            cost: vesselSizing.cost,
          };
        }
        break;
      }

      case 'Absorber':
      case 'Stripper':
      case 'DistillationColumn': {
        // Column sizing is more complex - use simplified correlation
        // Based on vapor flow rate and height
        if (block.inlet) {
          // Rough estimate: 2 m diameter, 10 m height for small columns
          const volume = Math.PI * 1 * 1 * 10; // ~31 m³
          const vesselSizing = sizeVessel(volume);

          // Columns cost more due to internals - apply factor of 3
          sizing = {
            blockId: block.id,
            blockType: block.type,
            sizingParam: 'volume',
            value: vesselSizing.volume,
            unit: 'm³',
            cost: vesselSizing.cost * 3,
          };
        }
        break;
      }

      case 'Reactor': {
        // Reactor sizing depends heavily on reaction kinetics
        // Use simplified volume-based correlation
        if (block.inlet) {
          // Assume 1 hour residence time for batch-equivalent
          const molarFlow = block.inlet.flow;
          const avgMW = 50;
          const avgDensity = 800;
          const volumetricFlow = (molarFlow * avgMW) / avgDensity;
          const volume = volumetricFlow * 1; // 1 hour residence

          const vesselSizing = sizeVessel(Math.max(volume, 1));

          // Reactors cost more due to internals, agitation, etc.
          sizing = {
            blockId: block.id,
            blockType: block.type,
            sizingParam: 'volume',
            value: vesselSizing.volume,
            unit: 'm³',
            cost: vesselSizing.cost * 2,
          };
        }
        break;
      }

      case 'Valve': {
        // Valves are relatively inexpensive
        // Use simple fixed cost estimate
        sizing = {
          blockId: block.id,
          blockType: block.type,
          sizingParam: 'count',
          value: 1,
          unit: 'unit',
          cost: 5000, // Fixed cost for control valve
        };
        break;
      }

      // Feed, Mixer, Splitter, Sink - no equipment cost
      case 'Feed':
      case 'Mixer':
      case 'Splitter':
      case 'Sink':
      case 'TextBox':
      default:
        // No equipment cost for these block types
        break;
    }

    if (sizing) {
      equipment.push(sizing);
      totalCAPEX += sizing.cost;
    }
  }

  return { equipment, totalCAPEX };
}

/**
 * Convert block data from engine-v2 format to BlockResult format
 *
 * Helper function to transform simulation output for CAPEX calculation
 *
 * @param blocks - Blocks from ProjectV2.blocks after simulation
 * @returns Array of BlockResult for CAPEX calculation
 */
export function convertBlocksToResults(
  blocks: Array<{
    id: string;
    type: string;
    duty?: number;
    power?: number;
    inputs?: Record<string, any>;
    outputs?: Record<string, any>;
  }>
): BlockResult[] {
  return blocks.map((block) => {
    // Get inlet stream (usually 'in' port)
    const inlet = block.inputs?.in || block.inputs?.feed || Object.values(block.inputs || {})[0];

    // Get outlet stream (usually 'out' port)
    const outlet = block.outputs?.out || block.outputs?.vapor || Object.values(block.outputs || {})[0];

    return {
      id: block.id,
      type: block.type,
      duty: block.duty,
      power: block.power,
      inlet: inlet
        ? {
            T: inlet.T,
            P: inlet.P,
            flow: inlet.flow,
            composition: inlet.composition,
          }
        : undefined,
      outlet: outlet
        ? {
            T: outlet.T,
            P: outlet.P,
            flow: outlet.flow,
            composition: outlet.composition,
          }
        : undefined,
    };
  });
}
