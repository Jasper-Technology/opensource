/**
 * Sequential Modular Block Solver
 *
 * Based on Jasper-Technology/opensource engine.
 * Solves flowsheet block-by-block with rigorous thermodynamics:
 * - Property method dispatch (Ideal, PR, NRTL)
 * - Enthalpy/entropy-based energy balances
 * - Proper equipment sizing (pump power, compressor isentropic, heat duty)
 * - Shortcut distillation (Fenske-Underwood-Gilliland)
 * - Reactors with heat of reaction
 * - Recycle convergence with Wegstein acceleration
 * - Kremser absorber/stripper
 */

import type { JasperProject, UnitOpNode, FlowsheetGraph } from '../../core/schema';
import {
  COMPONENT_DATABASE,
  mixtureEnthalpy,
  calculateKValues,
  rachfordRiceFlash,
  flashComposition,
  density,
  determinePhase,
  idealGasCp,
  heatOfReaction,
} from '../thermo/properties';
import { getPropertyPackage, type PropertyPackage } from '../thermo/propertyMethod';

const BAR_TO_PA = 1e5;
const R = 8.314; // J/(mol·K)

/**
 * Resolve composition keys: project uses component IDs, thermo uses formula/name.
 * Maps compId -> formula (or name) for COMPONENT_DATABASE lookup.
 */
function resolveCompositionForThermo(
  composition: Record<string, number>,
  project: JasperProject
): Record<string, number> {
  if (!composition || Object.keys(composition).length === 0) return {};
  const components = project.components || [];
  const resolved: Record<string, number> = {};
  for (const [key, frac] of Object.entries(composition)) {
    const comp = components.find((c) => c.id === key);
    const thermoKey = comp?.formula || comp?.name || key;
    resolved[thermoKey] = (resolved[thermoKey] ?? 0) + frac;
  }
  return resolved;
}

export interface StreamState {
  id: string;
  name: string;
  T: number;           // Temperature (K)
  P: number;           // Pressure (bar)
  flow: number;        // Total molar flow (kmol/h)
  composition: Record<string, number>; // Mole fractions
  phase: 'V' | 'L' | 'VL';
  H: number;           // Specific enthalpy (kJ/mol)
}

/** Normalize composition to sum to 1 */
function normalizeComposition(comp: Record<string, number>): Record<string, number> {
  const sum = Object.values(comp).reduce((a, b) => a + b, 0);
  if (sum <= 0) return comp;
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(comp)) out[k] = v / sum;
  return out;
}

/** Extract numeric value from ParamValue */
function getParam(param: any): number | undefined {
  if (!param) return undefined;
  if (param.kind === 'quantity') return param.q?.value;
  if (param.kind === 'number') return param.x;
  if (param.kind === 'int') return param.n;
  return undefined;
}

function getParamUnit(param: any): string {
  return param?.kind === 'quantity' ? param.q?.unit || 'bar' : 'bar';
}

function getParamString(param: any): string | undefined {
  if (!param) return undefined;
  if (param.kind === 'string') return param.s;
  if (param.kind === 'enum') return param.e;
  return undefined;
}

/** Convert param quantity to Kelvin */
function paramToKelvin(param: any, defaultVal: number): number {
  const v = getParam(param);
  if (v === undefined) return defaultVal;
  const u = getParamUnit(param);
  if (u === 'K') return v;
  if (u === 'C') return v + 273.15;
  if (u === 'F') return (v - 32) * 5 / 9 + 273.15;
  return v + 273.15; // assume C
}

/** Convert param quantity to bar (for StreamState.P) */
function paramToBar(param: any, defaultVal: number): number {
  const v = getParam(param);
  if (v === undefined) return defaultVal;
  const u = getParamUnit(param);
  if (u === 'bar') return v;
  if (u === 'Pa') return v / BAR_TO_PA;
  if (u === 'kPa') return v / 100;
  if (u === 'psi') return v * 0.0689476;
  return v;
}

export interface SolverResult {
  converged: boolean;
  streams: Map<string, StreamState>;
  blockResults: Map<string, any>;
  error?: string;
  recycleIterations?: number;
}

/** Resolve flowsheet graph (active flowsheet or main) - exported for engine */
export function getFlowsheetGraph(project: JasperProject) {
  if (project.flowsheets?.length) {
    const activeId = project.activeFlowsheetId || project.flowsheets[0]?.id || 'main';
    const f = project.flowsheets.find(x => x.id === activeId) || project.flowsheets[0];
    return f?.graph ?? project.flowsheet;
  }
  return project.flowsheet;
}

/**
 * Main block solver - sequential modular approach with recycle convergence
 */
