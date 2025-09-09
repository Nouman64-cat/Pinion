## RetryPolicy

Module: `pinion.retry`

```python
@dataclass(slots=True)
class RetryPolicy:
    max_retries: int = 3
    base_delay: float = 0.5
    cap: float = 10.0
    jitter: bool = True

    def compute_delay(self, attempt: int) -> float: ...
```

Behavior:

- Exponential backoff: `base_delay * 2**(attempt-1)`, capped at `cap`.
- With `jitter=True`, randomizes uniformly between 0 and the raw delay.

Tips:

- Disable jitter in tests for deterministic timing.
- Keep `cap` reasonable to prevent very long delays.

