import { z } from 'zod';

// Basic types
export type ID = string;

export const QuantitySchema = z.object({
  value: z.number(),
  unit: z.string(),
});
export type Quantity = z.infer<typeof QuantitySchema>;

// ParamValue union
export const ParamValueSchema = z.discriminatedUnion('kind', [
  z.object({ kind: z.literal('quantity'), q: QuantitySchema }),
  z.object({ kind: z.literal('number'), x: z.number() }),
  z.object({ kind: z.literal('int'), n: z.number().int() }),
  z.object({ kind: z.literal('string'), s: z.string() }),
  z.object({ kind: z.literal('boolean'), b: z.boolean() }),
  z.object({ kind: z.literal('enum'), e: z.string() }),
  z.object({ kind: z.literal('composition'), comp: z.record(z.string(), z.number()) }), // Mole fractions by component ID
]);
export type ParamValue = z.infer<typeof ParamValueSchema>;

// Enums
export const UnitTypeSchema = z.enum([
  'Feed',
  'Mixer',
  'Splitter',
  'Flash',
  'Pump',
  'Compressor',
  'Valve',
  'Heater',
  'Cooler',
  'HeatExchanger',
  'Absorber',
  'Stripper',
  'DistillationColumn',
  'Reactor',
  'Separator',
  'Sink',
  'TextBox',
]);
export type UnitType = z.infer<typeof UnitTypeSchema>;

export const PhaseSchema = z.enum(['V', 'L', 'VL', 'S']);
export type Phase = z.infer<typeof PhaseSchema>;

export const ProjectStatusSchema = z.enum(['draft', 'sim_ok', 'feasible', 'optimized', 'failed']);
export type ProjectStatus = z.infer<typeof ProjectStatusSchema>;

export const RunStatusSchema = z.enum(['queued', 'running', 'done', 'error']);
export type RunStatus = z.infer<typeof RunStatusSchema>;

export const ActorSchema = z.enum(['human', 'agent']);
export type Actor = z.infer<typeof ActorSchema>;

// ThermoConfig
export const ThermoConfigSchema = z.object({
  propertyMethod: z.string(),
  eos: z.string().optional(),
  activityModel: z.string().optional(),
  henry: z.boolean().optional(),
  electrolytes: z.boolean().optional(),
  simulatorHints: z.record(z.string(), z.any()).optional(),
});
export type ThermoConfig = z.infer<typeof ThermoConfigSchema>;

// Component
export const ComponentSchema = z.object({
  id: z.string(),
  name: z.string(),
  formula: z.string().optional(),
  cas: z.string().optional(),
  role: z.enum(['solute', 'solvent', 'inert']).optional(),
});
export type Component = z.infer<typeof ComponentSchema>;

// Graph
export const LayoutInfoSchema = z.object({
  nodes: z.record(z.string(), z.object({
    x: z.number(),
    y: z.number(),
  })),
});
export type LayoutInfo = z.infer<typeof LayoutInfoSchema>;

export const PortSchema = z.object({
  id: z.string(),
  name: z.string(),
  direction: z.enum(['in', 'out']),
  phase: PhaseSchema.optional(),
});
export type Port = z.infer<typeof PortSchema>;

export const UnitOpNodeSchema = z.object({
  id: z.string(),
  type: UnitTypeSchema,
  name: z.string(),
  params: z.record(z.string(), ParamValueSchema),
  ports: z.array(PortSchema),
  tags: z.array(z.string()).optional(),
});
export type UnitOpNode = z.infer<typeof UnitOpNodeSchema>;

export const StreamSpecSchema = z.object({
  T: QuantitySchema.optional(),
  P: QuantitySchema.optional(),
  flow: QuantitySchema.optional(),
  composition: z.record(z.string(), z.number()).optional(),
  phase: PhaseSchema.optional(),
});
export type StreamSpec = z.infer<typeof StreamSpecSchema>;

