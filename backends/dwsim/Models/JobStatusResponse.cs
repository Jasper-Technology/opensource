using System.Text.Json.Serialization;

namespace DwsimBackend.Models;

public record JobStatusResponse(
    [property: JsonPropertyName("job_id")] string JobId,
    string Status,
    int Position,
    [property: JsonPropertyName("queue_length")] int QueueLength,
    object? Result = null,
    string? Error = null,
    string? Traceback = null,
    List<string>? Messages = null
);
