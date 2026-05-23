using DwsimBackend.Models;
using DWSIM.Automation;
using DWSIM.Interfaces;
// Note: Do NOT import DWSIM.Interfaces.Enums — it has a StreamSpec that clashes with our model

namespace DwsimBackend.Services;

/// <summary>
/// Core solver: builds a DWSIM flowsheet from a Jasper project via Automation3,
/// solves it, and extracts results in the same format as the IDAES backend.
///
/// API reference: https://dwsim.org/wiki/index.php?title=Automation
/// Property codes: https://dwsim.org/wiki/index.php?title=Object_Property_Codes
/// </summary>
public static class DwsimSolver
{
    // Jasper unit type -> DWSIM AddFlowsheetObject typename string
    private static readonly Dictionary<string, string> UnitTypeMap = new(StringComparer.OrdinalIgnoreCase)
    {
        ["Flash"] = "Gas-Liquid Separator",
        ["Mixer"] = "Stream Mixer",
        ["Splitter"] = "Stream Splitter",
        ["Heater"] = "Heater",
        ["Cooler"] = "Cooler",
        ["Pump"] = "Pump",
        ["Compressor"] = "Compressor",
        ["Valve"] = "Valve",
        ["HeatExchanger"] = "Heat Exchanger",
        ["DistillationColumn"] = "Distillation Column",
        ["Absorber"] = "Absorption Column",
        ["Stripper"] = "Absorption Column",
        ["RCSTR"] = "Continuous Stirred Tank Reactor (CSTR)",
        ["RPfr"] = "Plug-Flow Reactor (PFR)",
        ["REquil"] = "Equilibrium Reactor",
        ["RGibbs"] = "Gibbs Reactor",
        ["RStoic"] = "Conversion Reactor",
        ["RYield"] = "Conversion Reactor",
    };

    public static readonly string[] SupportedUnitTypes =
        UnitTypeMap.Keys.Concat(new[] { "Feed", "Sink" }).ToArray();

