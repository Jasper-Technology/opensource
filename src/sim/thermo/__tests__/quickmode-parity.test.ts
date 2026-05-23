/**
 * Quick Mode Engine — ChemE Parity Tests
 *
 * Verifies each phase of the Quick mode thermodynamic engine
 * against literature values and textbook problems.
 *
 * Run: npx tsx src/sim/thermo/__tests__/quickmode-parity.test.ts
 */

import { COMPONENT_DATABASE, vaporPressure, density, idealGasEntropy, heatOfReaction } from '../properties';
import { prFlash, prMixtureEntropy, prMixtureEnthalpy } from '../pengRobinson';
import { nrtlGamma } from '../nrtl';
import { getPropertyPackage } from '../propertyMethod';
import { solveFlowsheet } from '../../solver/blockSolver';
import type { JasperProject } from '../../../core/schema';

// ============================================================================
// Test helpers
// ============================================================================

function assert(condition: boolean, msg: string) {
  if (!condition) throw new Error(`FAIL: ${msg}`);
}

function assertNear(actual: number, expected: number, tolerance: number, label: string) {
  const relErr = Math.abs(actual - expected) / (Math.abs(expected) || 1);
  if (relErr > tolerance) {
    throw new Error(`FAIL: ${label} — expected ${expected}, got ${actual} (relErr=${(relErr * 100).toFixed(2)}%, tol=${(tolerance * 100).toFixed(0)}%)`);
  }
  console.log(`  PASS: ${label} = ${actual.toFixed(4)} (expected ${expected}, err=${(relErr * 100).toFixed(2)}%)`);
}

let passed = 0;
let failed = 0;

function runTest(name: string, fn: () => void) {
  console.log(`\n--- ${name} ---`);
  try {
    fn();
    passed++;
  } catch (e: any) {
    console.error(`  ${e.message}`);
    failed++;
  }
}

// ============================================================================
// Phase 1: Lee-Kesler Pvap + Rackett Density
// ============================================================================

runTest('Phase 1: Lee-Kesler Pvap for Water at 373K', () => {
  const water = COMPONENT_DATABASE['H2O'];
  const Pvap = vaporPressure(water, 373.15);
  // Literature: 101325 Pa at 100°C
  assertNear(Pvap, 101325, 0.03, 'Water Pvap at 373.15K');
});

runTest('Phase 1: Lee-Kesler Pvap for Ethanol at 351.4K', () => {
  const ethanol = COMPONENT_DATABASE['C2H5OH'];
  const Pvap = vaporPressure(ethanol, 351.44);
  // Boiling point: should be ~101325 Pa
  assertNear(Pvap, 101325, 0.05, 'Ethanol Pvap at Tb');
});

runTest('Phase 1: Lee-Kesler Pvap for Benzene at 353.2K', () => {
  const benzene = COMPONENT_DATABASE['C6H6'];
  const Pvap = vaporPressure(benzene, 353.25);
  assertNear(Pvap, 101325, 0.05, 'Benzene Pvap at Tb');
});

runTest('Phase 1: Lee-Kesler Pvap for Methane at 111.7K', () => {
  const methane = COMPONENT_DATABASE['CH4'];
  const Pvap = vaporPressure(methane, 111.66);
  assertNear(Pvap, 101325, 0.05, 'Methane Pvap at Tb');
});

runTest('Phase 1: Rackett liquid density for Water at 298K', () => {
  const rho = density({ 'H2O': 1.0 }, 298.15, 101325, 'L');
  // Literature: ~997 kg/m3
  assertNear(rho, 997, 0.10, 'Water liquid density at 298K');
});

runTest('Phase 1: Rackett liquid density for Ethanol at 298K', () => {
  const rho = density({ 'C2H5OH': 1.0 }, 298.15, 101325, 'L');
  // Literature: ~789 kg/m3
  assertNear(rho, 789, 0.15, 'Ethanol liquid density at 298K');
});

