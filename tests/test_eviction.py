from __future__ import annotations

from pathlib import Path

from endbrain import EndBrain


def test_force_lifecycle_prefers_relation_eviction_first(store_dir: Path) -> None:
    brain = EndBrain(storage_dir=str(store_dir), memory_limit_mb=64, sync_interval_seconds=3600)
    brain.add_entity("e1", "Python", "technology", weight=0.2, importance=0.2)
    brain.add_entity("e2", "FastAPI", "framework", weight=0.2, importance=0.2)
    brain.add_relation("r1", "e2", "e1", "built_on", weight=0.1, importance=0.1)

    brain._run_lifecycle_assessment(force=True)

    assert brain.get_relation("r1") is None
    assert brain.get_entity("e1") is not None
    assert brain.get_entity("e2") is not None


def test_evicted_object_removed_from_persistence_after_flush(store_dir: Path) -> None:
    brain = EndBrain(storage_dir=str(store_dir), memory_limit_mb=64, sync_interval_seconds=3600)
    brain.add_entity("e1", "Python", "technology", weight=0.2, importance=0.2)
    brain.add_entity("e2", "FastAPI", "framework", weight=0.2, importance=0.2)
    brain.add_relation("r1", "e2", "e1", "built_on", weight=0.1, importance=0.1)

    brain._run_lifecycle_assessment(force=True)
    brain.flush()

    loaded = EndBrain(storage_dir=str(store_dir), memory_limit_mb=64, sync_interval_seconds=3600)
    assert loaded.get_relation("r1") is None
