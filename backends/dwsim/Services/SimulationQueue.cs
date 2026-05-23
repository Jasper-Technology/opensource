using System.Collections.Concurrent;
using DwsimBackend.Models;

namespace DwsimBackend.Services;

/// <summary>
/// Async job queue with concurrency limiting via SemaphoreSlim.
/// Mirrors the Python SimulationQueue from the IDAES backend.
/// </summary>
public sealed class SimulationQueue
{
    private const int MaxConcurrent = 2;
    private static readonly TimeSpan JobTtl = TimeSpan.FromHours(1);

    private readonly SemaphoreSlim _semaphore = new(MaxConcurrent, MaxConcurrent);
    private readonly ConcurrentDictionary<string, SimJob> _jobs = new();
    private readonly object _pendingLock = new();
    private readonly List<string> _pending = new();

    public sealed class SimJob
    {
        public string Id { get; } = Guid.NewGuid().ToString();
        public DateTime CreatedAt { get; } = DateTime.UtcNow;
        public string Status { get; set; } = "queued";
        public int Position { get; set; }
        public object? Result { get; set; }
        public string? Error { get; set; }
        public string? Traceback { get; set; }
        public List<string> Messages { get; set; } = new();
    }

    /// <summary>
    /// Enqueue a simulation task. Returns the job immediately with its queue position.
    /// The task runs in the background.
    /// </summary>
    public SimJob Enqueue(Func<SimJob, Task> work)
    {
        var job = new SimJob();

        lock (_pendingLock)
        {
            _pending.Add(job.Id);
            job.Position = _pending.Count;
        }

        _jobs[job.Id] = job;

        _ = Task.Run(() => RunJob(job, work));

        return job;
    }

    private async Task RunJob(SimJob job, Func<SimJob, Task> work)
    {
        await _semaphore.WaitAsync();
        try
        {
            lock (_pendingLock)
            {
                _pending.Remove(job.Id);
                for (int i = 0; i < _pending.Count; i++)
                {
                    if (_jobs.TryGetValue(_pending[i], out var pending))
                        pending.Position = i + 1;
                }
            }

            job.Status = "running";
            job.Position = 0;

            await work(job);

            if (job.Status == "running")
                job.Status = "done";
        }
        catch (Exception ex)
        {
            job.Error = ex.Message;
            job.Traceback = ex.ToString();
            job.Status = "error";
        }
        finally
        {
            _semaphore.Release();
        }
    }

    public SimJob? GetJob(string jobId) =>
        _jobs.TryGetValue(jobId, out var job) ? job : null;

    public int QueueDepth
    {
        get { lock (_pendingLock) { return _pending.Count; } }
    }

    public void CleanupOldJobs()
    {
        var cutoff = DateTime.UtcNow - JobTtl;
        var stale = _jobs
            .Where(kv => kv.Value.Status is "done" or "error" && kv.Value.CreatedAt < cutoff)
            .Select(kv => kv.Key)
            .ToList();

        foreach (var id in stale)
            _jobs.TryRemove(id, out _);
    }
}