export function solveFlowsheet(project: JasperProject): SolverResult {
  const streams = new Map<string, StreamState>();
  const blockResults = new Map<string, any>();
  const flowsheet = getFlowsheetGraph(project);

  // Create property package from project settings
  const methodName = project.thermodynamics?.propertyMethod ?? 'Ideal';
  const pkg = getPropertyPackage(methodName);

  try {
    initializeFeedStreams(project, flowsheet, streams, pkg);

    // Topological sort with tear stream detection
    const { order, tearStreams } = topologicalSortWithTear(flowsheet);

    if (tearStreams.length === 0) {
      // No recycles - simple sequential solve
      for (const blockId of order) {
        const block = flowsheet.nodes.find(n => n.id === blockId);
        if (!block) continue;
        solveBlock(block, project, flowsheet, streams, blockResults, pkg);
      }
      return { converged: true, streams, blockResults };
    }

    // Recycle convergence loop
    // Initialize tear streams with feed-like defaults
    for (const tearId of tearStreams) {
      if (!streams.has(tearId)) {
        const edge = flowsheet.edges.find(e => e.id === tearId);
        if (!edge) continue;
        // Initialize with first available stream composition or pure component
        const firstStream = Array.from(streams.values())[0];
        if (firstStream) {
          streams.set(tearId, {
            id: tearId,
            name: edge.name,
            T: firstStream.T,
            P: firstStream.P,
            flow: firstStream.flow * 0.1,
            composition: { ...firstStream.composition },
            phase: firstStream.phase,
            H: firstStream.H,
          });
        }
      }
    }

    // Wegstein acceleration storage
    const prevValues = new Map<string, number[]>();
    const prevPrevValues = new Map<string, number[]>();
    let recycleIter = 0;
    const MAX_RECYCLE_ITER = 50;
    const RECYCLE_TOL = 1e-4;

    for (recycleIter = 0; recycleIter < MAX_RECYCLE_ITER; recycleIter++) {
      // Save tear stream values before solve
      for (const tearId of tearStreams) {
        const s = streams.get(tearId);
        if (s) {
          prevPrevValues.set(tearId, prevValues.get(tearId) ?? []);
          prevValues.set(tearId, [s.T, s.P, s.flow, ...Object.values(s.composition)]);
        }
      }

      // Solve all blocks in order
      for (const blockId of order) {
        const block = flowsheet.nodes.find(n => n.id === blockId);
        if (!block) continue;
        solveBlock(block, project, flowsheet, streams, blockResults, pkg);
      }

      // Check convergence on tear streams
      let maxRelChange = 0;
      for (const tearId of tearStreams) {
        const s = streams.get(tearId);
        const prev = prevValues.get(tearId);
        if (!s || !prev) continue;
        const curr = [s.T, s.P, s.flow, ...Object.values(s.composition)];
        for (let i = 0; i < Math.min(curr.length, prev.length); i++) {
          const denom = Math.abs(prev[i]) + 1e-10;
          const rel = Math.abs(curr[i] - prev[i]) / denom;
          if (rel > maxRelChange) maxRelChange = rel;
        }

        // Wegstein acceleration
        const pprev = prevPrevValues.get(tearId);
        if (pprev && pprev.length === curr.length && recycleIter > 1) {
          const accelerated = [...curr];
          for (let i = 0; i < curr.length; i++) {
            const x1 = pprev[i];
            const x2 = prev[i];
            const g1 = prev[i]; // g(x1) = x2
            const g2 = curr[i]; // g(x2) = curr
            const slope = (x2 - x1) !== 0 ? (g2 - g1) / (x2 - x1) : 0;
            const q = slope / (slope - 1);
            const qClamped = Math.max(-5, Math.min(q, 0)); // bounded Wegstein
            accelerated[i] = (1 - qClamped) * curr[i] + qClamped * prev[i];
          }
          // Apply accelerated values back to tear stream
          s.T = Math.max(100, accelerated[0]);
          s.P = Math.max(0.01, accelerated[1]);
          s.flow = Math.max(0, accelerated[2]);
          const compKeys = Object.keys(s.composition);
          for (let i = 0; i < compKeys.length; i++) {
            s.composition[compKeys[i]] = Math.max(0, accelerated[3 + i]);
          }
          s.composition = normalizeComposition(s.composition);
          s.H = pkg.mixtureEnthalpy(s.composition, s.T, s.P * BAR_TO_PA);
        }
      }

      if (maxRelChange < RECYCLE_TOL) break;
    }

    return {
      converged: recycleIter < MAX_RECYCLE_ITER,
      streams,
      blockResults,
      recycleIterations: recycleIter,
    };
  } catch (error) {
    return {
      converged: false,
      streams,
      blockResults,
      error: error instanceof Error ? error.message : 'Unknown solver error',
    };
  }
}

/**
 * Initialize feed streams from Feed node params, falling back to edge spec.
 */
function initializeFeedStreams(
  project: JasperProject,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  pkg: PropertyPackage,
) {
  const feedBlocks = flowsheet.nodes.filter(n => n.type === 'Feed');

  for (const feed of feedBlocks) {
    const outletStreams = flowsheet.edges.filter(e => e.from.nodeId === feed.id);

    const nodeT = getParam(feed.params.T);
    const nodeTUnit = feed.params.T?.kind === 'quantity' ? feed.params.T.q?.unit : undefined;
    const nodeP = getParam(feed.params.P);
    const nodePUnit = feed.params.P?.kind === 'quantity' ? feed.params.P.q?.unit : undefined;
    const nodeFlow = getParam(feed.params.flow);
    const nodeComp = (feed.params.composition as { kind: 'composition'; comp: Record<string, number> } | undefined)?.comp;

    for (const stream of outletStreams) {
      const spec = stream.spec ?? {};

      const rawComp = nodeComp ?? spec.composition ?? {};
      let composition = resolveCompositionForThermo(rawComp, project);
      if (Object.keys(composition).length === 0) {
        const comps = project.components || [];
        if (comps.length > 0) {
          composition = { [comps[0].formula || comps[0].name]: 1.0 };
        } else continue;
      }

      const T = nodeT !== undefined
        ? convertTemperature(nodeT, nodeTUnit || 'C')
        : convertTemperature(spec.T?.value || 298.15, spec.T?.unit || 'K');
      const P = nodeP !== undefined
        ? convertPressure(nodeP, nodePUnit || 'bar')
        : convertPressure(spec.P?.value || 1.0, spec.P?.unit || 'bar');
      const flow = nodeFlow ?? spec.flow?.value ?? 100;

      const H = pkg.mixtureEnthalpy(composition, T, P * BAR_TO_PA);

      streams.set(stream.id, {
        id: stream.id,
        name: stream.name,
        T,
        P,
        flow,
        composition,
        phase: (spec.phase && (spec.phase === 'V' || spec.phase === 'L' || spec.phase === 'VL') ? spec.phase : 'L') as 'V' | 'L' | 'VL',
        H,
      });
    }
  }
}

/**
 * Topological sort with tear stream detection for recycle loops.
 * Returns { order, tearStreams } where tearStreams are back-edge stream IDs.
 */
function topologicalSortWithTear(flowsheet: FlowsheetGraph): { order: string[]; tearStreams: string[] } {
  const order: string[] = [];
  const tearStreams: string[] = [];
  const visited = new Set<string>();
  const visiting = new Set<string>();

  const graph = new Map<string, string[]>();
  for (const block of flowsheet.nodes) {
    if (block.type === 'TextBox' || block.type === 'Sink') continue;
    graph.set(block.id, []);
  }

  // Map from (from, to) to edge IDs for tear detection
  const edgeMap = new Map<string, string>();
  for (const stream of flowsheet.edges) {
    const from = stream.from.nodeId;
    const to = stream.to.nodeId;
    if (graph.has(from) && graph.has(to)) {
      graph.get(from)!.push(to);
      edgeMap.set(`${from}->${to}`, stream.id);
    }
  }

  function visit(blockId: string) {
    if (visited.has(blockId)) return;
    if (visiting.has(blockId)) {
      // Cycle detected - this edge is a tear stream
      return;
    }

    visiting.add(blockId);
    const neighbors = graph.get(blockId) || [];
    for (const neighbor of neighbors) {
      if (visiting.has(neighbor) && !visited.has(neighbor)) {
        // Back edge found - mark as tear stream
        const edgeId = edgeMap.get(`${blockId}->${neighbor}`);
        if (edgeId) tearStreams.push(edgeId);
      }
      visit(neighbor);
    }
    visiting.delete(blockId);
    visited.add(blockId);
    order.push(blockId);
  }

  for (const blockId of graph.keys()) {
    visit(blockId);
  }

  return { order: order.reverse(), tearStreams };
}

/**
 * Solve individual block
 */
