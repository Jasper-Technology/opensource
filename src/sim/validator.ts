/**
 * Flowsheet Validation
 * Like AspenPlus - validate BEFORE running simulation
 */

import type { JasperProject, UnitOpNode, StreamEdge } from '../core/schema';

export interface ValidationError {
  type: 'error' | 'warning';
  category: 'connectivity' | 'specification' | 'composition' | 'parameter';
  message: string;
  blockId?: string;
  streamId?: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
}

/**
 * Comprehensive flowsheet validation
 */
export function validateFlowsheet(project: JasperProject): ValidationResult {
  const errors: ValidationError[] = [];
  const warnings: ValidationError[] = [];

  // 1. Check we have blocks
  if (project.flowsheet.nodes.length === 0) {
    errors.push({
      type: 'error',
      category: 'connectivity',
      message: 'Flowsheet is empty - add at least one unit operation',
    });
    return { valid: false, errors, warnings };
  }

  // 2. Check we have components defined
  if (!project.components || project.components.length === 0) {
    errors.push({
      type: 'error',
      category: 'specification',
      message: 'No components defined - add components to project',
    });
  }

  // 3. Validate each block
  for (const block of project.flowsheet.nodes) {
    validateBlock(block, project, errors, warnings);
  }

  // 4. Validate each stream
  for (const stream of project.flowsheet.edges) {
    validateStream(stream, project, errors, warnings);
  }

  // 5. Check connectivity - find orphaned blocks
  const connectedBlocks = new Set<string>();
  for (const stream of project.flowsheet.edges) {
    connectedBlocks.add(stream.from.nodeId);
    connectedBlocks.add(stream.to.nodeId);
  }

  for (const block of project.flowsheet.nodes) {
    if (block.type === 'TextBox') continue; // Skip annotations
    
    if (!connectedBlocks.has(block.id)) {
      warnings.push({
        type: 'warning',
        category: 'connectivity',
        message: `Block "${block.name}" is not connected to any streams`,
        blockId: block.id,
      });
    }
  }

  // 6. Check for feed blocks - every flowsheet needs inputs
  const feeds = project.flowsheet.nodes.filter(n => n.type === 'Feed');
  if (feeds.length === 0) {
    errors.push({
      type: 'error',
      category: 'connectivity',
      message: 'No Feed blocks found - flowsheet needs at least one input stream',
    });
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

function validateBlock(
  block: UnitOpNode,
  project: JasperProject,
  errors: ValidationError[],
  warnings: ValidationError[]
) {
  // Skip non-process blocks
  if (block.type === 'TextBox' || block.type === 'Sink') return;

  // Check required parameters based on block type
  switch (block.type) {
    case 'Feed':
      validateFeedBlock(block, project, errors, warnings);
      break;
    case 'Flash':
    case 'Separator':
      validateSeparatorBlock(block, project, errors, warnings);
      break;
    case 'Pump':
      validatePumpBlock(block, errors, warnings);
      break;
    case 'Compressor':
      validateCompressorBlock(block, errors, warnings);
      break;
    case 'Heater':
    case 'Cooler':
      validateHeatExchangerBlock(block, errors, warnings);
      break;
    case 'Absorber':
    case 'Stripper':
    case 'DistillationColumn':
      validateColumnBlock(block, errors, warnings);
      break;
  }
}

function validateFeedBlock(
  block: UnitOpNode,
  project: JasperProject,
  errors: ValidationError[],
  _warnings: ValidationError[]
) {
  // Feed blocks MUST have outlet stream specified
  const outletStreams = project.flowsheet.edges.filter(e => e.from.nodeId === block.id);
  
  if (outletStreams.length === 0) {
    errors.push({
      type: 'error',
      category: 'connectivity',
      message: `Feed "${block.name}" has no outlet stream - connect to downstream equipment`,
      blockId: block.id,
    });
    return;
  }

  // Check if outlet stream has proper specification
  for (const stream of outletStreams) {
    if (!stream.spec) {
      errors.push({
        type: 'error',
        category: 'specification',
        message: `Feed "${block.name}" outlet stream "${stream.name}" is not specified`,
        blockId: block.id,
        streamId: stream.id,
      });
    } else {
      // Must have flow, temp, pressure, and composition
      if (!stream.spec.flow || stream.spec.flow.value <= 0) {
        errors.push({
          type: 'error',
          category: 'specification',
          message: `Stream "${stream.name}" from "${block.name}" has no flow rate specified`,
          streamId: stream.id,
        });
      }
      if (!stream.spec.T) {
        errors.push({
          type: 'error',
          category: 'specification',
          message: `Stream "${stream.name}" from "${block.name}" has no temperature specified`,
          streamId: stream.id,
        });
      }
      if (!stream.spec.P) {
        errors.push({
          type: 'error',
          category: 'specification',
          message: `Stream "${stream.name}" from "${block.name}" has no pressure specified`,
          streamId: stream.id,
        });
      }
      if (!stream.spec.composition || Object.keys(stream.spec.composition).length === 0) {
        errors.push({
          type: 'error',
          category: 'composition',
          message: `Stream "${stream.name}" from "${block.name}" has no composition specified`,
          streamId: stream.id,
        });
      } else {
        // Check composition sums to 1.0
        const total = Object.values(stream.spec.composition).reduce((sum, val) => sum + val, 0);
        if (Math.abs(total - 1.0) > 0.01) {
          errors.push({
            type: 'error',
            category: 'composition',
            message: `Stream "${stream.name}" composition sums to ${total.toFixed(3)}, must equal 1.0`,
            streamId: stream.id,
          });
        }
      }
    }
  }
}

function validateSeparatorBlock(
  block: UnitOpNode,
  project: JasperProject,
  errors: ValidationError[],
  _warnings: ValidationError[]
) {
  const inletStreams = project.flowsheet.edges.filter(e => e.to.nodeId === block.id);
  const outletStreams = project.flowsheet.edges.filter(e => e.from.nodeId === block.id);

  if (inletStreams.length === 0) {
    errors.push({
      type: 'error',
      category: 'connectivity',
      message: `${block.type} "${block.name}" has no inlet stream`,
      blockId: block.id,
    });
  }

  if (outletStreams.length < 2) {
    errors.push({
      type: 'error',
      category: 'connectivity',
      message: `${block.type} "${block.name}" needs at least 2 outlet streams (vapor & liquid)`,
      blockId: block.id,
    });
  }
}

function validatePumpBlock(
  block: UnitOpNode,
  _errors: ValidationError[],
  _warnings: ValidationError[]
) {
  // Pump needs pressure rise specification
  const dPParam = block.params.dP as any;
  if (!dPParam || dPParam.kind !== 'quantity' || dPParam.q.value <= 0) {
    _warnings.push({
      type: 'warning',
      category: 'parameter',
      message: `Pump "${block.name}" has no pressure rise specified - will use default`,
      blockId: block.id,
    });
  }
}

function validateCompressorBlock(
  block: UnitOpNode,
  errors: ValidationError[],
  _warnings: ValidationError[]
) {
  // Compressor needs outlet pressure or compression ratio
  const outletPParam = block.params.outletP as any;
  const ratioParam = block.params.ratio as any;
  
  if (!outletPParam && !ratioParam) {
    errors.push({
      type: 'error',
      category: 'parameter',
      message: `Compressor "${block.name}" needs outlet pressure or compression ratio`,
      blockId: block.id,
    });
  }
}

function validateHeatExchangerBlock(
  block: UnitOpNode,
  errors: ValidationError[],
  _warnings: ValidationError[]
) {
  // Heater/Cooler needs duty or outlet temperature
  const dutyParam = block.params.duty as any;
  const outletTParam = block.params.outletT as any;
  
  if (!dutyParam && !outletTParam) {
    errors.push({
      type: 'error',
      category: 'parameter',
      message: `${block.type} "${block.name}" needs duty or outlet temperature`,
      blockId: block.id,
    });
  }
}

function validateColumnBlock(
  block: UnitOpNode,
  errors: ValidationError[],
  _warnings: ValidationError[]
) {
  // Column needs number of stages
  const stagesParam = block.params.stages as any;
  if (!stagesParam || (stagesParam.kind === 'int' && stagesParam.n <= 0)) {
    errors.push({
      type: 'error',
      category: 'parameter',
      message: `Column "${block.name}" needs number of stages specified`,
      blockId: block.id,
    });
  }
}

function validateStream(
  stream: StreamEdge,
  project: JasperProject,
  errors: ValidationError[],
  _warnings: ValidationError[]
) {
  // Check source and target blocks exist
  const sourceBlock = project.flowsheet.nodes.find(n => n.id === stream.from.nodeId);
  const targetBlock = project.flowsheet.nodes.find(n => n.id === stream.to.nodeId);

  if (!sourceBlock) {
    errors.push({
      type: 'error',
      category: 'connectivity',
      message: `Stream "${stream.name}" source block not found`,
      streamId: stream.id,
    });
  }

  if (!targetBlock) {
    errors.push({
      type: 'error',
      category: 'connectivity',
      message: `Stream "${stream.name}" target block not found`,
      streamId: stream.id,
    });
  }
}

