import random
import time
from collections.abc import Callable

import httpx


class RetryPolicy:
    def __init__(self, *, max_attempts: int = 3, base_delay_seconds: float = 0.25, max_delay_seconds: float = 2.0):
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds

    def run(self, fn: Callable[[], httpx.Response]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = fn()
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError("server error", request=response.request, response=response)
                return response
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt == self.max_attempts:
                    raise
                jitter = random.uniform(0, self.base_delay_seconds)
                delay = min(self.max_delay_seconds, (2 ** (attempt - 1)) * self.base_delay_seconds + jitter)
                time.sleep(delay)
        if last_error:
            raise last_error
        raise RuntimeError("retry policy failed unexpectedly")