// ============================================================================
// Phase 2: Peng-Robinson flash
// ============================================================================

runTest('Phase 2: PR flash propane-butane at 300K, 5 bar', () => {
  // Database keys: C3H8 (Tc=369.8), n-C4H10 (Tc=425.1)
  const z = { 'C3H8': 0.5, 'n-C4H10': 0.5 };
  const T = 300; // K (below Tc for both)
  const P = 5e5; // 5 bar in Pa
  const result = prFlash(z, T, P, ['C3H8', 'n-C4H10']);
  console.log(`  VF = ${result.V.toFixed(4)}`);
  // At 300K/5bar, propane-butane should be two-phase
  assert(result.V > 0.05 && result.V < 0.95, `VF=${result.V} should be two-phase`);
  assert(result.converged, 'PR flash should converge');
  console.log(`  PASS: PR flash converged, VF=${result.V.toFixed(4)}`);
});

runTest('Phase 2: PR K-values via property package', () => {
  const pkg = getPropertyPackage('PR');
  const K = pkg.calculateKValues(['CH4', 'C2H6'], 200, 30e5);
  assert(K['CH4'] > K['C2H6'], 'CH4 should be more volatile than C2H6');
  console.log(`  PASS: K_CH4=${K['CH4'].toFixed(4)}, K_C2H6=${K['C2H6'].toFixed(4)}`);
});

runTest('Phase 2: SRK K-values via property package', () => {
  const pkg = getPropertyPackage('SRK');
  const K = pkg.calculateKValues(['CH4', 'C2H6'], 200, 30e5);
  assert(pkg.name === 'SRK', 'SRK package should be selected');
  assert(K['CH4'] > K['C2H6'], 'CH4 should be more volatile than C2H6');
  console.log(`  PASS: K_CH4=${K['CH4'].toFixed(4)}, K_C2H6=${K['C2H6'].toFixed(4)}`);
});

runTest('Phase 2: RK K-values via property package', () => {
  const pkg = getPropertyPackage('RK');
  const K = pkg.calculateKValues(['CH4', 'C2H6'], 200, 30e5);
  assert(pkg.name === 'RK', 'RK package should be selected');
  assert(K['CH4'] > K['C2H6'], 'CH4 should be more volatile than C2H6');
  console.log(`  PASS: K_CH4=${K['CH4'].toFixed(4)}, K_C2H6=${K['C2H6'].toFixed(4)}`);
});

// ============================================================================
// Phase 3: NRTL ethanol-water
// ============================================================================

runTest('Phase 3: NRTL gamma for ethanol-water at 354K', () => {
  const gamma = nrtlGamma(['C2H5OH', 'H2O'], [0.1, 0.9], 354);
  // Ethanol at low conc in water should have gamma >> 1
  assert(gamma[0] > 2, `gamma_EtOH=${gamma[0]} should be > 2`);
  assert(gamma[1] > 0.9 && gamma[1] < 1.5, `gamma_H2O=${gamma[1]} should be near 1`);
  console.log(`  PASS: gamma_EtOH=${gamma[0].toFixed(3)}, gamma_H2O=${gamma[1].toFixed(3)}`);
});

runTest('Phase 3: NRTL flash ethanol-water at 81°C, 1 atm', () => {
  const pkg = getPropertyPackage('NRTL');
  const T = 273.15 + 81; // K
  const P = 101325; // Pa
  const z = { 'C2H5OH': 0.3, 'H2O': 0.7 };
  const result = pkg.flash(z, T, P, ['C2H5OH', 'H2O']);
  console.log(`  VF = ${result.V.toFixed(4)}`);
  // At 81°C, 1 atm, ethanol-water with z_EtOH=0.3 should be partially vaporized
  assert(result.V >= 0 && result.V <= 1, 'VF should be in [0,1]');
  // Vapor should be enriched in ethanol relative to feed
  if (result.V > 0.01 && result.V < 0.99) {
    assert(result.y['C2H5OH'] > z['C2H5OH'], 'Vapor should be enriched in ethanol');
    console.log(`  PASS: y_EtOH=${result.y['C2H5OH'].toFixed(4)} > z_EtOH=${z['C2H5OH']}`);
  } else {
    console.log(`  PASS: Single phase (VF=${result.V.toFixed(4)})`);
  }
});

