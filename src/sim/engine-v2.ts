/**
 * Simulation Engine V2: Block-Based Execution
 *
 * Simplified execution model:
 * 1. Find Feed blocks (entry points)
 * 2. Execute each block recursively, propagating streams downstream
 * 3. Extract KPIs from completed blocks
 * 4. Return results in format UI expects
 */

import type {
  ProjectV2,
  BlockV2,
  SimulationResultV2,
  StreamResult,
} from '../core/schema-v2';
import { BLOCK_FUNCTIONS } from './blocks';

/**
 * Main simulation entry point
 */
export function simulateV2(project: ProjectV2): SimulationResultV2 {
  const log: string[] = [];

  try {
    // AspenPlus-style startup banner
    log.push('');
    log.push('═══════════════════════════════════════════════════════');
    log.push('  JASPER SIMULATION ENGINE V2');
    log.push('  Block-Based Sequential Modular Solver');
    log.push('═══════════════════════════════════════════════════════');
    log.push('');
    log.push(`Project: ${project.name}`);
    log.push(`Components: ${project.components.join(', ')}`);
    log.push(`Total Blocks: ${project.blocks.length}`);
    log.push(`Total Connections: ${project.connections.length}`);
    log.push('');

    // Validate project
    log.push('───────────────────────────────────────────────────────');
    log.push('PHASE 1: Validation');
    log.push('───────────────────────────────────────────────────────');
    const validationErrors = validateProject(project);
    if (validationErrors.length > 0) {
      log.push('✗ Validation FAILED');
      validationErrors.forEach((err) => {
        log.push(`  [${err.category.toUpperCase()}] ${err.message}`);
      });
      return {
        status: 'error',
        converged: false,
        kpis: {},
        rawOutputs: {
          streams: [],
          log,
          validationErrors,
        },
      };
    }
    log.push('✓ Validation passed');
    log.push('');

    // Clear all block runtime data
    for (const block of project.blocks) {
      block.inputs = {};
      block.outputs = undefined;
      block.status = 'idle';
      block.error = undefined;
      block.duty = undefined;
      block.power = undefined;
    }

    // Find Feed blocks (entry points)
    const feeds = project.blocks.filter((b) => b.type === 'Feed');

    if (feeds.length === 0) {
      log.push('✗ No feed blocks found');
      return {
        status: 'error',
        converged: false,
        kpis: {},
        rawOutputs: {
          streams: [],
          log,
          validationErrors: [
            { category: 'connectivity', message: 'No feed blocks found' },
          ],
        },
      };
    }

    log.push('───────────────────────────────────────────────────────');
    log.push('PHASE 2: Block Execution');
    log.push('───────────────────────────────────────────────────────');
    log.push(`Starting execution from ${feeds.length} feed block(s)`);

    // Execute each feed's downstream path
    for (const feed of feeds) {
      executeBlock(feed, project, log);
    }

    // Check for errors
    const errorBlocks = project.blocks.filter((b) => b.status === 'error');
    if (errorBlocks.length > 0) {
      return {
        status: 'error',
        converged: false,
        kpis: {},
        rawOutputs: {
          streams: [],
          log,
          validationErrors: errorBlocks.map((b) => ({
            category: 'physical',
            message: `${b.name}: ${b.error}`,
            blockId: b.id,
          })),
        },
      };
    }

    // Extract KPIs from completed blocks
    const kpis = extractKPIs(project.blocks);

    // Build stream results for UI
    const streams = buildStreamResults(project);

    // Build block results
    const blockResults: Record<string, any> = {};
    for (const block of project.blocks) {
      if (block.duty || block.power) {
        blockResults[block.id] = {
          duty: block.duty,
          power: block.power,
        };
      }
    }

    // Summary
    log.push('');
    log.push('───────────────────────────────────────────────────────');
    log.push('PHASE 3: Results Summary');
    log.push('───────────────────────────────────────────────────────');
    log.push(`✓ All blocks executed successfully`);
    log.push(`  Blocks computed: ${project.blocks.filter((b) => b.status === 'done').length}`);
    log.push(`  Streams calculated: ${streams.length}`);
    log.push('');

    if (Object.keys(kpis).length > 0) {
      log.push('Key Performance Indicators:');
      if (kpis.steam) log.push(`  Steam:       ${kpis.steam.toFixed(2)} GJ/h`);
      if (kpis.electricity) log.push(`  Electricity: ${kpis.electricity.toFixed(2)} kW`);
      if (kpis.cooling) log.push(`  Cooling:     ${kpis.cooling.toFixed(2)} GJ/h`);
      log.push('');
    }

    log.push('═══════════════════════════════════════════════════════');
    log.push('  SIMULATION COMPLETED SUCCESSFULLY');
    log.push('═══════════════════════════════════════════════════════');
    log.push('');

    return {
      status: 'done',
      converged: true,
      kpis,
      rawOutputs: {
        streams,
        log,
        blockResults,
      },
    };
  } catch (error: any) {
    log.push(`Fatal error: ${error.message}`);
    return {
      status: 'error',
      converged: false,
      kpis: {},
      rawOutputs: {
        streams: [],
        log,
        validationErrors: [
          { category: 'physical', message: error.message },
        ],
      },
    };
  }
}

