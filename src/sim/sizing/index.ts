/**
 * Equipment sizing dispatcher — engine-agnostic. Given a flowsheet and a
 * standardized simulation run, computes a physical size per cost-bearing unit,
 * keyed to the cost DB's sizing_basis. Pure + deterministic: identical inputs →
 * identical output (Quick and Rigorous get the same numbers from the same
 * inputs). See docs/sizing/methods.md.
 */
import type { FlowsheetGraph } from '../../core/schema';
import { COLUMN, REACTOR_RESIDENCE_S, U_BY_SERVICE, UTILITY_TEMPS, VESSEL } from './assumptions';
import {
  cylinderVolume,
  diameterFromVapor,
  flowParameter,
  hxArea,
  lmtd,
  mixtureMW,
  soudersBrownVelocity,
  trayFloodVelocity,
  volFlowM3s,
} from './correlations';
import { safeEval } from './safeEval';
import type { EquipmentSize, SizeBasis, SizedStream, UnitSizingInput } from './types';

/** Mirror of the cost DB's unit_cost_map.sizing_basis. */
export const UNIT_SIZE_BASIS: Record<string, SizeBasis> = {
  Cooler: 'area', HeatExchanger: 'area',
  Pump: 'power', Compressor: 'power', Expander: 'power',
  Heater: 'heat_duty',
  Flash: 'volume', Separator: 'volume', ThreePhaseSeparator: 'volume',
  Absorber: 'volume', Stripper: 'volume', DistillationColumn: 'volume',
  ShortcutDistillation: 'volume', ReactiveDistillation: 'volume',
  Reactor: 'volume', RCSTR: 'volume', RPfr: 'volume', RBatch: 'volume',
  RStoic: 'volume', RYield: 'volume', REquil: 'volume', RGibbs: 'volume',
  CustomUnit: 'delegate',
  Feed: 'none', Sink: 'none', Mixer: 'none', Splitter: 'none',
  Valve: 'none', PipeSegment: 'none', TextBox: 'none',
};

const COLUMN_TYPES = new Set([
  'Absorber', 'Stripper', 'DistillationColumn', 'ShortcutDistillation', 'ReactiveDistillation',
]);
const REACTOR_TYPES = new Set([
  'Reactor', 'RCSTR', 'RPfr', 'RBatch', 'RStoic', 'RYield', 'REquil', 'RGibbs',
]);

function withMW(s: SizedStream): SizedStream {
  return { ...s, mw: s.mw ?? mixtureMW(s.composition) };
}

function streamVolFlow(s: SizedStream): number {
  const mw = s.mw ?? mixtureMW(s.composition);
  return s.density && s.density > 0 ? volFlowM3s(s.flowMol, mw, s.density) : 0;
}

function none(input: UnitSizingInput): EquipmentSize {
  return {
    unitId: input.unitId, unitType: input.unitType, sizeBasis: 'none',
    sizes: {}, assumptions: [], method: 'n/a (connector)', source: '', inRange: true,
  };
}

function missing(input: UnitSizingInput, basis: SizeBasis, why: string): EquipmentSize {
  return {
    unitId: input.unitId, unitType: input.unitType, sizeBasis: basis,
    sizes: {}, assumptions: [], method: '', source: '', inRange: false, note: why,
  };
}