    public static Dictionary<string, object> Solve(
        JasperProject project, SimulationOptions options, List<string> messages)
    {
        var startTime = DateTime.UtcNow;

        ValidateCompositions(project);

        // DWSIM needs its install dir as CWD for loading compound databases
        var dwsimPath = Environment.GetEnvironmentVariable("DWSIM_PATH") ?? "/usr/local/lib/dwsim";
        var originalDir = Directory.GetCurrentDirectory();
        Directory.SetCurrentDirectory(dwsimPath);

        // Create flowsheet via Automation3
        var interf = new Automation3();
        var flowsheet = interf.CreateFlowsheet();
        messages.Add("DWSIM flowsheet created");

        // Add components (IFlowsheet.AddCompound)
        var compCount = 0;
        foreach (var comp in project.Components)
        {
            bool added = false;

            // Try CAS number first
            if (!string.IsNullOrEmpty(comp.Cas))
            {
                try { flowsheet.AddCompound(comp.Cas); added = true; compCount++; } catch { }
            }

            if (!added)
            {
                try { flowsheet.AddCompound(comp.Name); added = true; compCount++; } catch { }
            }

            if (!added && !string.IsNullOrEmpty(comp.Formula))
            {
                try { flowsheet.AddCompound(comp.Formula); added = true; compCount++; } catch { }
            }

            if (!added)
                messages.Add($"Warning: Component '{comp.Name}' (CAS: {comp.Cas}) not found in DWSIM database");
        }
        messages.Add($"Components loaded: {compCount}/{project.Components.Count}");

        // Add property package (IFlowsheet.CreateAndAddPropertyPackage)
        var ppName = MapPropertyPackageName(project.Thermodynamics);
        string actualPP = ppName;
        try
        {
            var pp = flowsheet.CreateAndAddPropertyPackage(ppName);
            if (pp == null)
            {
                messages.Add($"Warning: CreateAndAddPropertyPackage('{ppName}') returned null, trying fallback");
                pp = flowsheet.CreateAndAddPropertyPackage("Peng-Robinson (PR)");
                actualPP = pp != null ? "Peng-Robinson (PR)" : "unknown";
            }
            messages.Add($"Property package: {actualPP}");
        }
        catch (Exception ex)
        {
            messages.Add($"Warning: Could not add property package '{ppName}': {ex.Message}. Trying Peng-Robinson.");
            try
            {
                flowsheet.CreateAndAddPropertyPackage("Peng-Robinson (PR)");
                actualPP = "Peng-Robinson (PR)";
            }
            catch (Exception ex2)
            {
                messages.Add($"Error: Fallback also failed: {ex2.Message}");
                actualPP = "none";
            }
        }

        // Track Feed/Sink vs unit operations
        var feedNodes = new HashSet<string>();
        var sinkNodes = new HashSet<string>();
        var nodeMap = new Dictionary<string, ISimulationObject>();

        // Create unit operations (IFlowsheet.AddFlowsheetObject)
        foreach (var node in project.Flowsheet.Nodes)
        {
            if (node.Type == "Feed")
            {
                feedNodes.Add(node.Id);
            }
            else if (node.Type == "Sink")
            {
                sinkNodes.Add(node.Id);
            }
            else if (UnitTypeMap.TryGetValue(node.Type, out var dwsimTypeName))
            {
                try
                {
                    var obj = flowsheet.AddFlowsheetObject(dwsimTypeName, node.Id);
                    if (obj != null)
                    {
                        nodeMap[node.Id] = obj;
                        messages.Add($"Created unit: {node.Name} ({dwsimTypeName})");
                    }
                }
                catch (Exception ex)
                {
                    messages.Add($"Warning: Could not create unit '{node.Name}': {ex.Message}");
                }
            }
            else
            {
                messages.Add($"Warning: Unsupported unit type '{node.Type}' for node '{node.Name}'");
            }
        }

        // Create material streams from edges
        var streamMap = new Dictionary<string, ISimulationObject>();
        foreach (var edge in project.Flowsheet.Edges)
        {
            try
            {
                var stream = flowsheet.AddFlowsheetObject("Material Stream", edge.Id);
                if (stream == null)
                {
                    messages.Add($"Warning: AddFlowsheetObject returned null for stream {edge.Id}");
                    continue;
                }
                streamMap[edge.Id] = stream;

                // Set stream conditions from spec
                if (edge.Spec != null)
                {
                    try
                    {
                        SetStreamConditions(stream, edge.Spec, project.Components, messages);
                    }
                    catch (Exception ex)
                    {
                        messages.Add($"Warning: SetStreamConditions failed for {edge.Id}: {ex.Message}");
                    }
                }

                // Connect to source unit (using IGraphicObject)
                if (!feedNodes.Contains(edge.From.NodeId) &&
                    nodeMap.TryGetValue(edge.From.NodeId, out var srcUnit))
                {
                    try
                    {
                        flowsheet.ConnectObjects(
                            srcUnit.GraphicObject, stream.GraphicObject,
                            MapPortIndex(edge.From.PortName, "out"),
                            MapPortIndex("in", "in"));
                    }
                    catch (Exception ex)
                    {
                        messages.Add($"Warning: Connect {edge.From.NodeId} -> {edge.Id}: {ex.Message}");
                    }
                }

                // Connect to destination unit
                if (!sinkNodes.Contains(edge.To.NodeId) &&
                    nodeMap.TryGetValue(edge.To.NodeId, out var dstUnit))
                {
                    try
                    {
                        flowsheet.ConnectObjects(
                            stream.GraphicObject, dstUnit.GraphicObject,
                            0, MapPortIndex(edge.To.PortName, "in"));
                    }
                    catch (Exception ex)
                    {
                        messages.Add($"Warning: Connect {edge.Id} -> {edge.To.NodeId}: {ex.Message}");
                    }
                }
            }
            catch (Exception ex)
            {
                messages.Add($"Warning: Could not create stream {edge.Id}: {ex.Message}");
            }
        }

        messages.Add("Flowsheet built successfully");

        // Solve via Automation3.CalculateFlowsheet4 (returns List<Exception>)
        bool converged = false;
        string solverStatus = "not_solved";

        try
        {
            var errors = interf.CalculateFlowsheet4(flowsheet);
            if (errors == null || errors.Count == 0)
            {
                converged = true;
                solverStatus = "optimal";
                messages.Add("Flowsheet solved successfully");
            }
            else
            {
                solverStatus = "warning";
                foreach (var err in errors)
                    messages.Add($"Solver warning: {err.Message}");
                converged = errors.All(e =>
                    e.Message?.Contains("warning", StringComparison.OrdinalIgnoreCase) == true);
            }
        }
        catch (Exception ex)
        {
            solverStatus = "error";
            messages.Add($"Solver error: {ex.Message}");
        }

        var solveTime = (DateTime.UtcNow - startTime).TotalSeconds;

        // Extract results
        var streamResults = ExtractStreamResults(project, streamMap, messages);
        var unitResults = ExtractUnitResults(project, feedNodes, sinkNodes, nodeMap);

        try { interf.ReleaseResources(); } catch { }
        try { Directory.SetCurrentDirectory(originalDir); } catch { }

        return new Dictionary<string, object>
        {
            ["status"] = converged ? "success" : "warning",
            ["converged"] = converged,
            ["solver_status"] = solverStatus,
            ["iterations"] = 0,
            ["solve_time"] = solveTime,
            ["streams"] = streamResults,
            ["units"] = unitResults,
            ["degrees_of_freedom"] = 0,
            ["messages"] = messages,
        };
    }

