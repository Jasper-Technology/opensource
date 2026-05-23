using DwsimBackend.Models;

namespace DwsimBackend.Services;

/// <summary>
/// Maps Jasper thermodynamics configuration to DWSIM property package names.
/// Used by DwsimSolver via Automation3.AddPropertyPackage(flowsheet, name).
/// </summary>
public static class PropertyPackageMapper
{
    /// <summary>
    /// Map Jasper thermo config to a DWSIM property package name string.
    /// </summary>
    public static string GetPackageName(ThermodynamicsConfig config)
    {
        var method = config.PropertyMethod?.ToUpperInvariant() ?? "IDEAL";

        return method switch
        {
            "PR" or "PENG-ROBINSON" => "Peng-Robinson (PR)",
            "SRK" or "SOAVE-REDLICH-KWONG" => "SRK",
            "NRTL" => "NRTL",
            "UNIQUAC" => "UNIQUAC",
            "UNIFAC" => "UNIFAC",
            "STEAM" or "IAPWS" => "Steam Tables (IAPWS-IF97)",
            "IDEAL" or "RAOULTS" => "Raoult's Law",
            _ => "Peng-Robinson (PR)",
        };
    }

    /// <summary>
    /// Returns the list of supported thermo methods and their DWSIM names.
    /// </summary>
    public static Dictionary<string, string> SupportedMethods => new()
    {
        ["Ideal"] = "Raoult's Law",
        ["PR"] = "Peng-Robinson",
        ["SRK"] = "SRK",
        ["NRTL"] = "NRTL",
        ["UNIQUAC"] = "UNIQUAC",
        ["UNIFAC"] = "UNIFAC",
        ["Steam"] = "Steam Tables (IAPWS-IF97)",
    };
}