// --- per-basis sizing ------------------------------------------------------ //
function sizeArea(input: UnitSizingInput): EquipmentSize {
  if (input.duty === undefined || input.inlets.length === 0 || input.outlets.length === 0) {
    return missing(input, 'area', 'no duty / inlet / outlet to size area');
  }
  const assumptions: string[] = [];
  let thIn: number, thOut: number, tcIn: number, tcOut: number, U: number;

  if (input.inlets.length >= 2 && input.outlets.length >= 2) {
    // Two-sided exchanger: hottest inlet = hot side; coldest = cold side.
    const inT = input.inlets.map((s) => s.T);
    const outT = input.outlets.map((s) => s.T);
    thIn = Math.max(...inT); tcIn = Math.min(...inT);
    thOut = Math.min(...outT); tcOut = Math.max(...outT);
    U = U_BY_SERVICE.liquid_liquid;
    assumptions.push(`U=${U} W/m²·K (liquid-liquid default)`);
  } else {
    // One-sided (Cooler) vs a utility.
    const pin = input.inlets[0].T, pout = input.outlets[0].T;
    const util = UTILITY_TEMPS.cooling_water;
    thIn = pin; thOut = pout; tcIn = util.in; tcOut = util.out;
    U = U_BY_SERVICE.process_cooling_water;
    assumptions.push(`U=${U} W/m²·K (process-CW)`, 'cooling water 30→40 °C (assumed)');
  }
  const dT = lmtd(thIn, thOut, tcIn, tcOut);
  assumptions.push(`LMTD=${dT.toFixed(1)} K`);
  const area = hxArea(input.duty, U, dT);
  return {
    unitId: input.unitId, unitType: input.unitType, sizeBasis: 'area',
    sizes: { area }, assumptions, method: 'A = Q/(U·LMTD)', source: 'Towler 19.1',
    inRange: area > 0,
  };
}

function sizePower(input: UnitSizingInput): EquipmentSize {
  if (input.work === undefined) return missing(input, 'power', 'no mechanical work in results');
  return {
    unitId: input.unitId, unitType: input.unitType, sizeBasis: 'power',
    sizes: { power: Math.abs(input.work) }, assumptions: ['from simulation work'],
    method: 'sim work', source: 'simulation', inRange: true,
  };
}

function sizeHeatDuty(input: UnitSizingInput): EquipmentSize {
  if (input.duty === undefined) return missing(input, 'heat_duty', 'no duty in results');
  return {
    unitId: input.unitId, unitType: input.unitType, sizeBasis: 'heat_duty',
    sizes: { heat_duty: Math.abs(input.duty) }, assumptions: ['fired-heater sized by duty'],
    method: 'sim duty', source: 'simulation', inRange: true,
  };
}

function sizeReactor(input: UnitSizingInput): EquipmentSize {
  const feed = input.inlets[0];
  if (!feed) return missing(input, 'volume', 'no feed stream to size reactor');
  const vdot = streamVolFlow(withMW(feed)); // m³/s
  const gas = (feed.vaporFraction ?? 0) > 0.5;
  const tau = gas ? REACTOR_RESIDENCE_S.gas : REACTOR_RESIDENCE_S.liquid; // s
  const volume = Math.max(vdot * tau, 0.1);
  const diameter = Math.cbrt((4 * volume) / (Math.PI * VESSEL.aspectRatio));
  const length = VESSEL.aspectRatio * diameter;
  return {
    unitId: input.unitId, unitType: input.unitType, sizeBasis: 'volume',
    sizes: { volume, diameter, length },
    assumptions: [`residence time ${tau} s (${gas ? 'gas' : 'liquid'} default — OVERRIDE per reaction)`,
      `L/D=${VESSEL.aspectRatio}`],
    method: 'V = V̇·τ', source: 'Turton/heuristic', inRange: vdot > 0,
  };
}

function vaporLiquidOutlets(input: UnitSizingInput): { vap?: SizedStream; liq?: SizedStream } {
  let vap: SizedStream | undefined, liq: SizedStream | undefined;
  for (const s of input.outlets) {
    const vf = s.vaporFraction ?? (s.phase === 'V' ? 1 : 0);
    if (vf > 0.5 && !vap) vap = s;
    if (vf <= 0.5 && !liq) liq = s;
  }
  return { vap, liq };
}

