from __future__ import annotations
import random
import time
from dataclasses import dataclass

@dataclass
class RetryConfig:
    max_retries: int = 5
    base_sleep: float = 0.5
    max_sleep: float = 8.0

def backoff_sleep(i: int, cfg: RetryConfig) -> None:
    s = min(cfg.max_sleep, cfg.base_sleep * (2 ** i))
    s *= (0.8 + 0.4 * random.random())
    time.sleep(s)

class RateLimiter:
    def __init__(self, min_interval: float = 0.25):
        self.min_interval = float(min_interval)
        self._last = 0.0

    def wait(self):
        now = time.time()
        dt = now - self._last
        if dt < self.min_interval:
            time.sleep(self.min_interval - dt)
        self._last = time.time()