    private static void ValidateCompositions(JasperProject project)
    {
        foreach (var edge in project.Flowsheet.Edges)
        {
            if (edge.Spec?.Composition == null) continue;
            var total = edge.Spec.Composition.Values.Sum();
            if (Math.Abs(total - 1.0) > 0.001)
                throw new ArgumentException(
                    $"Stream {edge.Id}: composition sums to {total:F4} (must be within 0.999-1.001).");
        }
    }

    private static string MapPropertyPackageName(ThermodynamicsConfig config)
    {
        var method = config.PropertyMethod?.ToUpperInvariant() ?? "IDEAL";
        return method switch
        {
            "PR" or "PENG-ROBINSON" => "Peng-Robinson (PR)",
            "SRK" or "SOAVE-REDLICH-KWONG" => "Soave-Redlich-Kwong (SRK)",
            "NRTL" => "NRTL",
            "UNIQUAC" => "UNIQUAC",
            "UNIFAC" => "UNIFAC",
            "STEAM" or "IAPWS" => "Steam Tables (IAPWS-IF97)",
            "IDEAL" or "RAOULTS" => "Raoult's Law",
            _ => "Peng-Robinson (PR)",
        };
    }

    /// <summary>
    /// Set stream T, P, flow, composition via ISimulationObject.SetPropertyValue.
    /// Property codes from: https://dwsim.org/wiki/index.php?title=Object_Property_Codes
    /// </summary>
    private static void SetStreamConditions(
        ISimulationObject stream, StreamSpec spec, List<Component> components, List<string> messages)
    {
        // Cast to IMaterialStream for direct phase/compound access
        var ms = stream as IMaterialStream;
        if (ms == null)
        {
            messages.Add($"  Warning: stream is not IMaterialStream (type={stream.GetType().FullName})");
            SetStreamConditionsFallback(stream, spec, components, messages);
            return;
        }

        var overall = ms.Phases[0]; // Phase 0 = Overall mixture

        // Temperature (K) — use SetPropertyValue for proper spec registration
        if (spec.T != null)
            stream.SetPropertyValue("PROP_MS_0", ConvertToKelvin(spec.T.Value, spec.T.Unit));

        // Pressure (Pa)
        if (spec.P != null)
            stream.SetPropertyValue("PROP_MS_1", ConvertToPascal(spec.P.Value, spec.P.Unit));

        // Molar flow (mol/s) — PROP_MS_3 is molar flow
        if (spec.Flow != null)
            stream.SetPropertyValue("PROP_MS_3", ConvertToMolPerSecond(spec.Flow.Value, spec.Flow.Unit));

        // Composition: set via SetOverallComposition or direct compound access
        if (spec.Composition != null)
        {
            var compNames = overall.Compounds.Keys.ToList();
            var fractions = new double[compNames.Count];

            for (int i = 0; i < compNames.Count; i++)
            {
                // Match DWSIM compound name to Jasper component ID
                foreach (var comp in components)
                {
                    if (spec.Composition.TryGetValue(comp.Id, out var frac))
                    {
                        if (string.Equals(compNames[i], comp.Name, StringComparison.OrdinalIgnoreCase) ||
                            string.Equals(compNames[i], comp.Formula, StringComparison.OrdinalIgnoreCase) ||
                            string.Equals(compNames[i], comp.Cas, StringComparison.OrdinalIgnoreCase))
                        {
                            fractions[i] = frac;
                            break;
                        }
                    }
                }
            }

            try
            {
                ms.SetOverallComposition(fractions);
            }
            catch (Exception ex)
            {
                messages.Add($"Warning: SetOverallComposition failed for stream, using fallback: {ex.Message}");
                for (int i = 0; i < compNames.Count && i < fractions.Length; i++)
                {
                    try { overall.Compounds[compNames[i]].MoleFraction = fractions[i]; }
                    catch { }
                }
            }
        }

        // Vapor fraction
        if (spec.VaporFraction.HasValue)
        {
            overall.Properties.molarfraction = spec.VaporFraction.Value;
        }
    }

