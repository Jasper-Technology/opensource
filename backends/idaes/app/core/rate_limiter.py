"""Simple in-memory sliding-window rate limiter (no extra dependencies)."""
import time
from collections import defaultdict


class SlidingWindowRateLimiter:
    """
    Per-key sliding window rate limiter.

    Tracks request timestamps in a window and rejects requests that
    exceed the configured limit. Thread-safe for single-process use.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._log: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> tuple[bool, int]:
        """
        Check whether `key` is within its rate limit.

        Returns (allowed, retry_after_seconds).
        retry_after_seconds is 0 when allowed.
        """
        now = time.time()
        cutoff = now - self._window
        timestamps = self._log[key]

        # Evict old entries
        self._log[key] = [t for t in timestamps if t > cutoff]

        if len(self._log[key]) >= self._max:
            oldest = self._log[key][0]
            retry_after = max(1, int(oldest + self._window - now) + 1)
            return False, retry_after

        self._log[key].append(now)
        return True, 0


# 10 simulation submissions per IP per 60 seconds
rate_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60)
