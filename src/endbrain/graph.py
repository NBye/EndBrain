from __future__ import annotations

import json
from typing import Any

from endbrain.config import EndBrainConfig
from endbrain.memory import InMemoryGraph
from endbrain.model import Entity, Relation
from endbrain.query import normalize_query_keywords, retain_score, score_entity, score_relation
from endbrain.query.scoring import serialize_match_payload
from endbrain.storage import LocalStorage
from endbrain.utils.memory import estimate_json_bytes
from endbrain.utils.time import iso_to_ts, utc_now_iso, utc_now_ts


class EndBrain:
    def __init__(
        self,
        storage_dir: str,
        memory_limit_mb: int = 512,
        sync_interval_seconds: int = 5,
        auto_load: bool = True,
    ) -> None:
        self.config = EndBrainConfig(
            storage_dir=storage_dir,
            memory_limit_mb=memory_limit_mb,
            sync_interval_seconds=sync_interval_seconds,
            auto_load=auto_load,
        )

        self._storage = LocalStorage(self.config.storage_path)
        self._graph = InMemoryGraph()
        self._metadata = self._base_metadata()
        self._last_lifecycle_scan_ts = 0.0

        self._storage.ensure_layout(self._metadata)
        if self.config.auto_load:
            self.load()

    def _base_metadata(self) -> dict[str, Any]:
        now = utc_now_iso()
        return {
            "memory_limit_bytes": self.config.memory_limit_bytes,
            "current_memory_bytes": 0,
            "snapshot_version": 0,
            "last_snapshot_at": now,
            "last_sync_at": now,
            "dirty_object_count": 0,
            "eviction_count": 0,
            "compaction_count": 0,
            "package_version": "0.1.0",
        }

    def _merged_metadata(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        merged = self._base_metadata()
        if payload:
            merged.update(payload)
        merged["memory_limit_bytes"] = self.config.memory_limit_bytes
        return merged

    def load(self) -> "EndBrain":
        entity_rows, relation_rows, metadata = self._storage.load()
        self._graph = InMemoryGraph()

        for payload in entity_rows.values():
            self._graph.upsert_entity(Entity.from_dict(payload), mark_dirty=False)

        for payload in relation_rows.values():
            relation = Relation.from_dict(payload)
            if relation.source_id in self._graph.entities_by_id and relation.target_id in self._graph.entities_by_id:
                self._graph.upsert_relation(relation, mark_dirty=False)

        self._graph.clear_dirty_tracking()
        self._metadata = self._merged_metadata(metadata)
        self._recalculate_memory_bytes()
        self._metadata["dirty_object_count"] = 0
        return self

    def flush(self) -> None:
        self._metadata["snapshot_version"] = int(self._metadata.get("snapshot_version", 0)) + 1
        now = utc_now_iso()
        self._metadata["last_snapshot_at"] = now
        self._metadata["last_sync_at"] = now

        entity_payloads = {entity.id: entity.to_dict() for entity in self._graph.entities_by_id.values()}
        relation_payloads = {relation.id: relation.to_dict() for relation in self._graph.relations_by_id.values()}

        self._recalculate_memory_bytes()
        self._metadata["dirty_object_count"] = 0
        self._storage.save(self._metadata, entity_payloads, relation_payloads)
        self._storage.clear_wal()
        self._graph.clear_dirty_tracking()

    def compact(self) -> None:
        self.flush()
        self._metadata["compaction_count"] = int(self._metadata.get("compaction_count", 0)) + 1
        self._storage.save(
            self._metadata,
            {entity.id: entity.to_dict() for entity in self._graph.entities_by_id.values()},
            {relation.id: relation.to_dict() for relation in self._graph.relations_by_id.values()},
        )

    def _validate_metadata_json(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        payload = metadata or {}
        try:
            json.dumps(payload)
        except TypeError as exc:
            raise ValueError("metadata must be JSON serializable") from exc
        return payload

    def _set_dirty_count(self) -> None:
        self._metadata["dirty_object_count"] = (
            len(self._graph.dirty_entities)
            + len(self._graph.dirty_relations)
            + len(self._graph.deleted_entities)
            + len(self._graph.deleted_relations)
        )

    def _recalculate_memory_bytes(self) -> None:
        payload = {
            "entities": [entity.to_dict() for entity in self._graph.entities_by_id.values()],
            "relations": [relation.to_dict() for relation in self._graph.relations_by_id.values()],
            "entity_index_size": sum(len(v) for v in self._graph.entity_keyword_index.values()),
            "relation_index_size": sum(len(v) for v in self._graph.relation_keyword_index.values()),
        }
        self._metadata["current_memory_bytes"] = estimate_json_bytes(payload)

    def _append_wal(self, entry: dict[str, Any]) -> None:
        entry = dict(entry)
        entry["ts"] = utc_now_iso()
        self._storage.append_wal_entry(entry)

    def _entity_degree(self, entity_id: str) -> int:
        return self._graph.entity_degree(entity_id)

    def _maybe_auto_flush(self) -> None:
        interval = self.config.sync_interval_seconds
        if interval == 0:
            self.flush()
            return

        last_sync_ts = iso_to_ts(str(self._metadata.get("last_sync_at", "")))
        if (utc_now_ts() - last_sync_ts) >= interval and self._metadata.get("dirty_object_count", 0) > 0:
            self.flush()

    def _run_lifecycle_assessment(self, force: bool = False) -> None:
        now_ts = utc_now_ts()
        if not force and (now_ts - self._last_lifecycle_scan_ts) < 2.0:
            return
        self._last_lifecycle_scan_ts = now_ts

        self._recalculate_memory_bytes()
        memory_limit = self.config.memory_limit_bytes
        current_memory = int(self._metadata.get("current_memory_bytes", 0))
        if memory_limit <= 0:
            return

        pressure = current_memory / memory_limit
        total_objects = len(self._graph.entities_by_id) + len(self._graph.relations_by_id)
        if total_objects == 0:
            return

        threshold = 0.08
        if pressure >= 0.70:
            threshold = 0.18
        if pressure >= 0.90:
            threshold = 0.24

        candidates: list[tuple[int, int, float, str, str]] = []

        for relation in self._graph.relations_by_id.values():
            degree = self._entity_degree(relation.source_id) + self._entity_degree(relation.target_id)
            score = retain_score(relation, now_ts, degree)
            candidates.append((0, 1, score, "relation", relation.id))

        for entity in self._graph.entities_by_id.values():
            degree = self._entity_degree(entity.id)
            score = retain_score(entity, now_ts, degree)
            isolated_rank = 0 if degree == 0 else 1
            candidates.append((1, isolated_rank, score, "entity", entity.id))

        candidates.sort(key=lambda item: (item[0], item[1], item[2]))

        evicted = 0
        for _, _, score, object_type, object_id in candidates:
            if score >= threshold and pressure < 1.0 and not force:
                continue

            if object_type == "relation":
                removed = self._graph.remove_relation(object_id, mark_deleted=True)
                if removed:
                    self._append_wal({"op": "delete_relation", "id": object_id})
                    evicted += 1
            else:
                related_ids = self._graph.related_relation_ids(object_id)
                removed_relations = self._graph.remove_entity(object_id, mark_deleted=True)
                if removed_relations or object_id not in self._graph.entities_by_id:
                    self._append_wal(
                        {
                            "op": "delete_entity",
                            "id": object_id,
                            "cascade_relation_ids": sorted(related_ids),
                        }
                    )
                    evicted += 1

            if evicted == 0:
                continue

            self._recalculate_memory_bytes()
            pressure = int(self._metadata.get("current_memory_bytes", 0)) / memory_limit
            if pressure < 0.85 and evicted >= max(1, total_objects // 20):
                break

        if evicted > 0:
            self._metadata["eviction_count"] = int(self._metadata.get("eviction_count", 0)) + evicted
            self._set_dirty_count()

    def _after_write(self) -> None:
        self._set_dirty_count()
        self._run_lifecycle_assessment()
        self._set_dirty_count()
        self._maybe_auto_flush()

    def add_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        keywords: list[str] | None = None,
        weight: float = 0.5,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entity = Entity(
            id=entity_id,
            name=name,
            entity_type=entity_type,
            keywords=keywords or [],
            weight=weight,
            importance=importance,
            metadata=self._validate_metadata_json(metadata),
        )
        self._graph.upsert_entity(entity)
        self._append_wal({"op": "upsert_entity", "payload": entity.to_dict()})
        self._after_write()
        return entity.to_dict()

    def update_entity(self, entity_id: str, **updates: Any) -> dict[str, Any]:
        entity = self._graph.entities_by_id.get(entity_id)
        if entity is None:
            raise KeyError(f"entity not found: {entity_id}")

        if "name" in updates:
            entity.name = str(updates["name"])
        if "entity_type" in updates:
            entity.entity_type = str(updates["entity_type"])
        if "keywords" in updates:
            entity.keywords = list(updates["keywords"])
        if "weight" in updates:
            entity.weight = float(updates["weight"])
        if "importance" in updates:
            entity.importance = float(updates["importance"])
        if "metadata" in updates:
            entity.metadata = self._validate_metadata_json(updates["metadata"])

        entity.updated_at = utc_now_iso()
        self._graph.upsert_entity(entity)
        self._append_wal({"op": "upsert_entity", "payload": entity.to_dict()})
        self._after_write()
        return entity.to_dict()

    def delete_entity(self, entity_id: str) -> bool:
        if entity_id not in self._graph.entities_by_id:
            return False

        relation_ids = sorted(self._graph.related_relation_ids(entity_id))
        self._graph.remove_entity(entity_id)
        self._append_wal({"op": "delete_entity", "id": entity_id, "cascade_relation_ids": relation_ids})
        self._after_write()
        return True

    def add_relation(
        self,
        relation_id: str,
        source_id: str,
        target_id: str,
        relation_type: str,
        keywords: list[str] | None = None,
        weight: float = 0.5,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if source_id not in self._graph.entities_by_id:
            raise KeyError(f"source entity not found: {source_id}")
        if target_id not in self._graph.entities_by_id:
            raise KeyError(f"target entity not found: {target_id}")

        relation = Relation(
            id=relation_id,
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            keywords=keywords or [],
            weight=weight,
            importance=importance,
            metadata=self._validate_metadata_json(metadata),
        )
        self._graph.upsert_relation(relation)
        self._append_wal({"op": "upsert_relation", "payload": relation.to_dict()})
        self._after_write()
        return relation.to_dict()

    def update_relation(self, relation_id: str, **updates: Any) -> dict[str, Any]:
        relation = self._graph.relations_by_id.get(relation_id)
        if relation is None:
            raise KeyError(f"relation not found: {relation_id}")

        if "source_id" in updates:
            source_id = str(updates["source_id"])
            if source_id not in self._graph.entities_by_id:
                raise KeyError(f"source entity not found: {source_id}")
            relation.source_id = source_id
        if "target_id" in updates:
            target_id = str(updates["target_id"])
            if target_id not in self._graph.entities_by_id:
                raise KeyError(f"target entity not found: {target_id}")
            relation.target_id = target_id
        if "relation_type" in updates:
            relation.relation_type = str(updates["relation_type"])
        if "keywords" in updates:
            relation.keywords = list(updates["keywords"])
        if "weight" in updates:
            relation.weight = float(updates["weight"])
        if "importance" in updates:
            relation.importance = float(updates["importance"])
        if "metadata" in updates:
            relation.metadata = self._validate_metadata_json(updates["metadata"])

        relation.updated_at = utc_now_iso()
        self._graph.upsert_relation(relation)
        self._append_wal({"op": "upsert_relation", "payload": relation.to_dict()})
        self._after_write()
        return relation.to_dict()

    def delete_relation(self, relation_id: str) -> bool:
        removed = self._graph.remove_relation(relation_id)
        if not removed:
            return False

        self._append_wal({"op": "delete_relation", "id": relation_id})
        self._after_write()
        return True

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        entity = self._graph.entities_by_id.get(entity_id)
        if entity is None:
            return None

        entity.touch()
        self._graph.dirty_entities.add(entity_id)
        self._set_dirty_count()
        return entity.to_dict()

    def get_relation(self, relation_id: str) -> dict[str, Any] | None:
        relation = self._graph.relations_by_id.get(relation_id)
        if relation is None:
            return None

        relation.touch()
        self._graph.dirty_relations.add(relation_id)
        self._set_dirty_count()
        return relation.to_dict()

    def query_entities(self, keywords: list[str], top_k: int = 10) -> list[dict[str, Any]]:
        if top_k <= 0:
            return []

        query_keywords = normalize_query_keywords(keywords)
        if not query_keywords:
            return []

        candidate_ids: set[str] = set()
        for token in query_keywords:
            candidate_ids.update(self._graph.entity_keyword_index.get(token, set()))

        if not candidate_ids:
            candidate_ids = set(self._graph.entities_by_id)

        result: list[dict[str, Any]] = []
        for entity_id in candidate_ids:
            entity = self._graph.entities_by_id.get(entity_id)
            if entity is None:
                continue

            score, reason = score_entity(entity, query_keywords)
            if score <= 0:
                continue

            entity.touch()
            self._graph.dirty_entities.add(entity_id)
            result.append(serialize_match_payload(entity.to_dict(), score, reason))

        result.sort(key=lambda item: item.get("match_weight", 0.0), reverse=True)
        self._set_dirty_count()
        return result[:top_k]

    def query_relations(self, keywords: list[str], top_k: int = 10) -> list[dict[str, Any]]:
        if top_k <= 0:
            return []

        query_keywords = normalize_query_keywords(keywords)
        if not query_keywords:
            return []

        candidate_ids: set[str] = set()
        for token in query_keywords:
            candidate_ids.update(self._graph.relation_keyword_index.get(token, set()))

        if not candidate_ids:
            candidate_ids = set(self._graph.relations_by_id)

        result: list[dict[str, Any]] = []
        for relation_id in candidate_ids:
            relation = self._graph.relations_by_id.get(relation_id)
            if relation is None:
                continue

            score, reason = score_relation(relation, query_keywords)
            if score <= 0:
                continue

            relation.touch()
            self._graph.dirty_relations.add(relation_id)
            result.append(serialize_match_payload(relation.to_dict(), score, reason))

        result.sort(key=lambda item: item.get("match_weight", 0.0), reverse=True)
        self._set_dirty_count()
        return result[:top_k]

    def query_graph(self, keywords: list[str], top_k: int = 10, depth: int = 1) -> dict[str, Any]:
        if depth < 0:
            raise ValueError("depth must be >= 0")
        if depth > 3:
            depth = 3

        entity_hits = self.query_entities(keywords, top_k=top_k)
        relation_hits = self.query_relations(keywords, top_k=top_k)

        included_entity_ids = {item["id"] for item in entity_hits}
        included_relation_ids = {item["id"] for item in relation_hits}

        for relation_hit in relation_hits:
            included_entity_ids.add(relation_hit["source_id"])
            included_entity_ids.add(relation_hit["target_id"])

        frontier = set(included_entity_ids)
        visited = set(included_entity_ids)

        for _ in range(depth):
            if not frontier:
                break
            next_frontier: set[str] = set()
            for entity_id in frontier:
                relation_ids = self._graph.related_relation_ids(entity_id)
                included_relation_ids.update(relation_ids)

                for relation_id in relation_ids:
                    relation = self._graph.relations_by_id.get(relation_id)
                    if relation is None:
                        continue
                    if relation.source_id not in visited:
                        visited.add(relation.source_id)
                        next_frontier.add(relation.source_id)
                    if relation.target_id not in visited:
                        visited.add(relation.target_id)
                        next_frontier.add(relation.target_id)
            frontier = next_frontier

        entities = [self._graph.entities_by_id[eid].to_dict() for eid in sorted(visited) if eid in self._graph.entities_by_id]
        relations = [
            self._graph.relations_by_id[rid].to_dict()
            for rid in sorted(included_relation_ids)
            if rid in self._graph.relations_by_id
        ]

        return {
            "keywords": normalize_query_keywords(keywords),
            "depth": depth,
            "entities": entities,
            "relations": relations,
        }

    def get_stats(self) -> dict[str, Any]:
        self._recalculate_memory_bytes()
        self._set_dirty_count()
        memory_limit = self.config.memory_limit_bytes
        current = int(self._metadata.get("current_memory_bytes", 0))

        return {
            "entity_count": len(self._graph.entities_by_id),
            "relation_count": len(self._graph.relations_by_id),
            "memory_limit_bytes": memory_limit,
            "current_memory_bytes": current,
            "memory_pressure": round((current / memory_limit) if memory_limit else 0.0, 6),
            "snapshot_version": int(self._metadata.get("snapshot_version", 0)),
            "last_snapshot_at": self._metadata.get("last_snapshot_at"),
            "last_sync_at": self._metadata.get("last_sync_at"),
            "dirty_object_count": int(self._metadata.get("dirty_object_count", 0)),
            "eviction_count": int(self._metadata.get("eviction_count", 0)),
            "compaction_count": int(self._metadata.get("compaction_count", 0)),
            "package_version": self._metadata.get("package_version", "0.1.0"),
        }

    def close(self) -> None:
        self.flush()

    def __enter__(self) -> "EndBrain":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self.flush()
        return False
