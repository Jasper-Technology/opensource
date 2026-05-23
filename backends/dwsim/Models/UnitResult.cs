using System.Text.Json.Serialization;

namespace DwsimBackend.Models;

/// <summary>
/// Matches the Pydantic UnitResult from the IDAES backend exactly.
/// </summary>
public record UnitResult(
    string Id,
    string Name,
    string Type,
    double? Duty = null,
    double? Work = null,
    [property: JsonPropertyName("pressure_drop")] double? PressureDrop = null,
    double? Efficiency = null,
    [property: JsonPropertyName("custom_results")] Dictionary<string, object>? CustomResults = null
);