function solveBlock(
  block: UnitOpNode,
  _project: JasperProject,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  results: Map<string, any>,
  pkg: PropertyPackage,
) {
  if (block.type === 'TextBox' || block.type === 'Sink') return;

  switch (block.type) {
    case 'Feed':
      break;
    case 'Flash':
    case 'Separator':
      solveFlash(block, flowsheet, streams, results, pkg);
      break;
    case 'Mixer':
      solveMixer(block, flowsheet, streams, results, pkg);
      break;
    case 'Splitter':
      solveSplitter(block, flowsheet, streams, results);
      break;
    case 'Pump':
      solvePump(block, flowsheet, streams, results, pkg);
      break;
    case 'Heater':
    case 'Cooler':
      solveHeater(block, flowsheet, streams, results, pkg);
      break;
    case 'Absorber':
      solveAbsorber(block, flowsheet, streams, results, pkg);
      break;
    case 'Stripper':
      solveStripper(block, flowsheet, streams, results, pkg);
      break;
    case 'HeatExchanger':
      solveHeatExchangerSimple(block, flowsheet, streams, results, pkg);
      break;
    case 'Compressor':
      solveCompressor(block, flowsheet, streams, results, pkg);
      break;
    case 'Valve':
      solveValve(block, flowsheet, streams, results);
      break;
    case 'DistillationColumn':
      solveDistillation(block, flowsheet, streams, results, pkg);
      break;
    case 'RCSTR':
    case 'RPfr':
    case 'RStoic':
    case 'REquil':
    case 'RYield':
    case 'RGibbs':
    case 'RBatch':
      solveReactor(block, _project, flowsheet, streams, results, pkg);
      break;
    default:
      passThrough(block, flowsheet, streams);
  }
}

// ============================================================================
// FLASH
// ============================================================================

function solveFlash(
  block: UnitOpNode,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  results: Map<string, any>,
  pkg: PropertyPackage,
) {
  const inletEdge = flowsheet.edges.find(e => e.to.nodeId === block.id);
  if (!inletEdge) throw new Error(`${block.name}: No inlet stream`);

  const inlet = streams.get(inletEdge.id);
  if (!inlet) throw new Error(`${block.name}: Inlet stream not solved`);

  const T_flash = block.params.T ? paramToKelvin(block.params.T, inlet.T) : inlet.T;
  const P_flash_bar = block.params.P ? paramToBar(block.params.P, inlet.P) : inlet.P;
  const P_flash_Pa = P_flash_bar * BAR_TO_PA;

  const components = Object.keys(inlet.composition);
  const flashResult = pkg.flash(inlet.composition, T_flash, P_flash_Pa, components);
  const V = Math.max(0, Math.min(1, flashResult.V));

  const vaporNorm = normalizeComposition(flashResult.y);
  const liquidNorm = normalizeComposition(flashResult.x);

  const outlets = flowsheet.edges.filter(e => e.from.nodeId === block.id);
  const vaporOutlet = outlets.find(e => e.from.portName?.includes('vapor') || e.from.portName?.includes('gas'));
  const liquidOutlet = outlets.find(e => e.from.portName?.includes('liquid') || e.from.portName?.includes('heavy'));

  if (vaporOutlet) {
    const H_v = pkg.mixtureEnthalpy(vaporNorm, T_flash, P_flash_Pa, 'V');
    streams.set(vaporOutlet.id, {
      id: vaporOutlet.id,
      name: vaporOutlet.name,
      T: T_flash,
      P: P_flash_bar,
      flow: inlet.flow * V,
      composition: vaporNorm,
      phase: 'V' as const,
      H: H_v,
    });
  }

  if (liquidOutlet) {
    const H_l = pkg.mixtureEnthalpy(liquidNorm, T_flash, P_flash_Pa, 'L');
    streams.set(liquidOutlet.id, {
      id: liquidOutlet.id,
      name: liquidOutlet.name,
      T: T_flash,
      P: P_flash_bar,
      flow: inlet.flow * (1 - V),
      composition: liquidNorm,
      phase: 'L',
      H: H_l,
    });
  }

  results.set(block.id, { vaporFraction: V, duty: 0 });
}

// ============================================================================
// MIXER
// ============================================================================

function solveMixer(
  block: UnitOpNode,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  results: Map<string, any>,
  pkg: PropertyPackage,
) {
  const inletEdges = flowsheet.edges.filter(e => e.to.nodeId === block.id);
  const inlets = inletEdges.map(e => streams.get(e.id)).filter(s => s !== undefined) as StreamState[];

  if (inlets.length === 0) throw new Error(`${block.name}: No inlet streams`);

  if (inlets.length === 1) {
    const outletEdge = flowsheet.edges.find(e => e.from.nodeId === block.id);
    if (outletEdge) streams.set(outletEdge.id, { ...inlets[0], id: outletEdge.id, name: outletEdge.name });
    return;
  }

  const totalFlow = inlets.reduce((sum, s) => sum + s.flow, 0);
  const P_out_bar = Math.min(...inlets.map(s => s.P));
  const P_out_Pa = P_out_bar * BAR_TO_PA;

  const composition: Record<string, number> = {};
  for (const comp of new Set(inlets.flatMap(s => Object.keys(s.composition)))) {
    composition[comp] = inlets.reduce((sum, s) => sum + (s.composition[comp] || 0) * s.flow, 0) / totalFlow;
  }
  const sum = Object.values(composition).reduce((a, b) => a + b, 0);
  if (Math.abs(sum - 1) > 0.01) {
    for (const c of Object.keys(composition)) composition[c] /= sum;
  }

  const H_mix = inlets.reduce((sum, s) => sum + s.flow * s.H, 0) / totalFlow;

  let T = inlets.reduce((sum, s) => sum + s.T * s.flow, 0) / totalFlow;
  for (let iter = 0; iter < 20; iter++) {
    const H_calc = pkg.mixtureEnthalpy(composition, T, P_out_Pa);
    const err = H_calc - H_mix;
    if (Math.abs(err) < 0.001) break;
    const dT = 0.1;
    const dHdT = (pkg.mixtureEnthalpy(composition, T + dT, P_out_Pa) - H_calc) / dT;
    if (Math.abs(dHdT) < 1e-10) break;
    T = T - err / dHdT;
    if (T < 100) T = 100;
    if (T > 1000) T = 1000;
  }

  const phase = determinePhase(composition, T, P_out_Pa);

  const outletEdge = flowsheet.edges.find(e => e.from.nodeId === block.id);
  if (!outletEdge) throw new Error(`${block.name}: No outlet stream`);

  streams.set(outletEdge.id, {
    id: outletEdge.id,
    name: outletEdge.name,
    T,
    P: P_out_bar,
    flow: totalFlow,
    composition,
    phase,
    H: H_mix,
  });

  results.set(block.id, { totalFlow, composition });
}

// ============================================================================
// SPLITTER
// ============================================================================