// ============================================================================
// Phase 4: Isentropic compressor
// ============================================================================

runTest('Phase 4: Isentropic compressor for nitrogen', () => {
  const pkg = getPropertyPackage('Ideal');
  const T_in = 300; // K
  const P_in = 1e5; // 1 bar
  const P_out = 3e5; // 3 bar
  const comp = { 'N2': 1.0 };

  const S_in = pkg.mixtureEntropy(comp, T_in, P_in, 'V');

  // Find isentropic T_out
  let T_s = T_in * Math.pow(3, 0.4 / 1.4); // ideal gas guess ~410K
  for (let i = 0; i < 30; i++) {
    const S = pkg.mixtureEntropy(comp, T_s, P_out, 'V');
    const err = S - S_in;
    if (Math.abs(err) < 1e-6) break;
    const dT = 0.1;
    const dSdT = (pkg.mixtureEntropy(comp, T_s + dT, P_out, 'V') - S) / dT;
    if (Math.abs(dSdT) < 1e-15) break;
    T_s -= err / dSdT;
  }

  const H_in = pkg.mixtureEnthalpy(comp, T_in, P_in, 'V');
  const H_out = pkg.mixtureEnthalpy(comp, T_s, P_out, 'V');
  const work = H_out - H_in; // kJ/mol

  // Textbook: for N2 (gamma≈1.4), T_out_s = 300 * 3^(0.4/1.4) ≈ 410.6K
  // Work = Cp * (T_out - T_in) ≈ 29.1 * (410.6-300) / 1000 ≈ 3.22 kJ/mol
  assertNear(T_s, 410.6, 0.03, 'Isentropic outlet T for N2');
  assertNear(work, 3.22, 0.10, 'Isentropic work for N2 (kJ/mol)');
});

// ============================================================================
// Phase 5: Distillation (Fenske-Underwood-Gilliland)
// ============================================================================

runTest('Phase 5: Benzene-Toluene distillation', () => {
  const project: JasperProject = {
    projectId: 'test-distillation',
    orgId: undefined,
    name: 'Distillation Test',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    thermodynamics: { propertyMethod: 'Ideal' },
    components: [
      { id: 'benzene', name: 'Benzene', formula: 'C6H6' },
      { id: 'toluene', name: 'Toluene', formula: 'C7H8' },
    ],
    flowsheet: {
      nodes: [
        { id: 'feed', type: 'Feed', name: 'Feed', params: {
          T: { kind: 'quantity', q: { value: 80, unit: 'C' } },
          P: { kind: 'quantity', q: { value: 1, unit: 'bar' } },
          flow: { kind: 'number', x: 100 },
          composition: { kind: 'composition', comp: { benzene: 0.5, toluene: 0.5 } },
        }, ports: [] },
        { id: 'col', type: 'DistillationColumn', name: 'Column', params: {
          lightKey: { kind: 'string', s: 'C6H6' },
          heavyKey: { kind: 'string', s: 'C7H8' },
          lkRecovery: { kind: 'number', x: 0.99 },
          hkRecovery: { kind: 'number', x: 0.01 },
          refluxRatio: { kind: 'number', x: 2.0 },
        }, ports: [] },
        { id: 'dist', type: 'Sink', name: 'Distillate', params: {}, ports: [] },
        { id: 'bot', type: 'Sink', name: 'Bottoms', params: {}, ports: [] },
      ],
      edges: [
        { id: 'e1', name: 'Feed-Col', from: { nodeId: 'feed', portName: 'out' }, to: { nodeId: 'col', portName: 'in' } },
        { id: 'e2', name: 'Distillate', from: { nodeId: 'col', portName: 'distillate' }, to: { nodeId: 'dist', portName: 'in' } },
        { id: 'e3', name: 'Bottoms', from: { nodeId: 'col', portName: 'bottoms' }, to: { nodeId: 'bot', portName: 'in' } },
      ],
    },
    specs: { specs: [] },
    constraints: { constraints: [] },
    objective: { metric: 'steam', sense: 'min' },
    status: 'draft',
  };

  const result = solveFlowsheet(project);
  assert(result.converged, 'Distillation should converge');

  const distStream = result.streams.get('e2');
  const botStream = result.streams.get('e3');
  assert(distStream !== undefined, 'Distillate stream should exist');
  assert(botStream !== undefined, 'Bottoms stream should exist');

  // Distillate should be enriched in benzene
  const benzeneInDist = distStream!.composition['C6H6'] ?? 0;
  const tolueneInBot = botStream!.composition['C7H8'] ?? 0;
  assert(benzeneInDist > 0.9, `Distillate benzene purity ${benzeneInDist.toFixed(3)} should be > 0.9`);
  assert(tolueneInBot > 0.9, `Bottoms toluene purity ${tolueneInBot.toFixed(3)} should be > 0.9`);
  console.log(`  PASS: dist C6H6=${benzeneInDist.toFixed(3)}, bot C7H8=${tolueneInBot.toFixed(3)}`);

  const colResult = result.blockResults.get('col');
  console.log(`  N_min=${colResult?.N_min?.toFixed(1)}, N_actual=${colResult?.N_actual}, R_min=${colResult?.R_min?.toFixed(2)}`);
});

