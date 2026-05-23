namespace DwsimBackend.Models;

public record SimulationOptions(
    int MaxIterations = 100,
    double Tolerance = 1e-6
);

public record SimulateRequest(
    JasperProject Project,
    SimulationOptions? Options = null
);