function solveSplitter(
  block: UnitOpNode,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  _results: Map<string, any>,
) {
  const inletEdge = flowsheet.edges.find(e => e.to.nodeId === block.id);
  if (!inletEdge) throw new Error(`${block.name}: No inlet stream`);

  const inlet = streams.get(inletEdge.id);
  if (!inlet) throw new Error(`${block.name}: Inlet not solved`);

  const outletEdges = flowsheet.edges.filter(e => e.from.nodeId === block.id);
  const n = outletEdges.length;
  if (n === 0) return;

  const splitRatio = getParam(block.params.splitRatio) ?? 0.5;
  const r = Math.max(0, Math.min(1, splitRatio));

  const fractions: number[] = n === 1 ? [1] : n === 2 ? [r, 1 - r] : [r, ...Array(n - 1).fill((1 - r) / (n - 1))];

  outletEdges.forEach((outlet, i) => {
    streams.set(outlet.id, {
      ...inlet,
      id: outlet.id,
      name: outlet.name,
      flow: inlet.flow * (fractions[i] ?? 1 / n),
    });
  });
}

// ============================================================================
// PUMP
// ============================================================================

function solvePump(
  block: UnitOpNode,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  results: Map<string, any>,
  pkg: PropertyPackage,
) {
  const inletEdge = flowsheet.edges.find(e => e.to.nodeId === block.id);
  const outletEdge = flowsheet.edges.find(e => e.from.nodeId === block.id);

  if (!inletEdge || !outletEdge) throw new Error(`${block.name}: Missing streams`);

  const inlet = streams.get(inletEdge.id);
  if (!inlet) throw new Error(`${block.name}: Inlet not solved`);

  const dP_bar = getParam(block.params.dP) ?? 5;
  if (dP_bar <= 0) throw new Error(`${block.name}: Pump dP must be > 0`);
  const P_out_bar = inlet.P + dP_bar;
  const dP_Pa = dP_bar * BAR_TO_PA;

  const P_in_Pa = inlet.P * BAR_TO_PA;
  const rho = pkg.liquidDensity(inlet.composition, inlet.T, P_in_Pa);

  let MW = 0;
  for (const [comp, frac] of Object.entries(inlet.composition)) {
    MW += frac * (COMPONENT_DATABASE[comp]?.MW ?? 30);
  }
  if (MW === 0) MW = 30;

  const volumetricFlow = (inlet.flow * MW) / (rho * 3600);
  const efficiency = getParam(block.params.efficiency) ?? 0.75;
  const actualPower = (volumetricFlow * dP_Pa) / 1000 / efficiency;

  streams.set(outletEdge.id, {
    ...inlet,
    id: outletEdge.id,
    name: outletEdge.name,
    P: P_out_bar,
    phase: 'L' as const,
  });

  results.set(block.id, { power: actualPower, dP: dP_bar });
}

// ============================================================================
// COMPRESSOR (Phase 4: Isentropic with entropy)
// ============================================================================

function solveCompressor(
  block: UnitOpNode,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  results: Map<string, any>,
  pkg: PropertyPackage,
) {
  const inletEdge = flowsheet.edges.find(e => e.to.nodeId === block.id);
  const outletEdge = flowsheet.edges.find(e => e.from.nodeId === block.id);

  if (!inletEdge || !outletEdge) throw new Error(`${block.name}: Missing streams`);

  const inlet = streams.get(inletEdge.id);
  if (!inlet) throw new Error(`${block.name}: Inlet not solved`);

  const outletP_bar = getParam(block.params.outletP) ?? inlet.P * (getParam(block.params.ratio) ?? 2);
  if (outletP_bar <= inlet.P) throw new Error(`${block.name}: Compressor outlet pressure must be > inlet`);

  const P_in_Pa = inlet.P * BAR_TO_PA;
  const P_out_Pa = outletP_bar * BAR_TO_PA;
  const efficiency = getParam(block.params.efficiency) ?? 0.75;

  // Isentropic compression: find T_out_s where S(T_out_s, P_out) = S(T_in, P_in)
  const S_in = pkg.mixtureEntropy(inlet.composition, inlet.T, P_in_Pa, 'V');
  const H_in = pkg.mixtureEnthalpy(inlet.composition, inlet.T, P_in_Pa, 'V');

  // Newton iteration for isentropic outlet temperature
  let T_s = inlet.T * Math.pow(outletP_bar / inlet.P, (1.4 - 1) / 1.4); // Ideal gas initial guess
  for (let iter = 0; iter < 30; iter++) {
    const S_s = pkg.mixtureEntropy(inlet.composition, T_s, P_out_Pa, 'V');
    const err = S_s - S_in;
    if (Math.abs(err) < 1e-6) break;
    const dT = 0.1;
    const dSdT = (pkg.mixtureEntropy(inlet.composition, T_s + dT, P_out_Pa, 'V') - S_s) / dT;
    if (Math.abs(dSdT) < 1e-15) break;
    T_s -= err / dSdT;
    T_s = Math.max(inlet.T, Math.min(T_s, 2000));
  }

  const H_out_s = pkg.mixtureEnthalpy(inlet.composition, T_s, P_out_Pa, 'V');
  const deltaH_s = H_out_s - H_in; // kJ/mol isentropic work
  const deltaH_actual = deltaH_s / efficiency; // kJ/mol actual work

  // Actual outlet temperature from actual enthalpy
  const H_out_actual = H_in + deltaH_actual;
  let T_out = T_s + (deltaH_actual - deltaH_s) / (idealGasCpMix(inlet.composition, T_s) / 1000);
  // Refine
  for (let iter = 0; iter < 20; iter++) {
    const H_calc = pkg.mixtureEnthalpy(inlet.composition, T_out, P_out_Pa, 'V');
    const err = H_calc - H_out_actual;
    if (Math.abs(err) < 0.001) break;
    const dT = 0.1;
    const dHdT = (pkg.mixtureEnthalpy(inlet.composition, T_out + dT, P_out_Pa, 'V') - H_calc) / dT;
    if (Math.abs(dHdT) < 1e-10) break;
    T_out -= err / dHdT;
    T_out = Math.max(inlet.T, Math.min(T_out, 2000));
  }

  const power = inlet.flow * deltaH_actual; // kJ/h

  streams.set(outletEdge.id, {
    ...inlet,
    id: outletEdge.id,
    name: outletEdge.name,
    T: T_out,
    P: outletP_bar,
    H: H_out_actual,
    phase: 'V' as const,
  });

  results.set(block.id, { power, outletP: outletP_bar, T_out, efficiency, isentropicT: T_s });
}

/** Average Cp for a mixture (J/mol/K) */
function idealGasCpMix(composition: Record<string, number>, T: number): number {
  let Cp = 0;
  for (const [name, frac] of Object.entries(composition)) {
    const comp = COMPONENT_DATABASE[name];
    if (comp) Cp += frac * idealGasCp(comp, T);
  }
  return Cp || 30; // fallback
}

// ============================================================================
// VALVE
// ============================================================================

