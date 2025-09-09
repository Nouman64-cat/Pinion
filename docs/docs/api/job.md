## Job

Module: `pinion.types`

```python
from dataclasses import dataclass, field
from enum import Enum, auto

class Status(Enum):
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()

@dataclass(slots=True)
class Job:
    func_name: str
    args: tuple[...,] = ()
    kwargs: dict[str, object] = field(default_factory=dict)
    id: str = field(default_factory=...)
    status: Status = Status.PENDING
    attempts: int = 0
    created_at: float = ...
```

Notes:

- `func_name` is matched case-insensitively against the registry.
- `attempts` is incremented by the storage during `dequeue` when claiming a job.

