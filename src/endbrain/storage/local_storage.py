from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from endbrain.utils.time import utc_now_iso


class LocalStorage:
    def __init__(self, storage_dir: str | Path) -> None:
        self.root = Path(storage_dir)
        self.metadata_path = self.root / "metadata.json"
        self.snapshot_path = self.root / "graph_snapshot.json"
        self.entities_path = self.root / "entities.jsonl"
        self.relations_path = self.root / "relations.jsonl"
        self.wal_dir = self.root / "wal"
        self.wal_current_path = self.wal_dir / "current.log"

    def ensure_layout(self, metadata_defaults: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.wal_dir.mkdir(parents=True, exist_ok=True)

        if not self.metadata_path.exists():
            self._write_json(self.metadata_path, metadata_defaults)

        if not self.snapshot_path.exists():
            self._write_json(
                self.snapshot_path,
                {
                    "snapshot_version": 0,
                    "created_at": utc_now_iso(),
                    "entities": [],
                    "relations": [],
                },
            )

        self.entities_path.touch(exist_ok=True)
        self.relations_path.touch(exist_ok=True)
        self.wal_current_path.touch(exist_ok=True)

    def load(self) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
        metadata = self._read_json(self.metadata_path, {})
        snapshot = self._read_json(self.snapshot_path, {})

        entities: dict[str, dict[str, Any]] = {}
        relations: dict[str, dict[str, Any]] = {}

        for item in snapshot.get("entities", []):
            entity_id = str(item.get("id", ""))
            if entity_id:
                entities[entity_id] = dict(item)

        for item in snapshot.get("relations", []):
            relation_id = str(item.get("id", ""))
            if relation_id:
                relations[relation_id] = dict(item)

        entities.update(self._read_jsonl_as_dict(self.entities_path))
        relations.update(self._read_jsonl_as_dict(self.relations_path))

        for entry in self.read_wal_entries():
            self._apply_wal_entry(entities, relations, entry)

        return entities, relations, metadata

    def save(
        self,
        metadata: dict[str, Any],
        entities: dict[str, dict[str, Any]],
        relations: dict[str, dict[str, Any]],
    ) -> None:
        entity_rows = [entities[key] for key in sorted(entities)]
        relation_rows = [relations[key] for key in sorted(relations)]

        self._write_jsonl(self.entities_path, entity_rows)
        self._write_jsonl(self.relations_path, relation_rows)
        self._write_json(
            self.snapshot_path,
            {
                "snapshot_version": int(metadata.get("snapshot_version", 0)),
                "created_at": utc_now_iso(),
                "entities": entity_rows,
                "relations": relation_rows,
            },
        )
        self._write_json(self.metadata_path, metadata)

    def append_wal_entry(self, entry: dict[str, Any]) -> None:
        with self.wal_current_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")

    def read_wal_entries(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        if not self.wal_current_path.exists():
            return entries

        with self.wal_current_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries

    def clear_wal(self) -> None:
        self.wal_current_path.write_text("", encoding="utf-8")

    def _apply_wal_entry(
        self,
        entities: dict[str, dict[str, Any]],
        relations: dict[str, dict[str, Any]],
        entry: dict[str, Any],
    ) -> None:
        op = entry.get("op")
        if op == "upsert_entity":
            payload = entry.get("payload", {})
            entity_id = str(payload.get("id", ""))
            if entity_id:
                entities[entity_id] = dict(payload)
            return

        if op == "delete_entity":
            entity_id = str(entry.get("id", ""))
            entities.pop(entity_id, None)
            for relation_id in entry.get("cascade_relation_ids", []):
                relations.pop(str(relation_id), None)
            return

        if op == "upsert_relation":
            payload = entry.get("payload", {})
            relation_id = str(payload.get("id", ""))
            if relation_id:
                relations[relation_id] = dict(payload)
            return

        if op == "delete_relation":
            relation_id = str(entry.get("id", ""))
            relations.pop(relation_id, None)

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default

    def _write_json(self, path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_jsonl_as_dict(self, path: Path) -> dict[str, dict[str, Any]]:
        records: dict[str, dict[str, Any]] = {}
        if not path.exists():
            return records

        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                object_id = str(payload.get("id", ""))
                if object_id:
                    records[object_id] = payload
        return records

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False))
                handle.write("\n")