    /// <summary>Fallback for non-IMaterialStream objects using property codes.</summary>
    private static void SetStreamConditionsFallback(
        ISimulationObject stream, StreamSpec spec, List<Component> components, List<string> messages)
    {
        if (spec.T != null)
            try { stream.SetPropertyValue("PROP_MS_0", ConvertToKelvin(spec.T.Value, spec.T.Unit)); } catch { }
        if (spec.P != null)
            try { stream.SetPropertyValue("PROP_MS_1", ConvertToPascal(spec.P.Value, spec.P.Unit)); } catch { }
        if (spec.Flow != null)
            try { stream.SetPropertyValue("PROP_MS_3", ConvertToMolPerSecond(spec.Flow.Value, spec.Flow.Unit)); } catch { }
    }

    private static List<Models.StreamResult> ExtractStreamResults(
        JasperProject project,
        Dictionary<string, ISimulationObject> streamMap, List<string> messages)
    {
        var results = new List<Models.StreamResult>();

        foreach (var edge in project.Flowsheet.Edges)
        {
            if (!streamMap.TryGetValue(edge.Id, out var stream)) continue;

            try
            {
                var ms = stream as IMaterialStream;
                double temperature = 0, pressure = 0, flowMol = 0, flowMass = 0;
                double vaporFraction = 0, mw = 0;
                double? enthalpy = null, entropy = null, density = null;
                var composition = new Dictionary<string, double>();

                if (ms != null)
                {
                    var overall = ms.Phases[0];
                    temperature = overall.Properties.temperature ?? 0;
                    pressure = overall.Properties.pressure ?? 0;
                    flowMol = overall.Properties.molarflow ?? 0;
                    flowMass = overall.Properties.massflow ?? 0;
                    mw = overall.Properties.molecularWeight ?? 0;
                    enthalpy = overall.Properties.enthalpy;
                    entropy = overall.Properties.entropy;
                    density = overall.Properties.density;

                    // Vapor fraction from Phase 2 (Vapor)
                    var vapor = ms.Phases.ContainsKey(2) ? ms.Phases[2] : null;
                    vaporFraction = vapor?.Properties?.molarfraction ?? 0;

                    // Extract composition from Phase 0 compounds
                    foreach (var comp in project.Components)
                    {
                        double frac = 0;
                        // Try matching by name
                        foreach (var kvp in overall.Compounds)
                        {
                            if (string.Equals(kvp.Key, comp.Name, StringComparison.OrdinalIgnoreCase) ||
                                string.Equals(kvp.Key, comp.Formula, StringComparison.OrdinalIgnoreCase))
                            {
                                frac = kvp.Value.MoleFraction.GetValueOrDefault();
                                break;
                            }
                        }
                        composition[comp.Id] = frac;
                    }
                }
                else
                {
                    // Fallback to property codes
                    try { temperature = Convert.ToDouble(stream.GetPropertyValue("PROP_MS_0")); } catch { }
                    try { pressure = Convert.ToDouble(stream.GetPropertyValue("PROP_MS_1")); } catch { }
                    try { flowMol = Convert.ToDouble(stream.GetPropertyValue("PROP_MS_3")); } catch { }
                    try { flowMass = Convert.ToDouble(stream.GetPropertyValue("PROP_MS_2")); } catch { }
                    foreach (var comp in project.Components)
                        composition[comp.Id] = 0;
                }

                string phase = vaporFraction > 0.999 ? "V" : vaporFraction < 0.001 ? "L" : "VL";

                results.Add(new Models.StreamResult(
                    Id: edge.Id,
                    FromNode: edge.From.NodeId,
                    ToNode: edge.To.NodeId,
                    Temperature: temperature,
                    Pressure: pressure,
                    FlowMol: flowMol,
                    FlowMass: flowMass,
                    Phase: phase,
                    VaporFraction: vaporFraction,
                    Composition: composition,
                    Enthalpy: enthalpy,
                    Entropy: entropy,
                    Density: density,
                    MolecularWeight: mw
                ));
            }
            catch (Exception ex)
            {
                messages.Add($"Warning: Could not extract results for stream {edge.Id}: {ex.Message}");
            }
        }

        return results;
    }

