/**
 * Types for the shared, engine-agnostic equipment sizing layer.
 * Sizing is a pure post-processing pass on standardized simulation results.
 */
import type { CustomSizingSpec } from '../../core/schema';

/** What the cost DB's correlation for a unit consumes (unit_cost_map.sizing_basis). */
export type SizeBasis = 'area' | 'power' | 'heat_duty' | 'volume' | 'none' | 'delegate';

/** A stream as the sizing layer needs it (subset of the standardized stream). */
export interface SizedStream {
  id: string;
  T: number; // K
  P: number; // bar
  flowMol: number; // kmol/h
  density?: number; // kg/m³ (overall; engines emit this)
  mw?: number; // kg/kmol (computed from composition if absent)
  vaporFraction?: number; // 0..1
  phase?: string;
  composition?: Record<string, number>; // mole fractions
}

/** Per-unit inputs the sizing dispatcher assembles from the flowsheet + run. */
export interface UnitSizingInput {
  unitId: string;
  unitType: string;
  duty?: number; // kW (signed: + heating, − cooling)
  work?: number; // kW (mechanical work / power)
  nStages?: number; // if the engine exposed a column stage count
  refluxRatio?: number; // if the engine exposed a column reflux ratio
  inlets: SizedStream[];
  outlets: SizedStream[];
  /** For CustomUnit: the baseType to delegate sizing to when no custom spec. */
  baseType?: string;
  /** For CustomUnit: agent-defined sizing spec (formula or inherit). */
  customSizing?: CustomSizingSpec;
}

/** The sizing result attached to each unit. */
export interface EquipmentSize {
  unitId: string;
  unitType: string;
  sizeBasis: SizeBasis;
  sizes: {
    area?: number; // m²
    volume?: number; // m³
    diameter?: number; // m
    height?: number; // m
    length?: number; // m
    power?: number; // kW
    heat_duty?: number; // kW
    nStages?: number;
  };
  assumptions: string[];
  method: string;
  source: string;
  inRange: boolean;
  /** Set when sizing could not be computed (missing inputs); never fabricated. */
  note?: string;
}
