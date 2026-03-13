from __future__ import annotations

from pathlib import Path

import pytest

from endbrain import EndBrain


def test_init_creates_storage_layout(store_dir: Path) -> None:
    EndBrain(storage_dir=str(store_dir), memory_limit_mb=8, sync_interval_seconds=10)

    assert (store_dir / "metadata.json").exists()
    assert (store_dir / "graph_snapshot.json").exists()
    assert (store_dir / "entities.jsonl").exists()
    assert (store_dir / "relations.jsonl").exists()
    assert (store_dir / "wal" / "current.log").exists()


def test_invalid_memory_limit_raises(store_dir: Path) -> None:
    with pytest.raises(ValueError):
        EndBrain(storage_dir=str(store_dir), memory_limit_mb=0)


def test_auto_load_recovers_snapshot(store_dir: Path) -> None:
    brain = EndBrain(storage_dir=str(store_dir), memory_limit_mb=8, sync_interval_seconds=999)
    brain.add_entity("e1", "Python", "technology", keywords=["python"])
    brain.flush()

    loaded = EndBrain(storage_dir=str(store_dir), memory_limit_mb=8, sync_interval_seconds=999)
    entity = loaded.get_entity("e1")

    assert entity is not None
    assert entity["name"] == "Python"
