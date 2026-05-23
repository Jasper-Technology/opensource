namespace DwsimBackend.Middleware;

/// <summary>
/// API key validation middleware. Matches the IDAES backend auth pattern:
/// - Reads BACKEND_API_KEY from environment
/// - Validates X-API-Key header on protected endpoints
/// - Health endpoint is excluded (no auth required for wake-up pings)
/// </summary>
public sealed class ApiKeyAuthMiddleware
{
    private readonly RequestDelegate _next;
    private readonly string? _validApiKey;
    private static readonly HashSet<string> ExcludedPaths = new(StringComparer.OrdinalIgnoreCase)
    {
        "/api/health",
        "/",
    };

    public ApiKeyAuthMiddleware(RequestDelegate next)
    {
        _next = next;
        _validApiKey = Environment.GetEnvironmentVariable("BACKEND_API_KEY");
    }

    public async Task InvokeAsync(HttpContext context)
    {
        var path = context.Request.Path.Value ?? "";

        // Skip auth for excluded paths
        if (ExcludedPaths.Contains(path) || context.Request.Method == "OPTIONS")
        {
            await _next(context);
            return;
        }

        // If no API key is configured, reject all protected requests
        if (string.IsNullOrEmpty(_validApiKey))
        {
            context.Response.StatusCode = 403;
            await context.Response.WriteAsJsonAsync(new { detail = "Service is not configured for access" });
            return;
        }

        // Validate the X-API-Key header
        var providedKey = context.Request.Headers["X-API-Key"].FirstOrDefault();
        if (string.IsNullOrEmpty(providedKey) || providedKey != _validApiKey)
        {
            context.Response.StatusCode = 403;
            await context.Response.WriteAsJsonAsync(new { detail = "Invalid or missing API key" });
            return;
        }

        await _next(context);
    }
}