function sizeSeparatorVessel(input: UnitSizingInput): EquipmentSize {
  const { vap, liq } = vaporLiquidOutlets(input);
  const assumptions: string[] = [];
  // Path selection: meaningful vapor → Souders-Brown; else liquid residence.
  const inletVF = input.inlets[0]?.vaporFraction ?? 0;
  const hasVapor = !!vap && (vap.vaporFraction ?? 1) > VESSEL.vaporFractionThreshold;

  if (hasVapor && liq) {
    const rhoV = vap!.density ?? 0;
    const rhoL = liq.density ?? 0;
    const uMax = soudersBrownVelocity(rhoL, rhoV, VESSEL.soudersBrownK);
    const vapVol = streamVolFlow(withMW(vap!));
    const diameter = diameterFromVapor(vapVol, uMax);
    const liqVol = streamVolFlow(withMW(liq)); // m³/s
    const holdupVol = (liqVol * VESSEL.refluxHoldupMin * 60) / VESSEL.fillFraction; // m³
    const height = Math.max((4 * holdupVol) / (Math.PI * diameter * diameter), 1.5 * diameter);
    const volume = cylinderVolume(diameter, height);
    assumptions.push(`Souders-Brown K=${VESSEL.soudersBrownK} m/s`,
      `liquid holdup ${VESSEL.refluxHoldupMin} min`, 'vapor-liquid separator path');
    return {
      unitId: input.unitId, unitType: input.unitType, sizeBasis: 'volume',
      sizes: { volume, diameter, height }, assumptions,
      method: 'Souders-Brown', source: 'GPSA/Towler', inRange: diameter > 0,
    };
  }
  // Liquid-dominated drum: residence-time volume.
  const liquid = liq ?? input.outlets[0] ?? input.inlets[0];
  if (!liquid) return missing(input, 'volume', 'no stream to size vessel');
  const liqVol = streamVolFlow(withMW(liquid));
  const volume = Math.max((liqVol * VESSEL.refluxHoldupMin * 60) / VESSEL.fillFraction, 0.1);
  const diameter = Math.cbrt((4 * volume) / (Math.PI * VESSEL.aspectRatio));
  assumptions.push(`liquid residence ${VESSEL.refluxHoldupMin} min`,
    `fill ${VESSEL.fillFraction}`, `L/D=${VESSEL.aspectRatio}`,
    `liquid-dominated path (inlet vapor frac ${inletVF.toFixed(2)})`);
  return {
    unitId: input.unitId, unitType: input.unitType, sizeBasis: 'volume',
    sizes: { volume, diameter, height: VESSEL.aspectRatio * diameter },
    assumptions, method: 'liquid residence time', source: 'Towler', inRange: liqVol > 0,
  };
}

function sizeColumn(input: UnitSizingInput): EquipmentSize {
  const { vap, liq } = vaporLiquidOutlets(input);
  // Internal vapor traffic ≈ overhead vapor × (1+reflux) when known.
  const vapStream = vap ?? input.outlets.find((s) => (s.vaporFraction ?? 0) > 0) ?? input.outlets[0];
  const liqStream = liq ?? input.inlets.find((s) => (s.vaporFraction ?? 1) < 0.5) ?? input.inlets[0];
  if (!vapStream || !liqStream) return missing(input, 'volume', 'no vapor/liquid stream to size column');
  const rhoV = vapStream.density ?? 0;
  const rhoL = liqStream.density ?? 0;
  const assumptions: string[] = [];

  const reflux = input.refluxRatio;
  const vapMult = reflux !== undefined ? 1 + reflux : 1;
  if (reflux !== undefined) assumptions.push(`internal vapor ≈ overhead × (1+R=${reflux.toFixed(2)})`);
  else assumptions.push('internal vapor ≈ overhead vapor (no reflux exposed — estimate)');

  const vapVol = streamVolFlow(withMW(vapStream)) * vapMult;
  const uFlood = trayFloodVelocity(COLUMN.traySpacing, rhoL, rhoV);
  const uDesign = COLUMN.floodFraction * uFlood;
  const netArea = uDesign > 0 ? vapVol / uDesign : NaN;
  const colArea = netArea / 0.88; // 12 % downcomer
  const diameter = Math.sqrt((4 * colArea) / Math.PI);

  let nStages = input.nStages;
  if (nStages === undefined) {
    nStages = 10; // conservative fallback when no stage count is exposed
    assumptions.push('stage count not exposed → assumed 10 (FLAG: confirm via shortcut/rigorous)');
  }
  const height = nStages * COLUMN.traySpacing * COLUMN.heightAllowance;
  const volume = cylinderVolume(diameter, height);
  assumptions.push(`Towler flooding (eq 17.34), ${COLUMN.floodFraction * 100}% flood`,
    `tray spacing ${COLUMN.traySpacing} m`,
    `F_LV=${flowParameter(streamVolFlow(withMW(liqStream)) * (rhoL || 0), vapVol * (rhoV || 0), rhoL, rhoV).toFixed(3)}`);
  return {
    unitId: input.unitId, unitType: input.unitType, sizeBasis: 'volume',
    sizes: { volume, diameter, height, nStages }, assumptions,
    method: 'Fair/Towler flooding', source: 'Towler 17.34', inRange: diameter > 0,
  };
}

