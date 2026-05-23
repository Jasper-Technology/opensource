using System.Text.Json.Serialization;

namespace DwsimBackend.Models;

/// <summary>
/// Matches the Pydantic StreamResult from the IDAES backend exactly.
/// </summary>
public record StreamResult(
    string Id,
    [property: JsonPropertyName("from_node")] string FromNode,
    [property: JsonPropertyName("to_node")] string ToNode,
    double Temperature,
    double Pressure,
    [property: JsonPropertyName("flow_mol")] double FlowMol,
    [property: JsonPropertyName("flow_mass")] double FlowMass,
    string Phase,
    [property: JsonPropertyName("vapor_fraction")] double VaporFraction,
    Dictionary<string, double> Composition,
    double? Enthalpy = null,
    double? Entropy = null,
    double? Density = null,
    [property: JsonPropertyName("molecular_weight")] double MolecularWeight = 0
);
