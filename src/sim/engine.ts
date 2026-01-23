/**
 * Enhanced Simulation Engine
 * 
 * This module provides a bridge to integrate with external chemical engineering
 * simulation libraries like DWSIM, Cantera, or Process PI.
 * 
 * For now, it uses an enhanced deterministic simulation, but the architecture
 * supports integration with real simulation engines via:
 * - REST API calls to backend services
 * - WebAssembly modules
 * - Python backend via subprocess/API
 */

import type { JasperProject, SimulationRun } from '../core/schema';
import { stableHash } from '../core/hash';
import { evaluateMetricRef } from '../core/metrics';
import { computeCOM } from './economics';
import { validateFlowsheet } from './validator';
import { solveFlowsheet } from './solver/blockSolver';

export interface SimulationEngine {
  name: string;
  run(project: JasperProject, versionId: string): Promise<Omit<SimulationRun, 'runId' | 'projectId' | 'versionId' | 'createdAt'>>;
}

/**
 * Enhanced deterministic simulation engine
 * Uses more sophisticated heuristics based on chemical engineering principles
 */
export class EnhancedJasperSim implements SimulationEngine {
  name = 'jasperSim';

  async run(
    project: JasperProject,
    versionId: string
  ): Promise<Omit<SimulationRun, 'runId' | 'projectId' | 'versionId' | 'createdAt'>> {
    const inputsHash = stableHash({
      snapshot: project,
      versionId,
    });

    // STEP 1: Validate flowsheet (like AspenPlus)
    const validation = validateFlowsheet(project);
    
    if (!validation.valid) {
      // Return error with detailed messages
      const errorMessages = validation.errors.map(e => 
        `[${e.category.toUpperCase()}] ${e.message}`
      ).join('\n');

      return {
        simulator: this.name,
        status: 'error',
        inputsHash,
        converged: false,
        kpis: {},
        specResults: [],
        violations: [],
        rawOutputs: {
          validationErrors: validation.errors,
          validationWarnings: validation.warnings,
          errorSummary: `SIMULATION FAILED - ${validation.errors.length} error(s) found:\n\n${errorMessages}`,
        },
      };
    }

    // STEP 2: Solve flowsheet using rigorous thermodynamics
    const solverResult = solveFlowsheet(project);
    
    if (!solverResult.converged) {
      return {
        simulator: this.name,
        status: 'error',
        inputsHash,
        converged: false,
        kpis: {},
        specResults: [],
        violations: [],
        rawOutputs: {
          validationWarnings: validation.warnings,
          solverError: solverResult.error,
          errorSummary: `SOLVER FAILED: ${solverResult.error}`,
        },
      };
    }

    // STEP 3: Extract KPIs from solved flowsheet
    const kpis = this.extractKPIs(project, solverResult);
    
    // STEP 4: Evaluate specs
    const specResults = this.evaluateSpecs(project, kpis);
    
    // STEP 5: Evaluate constraints
    const violations = this.evaluateConstraints(project, kpis);

    // STEP 6: Update COM with computed KPIs
    kpis.COM = computeCOM(
      {
        runId: '',
        projectId: project.projectId,
        versionId,
        createdAt: '',
        simulator: this.name,
        status: 'done',
        inputsHash,
        converged: true,
        kpis,
        specResults,
        violations,
      },
      project.economics
    );

    return {
      simulator: this.name,
      status: 'done',
      inputsHash,
      converged: true,
      kpis,
      specResults,
      violations,
      rawOutputs: {
        validationWarnings: validation.warnings,
        streams: Array.from(solverResult.streams.values()),
        blockResults: Object.fromEntries(solverResult.blockResults),
      },
    };
  }

