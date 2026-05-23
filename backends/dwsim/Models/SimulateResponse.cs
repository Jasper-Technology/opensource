using System.Text.Json.Serialization;

namespace DwsimBackend.Models;

public record SimulateSubmitResponse(
    [property: JsonPropertyName("job_id")] string JobId,
    string Status,
    int Position,
    [property: JsonPropertyName("queue_length")] int QueueLength
);
