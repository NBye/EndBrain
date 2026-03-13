from __future__ import annotations

import json
from pathlib import Path

from endbrain import EndBrain


def _read_non_empty_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_write_before_interval_only_hits_wal(store_dir: Path) -> None:
    brain = EndBrain(storage_dir=str(store_dir), memory_limit_mb=8, sync_interval_seconds=3600)
    brain.add_entity("e1", "Python", "technology")

    entities_lines = _read_non_empty_lines(store_dir / "entities.jsonl")
    wal_lines = _read_non_empty_lines(store_dir / "wal" / "current.log")

    assert entities_lines == []
    assert len(wal_lines) >= 1


def test_flush_writes_and_clears_wal(store_dir: Path) -> None:
    brain = EndBrain(storage_dir=str(store_dir), memory_limit_mb=8, sync_interval_seconds=3600)
    brain.add_entity("e1", "Python", "technology")
    brain.flush()

    entities_lines = _read_non_empty_lines(store_dir / "entities.jsonl")
    wal_lines = _read_non_empty_lines(store_dir / "wal" / "current.log")

    assert len(entities_lines) == 1
    payload = json.loads(entities_lines[0])
    assert payload["id"] == "e1"
    assert wal_lines == []


def test_sync_interval_zero_auto_flush(store_dir: Path) -> None:
    brain = EndBrain(storage_dir=str(store_dir), memory_limit_mb=8, sync_interval_seconds=0)
    brain.add_entity("e1", "Python", "technology")

    entities_lines = _read_non_empty_lines(store_dir / "entities.jsonl")
    assert len(entities_lines) == 1
