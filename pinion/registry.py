from __future__ import annotations

from typing import Any, Callable


REGISTRY: dict[str, Callable[..., Any]] = {}


def task(name: str | None = None):
    def deco(fn: Callable[..., Any]):
        REGISTRY[(name or fn.__name__).lower()] = fn
        return fn

    return deco