export const StreamBoundsSchema = z.object({
  T: z.object({
    min: QuantitySchema,
    max: QuantitySchema,
  }).optional(),
  P: z.object({
    min: QuantitySchema,
    max: QuantitySchema,
  }).optional(),
  flow: z.object({
    min: QuantitySchema,
    max: QuantitySchema,
  }).optional(),
});
export type StreamBounds = z.infer<typeof StreamBoundsSchema>;

export const StreamEdgeSchema = z.object({
  id: z.string(),
  name: z.string(),
  from: z.object({
    nodeId: z.string(),
    portName: z.string(),
  }),
  to: z.object({
    nodeId: z.string(),
    portName: z.string(),
  }),
  spec: StreamSpecSchema.optional(),
  bounds: StreamBoundsSchema.optional(),
});
export type StreamEdge = z.infer<typeof StreamEdgeSchema>;

export const FlowsheetGraphSchema = z.object({
  nodes: z.array(UnitOpNodeSchema),
  edges: z.array(StreamEdgeSchema),
  layout: LayoutInfoSchema.optional(),
});
export type FlowsheetGraph = z.infer<typeof FlowsheetGraphSchema>;

// Specs
export const SpecSchema = z.discriminatedUnion('type', [
  z.object({
    id: z.string(),
    type: z.literal('purity'),
    streamId: z.string(),
    component: z.string(),
    target: z.number(),
  }),
  z.object({
    id: z.string(),
    type: z.literal('recovery'),
    component: z.string(),
    feedStreamId: z.string(),
    productStreamId: z.string(),
    target: z.number(),
  }),
  z.object({
    id: z.string(),
    type: z.literal('capture'),
    component: z.string(),
    ventStreamId: z.string(),
    targetRemoval: z.number(),
  }),
]);
export type Spec = z.infer<typeof SpecSchema>;

export const SpecSetSchema = z.object({
  specs: z.array(SpecSchema),
});
export type SpecSet = z.infer<typeof SpecSetSchema>;

// MetricRef
export const MetricRefSchema = z.discriminatedUnion('kind', [
  z.object({
    kind: z.literal('stream'),
    streamId: z.string(),
    metric: z.enum(['T', 'P', 'flow', 'vaporFrac']),
  }),
  z.object({
    kind: z.literal('unit'),
    nodeId: z.string(),
    metric: z.enum(['dP', 'duty', 'power', 'UA', 'stages']),
  }),
  z.object({
    kind: z.literal('kpi'),
    metric: z.enum(['steam', 'electricity', 'CO2_emissions', 'COM', 'CAPEX_proxy']),
  }),
]);
export type MetricRef = z.infer<typeof MetricRefSchema>;

// Constraints
export const ConstraintSchema = z.discriminatedUnion('type', [
  z.object({
    id: z.string(),
    type: z.literal('max'),
    ref: MetricRefSchema,
    limit: z.number(),
    hard: z.boolean(),
  }),
  z.object({
    id: z.string(),
    type: z.literal('min'),
    ref: MetricRefSchema,
    limit: z.number(),
    hard: z.boolean(),
  }),
  z.object({
    id: z.string(),
    type: z.literal('range'),
    ref: MetricRefSchema,
    min: z.number(),
    max: z.number(),
    hard: z.boolean(),
  }),
]);
export type Constraint = z.infer<typeof ConstraintSchema>;

export const ConstraintSetSchema = z.object({
  constraints: z.array(ConstraintSchema),
});
export type ConstraintSet = z.infer<typeof ConstraintSetSchema>;

// Objective
export const ObjectiveSchema = z.object({
  metric: z.enum(['steam', 'electricity', 'COM', 'CAPEX_proxy']),
  sense: z.enum(['min', 'max']),
  weight: z.number().optional(),
});
export type Objective = z.infer<typeof ObjectiveSchema>;

// EconomicConfig
export const EconomicConfigSchema = z.object({
  steamPrice: z.number().optional(),
  electricityPrice: z.number().optional(),
  co2Price: z.number().optional(),
  capexFactor: z.number().optional(),
  notes: z.string().optional(),
});
export type EconomicConfig = z.infer<typeof EconomicConfigSchema>;