function solveValve(
  block: UnitOpNode,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  results: Map<string, any>,
) {
  const inletEdge = flowsheet.edges.find(e => e.to.nodeId === block.id);
  const outletEdge = flowsheet.edges.find(e => e.from.nodeId === block.id);

  if (!inletEdge || !outletEdge) throw new Error(`${block.name}: Missing streams`);

  const inlet = streams.get(inletEdge.id);
  if (!inlet) throw new Error(`${block.name}: Inlet not solved`);

  const dP_bar = getParam(block.params.dP) ?? -0.5;
  const P_out_bar = inlet.P + dP_bar;
  if (P_out_bar <= 0) throw new Error(`${block.name}: Valve outlet pressure must be > 0`);

  streams.set(outletEdge.id, {
    ...inlet,
    id: outletEdge.id,
    name: outletEdge.name,
    P: P_out_bar,
  });

  results.set(block.id, { dP: dP_bar });
}

// ============================================================================
// HEATER / COOLER
// ============================================================================

function solveHeater(
  block: UnitOpNode,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  results: Map<string, any>,
  pkg: PropertyPackage,
) {
  const inletEdge = flowsheet.edges.find(e => e.to.nodeId === block.id);
  const outletEdge = flowsheet.edges.find(e => e.from.nodeId === block.id);

  if (!inletEdge || !outletEdge) throw new Error(`${block.name}: Missing streams`);

  const inlet = streams.get(inletEdge.id);
  if (!inlet) throw new Error(`${block.name}: Inlet not solved`);

  const T_out = block.params.outletT
    ? paramToKelvin(block.params.outletT, inlet.T)
    : inlet.T + (block.type === 'Heater' ? 50 : -50);

  const P_Pa = inlet.P * BAR_TO_PA;
  const H_in = inlet.H;
  const H_out = pkg.mixtureEnthalpy(inlet.composition, T_out, P_Pa);
  const duty = inlet.flow * (H_out - H_in);

  const phase = determinePhase(inlet.composition, T_out, P_Pa);

  streams.set(outletEdge.id, {
    ...inlet,
    id: outletEdge.id,
    name: outletEdge.name,
    T: T_out,
    H: H_out,
    phase,
  });

  results.set(block.id, { duty, T_out });
}

// ============================================================================
// DISTILLATION COLUMN (Phase 5: Fenske-Underwood-Gilliland)
// ============================================================================

function solveDistillation(
  block: UnitOpNode,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  results: Map<string, any>,
  pkg: PropertyPackage,
) {
  const inletEdge = flowsheet.edges.find(e => e.to.nodeId === block.id);
  if (!inletEdge) throw new Error(`${block.name}: No inlet stream`);

  const inlet = streams.get(inletEdge.id);
  if (!inlet) throw new Error(`${block.name}: Inlet stream not solved`);

  const components = Object.keys(inlet.composition);
  if (components.length < 2) {
    passThrough(block, flowsheet, streams);
    results.set(block.id, { error: 'Need at least 2 components' });
    return;
  }

  // Read parameters
  const lightKeyName = getParamString(block.params.lightKey) ?? components[0];
  const heavyKeyName = getParamString(block.params.heavyKey) ?? components[components.length - 1];
  const lkRecovery = getParam(block.params.lkRecovery) ?? 0.99;
  const hkRecovery = getParam(block.params.hkRecovery) ?? 0.01; // fraction of HK in distillate
  const RR = getParam(block.params.refluxRatio) ?? 1.5; // actual reflux ratio
  const P_bar = block.params.P ? paramToBar(block.params.P, inlet.P) : inlet.P;
  const P_Pa = P_bar * BAR_TO_PA;

  // K-values at feed conditions
  const K = pkg.calculateKValues(components, inlet.T, P_Pa);
  const K_lk = K[lightKeyName] ?? 2;
  const K_hk = K[heavyKeyName] ?? 0.5;
  const alpha_lk_hk = K_lk / K_hk; // relative volatility of LK to HK

  if (alpha_lk_hk <= 1.01) {
    // Can't separate
    passThrough(block, flowsheet, streams);
    results.set(block.id, { error: 'Relative volatility too close to 1' });
    return;
  }

  // Fenske: minimum stages
  const N_min = Math.log((lkRecovery / (1 - lkRecovery)) * ((1 - hkRecovery) / hkRecovery)) / Math.log(alpha_lk_hk);

  // Underwood: minimum reflux
  // For binary: R_min = (1/(alpha-1)) * (x_D/x_F - alpha*(1-x_D)/(1-x_F))
  // Simplified for multicomponent using feed composition
  const z_lk = inlet.composition[lightKeyName] ?? 0;
  const z_hk = inlet.composition[heavyKeyName] ?? 0;
  const x_D_lk = lkRecovery * z_lk / (lkRecovery * z_lk + hkRecovery * z_hk);
  const R_min = Math.max(0.1, (1 / (alpha_lk_hk - 1)) * (x_D_lk / z_lk - alpha_lk_hk * (1 - x_D_lk) / (1 - z_lk)));

  // Gilliland correlation for actual stages
  const X = (RR - R_min) / (RR + 1);
  const Y = 1 - Math.exp((1 + 54.4 * X) / (11 + 117.2 * X) * (X - 1) / Math.sqrt(X));
  const N_actual = Math.max(Math.ceil((N_min + Y) / (1 - Y)), 3);

  // Feed stage (Kirkbride)
  const N_feed = Math.round(N_actual / 2);

  // Material balance: compute distillate and bottoms compositions
  const F = inlet.flow;
  const distComp: Record<string, number> = {};
  const botComp: Record<string, number> = {};
  let D_flow = 0;
  let B_flow = 0;

  for (const comp of components) {
    const z_i = inlet.composition[comp] ?? 0;
    const F_i = z_i * F;

    // Relative volatility of comp to HK
    const K_i = K[comp] ?? 1;
    const alpha_i = K_i / K_hk;

    let d_i: number;
    if (comp === lightKeyName) {
      d_i = F_i * lkRecovery;
    } else if (comp === heavyKeyName) {
      d_i = F_i * hkRecovery;
    } else if (alpha_i > alpha_lk_hk) {
      // Lighter than LK - goes to distillate
      d_i = F_i * 0.999;
    } else if (alpha_i < 1) {
      // Heavier than HK - goes to bottoms
      d_i = F_i * 0.001;
    } else {
      // Distributed component - use Fenske with N_min stages
      const recovery = Math.pow(alpha_i, N_min) / (1 + Math.pow(alpha_i, N_min));
      d_i = F_i * recovery;
    }

    const b_i = F_i - d_i;
    distComp[comp] = d_i;
    botComp[comp] = b_i;
    D_flow += d_i;
    B_flow += b_i;
  }

  // Normalize to mole fractions
  for (const comp of components) {
    distComp[comp] = D_flow > 0 ? distComp[comp] / D_flow : 0;
    botComp[comp] = B_flow > 0 ? botComp[comp] / B_flow : 0;
  }

  // Condenser and reboiler duties (approximate)
  const Hvap_avg = 30; // kJ/mol rough estimate for typical organic
  const Q_condenser = -D_flow * (RR + 1) * Hvap_avg; // kJ/h (negative = cooling)
  const Q_reboiler = -Q_condenser + F * (pkg.mixtureEnthalpy(inlet.composition, inlet.T, P_Pa) -
    D_flow / F * pkg.mixtureEnthalpy(distComp, inlet.T - 10, P_Pa) -
    B_flow / F * pkg.mixtureEnthalpy(botComp, inlet.T + 10, P_Pa));

  // Set outlet streams
  const outlets = flowsheet.edges.filter(e => e.from.nodeId === block.id);
  const distOutlet = outlets.find(e =>
    e.from.portName?.includes('distillate') || e.from.portName?.includes('overhead') || e.from.portName?.includes('top')
  ) ?? outlets[0];
  const botOutlet = outlets.find(e =>
    e.from.portName?.includes('bottoms') || e.from.portName?.includes('bottom')
  ) ?? outlets[1];

  const T_top = inlet.T - 10; // approximate
  const T_bot = inlet.T + 10;

  if (distOutlet) {
    streams.set(distOutlet.id, {
      id: distOutlet.id,
      name: distOutlet.name,
      T: T_top,
      P: P_bar,
      flow: D_flow,
      composition: normalizeComposition(distComp),
      phase: 'L' as const,
      H: pkg.mixtureEnthalpy(normalizeComposition(distComp), T_top, P_Pa),
    });
  }

  if (botOutlet) {
    streams.set(botOutlet.id, {
      id: botOutlet.id,
      name: botOutlet.name,
      T: T_bot,
      P: P_bar,
      flow: B_flow,
      composition: normalizeComposition(botComp),
      phase: 'L' as const,
      H: pkg.mixtureEnthalpy(normalizeComposition(botComp), T_bot, P_Pa),
    });
  }

  results.set(block.id, {
    N_min,
    R_min,
    N_actual,
    N_feed,
    refluxRatio: RR,
    alpha_lk_hk,
    Q_condenser,
    Q_reboiler,
    D_flow,
    B_flow,
  });
}