    private static List<Models.UnitResult> ExtractUnitResults(
        JasperProject project, HashSet<string> feedNodes, HashSet<string> sinkNodes,
        Dictionary<string, ISimulationObject> nodeMap)
    {
        var results = new List<Models.UnitResult>();

        foreach (var node in project.Flowsheet.Nodes)
        {
            if (feedNodes.Contains(node.Id) || sinkNodes.Contains(node.Id))
            {
                results.Add(new Models.UnitResult(Id: node.Id, Name: node.Name, Type: node.Type));
                continue;
            }

            if (!nodeMap.TryGetValue(node.Id, out var unitObj))
                continue;

            double? duty = null, work = null;
            // Duty/work property codes are unit-type specific
            switch (node.Type)
            {
                case "Heater":
                    duty = TryGetProperty(unitObj, "PROP_HT_1"); // Heat duty (kW)
                    break;
                case "Cooler":
                    duty = TryGetProperty(unitObj, "PROP_CL_1"); // Heat duty (kW)
                    break;
                case "HeatExchanger":
                    duty = TryGetProperty(unitObj, "PROP_HX_1"); // Heat exchanged (kW)
                    break;
                case "Pump":
                    work = TryGetProperty(unitObj, "PROP_PU_4"); // Power (kW)
                    break;
                case "Compressor":
                    work = TryGetProperty(unitObj, "PROP_CO_3"); // Power (kW)
                    break;
                // Flash/Mixer/Splitter/Valve have no duty/work
            }

            results.Add(new Models.UnitResult(
                Id: node.Id, Name: node.Name, Type: node.Type,
                Duty: duty, Work: work));
        }

        return results;
    }

    private static double? TryGetProperty(ISimulationObject obj, string propCode)
    {
        try
        {
            var val = obj.GetPropertyValue(propCode);
            if (val == null) return null;
            var d = Convert.ToDouble(val);
            // Filter out nonsensical defaults (T/P values that are clearly not duty/work)
            return double.IsNaN(d) || double.IsInfinity(d) ? null : d;
        }
        catch { return null; }
    }