// ============================================================================
// Phase 6: Reactor heat of reaction
// ============================================================================

runTest('Phase 6: Heat of reaction for water-gas shift', () => {
  // CO + H2O -> CO2 + H2
  // deltaH_298 = Hf(CO2) + Hf(H2) - Hf(CO) - Hf(H2O)
  //            = -393.51 + 0 - (-110.53) - (-241.83) = -41.15 kJ/mol
  const stoich = { 'CO': -1, 'H2O': -1, 'CO2': 1, 'H2': 1 };
  const deltaH = heatOfReaction(stoich, 298.15);
  assertNear(deltaH, -41.15, 0.05, 'WGS deltaH at 298K');
});

runTest('Phase 6: Adiabatic reactor temperature rise', () => {
  const project: JasperProject = {
    projectId: 'test-reactor',
    orgId: undefined,
    name: 'Reactor Test',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    thermodynamics: { propertyMethod: 'Ideal' },
    components: [
      { id: 'co', name: 'CO', formula: 'CO' },
      { id: 'h2o', name: 'Water', formula: 'H2O' },
      { id: 'co2', name: 'CO2', formula: 'CO2' },
      { id: 'h2', name: 'H2', formula: 'H2' },
    ],
    reactions: [
      { id: 'wgs', stoichiometry: { CO: -1, H2O: -1, CO2: 1, H2: 1 }, type: 'rate' },
    ],
    flowsheet: {
      nodes: [
        { id: 'feed', type: 'Feed', name: 'Feed', params: {
          T: { kind: 'quantity', q: { value: 400, unit: 'C' } },
          P: { kind: 'quantity', q: { value: 30, unit: 'bar' } },
          flow: { kind: 'number', x: 100 },
          composition: { kind: 'composition', comp: { co: 0.3, h2o: 0.5, co2: 0.1, h2: 0.1 } },
        }, ports: [] },
        { id: 'reactor', type: 'RStoic', name: 'WGS Reactor', params: {
          mode: { kind: 'string', s: 'adiabatic' },
          conversion: { kind: 'number', x: 0.9 },
        }, ports: [] },
        { id: 'sink', type: 'Sink', name: 'Product', params: {}, ports: [] },
      ],
      edges: [
        { id: 'e1', name: 'Feed', from: { nodeId: 'feed', portName: 'out' }, to: { nodeId: 'reactor', portName: 'in' } },
        { id: 'e2', name: 'Product', from: { nodeId: 'reactor', portName: 'out' }, to: { nodeId: 'sink', portName: 'in' } },
      ],
    },
    specs: { specs: [] },
    constraints: { constraints: [] },
    objective: { metric: 'steam', sense: 'min' },
    status: 'draft',
  };

  const result = solveFlowsheet(project);
  assert(result.converged, 'Reactor should converge');

  const product = result.streams.get('e2');
  assert(product !== undefined, 'Product stream should exist');

  // WGS is mildly exothermic (-41 kJ/mol), adiabatic T should rise
  assert(product!.T > 673.15, `Outlet T=${product!.T.toFixed(1)}K should be > inlet 673.15K (exothermic)`);
  console.log(`  PASS: T_out=${product!.T.toFixed(1)}K > T_in=673.15K`);

  // CO should be mostly consumed
  const coPurity = product!.composition['CO'] ?? 0;
  assert(coPurity < 0.1, `CO mole frac ${coPurity.toFixed(3)} should be < 0.1 at 90% conversion`);
  console.log(`  PASS: CO_out=${coPurity.toFixed(4)}`);
});