// ============================================================================
// REACTOR (Phase 6: Heat of reaction, equilibrium)
// ============================================================================

function solveReactor(
  block: UnitOpNode,
  project: JasperProject,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  results: Map<string, any>,
  pkg: PropertyPackage,
) {
  const inletEdge = flowsheet.edges.find(e => e.to.nodeId === block.id);
  const outletEdges = flowsheet.edges.filter(e => e.from.nodeId === block.id);
  if (!inletEdge || outletEdges.length === 0) return;
  const inlet = streams.get(inletEdge.id);
  if (!inlet) return;

  const reactions = project.reactions ?? [];
  if (reactions.length === 0) {
    for (const oe of outletEdges) {
      streams.set(oe.id, { ...inlet, id: oe.id, name: oe.name });
    }
    results.set(block.id, { duty: 0 });
    return;
  }

  // Reactor mode: adiabatic or isothermal
  const mode = getParamString(block.params.mode) ?? 'adiabatic';

  // Work with molar flows (kmol/h per component)
  const molarFlows: Record<string, number> = {};
  for (const [comp, frac] of Object.entries(inlet.composition)) {
    molarFlows[comp] = frac * inlet.flow;
  }

  const conversionParam = block.params?.conversion;
  const conversion = conversionParam?.kind === 'number'
    ? conversionParam.x
    : conversionParam?.kind === 'quantity'
    ? conversionParam.q.value
    : 0.90;

  let totalQrxn = 0; // kJ/h total heat released by reactions

  for (const rxn of reactions) {
    const stoich = rxn.stoichiometry;
    if (!stoich || Object.keys(stoich).length === 0) continue;

    if (rxn.type === 'equilibrium' && (block.type === 'REquil' || block.type === 'RGibbs')) {
      // Equilibrium reactor: compute K_eq from deltaG, solve for extent
      const deltaH = heatOfReaction(stoich, inlet.T); // kJ/mol
      // Approximate deltaG ≈ deltaH (ignoring entropy for now, acceptable for student use)
      // K_eq = exp(-deltaG / (R*T))  — use deltaH as proxy
      const K_eq = rxn.equilibrium_constant ?? Math.exp(-deltaH * 1000 / (R * inlet.T));

      // For A -> B type: K_eq = [B]/[A] = (n_B/V)/(n_A/V) = n_B/n_A
      // Find extent that satisfies K_eq
      let limitingComp: string | null = null;
      let maxExtent = Infinity;
      for (const [comp, coeff] of Object.entries(stoich)) {
        if (coeff < 0) {
          const available = molarFlows[comp] ?? 0;
          const extent = available / Math.abs(coeff);
          if (extent < maxExtent) { maxExtent = extent; limitingComp = comp; }
        }
      }
      if (!limitingComp || maxExtent <= 0) continue;

      // Bisection for equilibrium extent
      let lo = 0, hi = maxExtent * 0.999;
      for (let iter = 0; iter < 50; iter++) {
        const xi = (lo + hi) / 2;
        let Qp = 1; // product of products^nu
        let Qr = 1; // product of reactants^|nu|
        for (const [comp, coeff] of Object.entries(stoich)) {
          const n = Math.max(1e-10, (molarFlows[comp] ?? 0) + coeff * xi);
          if (coeff > 0) Qp *= Math.pow(n, coeff);
          else Qr *= Math.pow(n, -coeff);
        }
        const Q = Qp / Qr;
        if (Q < K_eq) lo = xi; else hi = xi;
        if (Math.abs(hi - lo) / (maxExtent + 1e-10) < 1e-6) break;
      }
      const xi = (lo + hi) / 2;
      for (const [comp, coeff] of Object.entries(stoich)) {
        molarFlows[comp] = Math.max(0, (molarFlows[comp] ?? 0) + coeff * xi);
      }
      totalQrxn += deltaH * xi; // kJ/h (xi in kmol/h)
      continue;
    }

    // Rate reaction with conversion
    let limitingComp: string | null = null;
    let maxExtent = Infinity;
    for (const [comp, coeff] of Object.entries(stoich)) {
      if (coeff < 0) {
        const available = molarFlows[comp] ?? 0;
        const extent = available / Math.abs(coeff);
        if (extent < maxExtent) { maxExtent = extent; limitingComp = comp; }
      }
    }
    if (!limitingComp || maxExtent <= 0) continue;

    const actualExtent = maxExtent * Math.min(1, Math.max(0, conversion));
    for (const [comp, coeff] of Object.entries(stoich)) {
      molarFlows[comp] = Math.max(0, (molarFlows[comp] ?? 0) + coeff * actualExtent);
    }

    const deltaH = heatOfReaction(stoich, inlet.T);
    totalQrxn += deltaH * actualExtent;
  }

  // Convert back to mole fractions
  const totalFlow = Object.values(molarFlows).reduce((s, v) => s + v, 0);
  const outComp: Record<string, number> = {};
  for (const [comp, flow] of Object.entries(molarFlows)) {
    outComp[comp] = totalFlow > 0 ? flow / totalFlow : 0;
  }

  // Temperature calculation
  let outletT: number;
  let duty: number;

  if (mode === 'isothermal') {
    outletT = inlet.T;
    duty = -totalQrxn; // Heat removal needed (kJ/h)
  } else {
    // Adiabatic: Q_rxn + F*Cp*(T_out - T_in) = 0
    // T_out = T_in - Q_rxn / (F * Cp_mix)
    const Cp_mix = idealGasCpMix(inlet.composition, inlet.T); // J/mol/K
    const F_mol_per_h = inlet.flow; // kmol/h
    if (Math.abs(Cp_mix) > 1e-10 && F_mol_per_h > 0) {
      // totalQrxn is kJ/h, Cp is J/mol/K, flow is kmol/h
      // deltaT = -totalQrxn * 1000 / (F_mol_per_h * 1000 * Cp_mix)
      //        = -totalQrxn / (F_mol_per_h * Cp_mix)
      outletT = inlet.T - totalQrxn * 1000 / (F_mol_per_h * 1000 * Cp_mix);
    } else {
      outletT = inlet.T;
    }
    outletT = Math.max(200, Math.min(outletT, 3000));
    duty = 0; // adiabatic
  }

  const P_Pa = inlet.P * BAR_TO_PA;
  const H_out = pkg.mixtureEnthalpy(normalizeComposition(outComp), outletT, P_Pa);

  for (const oe of outletEdges) {
    streams.set(oe.id, {
      id: oe.id,
      name: oe.name,
      T: outletT,
      P: inlet.P,
      flow: totalFlow,
      composition: normalizeComposition(outComp),
      phase: inlet.phase,
      H: H_out,
    });
  }

  results.set(block.id, { duty, conversion, Q_rxn: totalQrxn, T_out: outletT });
}

