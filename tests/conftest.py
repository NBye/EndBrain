from __future__ import annotations

from pathlib import Path

import pytest

from endbrain import EndBrain


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "store"


@pytest.fixture
def brain(store_dir: Path) -> EndBrain:
    instance = EndBrain(storage_dir=str(store_dir), memory_limit_mb=8, sync_interval_seconds=3600)
    try:
        yield instance
    finally:
        instance.close()
