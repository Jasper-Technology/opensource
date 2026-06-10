/**
 * S5 — agent custom-sizing layer: the sandboxed evaluator and the CustomUnit
 * dispatch (formula → custom, inherit → baseType built-in, unsafe → rejected).
 */
import { describe, expect, it } from 'vitest';
import { safeEval } from './safeEval';
import { sizeUnit } from './index';
import type { SizedStream, UnitSizingInput } from './types';
import type { CustomSizingSpec } from '../../core/schema';

const feed = (extra?: Partial<SizedStream>): SizedStream => ({
  id: 's1', T: 350, P: 5, flowMol: 3600, density: 800, vaporFraction: 0,
  composition: { CH4: 1 }, phase: 'L', ...extra,
});

const custom = (sizing: CustomSizingSpec): UnitSizingInput => ({
  unitId: 'cu', unitType: 'CustomUnit', baseType: 'RCSTR',
  inlets: [feed()], outlets: [feed()], customSizing: sizing,
});

// --- safe evaluator -------------------------------------------------------- //
describe('safeEval', () => {
  it('arithmetic + precedence', () => {
    expect(safeEval('2 + 3 * 4', {})).toBe(14);
    expect(safeEval('(2 + 3) * 4', {})).toBe(20);
    expect(safeEval('2 ^ 3 ^ 2', {})).toBe(512); // right-associative
    expect(safeEval('-2 ^ 2', {})).toBe(4);       // unary binds: (-2)^2
  });

  it('variables + whitelisted functions + constants', () => {
    expect(safeEval('flow_vol * tau', { flow_vol: 0.02, tau: 3600 })).toBeCloseTo(72, 5);
    expect(safeEval('sqrt(flow / (pi * u))', { flow: 4, u: 1 })).toBeCloseTo(Math.sqrt(4 / Math.PI), 6);
    expect(safeEval('max(a, b)', { a: 3, b: 7 })).toBe(7);
  });

  it('rejects unknown variables and functions', () => {
    expect(() => safeEval('foo + 1', {})).toThrow(/unknown variable/);
    expect(() => safeEval('alert(1)', {})).toThrow(/unknown function/);
  });

  it('rejects code-injection attempts (no eval semantics)', () => {
    expect(() => safeEval('a.b', { a: 1 })).toThrow();             // property access
    expect(() => safeEval('constructor', {})).toThrow();           // unknown variable
    expect(() => safeEval('this', {})).toThrow();
    expect(() => safeEval('1; drop', {})).toThrow();
    expect(() => safeEval('process.exit(1)', {})).toThrow();
    expect(() => safeEval('flow_vol =', { flow_vol: 1 })).toThrow();
  });
});

// --- CustomUnit dispatch --------------------------------------------------- //
describe('CustomUnit sizing dispatch', () => {
  it('formula → agent-defined volume, derived geometry, flagged', () => {
    const r = sizeUnit(custom({
      sizeQuantity: 'volume', method: 'formula', expression: 'flow_vol * tau',
      variables: { tau: 3600 }, assumptions: ['τ = 1 h (agent)'], source: 'Doe 2024',
    }));
    expect(r.sizeBasis).toBe('volume');
    expect(r.sizes.volume!).toBeGreaterThan(0);
    expect(r.sizes.diameter!).toBeGreaterThan(0);
    expect(r.method).toContain('agent formula');
    expect(r.source).toBe('Doe 2024');
    expect(r.assumptions[0]).toMatch(/agent-defined/);
    expect(r.inRange).toBe(true);
  });

  it('inherit → falls back to the baseType built-in (RCSTR residence)', () => {
    const r = sizeUnit(custom({
      sizeQuantity: 'volume', method: 'inherit', variables: {}, assumptions: [],
    }));
    expect(r.sizeBasis).toBe('volume');
    expect(r.method).toBe('V = V̇·τ');                // the RCSTR built-in
    expect(r.assumptions.join(' ')).toContain('residence');
  });

  it('no customSizing → inherit baseType', () => {
    const r = sizeUnit({
      unitId: 'cu', unitType: 'CustomUnit', baseType: 'Pump', work: 12,
      inlets: [], outlets: [],
    });
    expect(r.sizeBasis).toBe('power');
    expect(r.sizes.power).toBe(12);
  });

  it('unsafe / invalid formula → flagged, never fabricated', () => {
    const r = sizeUnit(custom({
      sizeQuantity: 'volume', method: 'formula', expression: 'process.exit(1)',
      variables: {}, assumptions: [],
    }));
    expect(r.inRange).toBe(false);
    expect(r.note).toMatch(/rejected/);
    expect(r.sizes.volume).toBeUndefined();
  });

  it('missing baseType and no formula → flagged', () => {
    const r = sizeUnit({ unitId: 'cu', unitType: 'CustomUnit', inlets: [], outlets: [] });
    expect(r.inRange).toBe(false);
    expect(r.note).toBeTruthy();
  });
});