/**
 * Execute a block and propagate to downstream blocks
 * Recursive execution following connections
 */
function executeBlock(
  block: BlockV2,
  project: ProjectV2,
  log: string[]
): void {
  // Skip if already computed
  if (block.status === 'done') {
    return;
  }

  // Prevent infinite loops
  if (block.status === 'computing') {
    throw new Error(`Circular dependency detected at ${block.name}`);
  }

  // Check if all required inputs are available
  // Count how many incoming connections this block has
  const incomingConnections = project.connections.filter(
    (c) => c.to.blockId === block.id
  );

  // For blocks with multiple inputs (like Mixer), wait until all inputs are ready
  const currentInputCount = Object.keys(block.inputs || {}).length;
  if (currentInputCount < incomingConnections.length) {
    // Not all inputs are ready yet, skip for now
    return;
  }

  try {
    block.status = 'computing';

    // Get block function
    const blockFn = BLOCK_FUNCTIONS[block.type];
    if (!blockFn) {
      throw new Error(`Unknown block type: ${block.type}`);
    }

    // Execute block function
    const result = blockFn(block.inputs || {}, block.params, project.components);

    // Store outputs and results
    block.outputs = result.outputs;
    block.duty = result.duty;
    block.power = result.power;
    block.status = 'done';

    // Log execution with details
    let logLine = `  ✓ ${block.name} (${block.type})`;
    if (block.duty) {
      logLine += ` | Duty: ${block.duty.toFixed(1)} kW`;
    }
    if (block.power) {
      logLine += ` | Power: ${block.power.toFixed(1)} kW`;
    }
    log.push(logLine);

    // Propagate outputs to connected downstream blocks
    const outgoingConnections = project.connections.filter(
      (c) => c.from.blockId === block.id
    );

    for (const conn of outgoingConnections) {
      const downstream = project.blocks.find((b) => b.id === conn.to.blockId);
      if (!downstream) {
        log.push(
          `⚠ Warning: Connection from ${block.name} points to non-existent block`
        );
        continue;
      }

      // Set input on downstream block
      if (!downstream.inputs) {
        downstream.inputs = {};
      }

      const outputStream = block.outputs![conn.from.port];
      if (!outputStream) {
        throw new Error(
          `${block.name} has no output port "${conn.from.port}"`
        );
      }

      downstream.inputs[conn.to.port] = outputStream;

      // Recursively execute downstream block
      executeBlock(downstream, project, log);
    }
  } catch (error: any) {
    block.status = 'error';
    block.error = error.message;
    log.push(`  ✗ ${block.name} (${block.type}) FAILED: ${error.message}`);
    throw error; // Propagate to stop simulation
  }
}

/**
 * Extract KPIs from completed blocks
 */