/**
 * Agent-defined sizing for a CustomUnit (S5). Evaluates a sandboxed arithmetic
 * formula against named result variables to produce the declared sizeQuantity.
 * Returns null to signal "fall back to the baseType built-in" (method 'inherit'
 * or no expression). Always flagged agent-defined — never a validated built-in.
 */
function sizeCustom(input: UnitSizingInput): EquipmentSize | null {
  const spec = input.customSizing;
  if (!spec || spec.method !== 'formula' || !spec.expression) return null;

  const feed = input.inlets[0];
  const liqOut = input.outlets.find((s) => (s.vaporFraction ?? (s.phase === 'V' ? 1 : 0)) <= 0.5);
  const vapOut = input.outlets.find((s) => (s.vaporFraction ?? (s.phase === 'V' ? 1 : 0)) > 0.5);
  const vars: Record<string, number> = {
    ...spec.variables, // named constants (tau, U, …) — result vars below win on name clash
    duty: input.duty ?? 0,
    work: input.work ?? 0,
    flow_mol: feed?.flowMol ?? 0,
    flow_vol: feed ? streamVolFlow(withMW(feed)) : 0,
    density_l: liqOut?.density ?? feed?.density ?? 0,
    density_v: vapOut?.density ?? 0,
    T: feed?.T ?? 0,
    P: feed?.P ?? 0,
  };

  const quantity = spec.sizeQuantity; // 'area' | 'volume' | 'power' | 'heat_duty'
  let value: number;
  try {
    value = safeEval(spec.expression, vars);
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'invalid expression';
    return missing(input, quantity, `agent sizing formula rejected: ${msg}`);
  }

  const assumptions = ['agent-defined sizing (not a validated built-in)', ...spec.assumptions];
  const method = `agent formula: ${spec.expression}`;
  const source = spec.source || 'agent-defined';
  const base = {
    unitId: input.unitId, unitType: input.unitType, sizeBasis: quantity,
    assumptions, method, source, inRange: value > 0,
  };
  if (quantity === 'volume') {
    const volume = Math.max(value, 0);
    const diameter = Math.cbrt((4 * volume) / (Math.PI * VESSEL.aspectRatio));
    return { ...base, sizes: { volume, diameter, length: VESSEL.aspectRatio * diameter } };
  }
  return { ...base, sizes: { [quantity]: Math.abs(value) } };
}

