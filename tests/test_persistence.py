from __future__ import annotations

from pathlib import Path

from endbrain import EndBrain


def test_recover_from_wal_without_manual_flush(store_dir: Path) -> None:
    writer = EndBrain(storage_dir=str(store_dir), memory_limit_mb=8, sync_interval_seconds=3600)
    writer.add_entity("e1", "Python", "technology")
    writer.add_entity("e2", "FastAPI", "framework")
    writer.add_relation("r1", "e2", "e1", "built_on")

    reader = EndBrain(storage_dir=str(store_dir), memory_limit_mb=8, sync_interval_seconds=3600)
    assert reader.get_entity("e1") is not None
    assert reader.get_relation("r1") is not None


def test_delete_persists_after_flush(store_dir: Path) -> None:
    brain = EndBrain(storage_dir=str(store_dir), memory_limit_mb=8, sync_interval_seconds=3600)
    brain.add_entity("e1", "Python", "technology")
    brain.flush()

    assert brain.delete_entity("e1") is True
    brain.flush()

    loaded = EndBrain(storage_dir=str(store_dir), memory_limit_mb=8, sync_interval_seconds=3600)
    assert loaded.get_entity("e1") is None


def test_compact_keeps_data_and_updates_stats(store_dir: Path) -> None:
    brain = EndBrain(storage_dir=str(store_dir), memory_limit_mb=8, sync_interval_seconds=3600)
    brain.add_entity("e1", "Python", "technology")
    brain.compact()

    stats = brain.get_stats()
    assert stats["compaction_count"] >= 1

    loaded = EndBrain(storage_dir=str(store_dir), memory_limit_mb=8, sync_interval_seconds=3600)
    assert loaded.get_entity("e1") is not None
