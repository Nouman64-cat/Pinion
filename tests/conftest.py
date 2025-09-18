import pytest

from pinion.registry import REGISTRY


@pytest.fixture(autouse=True)
def restore_registry():
    snapshot = REGISTRY.copy()
    try:
        yield
    finally:
        REGISTRY.clear()
        REGISTRY.update(snapshot)