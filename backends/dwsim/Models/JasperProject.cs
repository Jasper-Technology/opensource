using System.Text.Json.Serialization;

namespace DwsimBackend.Models;

/// <summary>
/// Matches the Pydantic JasperProject schema from the IDAES backend.
/// These models define the structure exchanged with the Jasper frontend.
/// </summary>

public record Quantity(
    string Kind,
    double Value,
    string Unit
);

public record PortReference(
    string NodeId,
    string PortName
);

public record Component(
    string Id,
    string Name,
    string? Formula = null,
    [property: JsonPropertyName("casNumber")] string? Cas = null
);

public record ThermodynamicsConfig(
    string PropertyMethod = "Ideal",
    string? Eos = null,
    string? ActivityModel = null
);

public record StreamSpec(
    Quantity? T = null,
    Quantity? P = null,
    Quantity? Flow = null,
    Dictionary<string, double>? Composition = null,
    double? VaporFraction = null,
    string? Phase = null
);

public record FlowsheetNode(
    string Id,
    string Type,
    string Name,
    double? X = null,
    double? Y = null,
    Dictionary<string, object>? Params = null
)
{
    public Dictionary<string, object> Params { get; init; } = Params ?? new();
}

public record FlowsheetEdge(
    string Id,
    [property: JsonPropertyName("from")] PortReference From,
    PortReference To,
    StreamSpec? Spec = null,
    string? Label = null
);

public record Flowsheet(
    List<FlowsheetNode> Nodes,
    List<FlowsheetEdge> Edges
);

public record Reaction(
    string Id,
    Dictionary<string, double> Stoichiometry,
    string Type = "rate",
    double? RateConstant = null,
    double? EquilibriumConstant = null
);

public record JasperProject(
    string? ProjectId,
    string Name,
    ThermodynamicsConfig Thermodynamics,
    List<Component> Components,
    Flowsheet Flowsheet,
    List<Reaction>? Reactions = null
)
{
    public ThermodynamicsConfig Thermodynamics { get; init; } = Thermodynamics ?? new();
}