function extractKPIs(blocks: BlockV2[]): Record<string, number> {
  const kpis: Record<string, number> = {};

  // Total power consumption (kW)
  const totalPower = blocks
    .filter((b) => b.power)
    .reduce((sum, b) => sum + (b.power || 0), 0);
  if (totalPower > 0) {
    kpis.electricity = totalPower;
  }

  // Total heating duty (kW -> GJ/h)
  const totalHeating = blocks
    .filter((b) => b.duty && b.duty > 0)
    .reduce((sum, b) => sum + (b.duty || 0), 0);
  if (totalHeating > 0) {
    kpis.steam = (totalHeating * 3.6) / 1000; // kW -> GJ/h
  }

  // Total cooling duty (kW -> GJ/h)
  const totalCooling = blocks
    .filter((b) => b.duty && b.duty < 0)
    .reduce((sum, b) => sum + Math.abs(b.duty || 0), 0);
  if (totalCooling > 0) {
    kpis.cooling = (totalCooling * 3.6) / 1000; // kW -> GJ/h
  }

  // TODO: Add more KPIs (CO2 captured, etc.)

  return kpis;
}

/**
 * Build stream results for UI display
 * Converts internal units to UI-friendly units
 * Uses connection names (S1, S2, etc.) that match diagram labels
 */
function buildStreamResults(project: ProjectV2): StreamResult[] {
  const streamResults: StreamResult[] = [];

  for (let i = 0; i < project.connections.length; i++) {
    const conn = project.connections[i];
    const sourceBlock = project.blocks.find((b) => b.id === conn.from.blockId);
    if (!sourceBlock || !sourceBlock.outputs) {
      continue;
    }

    const streamData = sourceBlock.outputs[conn.from.port];
    if (!streamData) {
      continue;
    }

    // Use connection name if available, otherwise generate S1, S2, etc.
    // This matches the stream labels shown on the diagram
    const streamName = conn.name || `S${i + 1}`;

    // Convert units for UI
    streamResults.push({
      id: conn.id,
      name: streamName,
      T: streamData.T, // Keep in K (UI will convert)
      P: streamData.P / 100000, // Pa -> bar
      flow: streamData.flow,
      composition: streamData.composition,
      phase: streamData.phase,
      H: streamData.H || 0,
      vaporFrac: streamData.vaporFrac,
    });
  }

  return streamResults;
}

/**
 * Basic validation
 */
function validateProject(project: ProjectV2): Array<{ category: string; message: string; blockId?: string }> {
  const errors: Array<{ category: string; message: string; blockId?: string }> = [];

  // Check for components
  if (project.components.length === 0) {
    errors.push({
      category: 'parameter',
      message: 'No components defined',
    });
  }

  // Check for blocks
  if (project.blocks.length === 0) {
    errors.push({
      category: 'connectivity',
      message: 'No blocks in flowsheet',
    });
  }

  // Check for feed blocks
  const feeds = project.blocks.filter((b) => b.type === 'Feed');
  if (feeds.length === 0) {
    errors.push({
      category: 'connectivity',
      message: 'No feed blocks found',
    });
  }

  // Validate feed specifications
  for (const feed of feeds) {
    if (!feed.params.T || !feed.params.P || !feed.params.flow) {
      errors.push({
        category: 'parameter',
        message: `Feed block "${feed.name}" missing required parameters`,
        blockId: feed.id,
      });
    }

    const comp = feed.params.composition as Record<string, number> | undefined;
    if (!comp) {
      errors.push({
        category: 'composition',
        message: `Feed block "${feed.name}" missing composition`,
        blockId: feed.id,
      });
    } else {
      const sum = Object.values(comp).reduce((a, b) => a + b, 0);
      if (Math.abs(sum - 1.0) > 0.01) {
        errors.push({
          category: 'composition',
          message: `Feed block "${feed.name}" composition doesn't sum to 1.0 (sum = ${sum.toFixed(3)})`,
          blockId: feed.id,
        });
      }
    }
  }

  return errors;
}