// ============================================================================
// Phase 7: Recycle convergence
// ============================================================================

runTest('Phase 7: Simple recycle converges', () => {
  // Feed -> Mixer -> Splitter -> (product to Sink, 30% recycles to Mixer)
  // Steady state: recycle flow = 100 * 0.3/0.7 ≈ 42.86 kmol/h, mixer out = 142.86
  const project: JasperProject = {
    projectId: 'test-recycle',
    orgId: undefined,
    name: 'Recycle Test',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    thermodynamics: { propertyMethod: 'Ideal' },
    components: [
      { id: 'benzene', name: 'Benzene', formula: 'C6H6' },
      { id: 'toluene', name: 'Toluene', formula: 'C7H8' },
    ],
    flowsheet: {
      nodes: [
        { id: 'feed', type: 'Feed', name: 'Feed', params: {
          T: { kind: 'quantity', q: { value: 25, unit: 'C' } },
          P: { kind: 'quantity', q: { value: 1, unit: 'bar' } },
          flow: { kind: 'number', x: 100 },
          composition: { kind: 'composition', comp: { benzene: 0.5, toluene: 0.5 } },
        }, ports: [] },
        { id: 'mixer', type: 'Mixer', name: 'Mixer', params: {}, ports: [] },
        { id: 'splitter', type: 'Splitter', name: 'Splitter', params: {
          splitRatio: { kind: 'number', x: 0.7 },
        }, ports: [] },
        { id: 'sink', type: 'Sink', name: 'Product', params: {}, ports: [] },
      ],
      edges: [
        { id: 'e-feed', name: 'Feed', from: { nodeId: 'feed', portName: 'out' }, to: { nodeId: 'mixer', portName: 'in1' } },
        { id: 'e-mix-split', name: 'Mix-Split', from: { nodeId: 'mixer', portName: 'out' }, to: { nodeId: 'splitter', portName: 'in' } },
        { id: 'e-product', name: 'Product', from: { nodeId: 'splitter', portName: 'out1' }, to: { nodeId: 'sink', portName: 'in' } },
        { id: 'e-recycle', name: 'Recycle', from: { nodeId: 'splitter', portName: 'out2' }, to: { nodeId: 'mixer', portName: 'in2' } },
      ],
    },
    specs: { specs: [] },
    constraints: { constraints: [] },
    objective: { metric: 'steam', sense: 'min' },
    status: 'draft',
  };

  const result = solveFlowsheet(project);
  console.log(`  converged=${result.converged}, recycleIterations=${result.recycleIterations}`);
  assert(result.converged, 'Recycle should converge');
  if (result.recycleIterations !== undefined) {
    assert(result.recycleIterations < 30, `Should converge in < 30 iterations (got ${result.recycleIterations})`);
    console.log(`  PASS: Converged in ${result.recycleIterations} iterations`);
  }

  // Check steady-state: product flow should be ~100 (same as feed)
  const product = result.streams.get('e-product');
  if (product) {
    assertNear(product.flow, 100, 0.05, 'Product flow at steady state');
  }
});

