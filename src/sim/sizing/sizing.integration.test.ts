/**
 * S2 integration: prove the sizing layer runs end-to-end on the *real* Quick
 * engine. solveFlowsheet must enrich each stream with density + vaporFraction,
 * and sizeFlowsheet must turn the standardized result into per-unit sizes whose
 * basis matches the cost DB (power / heat_duty / volume). This is the WIRING
 * test; the exact-math assertions live in sizing.test.ts.
 */
import { describe, expect, it } from 'vitest';
import { solveFlowsheet } from '../solver/blockSolver';
import { sizeFlowsheet } from './index';
import type { Component, JasperProject, StreamEdge, UnitOpNode } from '../../core/schema';

function buildProject(components: Component[], nodes: UnitOpNode[], edges: StreamEdge[]): JasperProject {
  return {
    projectId: 'sizing-int',
    name: 'Sizing integration',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    thermodynamics: { propertyMethod: 'Ideal' },
    components,
    flowsheet: { nodes, edges },
    specs: { specs: [] },
    constraints: { constraints: [] },
    objective: { metric: 'steam', sense: 'min' },
    status: 'draft',
  } as JasperProject;
}

const sink = (id: string): UnitOpNode => ({ id, type: 'Sink', name: id, params: {}, ports: [] });
const water: Component = { id: 'water', name: 'Water', formula: 'H2O' };

/** A standardized run as the engine assembles it for the sizing bridge. */
function runFor(project: JasperProject) {
  const res = solveFlowsheet(project);
  expect(res.converged).toBe(true);
  const rawOutputs = {
    streams: Array.from(res.streams.values()),
    blockResults: Object.fromEntries(res.blockResults),
  };
  return { res, rawOutputs };
}

describe('S2 — sizing on real Quick-engine output', () => {
  it('enriches solved streams with density + vapor fraction', () => {
    const project = buildProject(
      [water],
      [
        {
          id: 'feed', type: 'Feed', name: 'Feed', ports: [], params: {
            T: { kind: 'quantity', q: { value: 25, unit: 'C' } },
            P: { kind: 'quantity', q: { value: 1, unit: 'bar' } },
            flow: { kind: 'number', x: 100 },
            composition: { kind: 'composition', comp: { water: 1.0 } },
          },
        },
        sink('out'),
      ],
      [{ id: 'e1', name: 'f', from: { nodeId: 'feed', portName: 'out' }, to: { nodeId: 'out', portName: 'in' } }],
    );
    const { res } = runFor(project);
    const s = res.streams.get('e1')!;
    expect(s.density).toBeGreaterThan(0);          // liquid water density populated
    expect(s.vaporFraction).toBeLessThan(0.5);     // it's a liquid
  });

  it('sizes a Pump by power (basis = power, from sim work)', () => {
    const project = buildProject(
      [water],
      [
        {
          id: 'feed', type: 'Feed', name: 'Feed', ports: [], params: {
            T: { kind: 'quantity', q: { value: 25, unit: 'C' } },
            P: { kind: 'quantity', q: { value: 1, unit: 'bar' } },
            flow: { kind: 'number', x: 100 },
            composition: { kind: 'composition', comp: { water: 1.0 } },
          },
        },
        { id: 'pmp', type: 'Pump', name: 'Pump', ports: [], params: { dP: { kind: 'number', x: 5 } } },
        sink('out'),
      ],
      [
        { id: 'e1', name: 'f', from: { nodeId: 'feed', portName: 'out' }, to: { nodeId: 'pmp', portName: 'in' } },
        { id: 'e2', name: 'o', from: { nodeId: 'pmp', portName: 'out' }, to: { nodeId: 'out', portName: 'in' } },
      ],
    );
    const { res, rawOutputs } = runFor(project);
    const sizes = sizeFlowsheet(project.flowsheet, { rawOutputs });
    const pump = sizes.get('pmp')!;
    expect(pump.sizeBasis).toBe('power');
    expect(pump.sizes.power).toBeCloseTo(res.blockResults.get('pmp')!.power, 6);
  });

  it('sizes a Heater by heat_duty (basis = heat_duty, from sim duty)', () => {
    const project = buildProject(
      [water],
      [
        {
          id: 'feed', type: 'Feed', name: 'Feed', ports: [], params: {
            T: { kind: 'quantity', q: { value: 25, unit: 'C' } },
            P: { kind: 'quantity', q: { value: 2, unit: 'bar' } },
            flow: { kind: 'number', x: 100 },
            composition: { kind: 'composition', comp: { water: 1.0 } },
          },
        },
        { id: 'htr', type: 'Heater', name: 'Heater', ports: [], params: { outletT: { kind: 'quantity', q: { value: 90, unit: 'C' } } } },
        sink('out'),
      ],
      [
        { id: 'e1', name: 'f', from: { nodeId: 'feed', portName: 'out' }, to: { nodeId: 'htr', portName: 'in' } },
        { id: 'e2', name: 'o', from: { nodeId: 'htr', portName: 'out' }, to: { nodeId: 'out', portName: 'in' } },
      ],
    );
    const { res, rawOutputs } = runFor(project);
    const sizes = sizeFlowsheet(project.flowsheet, { rawOutputs });
    const htr = sizes.get('htr')!;
    expect(htr.sizeBasis).toBe('heat_duty');
    expect(htr.sizes.heat_duty).toBeCloseTo(Math.abs(res.blockResults.get('htr')!.duty), 6);
  });

  it('sizes a Flash drum by volume, driven by enriched liquid density', () => {
    const project = buildProject(
      [water, { id: 'n2', name: 'Nitrogen', formula: 'N2' }],
      [
        {
          id: 'feed', type: 'Feed', name: 'Feed', ports: [], params: {
            T: { kind: 'quantity', q: { value: 25, unit: 'C' } },
            P: { kind: 'quantity', q: { value: 1, unit: 'bar' } },
            flow: { kind: 'number', x: 100 },
            composition: { kind: 'composition', comp: { water: 0.6, n2: 0.4 } },
          },
        },
        { id: 'flsh', type: 'Flash', name: 'Flash', ports: [], params: {} },
        sink('v'), sink('l'),
      ],
      [
        { id: 'e1', name: 'f', from: { nodeId: 'feed', portName: 'out' }, to: { nodeId: 'flsh', portName: 'in' } },
        { id: 'ev', name: 'v', from: { nodeId: 'flsh', portName: 'vapor' }, to: { nodeId: 'v', portName: 'in' } },
        { id: 'el', name: 'l', from: { nodeId: 'flsh', portName: 'liquid' }, to: { nodeId: 'l', portName: 'in' } },
      ],
    );
    const { rawOutputs } = runFor(project);
    const sizes = sizeFlowsheet(project.flowsheet, { rawOutputs });
    const flash = sizes.get('flsh')!;
    expect(flash.sizeBasis).toBe('volume');
    expect(flash.sizes.volume!).toBeGreaterThan(0);
    expect(flash.sizes.diameter!).toBeGreaterThan(0);
    expect(flash.inRange).toBe(true);
  });
});