/** Size a single unit, dispatching on its cost-DB basis. */
export function sizeUnit(input: UnitSizingInput): EquipmentSize {
  const basis = UNIT_SIZE_BASIS[input.unitType] ?? 'none';
  switch (basis) {
    case 'none': return none(input);
    case 'power': return sizePower(input);
    case 'heat_duty': return sizeHeatDuty(input);
    case 'area': return sizeArea(input);
    case 'delegate': {
      // Agent-defined formula sizing wins; otherwise inherit the baseType built-in.
      const custom = sizeCustom(input);
      if (custom) return custom;
      if (!input.baseType) return missing(input, 'delegate', 'custom unit needs a baseType or sizing spec');
      return sizeUnit({ ...input, unitType: input.baseType, customSizing: undefined });
    }
    case 'volume':
      if (COLUMN_TYPES.has(input.unitType)) return sizeColumn(input);
      if (REACTOR_TYPES.has(input.unitType)) return sizeReactor(input);
      return sizeSeparatorVessel(input); // Flash / Separator / ThreePhaseSeparator
    default: return none(input);
  }
}

// --- bridge: standardized SimulationRun → per-unit sizes -------------------- //
type RawStream = {
  id: string; T?: number; P?: number; flow?: number; density?: number;
  mw?: number; vaporFraction?: number; phase?: string;
  composition?: Record<string, number>;
};
type RawUnitResult = Record<string, unknown> & { id?: string };

function toSizedStream(s: RawStream): SizedStream {
  return {
    id: s.id, T: s.T ?? 0, P: s.P ?? 0, flowMol: s.flow ?? 0,
    density: s.density, mw: s.mw, vaporFraction: s.vaporFraction, phase: s.phase,
    composition: s.composition,
  };
}

function num(r: RawUnitResult | undefined, ...keys: string[]): number | undefined {
  if (!r) return undefined;
  for (const k of keys) {
    const v = r[k];
    if (typeof v === 'number' && Number.isFinite(v)) return v;
  }
  return undefined;
}

/**
 * Size every cost-bearing unit in a flowsheet from a standardized run.
 * Tolerant of both Quick (`rawOutputs.blockResults` keyed by node id) and
 * backend (`rawOutputs.units` array) result shapes.
 */
export function sizeFlowsheet(
  graph: FlowsheetGraph,
  run: { rawOutputs?: Record<string, unknown> } | undefined,
): Map<string, EquipmentSize> {
  const raw = run?.rawOutputs ?? {};
  const streamsById = new Map<string, SizedStream>();
  for (const s of (raw.streams as RawStream[] | undefined) ?? []) {
    if (s?.id) streamsById.set(s.id, toSizedStream(s));
  }
  const resultsById = new Map<string, RawUnitResult>();
  const blockResults = raw.blockResults as Record<string, RawUnitResult> | undefined;
  if (blockResults) for (const [id, r] of Object.entries(blockResults)) resultsById.set(id, r);
  for (const u of (raw.units as RawUnitResult[] | undefined) ?? []) {
    if (u?.id) resultsById.set(u.id as string, u);
  }

  const out = new Map<string, EquipmentSize>();
  for (const node of graph.nodes) {
    const basis = UNIT_SIZE_BASIS[node.type];
    if (!basis || basis === 'none') continue;
    const inlets: SizedStream[] = [];
    const outlets: SizedStream[] = [];
    for (const e of graph.edges) {
      const s = streamsById.get(e.id);
      if (!s) continue;
      if (e.to?.nodeId === node.id) inlets.push(s);
      if (e.from?.nodeId === node.id) outlets.push(s);
    }
    const r = resultsById.get(node.id);
    const input: UnitSizingInput = {
      unitId: node.id, unitType: node.type,
      duty: num(r, 'duty', 'Q', 'heat_duty'),
      work: num(r, 'power', 'work', 'W'),
      nStages: num(r, 'num_actual_stages', 'n_stages', 'nStages', 'stages'),
      refluxRatio: num(r, 'reflux_ratio', 'refluxRatio', 'R'),
      inlets, outlets,
      baseType: node.customSpec?.baseType,
      customSizing: node.customSpec?.sizing,
    };
    out.set(node.id, sizeUnit(input));
  }
  return out;
}

export { type EquipmentSize, type UnitSizingInput, type SizedStream } from './types';
