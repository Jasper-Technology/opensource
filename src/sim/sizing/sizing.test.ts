import { describe, expect, it } from 'vitest';
import {
  diameterFromVapor, hxArea, lmtd, mixtureMW, soudersBrownVelocity,
  trayFloodVelocity, volFlowM3s,
} from './correlations';
import { sizeFlowsheet, sizeUnit } from './index';
import type { SizedStream, UnitSizingInput } from './types';

// --- pure correlations (exact) -------------------------------------------- //
describe('correlations', () => {
  it('mixtureMW from composition', () => {
    // 50/50 H2 (2.016) / methane (16.043) → ~9.03
    expect(mixtureMW({ H2: 0.5, CH4: 0.5 })).toBeCloseTo(9.03, 1);
  });

  it('LMTD', () => {
    // hot 400→350, cold 300→320: dt1=80, dt2=50 → (80-50)/ln(80/50)=63.83
    expect(lmtd(400, 350, 300, 320)).toBeCloseTo(63.83, 1);
  });

  it('HX area = Q/(U·LMTD)', () => {
    // 1000 kW, U=600, LMTD=38 → 1e6/(600·38)=43.86 m²
    expect(hxArea(1000, 600, 38)).toBeCloseTo(43.86, 1);
  });

  it('Souders-Brown velocity', () => {
    // K=0.107, rhoL=800, rhoV=2 → 0.107·sqrt(399)=2.137 m/s
    expect(soudersBrownVelocity(800, 2, 0.107)).toBeCloseTo(2.137, 2);
  });

  it('diameter from vapor flow', () => {
    // 1 m³/s at 2 m/s → A=0.5, D=sqrt(2/π)=0.7979
    expect(diameterFromVapor(1, 2)).toBeCloseTo(0.798, 2);
  });

  it('tray flooding velocity (Towler 17.34)', () => {
    // lt=0.6 → k=0.0534; ·sqrt(399)=1.066 m/s
    expect(trayFloodVelocity(0.6, 800, 2)).toBeCloseTo(1.066, 2);
  });

  it('volumetric flow', () => {
    // 3600 kmol/h, MW 50, density 800 → mass 50 kg/s, vol 0.0625 m³/s
    expect(volFlowM3s(3600, 50, 800)).toBeCloseTo(0.0625, 4);
  });
});

// --- dispatcher ----------------------------------------------------------- //
const liqIn = (extra?: Partial<SizedStream>): SizedStream => ({
  id: 's1', T: 350, P: 5, flowMol: 3600, density: 800, vaporFraction: 0,
  composition: { CH4: 1 }, phase: 'L', ...extra,
});

describe('sizeUnit dispatch', () => {
  it('power from work (pump)', () => {
    const r = sizeUnit({ unitId: 'p', unitType: 'Pump', work: 50, inlets: [], outlets: [] });
    expect(r.sizeBasis).toBe('power');
    expect(r.sizes.power).toBe(50);
  });

  it('heat_duty (Heater→fired heater)', () => {
    const r = sizeUnit({ unitId: 'h', unitType: 'Heater', duty: 2000, inlets: [liqIn()], outlets: [liqIn({ T: 450 })] });
    expect(r.sizeBasis).toBe('heat_duty');
    expect(r.sizes.heat_duty).toBe(2000);
  });

  it('area (Cooler vs cooling water)', () => {
    const r = sizeUnit({
      unitId: 'c', unitType: 'Cooler', duty: -1000,
      inlets: [liqIn({ T: 400 })], outlets: [liqIn({ T: 320 })],
    });
    expect(r.sizeBasis).toBe('area');
    expect(r.sizes.area!).toBeGreaterThan(0);
    expect(r.assumptions.join(' ')).toContain('cooling water');
  });

  it('volume Souders-Brown (Flash separator)', () => {
    const r = sizeUnit({
      unitId: 'f', unitType: 'Flash', inlets: [liqIn({ vaporFraction: 0.5 })],
      outlets: [
        { id: 'v', T: 350, P: 5, flowMol: 1800, density: 5, vaporFraction: 1, phase: 'V', composition: { CH4: 1 } },
        { id: 'l', T: 350, P: 5, flowMol: 1800, density: 800, vaporFraction: 0, phase: 'L', composition: { CH4: 1 } },
      ],
    });
    expect(r.sizeBasis).toBe('volume');
    expect(r.sizes.diameter!).toBeGreaterThan(0);
    expect(r.method).toBe('Souders-Brown');
  });

  it('volume residence (reactor)', () => {
    const r = sizeUnit({ unitId: 'r', unitType: 'RCSTR', inlets: [liqIn()], outlets: [liqIn()] });
    expect(r.sizeBasis).toBe('volume');
    expect(r.sizes.volume!).toBeGreaterThan(0);
    expect(r.assumptions.join(' ')).toContain('residence');
  });

  it('volume flooding (distillation column)', () => {
    const r = sizeUnit({
      unitId: 'd', unitType: 'DistillationColumn', nStages: 20, refluxRatio: 1.5,
      inlets: [liqIn()],
      outlets: [
        { id: 'ov', T: 340, P: 2, flowMol: 1000, density: 4, vaporFraction: 1, phase: 'V', composition: { CH4: 1 } },
        { id: 'bl', T: 380, P: 2, flowMol: 2600, density: 750, vaporFraction: 0, phase: 'L', composition: { CH4: 1 } },
      ],
    });
    expect(r.sizes.diameter!).toBeGreaterThan(0);
    expect(r.sizes.nStages).toBe(20);
    expect(r.method).toContain('flooding');
  });

  it('connector → none', () => {
    expect(sizeUnit({ unitId: 'm', unitType: 'Mixer', inlets: [], outlets: [] }).sizeBasis).toBe('none');
  });

  it('missing inputs → flagged, never fabricated', () => {
    const r = sizeUnit({ unitId: 'p', unitType: 'Pump', inlets: [], outlets: [] });
    expect(r.inRange).toBe(false);
    expect(r.note).toBeTruthy();
    expect(r.sizes.power).toBeUndefined();
  });
});

describe('sizeFlowsheet bridge', () => {
  it('sizes a unit from a standardized run', () => {
    const graph = {
      nodes: [{ id: 'P1', type: 'Pump', name: 'P1', params: {}, ports: [] }],
      edges: [
        { id: 'e1', name: 'e1', from: { nodeId: 'F', portName: 'out' }, to: { nodeId: 'P1', portName: 'in' } },
        { id: 'e2', name: 'e2', from: { nodeId: 'P1', portName: 'out' }, to: { nodeId: 'S', portName: 'in' } },
      ],
    } as unknown as Parameters<typeof sizeFlowsheet>[0];
    const run = { rawOutputs: { blockResults: { P1: { power: 42 } }, streams: [] } };
    const sizes = sizeFlowsheet(graph, run);
    expect(sizes.get('P1')!.sizes.power).toBe(42);
  });
});
