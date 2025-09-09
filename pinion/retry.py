from __future__ import annotations

from dataclasses import dataclass
import random


@dataclass(slots=True)
class RetryPolicy:
    max_retries: int = 3
    base_delay: float = 0.5  # seconds
    cap: float = 10.0
    jitter: bool = True

    def compute_delay(self, attempt: int) -> float:
        raw = min(self.cap, self.base_delay * (2 ** (attempt - 1)))
        return random.uniform(0, raw) if self.jitter else raw