// Project
export const JasperProjectSchema = z.object({
  projectId: z.string(),
  orgId: z.string().optional(),
  name: z.string(),
  createdAt: z.string(),
  updatedAt: z.string(),
  thermodynamics: ThermoConfigSchema,
  components: z.array(ComponentSchema),
  flowsheet: FlowsheetGraphSchema,
  specs: SpecSetSchema,
  constraints: ConstraintSetSchema,
  objective: ObjectiveSchema,
  economics: EconomicConfigSchema.optional(),
  status: ProjectStatusSchema,
  latestVersionId: z.string().optional(),
});
export type JasperProject = z.infer<typeof JasperProjectSchema>;

// Versioning
export const ProjectVersionSchema = z.object({
  versionId: z.string(),
  projectId: z.string(),
  label: z.string(),
  status: ProjectStatusSchema,
  createdAt: z.string(),
  parentVersionId: z.string().optional(),
  snapshotJson: JasperProjectSchema,
  snapshotHash: z.string(),
});
export type ProjectVersion = z.infer<typeof ProjectVersionSchema>;

// Runs
export const SpecResultSchema = z.object({
  specId: z.string(),
  achieved: z.number(),
  target: z.number(),
  ok: z.boolean(),
});
export type SpecResult = z.infer<typeof SpecResultSchema>;

export const ViolationSchema = z.object({
  constraintId: z.string(),
  value: z.number(),
  message: z.string(),
  hard: z.boolean(),
});
export type Violation = z.infer<typeof ViolationSchema>;

export const SimulationRunSchema = z.object({
  runId: z.string(),
  projectId: z.string(),
  versionId: z.string(),
  createdAt: z.string(),
  simulator: z.string(),
  status: RunStatusSchema,
  inputsHash: z.string(),
  converged: z.boolean(),
  kpis: z.record(z.string(), z.number()),
  specResults: z.array(SpecResultSchema),
  violations: z.array(ViolationSchema),
  rawOutputs: z.record(z.string(), z.any()).optional(),
});
export type SimulationRun = z.infer<typeof SimulationRunSchema>;

// Actions
export const JasperActionSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('SET_PARAM'),
    nodeId: z.string(),
    key: z.string(),
    value: ParamValueSchema,
  }),
  z.object({
    type: z.literal('SET_STREAM_SPEC'),
    streamId: z.string(),
    spec: StreamSpecSchema.partial(),
  }),
  z.object({
    type: z.literal('ADD_NODE'),
    node: UnitOpNodeSchema,
  }),
  z.object({
    type: z.literal('REMOVE_NODE'),
    nodeId: z.string(),
  }),
  z.object({
    type: z.literal('ADD_STREAM'),
    edge: StreamEdgeSchema,
  }),
  z.object({
    type: z.literal('REMOVE_STREAM'),
    streamId: z.string(),
  }),
  z.object({
    type: z.literal('REWIRE_STREAM'),
    streamId: z.string(),
    from: z.object({
      nodeId: z.string(),
      portName: z.string(),
    }).optional(),
    to: z.object({
      nodeId: z.string(),
      portName: z.string(),
    }).optional(),
  }),
]);
export type JasperAction = z.infer<typeof JasperActionSchema>;

export const ActionLogEntrySchema = z.object({
  actionId: z.string(),
  projectId: z.string(),
  versionId: z.string(),
  runId: z.string().optional(),
  actor: ActorSchema,
  createdAt: z.string(),
  action: JasperActionSchema,
  rationale: z.string().optional(),
});
export type ActionLogEntry = z.infer<typeof ActionLogEntrySchema>;

// User
export const UserSchema = z.object({
  userId: z.string(),
  email: z.string().optional(),
  name: z.string().optional(),
});
export type User = z.infer<typeof UserSchema>;

