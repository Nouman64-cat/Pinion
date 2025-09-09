from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any
import time
import uuid


class Status(Enum):
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()


@dataclass(slots=True)
class Job:
    func_name: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: Status = Status.PENDING
    attempts: int = 0
    created_at: float = field(default_factory=time.time)

