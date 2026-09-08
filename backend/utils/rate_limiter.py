"""
Adaptive Rate Limiter for Gemini API
-------------------------------------
Tracks actual call timing and adjusts inter-call delays dynamically.
Respects the free tier limit of 15 RPM without unnecessary fixed waits.
"""
import time
from collections import deque
from utils.logger import get_logger

log = get_logger("rate_limiter")

# Gemini free tier: 15 requests per minute
_MAX_RPM = 15
_WINDOW_SECONDS = 60.0
_MIN_DELAY = 0.5   # never go below 0.5s between calls
_MAX_DELAY = 30.0  # cap single wait at 30s


class AdaptiveRateLimiter:
    def __init__(self, max_rpm: int = _MAX_RPM):
        self.max_rpm = max_rpm
        self._call_times: deque = deque()

    def wait(self):
        """
        Block until it is safe to make the next API call.
        Tracks a sliding 60-second window of call timestamps.
        """
        now = time.monotonic()

        # Evict calls older than the window
        while self._call_times and now - self._call_times[0] >= _WINDOW_SECONDS:
            self._call_times.popleft()

        if len(self._call_times) >= self.max_rpm:
            # Must wait until the oldest call falls out of the window
            oldest = self._call_times[0]
            wait_time = _WINDOW_SECONDS - (now - oldest) + 0.1  # +0.1s buffer
            wait_time = max(_MIN_DELAY, min(wait_time, _MAX_DELAY))
            log.debug("Rate limit: waiting %.1fs (%d calls in last 60s)", wait_time, len(self._call_times))
            time.sleep(wait_time)

        self._call_times.append(time.monotonic())

    def record_call(self):
        """Record a call that already happened (for external tracking)."""
        self._call_times.append(time.monotonic())

    @property
    def calls_in_window(self) -> int:
        now = time.monotonic()
        return sum(1 for t in self._call_times if now - t < _WINDOW_SECONDS)


# Singleton limiter shared across all Gemini calls
_limiter = AdaptiveRateLimiter(max_rpm=_MAX_RPM)


def get_limiter() -> AdaptiveRateLimiter:
    return _limiter