// ============================================================================
// ABSORBER (Phase 8: Kremser equation)
// ============================================================================

function solveAbsorber(
  block: UnitOpNode,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  results: Map<string, any>,
  pkg: PropertyPackage,
) {
  const gasInlet = flowsheet.edges.find(e => e.to.nodeId === block.id && e.to.portName === 'gas-in');
  const liquidInlet = flowsheet.edges.find(e => e.to.nodeId === block.id && e.to.portName === 'liquid-in');

  if (!gasInlet || !liquidInlet) {
    console.warn(`${block.name}: Missing gas or liquid inlet`);
    return;
  }

  const gasIn = streams.get(gasInlet.id);
  const liquidIn = streams.get(liquidInlet.id);

  if (!gasIn || !liquidIn) {
    console.warn(`${block.name}: Inlet streams not solved`);
    return;
  }

  // Kremser equation for each solute component
  const N_stages = getParam(block.params.stages) ?? 10;
  const P_Pa = gasIn.P * BAR_TO_PA;
  const T_avg = (gasIn.T + liquidIn.T) / 2;

  // K-values at average conditions for equilibrium slope m
  const gasComponents = Object.keys(gasIn.composition);
  const K = pkg.calculateKValues(gasComponents, T_avg, P_Pa);

  const G = gasIn.flow; // kmol/h gas
  const L = liquidIn.flow; // kmol/h liquid

  const gasOutComp: Record<string, number> = {};
  const liquidOutComp: Record<string, number> = { ...liquidIn.composition };
  let totalGasOut = 0;
  let totalLiqOut = liquidIn.flow;
  let totalAbsorbed = 0;

  for (const comp of gasComponents) {
    const y_in = gasIn.composition[comp] ?? 0;
    const m = K[comp] ?? 1; // equilibrium slope (K-value)
    const A = L / (m * G); // absorption factor

    let fraction_absorbed: number;
    if (Math.abs(A - 1) < 0.001) {
      // A ≈ 1: special case
      fraction_absorbed = N_stages / (N_stages + 1);
    } else if (A > 0.01) {
      // Kremser: fraction absorbed = (A^(N+1) - A) / (A^(N+1) - 1)
      const AN1 = Math.pow(A, N_stages + 1);
      fraction_absorbed = (AN1 - A) / (AN1 - 1);
    } else {
      // Very low absorption factor
      fraction_absorbed = 0;
    }

    // Solutes with high A get absorbed; inerts (very high K) pass through
    const comp_flow_in = y_in * G;
    const absorbed = comp_flow_in * Math.min(fraction_absorbed, 0.9999);

    gasOutComp[comp] = comp_flow_in - absorbed;
    totalGasOut += comp_flow_in - absorbed;
    totalAbsorbed += absorbed;

    // Add to liquid
    liquidOutComp[comp] = (liquidOutComp[comp] ?? 0) * liquidIn.flow + absorbed;
  }
  totalLiqOut = liquidIn.flow + totalAbsorbed;

  // Normalize
  for (const comp of Object.keys(gasOutComp)) {
    gasOutComp[comp] = totalGasOut > 0 ? gasOutComp[comp] / totalGasOut : 0;
  }
  for (const comp of Object.keys(liquidOutComp)) {
    liquidOutComp[comp] = totalLiqOut > 0 ? liquidOutComp[comp] / totalLiqOut : 0;
  }

  const gasOutlet = flowsheet.edges.find(e => e.from.nodeId === block.id && e.from.portName === 'gas-out');
  if (gasOutlet) {
    streams.set(gasOutlet.id, {
      id: gasOutlet.id,
      name: gasOutlet.name,
      T: gasIn.T + 5,
      P: gasIn.P - 0.05,
      flow: totalGasOut,
      composition: normalizeComposition(gasOutComp),
      phase: 'V' as const,
      H: pkg.mixtureEnthalpy(normalizeComposition(gasOutComp), gasIn.T + 5, P_Pa),
    });
  }

  const liquidOutlet = flowsheet.edges.find(e => e.from.nodeId === block.id && e.from.portName === 'liquid-out');
  if (liquidOutlet) {
    streams.set(liquidOutlet.id, {
      id: liquidOutlet.id,
      name: liquidOutlet.name,
      T: liquidIn.T + 10,
      P: liquidIn.P,
      flow: totalLiqOut,
      composition: normalizeComposition(liquidOutComp),
      phase: 'L' as const,
      H: pkg.mixtureEnthalpy(normalizeComposition(liquidOutComp), liquidIn.T + 10, P_Pa),
    });
  }

  results.set(block.id, { N_stages, totalAbsorbed, L_over_G: L / G });
}

// ============================================================================
// STRIPPER (Phase 8: Kremser equation)
// ============================================================================

