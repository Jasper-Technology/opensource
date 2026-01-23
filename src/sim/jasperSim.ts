import type { JasperProject, SimulationRun } from '../core/schema';
import { stableHash } from '../core/hash';
import { convertProjectV1toV2 } from './converter';
import { simulateV2 } from './engine-v2';
import { computeCOM } from './economics';

/**
 * Main simulation entry point
 * Uses V2 block-based simulation engine
 */
export async function runSimulation(
  project: JasperProject,
  versionId: string
): Promise<Omit<SimulationRun, 'runId' | 'projectId' | 'versionId' | 'createdAt'>> {
  const inputsHash = stableHash({
    snapshot: project,
    versionId,
  });

  try {
    // Convert old project schema to V2
    const projectV2 = convertProjectV1toV2(project);

    // Run V2 simulation engine
    const result = simulateV2(projectV2);

    // If simulation failed, return error
    if (result.status === 'error') {
      return {
        simulator: 'jasperSimV2',
        status: 'error',
        inputsHash,
        converged: false,
        kpis: {},
        specResults: [],
        violations: [],
        rawOutputs: result.rawOutputs,
      };
    }

    // Update COM with computed KPIs
    const kpis = { ...result.kpis };
    kpis.COM = computeCOM(
      {
        runId: '',
        projectId: project.projectId,
        versionId,
        createdAt: '',
        simulator: 'jasperSimV2',
        status: 'done',
        inputsHash,
        converged: true,
        kpis,
        specResults: [],
        violations: [],
      },
      project.economics
    );

    return {
      simulator: 'jasperSimV2',
      status: 'done',
      inputsHash,
      converged: true,
      kpis,
      specResults: [], // V2 engine doesn't use specs yet
      violations: [], // V2 engine doesn't use constraints yet
      rawOutputs: result.rawOutputs,
    };
  } catch (error: any) {
    return {
      simulator: 'jasperSimV2',
      status: 'error',
      inputsHash,
      converged: false,
      kpis: {},
      specResults: [],
      violations: [],
      rawOutputs: {
        errorSummary: `SIMULATION FAILED: ${error.message}`,
        log: [error.message],
      },
    };
  }
}
