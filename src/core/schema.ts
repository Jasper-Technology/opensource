import { z } from 'zod';

// Basic types
export type ID = string;

export const QuantitySchema = z.object({
  value: z.number(),
  unit: z.string(),
});
export type Quantity = z.infer<typeof QuantitySchema>;

// Per-reactor reaction entry. Stoichiometry is stored as positive
// magnitudes; the reactant/product role lives in which dict it's listed
// under. `spec` carries the kinetics/equilibrium/conversion knob that
// distinguishes RStoic vs REquil vs RCSTR/RPfr — one schema covers all
// four so the editor and sanitizer can stay generic.
//
// spec.kind:
//   'conversion' — RStoic. Fractional extent on a reference reactant.
//   'keq'        — REquil. Equilibrium constant (or 'auto' to compute
//                  from ΔG at the operating T).
//   'kinetic'    — RCSTR / RPfr. Arrhenius A + Ea + per-reactant order;
//                  solver integrates over residence time.
export const ReactionSpecSchema = z.discriminatedUnion('kind', [
  z.object({
    kind: z.literal('conversion'),
    conversion: z.number().min(0).max(1),
    referenceComponent: z.string(),
  }),
  z.object({
    kind: z.literal('keq'),
    keq: z.number().optional(),    // undefined → compute from ΔG at T
  }),
  z.object({
    kind: z.literal('kinetic'),
    A: z.number(),                  // pre-exponential, in chosen units
    Ea: z.number(),                 // activation energy, J/mol
    T_ref: z.number().optional(),
    orders: z.record(z.string(), z.number()).optional(),
  }),
]);
export type ReactionSpec = z.infer<typeof ReactionSpecSchema>;

export const ReactionEntrySchema = z.object({
  id: z.string(),
  reactants: z.record(z.string(), z.number()),
  products: z.record(z.string(), z.number()),
  spec: ReactionSpecSchema,
});
export type ReactionEntry = z.infer<typeof ReactionEntrySchema>;

// Back-compat alias — earlier code referenced RStoicReaction. New code
// should use ReactionEntry directly.
export const RStoicReactionSchema = ReactionEntrySchema;
export type RStoicReaction = ReactionEntry;

// ParamValue union
export const ParamValueSchema = z.discriminatedUnion('kind', [
  z.object({ kind: z.literal('quantity'), q: QuantitySchema }),
  z.object({ kind: z.literal('number'), x: z.number() }),
  z.object({ kind: z.literal('int'), n: z.number().int() }),
  z.object({ kind: z.literal('string'), s: z.string() }),
  z.object({ kind: z.literal('boolean'), b: z.boolean() }),
  z.object({ kind: z.literal('enum'), e: z.string() }),
  z.object({ kind: z.literal('composition'), comp: z.record(z.string(), z.number()) }), // Mole fractions by component ID
  z.object({ kind: z.literal('reactionSet'), reactions: z.array(ReactionEntrySchema) }),
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
  'Expander',             // Phase 2 — gas expansion / turbine
  'Valve',
  'Heater',
  'Cooler',
  'HeatExchanger',
  'PipeSegment',          // Phase 2 — friction + elevation pressure drop (DWSIM-only)
  'Absorber',
  'Stripper',
  'DistillationColumn',
  'ShortcutDistillation', // Phase 2 — Fenske–Underwood–Gilliland (DWSIM-only)
  'ReactiveDistillation', // Phase 2 — reactive distillation column (DWSIM-only)
  'Reactor',   // legacy — kept for backward compat
  'RCSTR',     // Continuous Stirred Tank Reactor (Aspen RCSTR)
  'RPfr',      // Plug Flow Reactor (Aspen RPlug)
  'RBatch',    // Batch Reactor (Aspen RBatch)
  'RStoic',    // Stoichiometric Reactor (Aspen RStoic)
  'RYield',    // Yield Reactor (Aspen RYield)
  'REquil',    // Equilibrium Reactor (Aspen REquil)
  'RGibbs',    // Gibbs Free Energy Reactor (Aspen RGibbs)
  'Separator',
  'ThreePhaseSeparator',  // Phase 2 — gas-oil-water (DWSIM-only)
  'Sink',
  'TextBox',
  'CustomUnit',           // Agent-defined block that delegates to a baseType + overrides
]);
export type UnitType = z.infer<typeof UnitTypeSchema>;

// CustomUnit — an agent-proposed unit op for edge cases not covered by the
// built-in catalog. It does NOT introduce new physics: at solve time the unit
// unwraps to its `baseType` with `overrides` merged into params, so all three
// engines (Jasper, DWSIM, IDAES) keep working unchanged.
//
// `sources` and `equations` are user-facing audit trail (rendered on the
// Validation Card and in NodePanel); the simulator ignores them. A CustomUnit
// without a customSpec is a validation error — see src/sim/validator.ts.
export const CustomUnitSourceSchema = z.object({
  title: z.string(),
  url: z.string().optional(),
  doi: z.string().optional(),
  snippet: z.string().optional(),
});
export type CustomUnitSource = z.infer<typeof CustomUnitSourceSchema>;