// ============================================================================
// Phase 8: Kremser absorption
// ============================================================================

runTest('Phase 8: Kremser CO2 absorption', () => {
  const project: JasperProject = {
    projectId: 'test-absorber',
    orgId: undefined,
    name: 'Absorber Test',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    thermodynamics: { propertyMethod: 'Ideal' },
    components: [
      { id: 'co2', name: 'CO2', formula: 'CO2' },
      { id: 'n2', name: 'N2', formula: 'N2' },
      { id: 'h2o', name: 'Water', formula: 'H2O' },
    ],
    flowsheet: {
      nodes: [
        { id: 'gas-feed', type: 'Feed', name: 'Gas Feed', params: {
          T: { kind: 'quantity', q: { value: 40, unit: 'C' } },
          P: { kind: 'quantity', q: { value: 1, unit: 'bar' } },
          flow: { kind: 'number', x: 100 },
          composition: { kind: 'composition', comp: { co2: 0.15, n2: 0.85 } },
        }, ports: [] },
        { id: 'liq-feed', type: 'Feed', name: 'Solvent Feed', params: {
          T: { kind: 'quantity', q: { value: 25, unit: 'C' } },
          P: { kind: 'quantity', q: { value: 1, unit: 'bar' } },
          flow: { kind: 'number', x: 500 },
          composition: { kind: 'composition', comp: { h2o: 1.0 } },
        }, ports: [] },
        { id: 'absorber', type: 'Absorber', name: 'Absorber', params: {
          stages: { kind: 'int', n: 10 },
        }, ports: [] },
        { id: 'gas-out', type: 'Sink', name: 'Clean Gas', params: {}, ports: [] },
        { id: 'liq-out', type: 'Sink', name: 'Rich Solvent', params: {}, ports: [] },
      ],
      edges: [
        { id: 'e-gas', name: 'Gas In', from: { nodeId: 'gas-feed', portName: 'out' }, to: { nodeId: 'absorber', portName: 'gas-in' } },
        { id: 'e-liq', name: 'Liq In', from: { nodeId: 'liq-feed', portName: 'out' }, to: { nodeId: 'absorber', portName: 'liquid-in' } },
        { id: 'e-gasout', name: 'Clean Gas', from: { nodeId: 'absorber', portName: 'gas-out' }, to: { nodeId: 'gas-out', portName: 'in' } },
        { id: 'e-liqout', name: 'Rich Solvent', from: { nodeId: 'absorber', portName: 'liquid-out' }, to: { nodeId: 'liq-out', portName: 'in' } },
      ],
    },
    specs: { specs: [] },
    constraints: { constraints: [] },
    objective: { metric: 'steam', sense: 'min' },
    status: 'draft',
  };

  const result = solveFlowsheet(project);
  assert(result.converged, 'Absorber should converge');

  const gasOut = result.streams.get('e-gasout');
  assert(gasOut !== undefined, 'Gas outlet should exist');

  const co2Out = gasOut!.composition['CO2'] ?? 0;
  console.log(`  CO2 in clean gas = ${(co2Out * 100).toFixed(2)}%`);
  // With 10 stages and L/G=5, should get significant CO2 removal
  assert(co2Out < 0.15, `CO2 mole fraction ${co2Out.toFixed(3)} should be < feed (0.15)`);
  console.log(`  PASS: CO2 reduced from 15% to ${(co2Out * 100).toFixed(2)}%`);
});

// ============================================================================
// Summary
// ============================================================================

console.log(`\n${'='.repeat(60)}`);
console.log(`Results: ${passed} passed, ${failed} failed out of ${passed + failed} tests`);
if (failed > 0) {
  process.exit(1);
} else {
  console.log('All Quick Mode parity tests passed!');
}