function solveStripper(
  block: UnitOpNode,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  results: Map<string, any>,
  pkg: PropertyPackage,
) {
  const feedInlet = flowsheet.edges.find(e => e.to.nodeId === block.id && e.to.portName === 'feed');

  if (!feedInlet) {
    console.warn(`${block.name}: No feed inlet`);
    return;
  }

  const feed = streams.get(feedInlet.id);
  if (!feed) {
    console.warn(`${block.name}: Feed stream not solved`);
    return;
  }

  const N_stages = getParam(block.params.stages) ?? 8;
  const P_bar = block.params.P ? paramToBar(block.params.P, feed.P) : feed.P;
  const P_Pa = P_bar * BAR_TO_PA;
  const T_strip = feed.T + 80; // Reboiler temperature

  // K-values at stripper conditions
  const components = Object.keys(feed.composition);
  const K = pkg.calculateKValues(components, T_strip, P_Pa);

  // Stripping: reverse of absorption
  // S_i = m_i * V / L (stripping factor)
  // For a stripper, we generate vapor from liquid
  const V_estimate = feed.flow * 0.1; // assume 10% vaporization as steam
  const L = feed.flow;

  const overheadComp: Record<string, number> = {};
  const bottomsComp: Record<string, number> = {};
  let totalOverhead = 0;
  let totalBottoms = 0;

  for (const comp of components) {
    const x_in = feed.composition[comp] ?? 0;
    const comp_flow = x_in * L;
    const m = K[comp] ?? 1;
    const S = m * V_estimate / L; // stripping factor

    let fraction_stripped: number;
    if (Math.abs(S - 1) < 0.001) {
      fraction_stripped = N_stages / (N_stages + 1);
    } else if (S > 0.01) {
      const SN1 = Math.pow(S, N_stages + 1);
      fraction_stripped = (SN1 - S) / (SN1 - 1);
    } else {
      fraction_stripped = 0;
    }

    // Only strip volatile components (high K)
    const stripped = comp_flow * Math.min(fraction_stripped, 0.999);
    overheadComp[comp] = stripped;
    bottomsComp[comp] = comp_flow - stripped;
    totalOverhead += stripped;
    totalBottoms += comp_flow - stripped;
  }

  // Normalize
  for (const comp of components) {
    overheadComp[comp] = totalOverhead > 0 ? overheadComp[comp] / totalOverhead : 0;
    bottomsComp[comp] = totalBottoms > 0 ? bottomsComp[comp] / totalBottoms : 0;
  }

  const overheadOutlet = flowsheet.edges.find(e => e.from.nodeId === block.id && e.from.portName === 'overhead');
  if (overheadOutlet) {
    streams.set(overheadOutlet.id, {
      id: overheadOutlet.id,
      name: overheadOutlet.name,
      T: T_strip,
      P: P_bar,
      flow: totalOverhead,
      composition: normalizeComposition(overheadComp),
      phase: 'V' as const,
      H: pkg.mixtureEnthalpy(normalizeComposition(overheadComp), T_strip, P_Pa),
    });
  }

  const bottomsOutlet = flowsheet.edges.find(e => e.from.nodeId === block.id && e.from.portName === 'bottoms');
  if (bottomsOutlet) {
    streams.set(bottomsOutlet.id, {
      id: bottomsOutlet.id,
      name: bottomsOutlet.name,
      T: T_strip - 10,
      P: P_bar,
      flow: totalBottoms,
      composition: normalizeComposition(bottomsComp),
      phase: 'L' as const,
      H: pkg.mixtureEnthalpy(normalizeComposition(bottomsComp), T_strip - 10, P_Pa),
    });
  }

  results.set(block.id, { N_stages, totalStripped: totalOverhead });
}

// ============================================================================
// HEAT EXCHANGER
// ============================================================================

function solveHeatExchangerSimple(
  block: UnitOpNode,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  results: Map<string, any>,
  pkg: PropertyPackage,
) {
  const hotInlet = flowsheet.edges.find(e => e.to.nodeId === block.id && e.to.portName === 'in');
  const hotOutlet = flowsheet.edges.find(e => e.from.nodeId === block.id && e.from.portName === 'out');
  const coldInlet = flowsheet.edges.find(e => e.to.nodeId === block.id && e.to.portName === 'cold-in');
  const coldOutlet = flowsheet.edges.find(e => e.from.nodeId === block.id && e.from.portName === 'cold-out');

  if (!hotInlet || !hotOutlet || !coldInlet || !coldOutlet) {
    console.warn(`${block.name}: Missing HX inlets/outlets`);
    return;
  }

  const hotIn = streams.get(hotInlet.id);
  const coldIn = streams.get(coldInlet.id);

  if (!hotIn || !coldIn) {
    console.warn(`${block.name}: Inlet streams not solved`);
    return;
  }

  const effectiveness = 0.80;
  const deltaT = (hotIn.T - coldIn.T) * effectiveness;

  const T_hot_out = hotIn.T - deltaT;
  const T_cold_out = coldIn.T + deltaT;
  const P_hot_Pa = hotIn.P * BAR_TO_PA;
  const P_cold_Pa = coldIn.P * BAR_TO_PA;

  streams.set(hotOutlet.id, {
    ...hotIn,
    id: hotOutlet.id,
    name: hotOutlet.name,
    T: T_hot_out,
    H: pkg.mixtureEnthalpy(hotIn.composition, T_hot_out, P_hot_Pa),
  });

  streams.set(coldOutlet.id, {
    ...coldIn,
    id: coldOutlet.id,
    name: coldOutlet.name,
    T: T_cold_out,
    H: pkg.mixtureEnthalpy(coldIn.composition, T_cold_out, P_cold_Pa),
  });

  const duty = hotIn.flow * (hotIn.H - pkg.mixtureEnthalpy(hotIn.composition, T_hot_out, P_hot_Pa));
  results.set(block.id, { effectiveness, duty });
}

// ============================================================================
// PASS THROUGH
// ============================================================================

function passThrough(
  block: UnitOpNode,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
) {
  const inletEdge = flowsheet.edges.find(e => e.to.nodeId === block.id);
  const outletEdges = flowsheet.edges.filter(e => e.from.nodeId === block.id);

  if (!inletEdge || outletEdges.length === 0) return;

  const inlet = streams.get(inletEdge.id);
  if (!inlet) return;

  for (const outlet of outletEdges) {
    streams.set(outlet.id, {
      ...inlet,
      id: outlet.id,
      name: outlet.name,
    });
  }
}

// ============================================================================
// UNIT CONVERSION HELPERS
// ============================================================================

function convertTemperature(value: number, unit: string): number {
  switch (unit) {
    case 'K': return value;
    case 'C': return value + 273.15;
    case 'F': return (value - 32) * 5/9 + 273.15;
    default: return value;
  }
}

function convertPressure(value: number, unit: string): number {
  switch (unit) {
    case 'bar': return value;
    case 'Pa': return value / 1e5;
    case 'psi': return value * 0.0689476;
    default: return value;
  }
}