// Agent-defined equipment sizing for a CustomUnit. `method: 'inherit'` reuses the
// baseType's built-in correlation; `method: 'formula'` evaluates a sandboxed
// arithmetic `expression` (whitelisted math + named result variables — see
// src/sim/sizing/safeEval.ts) to produce `sizeQuantity`. Always flagged
// "agent-defined" in the UI and never executed as code; `source`/`assumptions`
// are the audit trail, matching the cost-DB provenance ethos.
export const CustomSizingSpecSchema = z.object({
  sizeQuantity: z.enum(['area', 'volume', 'power', 'heat_duty']),
  method: z.enum(['inherit', 'formula']).default('inherit'),
  expression: z.string().optional(),                      // required when method === 'formula'
  variables: z.record(z.string(), z.number()).default({}),// named constants the expression may reference (e.g. tau, U)
  assumptions: z.array(z.string()).default([]),
  source: z.string().optional(),
});
export type CustomSizingSpec = z.infer<typeof CustomSizingSpecSchema>;

export const CustomUnitSpecSchema = z.object({
  name: z.string(),
  description: z.string().optional(),
  baseType: z.string(),                                   // a UnitType (string-typed to avoid circular ref to UnitTypeSchema)
  overrides: z.record(z.string(), ParamValueSchema).default({}),
  sources: z.array(CustomUnitSourceSchema).default([]),
  equations: z.array(z.string()).default([]),             // free-form prose / LaTeX strings
  sizing: CustomSizingSpecSchema.optional(),              // agent-defined sizing; absent → inherit baseType
});
export type CustomUnitSpec = z.infer<typeof CustomUnitSpecSchema>;

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

// Reactions
export const ArrheniusKineticsSchema = z.object({
  A: z.number(),      // pre-exponential factor
  Ea: z.number(),     // activation energy (J/mol)
  T_ref: z.number().optional(),
});
export type ArrheniusKinetics = z.infer<typeof ArrheniusKineticsSchema>;

export const ReactionSchema = z.object({
  id: z.string(),
  stoichiometry: z.record(z.string(), z.number()), // component formula -> signed coefficient
  type: z.enum(['rate', 'equilibrium']).default('rate'),
  rate_constant: z.number().optional(),
  equilibrium_constant: z.number().optional(),
  arrhenius: ArrheniusKineticsSchema.optional(),
  concentration_orders: z.record(z.string(), z.number()).optional(),
});
export type Reaction = z.infer<typeof ReactionSchema>;

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
  customSpec: CustomUnitSpecSchema.optional(),            // set when type === 'CustomUnit'
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
export const VaryHandleSchema = z.object({
  unitId: z.string(),
  param: z.string(),  // dotted path, e.g. "reflux_ratio" or "outlet.temperature"
});
export type VaryHandle = z.infer<typeof VaryHandleSchema>;

export const SpecSchema = z.discriminatedUnion('type', [
  z.object({
    id: z.string(),
    type: z.literal('purity'),
    streamId: z.string(),
    component: z.string(),
    target: z.number(),
    vary: VaryHandleSchema.optional(),
  }),
  z.object({
    id: z.string(),
    type: z.literal('recovery'),
    component: z.string(),
    feedStreamId: z.string(),
    productStreamId: z.string(),
    target: z.number(),
    vary: VaryHandleSchema.optional(),
  }),
  z.object({
    id: z.string(),
    type: z.literal('capture'),
    component: z.string(),
    ventStreamId: z.string(),
    targetRemoval: z.number(),
    vary: VaryHandleSchema.optional(),
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
  operatingHours: z.number().optional(), // h/yr annualization basis (default 8000)
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
  flowsheet: FlowsheetGraphSchema, // Main flowsheet (for backward compatibility)
  flowsheets: z.array(z.object({
    id: z.string(),
    name: z.string(),
    graph: FlowsheetGraphSchema,
  })).optional(), // Multiple flowsheet tabs
  activeFlowsheetId: z.string().optional(), // Currently active tab
  reactions: z.array(ReactionSchema).optional(),
  specs: SpecSetSchema,
  constraints: ConstraintSetSchema,
  objective: ObjectiveSchema,
  economics: EconomicConfigSchema.optional(),
  status: ProjectStatusSchema,
  latestVersionId: z.string().optional(),
  cloudSynced: z.boolean().optional(), // true once pushed to Supabase via Share
  collaboratorRole: z.enum(['owner', 'editor', 'viewer']).optional(), // role of current user
  _v: z.number().int().optional(), // monotonic write counter, incremented on every Supabase save
  customUnitTypes: z.array(CustomUnitSpecSchema).optional(), // reusable CustomUnit definitions (Validation-Card approved)
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
  iterations: z.number().int().optional(),  // number of solver iterations used
  handle: z.string().optional(),            // human-readable handle description
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
  // Strip a parameter entirely — different from SET_PARAM to "0", which
  // some units (Flash T, Heater duty, …) treat as a literal zero rather
  // than "unspec". Use this to make a Flash adiabatic, a Heater
  // duty-free, etc.
  z.object({
    type: z.literal('REMOVE_PARAM'),
    nodeId: z.string(),
    key: z.string(),
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