  /**
   * Extract KPIs from rigorous simulation results
   */
  private extractKPIs(project: JasperProject, solverResult: any): Record<string, number> {
    const kpis: Record<string, number> = {};

    // Energy consumption from block results
    let totalPower = 0; // kW
    let totalSteam = 0;  // GJ/h

    for (const [, result] of solverResult.blockResults.entries()) {
      if (result.power) {
        totalPower += result.power;
      }
      if (result.duty && result.duty > 0) {
        // Positive duty = heating = steam
        totalSteam += result.duty / 1000; // kJ/h to GJ/h
      }
    }

    kpis.electricity = totalPower;
    kpis.steam = totalSteam;

    // Mass balance - total flow
    const streams = Array.from(solverResult.streams.values()) as any[];
    if (streams.length > 0) {
      const totalFlow = streams.reduce((sum: number, s: any) => sum + s.flow, 0);
      kpis.totalFlow = totalFlow;
    }

    // CO2 capture calculation (if applicable)
    const feedStreams = streams.filter((s: any) => {
      return project.flowsheet.edges.find((e: any) => 
        e.id === s.id && project.flowsheet.nodes.find((n: any) => 
          n.id === e.from.nodeId && n.type === 'Feed'
        )
      );
    });

    const productStreams = streams.filter((s: any) => {
      return project.flowsheet.edges.find((e: any) => 
        e.id === s.id && project.flowsheet.nodes.find((n: any) => 
          n.id === e.to.nodeId && n.type === 'Sink'
        )
      );
    });

    // Calculate CO2 in feed vs product
    let CO2_in = 0;
    let CO2_out = 0;

    for (const stream of feedStreams) {
      const CO2_frac = stream.composition['CO2'] || 0;
      CO2_in += stream.flow * CO2_frac;
    }

    for (const stream of productStreams) {
      const CO2_frac = stream.composition['CO2'] || 0;
      CO2_out += stream.flow * CO2_frac;
    }

    if (CO2_in > 0) {
      kpis.CO2_captured = CO2_in - CO2_out; // kmol/h
      kpis.captureEfficiency = (CO2_in - CO2_out) / CO2_in;
    }

    return kpis;
  }

  private evaluateSpecs(project: JasperProject, kpis: Record<string, number>): any[] {
    const specResults: any[] = [];
    const achievedCapture = kpis.achievedCapture || 0;
    const totalStages = kpis.totalStages || 0;
    const circulationRate = kpis.circulationRate || 0;

    for (const spec of project.specs.specs) {
      if (spec.type === 'capture') {
        specResults.push({
          specId: spec.id,
          achieved: achievedCapture,
          target: spec.targetRemoval,
          ok: achievedCapture >= spec.targetRemoval,
        });
      } else if (spec.type === 'purity') {
        const purity = Math.min(0.99, 0.7 + (totalStages / 100) * 0.25 + (circulationRate / 1000) * 0.1);
        specResults.push({
          specId: spec.id,
          achieved: purity,
          target: spec.target,
          ok: purity >= spec.target,
        });
      } else if (spec.type === 'recovery') {
        const recovery = Math.min(0.99, 0.6 + (totalStages / 80) * 0.3);
        specResults.push({
          specId: spec.id,
          achieved: recovery,
          target: spec.target,
          ok: recovery >= spec.target,
        });
      }
    }

    return specResults;
  }

  private evaluateConstraints(project: JasperProject, kpis: Record<string, number>): any[] {
    const violations: any[] = [];

    for (const constraint of project.constraints.constraints) {
      const value = evaluateMetricRef(constraint.ref, project, {
        runId: '',
        projectId: project.projectId,
        versionId: '',
        createdAt: '',
        simulator: this.name,
        status: 'done',
        inputsHash: '',
        converged: true,
        kpis,
        specResults: [],
        violations: [],
      } as any);

      if (value === null) continue;

      let violated = false;
      let message = '';

      if (constraint.type === 'max') {
        violated = value > constraint.limit;
        if (violated) {
          message = `${constraint.ref.kind === 'kpi' ? constraint.ref.metric : 'metric'} = ${value.toFixed(2)} exceeds max limit ${constraint.limit}`;
        }
      } else if (constraint.type === 'min') {
        violated = value < constraint.limit;
        if (violated) {
          message = `${constraint.ref.kind === 'kpi' ? constraint.ref.metric : 'metric'} = ${value.toFixed(2)} below min limit ${constraint.limit}`;
        }
      } else if (constraint.type === 'range') {
        violated = value < constraint.min || value > constraint.max;
        if (violated) {
          message = `${constraint.ref.kind === 'kpi' ? constraint.ref.metric : 'metric'} = ${value.toFixed(2)} outside range [${constraint.min}, ${constraint.max}]`;
        }
      }

      if (violated) {
        violations.push({
          constraintId: constraint.id,
          value,
          message,
          hard: constraint.hard,
        });
      }
    }

    return violations;
  }
}

/**
 * Factory function to get simulation engine
 * Can be extended to return different engines based on configuration
 */
export function getSimulationEngine(): SimulationEngine {
  return new EnhancedJasperSim();
}

/**
 * Future: Integration with DWSIM via API
 * 
 * export class DWSIMEngine implements SimulationEngine {
 *   name = 'dwsim';
 *   
 *   async run(project: JasperProject, versionId: string): Promise<...> {
 *     // Call DWSIM API or backend service
 *     const response = await fetch('/api/dwsim/simulate', {
 *       method: 'POST',
 *       body: JSON.stringify(project),
 *     });
 *     return response.json();
 *   }
 * }
 */

