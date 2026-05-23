using System.Reflection;
using System.Text.Json;
using System.Text.Json.Serialization;
using DwsimBackend.Middleware;
using DwsimBackend.Models;
using DwsimBackend.Services;

// ──────────────────────────────────────────────
// DWSIM assembly resolver — must run before any DWSIM types are loaded.
// DWSIM dynamically loads many assemblies; without this, you get
// FileNotFoundException for transitive dependencies.
// ──────────────────────────────────────────────
var dwsimPath = Environment.GetEnvironmentVariable("DWSIM_PATH") ?? "/usr/local/lib/dwsim";

// Assembly resolver for DWSIM's transitive dependencies
AppDomain.CurrentDomain.AssemblyResolve += (_, args) =>
{
    var name = new AssemblyName(args.Name).Name + ".dll";
    var path = Path.Combine(dwsimPath, name);
    return File.Exists(path) ? Assembly.LoadFrom(path) : null;
};

// Log startup
Console.WriteLine($"[DwsimBackend] Starting. DWSIM_PATH={dwsimPath}");
Console.WriteLine($"[DwsimBackend] DWSIM DLLs present: {File.Exists(Path.Combine(dwsimPath, "DWSIM.Automation.dll"))}");

var builder = WebApplication.CreateBuilder(args);

// Configure JSON serialization to match the IDAES backend (snake_case)
builder.Services.ConfigureHttpJsonOptions(options =>
{
    // Use camelCase for deserialization (matches frontend JSON) but snake_case
    // JsonPropertyName attributes on response models handle output format.
    options.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
    options.SerializerOptions.PropertyNameCaseInsensitive = true;
    options.SerializerOptions.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
    options.SerializerOptions.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.CamelCase));
});

// Register simulation queue as singleton
builder.Services.AddSingleton<SimulationQueue>();

// Configure CORS
var corsOrigins = Environment.GetEnvironmentVariable("CORS_ORIGINS") ?? "";
var origins = corsOrigins
    .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
    .ToArray();

var aspEnv = Environment.GetEnvironmentVariable("ASPNETCORE_ENVIRONMENT") ?? "Production";
if (aspEnv == "Production" && origins.Length == 0)
{
    throw new InvalidOperationException(
        "CORS_ORIGINS must be set in production. Refusing to start with no allowlist.");
}

builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        if (origins.Length > 0)
        {
            policy.WithOrigins(origins)
                  .AllowCredentials();
        }
        policy.WithHeaders("Content-Type", "X-API-Key", "Authorization")
              .WithMethods("GET", "POST", "OPTIONS");
    });
});

var app = builder.Build();

app.UseCors();
app.UseMiddleware<ApiKeyAuthMiddleware>();

// ──────────────────────────────────────────────
// GET /
// ──────────────────────────────────────────────
app.MapGet("/", () => new { status = "ok", service = "jasper-dwsim-backend" });

// ──────────────────────────────────────────────
// GET /api/health — no auth required (wake ping)
// ──────────────────────────────────────────────
app.MapGet("/api/health", () =>
{
    string version;
    try
    {
        version = Assembly.LoadFrom(Path.Combine(dwsimPath, "DWSIM.Automation.dll"))
            .GetName().Version?.ToString() ?? "unknown";
    }
    catch
    {
        version = "unknown";
    }

    return new
    {
        status = "ok",
        engine = "DWSIM",
        engine_version = version,
        solver_available = true,
    };
});

// ──────────────────────────────────────────────
// GET /api/units — supported unit operations
// ──────────────────────────────────────────────
app.MapGet("/api/units", () => new
{
    units = DwsimSolver.SupportedUnitTypes.ToDictionary(
        t => t,
        t => new { description = t, supported = true }
    ),
    property_methods = PropertyPackageMapper.SupportedMethods.ToDictionary(
        kv => kv.Key,
        kv => new { description = kv.Value, supported = true }
    ),
});

// ──────────────────────────────────────────────
// POST /api/simulate — submit simulation job
// ──────────────────────────────────────────────
app.MapPost("/api/simulate", (SimulateRequest request, SimulationQueue queue) =>
{
    var options = request.Options ?? new SimulationOptions();

    // Per-solve timeout. The thread keeps churning on timeout (no .NET API
    // for hard cancellation of arbitrary code), but the queue slot frees so
    // the next caller isn't blocked indefinitely.
    var solveTimeout = TimeSpan.FromMinutes(5);

    var job = queue.Enqueue(async (simJob) =>
    {
        var solveTask = Task.Run(() =>
            DwsimSolver.Solve(request.Project, options, simJob.Messages));
        var completed = await Task.WhenAny(solveTask, Task.Delay(solveTimeout));
        if (completed != solveTask)
        {
            throw new TimeoutException(
                $"DWSIM solve exceeded {solveTimeout.TotalSeconds}s timeout");
        }
        simJob.Result = await solveTask;
    });

    return Results.Ok(new SimulateSubmitResponse(
        JobId: job.Id,
        Status: job.Status,
        Position: job.Position,
        QueueLength: queue.QueueDepth
    ));
});

// ──────────────────────────────────────────────
// GET /api/jobs/{jobId} — poll job status
// ──────────────────────────────────────────────
app.MapGet("/api/jobs/{jobId}", (string jobId, SimulationQueue queue) =>
{
    var job = queue.GetJob(jobId);
    if (job == null)
        return Results.NotFound(new { detail = "Job not found or expired" });

    queue.CleanupOldJobs();

    return Results.Ok(new JobStatusResponse(
        JobId: job.Id,
        Status: job.Status,
        Position: job.Position,
        QueueLength: queue.QueueDepth,
        Result: job.Result,
        Error: job.Error,
        Traceback: job.Traceback,
        Messages: job.Messages
    ));
});

// Start on configured port
var port = Environment.GetEnvironmentVariable("PORT") ?? "8000";
app.Run($"http://0.0.0.0:{port}");