    /// <summary>
    /// Maps a Jasper canonical port name to a DWSIM port index.
    /// Canonical names are defined in idaes-backend/app/data/unit_definitions.py (source of truth).
    /// NEVER silently fall through to 0 — unknown port names indicate a schema bug and must raise.
    /// </summary>
    private static int MapPortIndex(string portName, string direction) =>
        portName.ToLowerInvariant() switch
        {
            // Single-port blocks
            "in" or "inlet" or "feed" or "input" => 0,
            "out" or "outlet" or "product" or "output" => 0,

            // Multi-inlet Mixer (canonical in{n}, alias inlet{n}/feed{n})
            "in1" or "inlet1" or "feed1" => 0,
            "in2" or "inlet2" or "feed2" => 1,
            "in3" or "inlet3" or "feed3" => 2,
            "in4" or "inlet4" or "feed4" => 3,
            "in5" or "inlet5" or "feed5" => 4,
            "in6" or "inlet6" or "feed6" => 5,
            "in7" or "inlet7" or "feed7" => 6,
            "in8" or "inlet8" or "feed8" => 7,

            // Multi-outlet Splitter (canonical out{n}, alias outlet{n}/product{n})
            "out1" or "outlet1" or "product1" => 0,
            "out2" or "outlet2" or "product2" => 1,
            "out3" or "outlet3" or "product3" => 2,
            "out4" or "outlet4" or "product4" => 3,
            "out5" or "outlet5" or "product5" => 4,
            "out6" or "outlet6" or "product6" => 5,
            "out7" or "outlet7" or "product7" => 6,
            "out8" or "outlet8" or "product8" => 7,

            // Flash / 2-phase separator — DWSIM has vapor on port 0, liquid on port 1
            "vapor" or "vap" or "v" => 0,
            "liquid" or "liq" or "l" => 1,

            // Distillation column — overhead (canonical) with legacy aliases
            "overhead" or "distillate" or "top" or "tops" => 0,
            "bottoms" or "bottom" or "btms" => 1,

            // Heat exchanger — hot side ports 0/1, cold side ports 2/3
            "hot-in" or "hot_inlet" or "shell-in" => 0,
            "hot-out" or "hot_outlet" or "shell-out" => 1,
            "cold-in" or "cold_inlet" or "tube-in" => 2,
            "cold-out" or "cold_outlet" or "tube-out" => 3,

            // Absorber / Stripper — DWSIM Absorption Column uses the same index layout
            "gas-in" or "vapor-in" => 0,
            "gas-out" or "vapor-out" => 1,
            "liquid-in" => 2,
            "liquid-out" => 3,

            // Two-product splitter alt names (light/heavy for LLE)
            "light" => 0,
            "heavy" => 1,

            // Three-phase separator (extra aqueous phase port)
            "aqueous" => 2,

            _ => throw new ArgumentException(
                $"Unknown port name '{portName}' (direction={direction}). " +
                "Add it to MapPortIndex in DwsimSolver.cs or use a canonical name from " +
                "idaes-backend/app/data/unit_definitions.py."),
        };

    private static double ConvertToKelvin(double value, string unit) =>
        unit.ToUpperInvariant() switch
        {
            "K" or "KELVIN" => value,
            "C" or "CELSIUS" or "DEGC" or "DEG_C" => value + 273.15,
            "F" or "FAHRENHEIT" or "DEGF" or "DEG_F" => (value - 32) * 5.0 / 9.0 + 273.15,
            "R" or "RANKINE" => value * 5.0 / 9.0,
            _ => value,
        };

    private static double ConvertToPascal(double value, string unit) =>
        unit.ToUpperInvariant() switch
        {
            "PA" or "PASCAL" => value,
            "KPA" => value * 1e3,
            "MPA" => value * 1e6,
            "BAR" => value * 1e5,
            "ATM" => value * 101325,
            "PSI" or "PSIA" => value * 6894.757,
            "MMHG" or "TORR" => value * 133.322,
            _ => value,
        };

    private static double ConvertToMolPerSecond(double value, string unit) =>
        unit.ToUpperInvariant() switch
        {
            "MOL/S" => value,
            "KMOL/S" => value * 1000,
            "MOL/H" => value / 3600,
            "KMOL/H" => value * 1000 / 3600,
            "MOL/MIN" => value / 60,
            "KMOL/MIN" => value * 1000 / 60,
            _ => value,
        };
}
