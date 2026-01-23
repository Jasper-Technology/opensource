/**
 * Schema Converter: V1 → V2
 *
 * Converts old schema (with discriminated unions) to new simplified schema.
 * Allows seamless migration without breaking existing projects.
 */

import type { JasperProject, ParamValue, StreamEdge } from '../core/schema';
import type { ProjectV2, BlockV2, ConnectionV2 } from '../core/schema-v2';

/**
 * Convert old project to new format
 */
export function convertProjectV1toV2(oldProject: JasperProject): ProjectV2 {
  return {
    id: oldProject.projectId,
    name: oldProject.name,
    // Use component IDs (formula like "H2O") - they match thermo database keys
    components: oldProject.components.map((c) => c.id),
    blocks: oldProject.flowsheet.nodes.map((node) => convertBlock(node, oldProject)),
    connections: oldProject.flowsheet.edges.map((edge) => convertConnection(edge)),
    thermodynamics: oldProject.thermodynamics,
    economics: oldProject.economics,
  };
}

/**
 * Convert block (UnitOpNode → BlockV2)
 */
function convertBlock(node: any, project: JasperProject): BlockV2 {
  const layout = project.flowsheet.layout?.nodes[node.id];

  return {
    id: node.id,
    type: node.type,
    name: node.name,
    x: layout?.x || 0,
    y: layout?.y || 0,
    params: convertParams(node.params, node.type, node.id, project),
  };
}

/**
 * Convert parameters (flatten discriminated unions)
 */
function convertParams(
  params: Record<string, ParamValue>,
  blockType: string,
  nodeId: string,
  project: JasperProject
): Record<string, any> {
  const result: Record<string, any> = {};

  // Convert all existing parameters
  for (const [key, value] of Object.entries(params)) {
    const converted = flattenParamValue(value);
    // Only set if conversion succeeded (not undefined)
    if (converted !== undefined) {
      result[key] = converted;
    }
  }

  // For Feed blocks, ensure we have T, P, flow, composition
  // Priority: 1) params on Feed block, 2) edge spec (legacy)
  if (blockType === 'Feed') {
    // If params are already set from the Feed block, use them
    // (they were already processed above via flattenParamValue)

    // Fallback to edge spec for legacy projects
    if (!result.T || !result.P || !result.flow || !result.composition) {
      const feedEdge = project.flowsheet.edges.find(
        (e) => e.from.nodeId === nodeId
      );

      if (feedEdge?.spec) {
        // Convert stream spec to feed params (only if not already set)
        if (!result.T && feedEdge.spec.T) {
          result.T = convertTemperature(feedEdge.spec.T);
        }
        if (!result.P && feedEdge.spec.P) {
          result.P = convertPressure(feedEdge.spec.P);
        }
        if (!result.flow && feedEdge.spec.flow) {
          result.flow = feedEdge.spec.flow.value; // Assume kmol/h
        }
        if (!result.composition && feedEdge.spec.composition) {
          // Use component IDs directly - they match thermo database keys (e.g., "H2O", "CO2")
          const composition: Record<string, number> = {};
          for (const [compKey, fraction] of Object.entries(feedEdge.spec.composition)) {
            composition[compKey] = fraction;
          }
          result.composition = composition;
        }
        if (!result.phase && feedEdge.spec.phase) {
          result.phase = feedEdge.spec.phase;
        }
      }
    }
  }

  // For Flash blocks, ensure we have T and P parameters
  // If missing or invalid, try to get from inlet stream, otherwise use defaults
  if (blockType === 'Flash') {
    // Check if T is missing or invalid (undefined, null, or NaN)
    if (result.T === undefined || result.T === null || isNaN(result.T)) {
      // Try to get from inlet stream
      const inletEdge = project.flowsheet.edges.find(
        (e) => e.to.nodeId === nodeId
      );

      if (inletEdge?.spec?.T) {
        result.T = convertTemperature(inletEdge.spec.T);
      } else {
        // Use default (50°C = 323.15K)
        result.T = 323.15;
      }
    }

    // Check if P is missing or invalid (undefined, null, or NaN)
    if (result.P === undefined || result.P === null || isNaN(result.P)) {
      // Try to get from inlet stream
      const inletEdge = project.flowsheet.edges.find(
        (e) => e.to.nodeId === nodeId
      );

      if (inletEdge?.spec?.P) {
        result.P = convertPressure(inletEdge.spec.P);
      } else {
        // Use default (1 bar = 1e5 Pa)
        result.P = 1e5;
      }
    }
  }

  return result;
}

/**
 * Flatten a ParamValue discriminated union to simple value
 */
function flattenParamValue(value: ParamValue): any {
  if (!value) return undefined;

  switch (value.kind) {
    case 'quantity':
      // Convert quantity to base SI units
      return convertQuantity(value.q);
    case 'number':
      return value.x;
    case 'int':
      return value.n;
    case 'string':
      return value.s;
    case 'boolean':
      return value.b;
    case 'enum':
      return value.e;
    case 'composition':
      // Return composition object directly - already in the right format
      return value.comp;
    default:
      return undefined;
  }
}

/**
 * Convert quantity with unit to base SI unit value
 */
function convertQuantity(q: { value: number; unit: string }): number {
  const { value, unit } = q;

  // Temperature conversions
  if (unit === 'C' || unit === '°C' || unit === 'celsius') {
    return value + 273.15; // C -> K
  }
  if (unit === 'F' || unit === '°F' || unit === 'fahrenheit') {
    return ((value - 32) * 5) / 9 + 273.15; // F -> K
  }
  if (unit === 'K' || unit === 'kelvin') {
    return value;
  }

  // Pressure conversions
  if (unit === 'bar') {
    return value * 100000; // bar -> Pa
  }
  if (unit === 'Pa' || unit === 'pascal') {
    return value;
  }
  if (unit === 'psi') {
    return value * 6894.76; // psi -> Pa
  }
  if (unit === 'atm') {
    return value * 101325; // atm -> Pa
  }
  if (unit === 'kPa') {
    return value * 1000; // kPa -> Pa
  }
  if (unit === 'MPa') {
    return value * 1000000; // MPa -> Pa
  }

  // Flow rate conversions (assume molar flow)
  if (unit === 'kmol/h') {
    return value;
  }
  if (unit === 'mol/h') {
    return value / 1000;
  }
  if (unit === 'mol/s') {
    return (value * 3600) / 1000;
  }

  // Default: return value as-is
  return value;
}

/**
 * Convert temperature from Quantity to Kelvin
 */
function convertTemperature(q: { value: number; unit: string }): number {
  return convertQuantity(q);
}

/**
 * Convert pressure from Quantity to Pascal
 */
function convertPressure(q: { value: number; unit: string }): number {
  return convertQuantity(q);
}

/**
 * Convert connection (StreamEdge → ConnectionV2)
 */
function convertConnection(edge: StreamEdge): ConnectionV2 {
  return {
    id: edge.id,
    name: edge.name, // Preserve stream name (e.g., "S1-Gas", "S2-Water")
    from: {
      blockId: edge.from.nodeId,
      port: edge.from.portName,
    },
    to: {
      blockId: edge.to.nodeId,
      port: edge.to.portName,
    },
  };
}
