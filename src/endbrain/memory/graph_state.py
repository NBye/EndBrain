from __future__ import annotations

from collections import defaultdict

from endbrain.model import Entity, Relation
from endbrain.utils.text import normalize_keywords


class InMemoryGraph:
    def __init__(self) -> None:
        self.entities_by_id: dict[str, Entity] = {}
        self.relations_by_id: dict[str, Relation] = {}

        self.adj_out: dict[str, set[str]] = defaultdict(set)
        self.adj_in: dict[str, set[str]] = defaultdict(set)

        self.entity_keyword_index: dict[str, set[str]] = defaultdict(set)
        self.relation_keyword_index: dict[str, set[str]] = defaultdict(set)

        self.dirty_entities: set[str] = set()
        self.dirty_relations: set[str] = set()
        self.deleted_entities: set[str] = set()
        self.deleted_relations: set[str] = set()

    def clear_dirty_tracking(self) -> None:
        self.dirty_entities.clear()
        self.dirty_relations.clear()
        self.deleted_entities.clear()
        self.deleted_relations.clear()

    def related_relation_ids(self, entity_id: str) -> set[str]:
        return set(self.adj_out.get(entity_id, set())) | set(self.adj_in.get(entity_id, set()))

    def entity_degree(self, entity_id: str) -> int:
        return len(self.adj_out.get(entity_id, set())) + len(self.adj_in.get(entity_id, set()))

    def _entity_tokens(self, entity: Entity) -> list[str]:
        raw = list(entity.keywords)
        raw.extend([entity.name, entity.entity_type])
        return normalize_keywords(raw)

    def _relation_tokens(self, relation: Relation) -> list[str]:
        raw = list(relation.keywords)
        raw.append(relation.relation_type)
        return normalize_keywords(raw)

    def _drop_entity_index(self, entity: Entity) -> None:
        for token in self._entity_tokens(entity):
            bucket = self.entity_keyword_index.get(token)
            if not bucket:
                continue
            bucket.discard(entity.id)
            if not bucket:
                self.entity_keyword_index.pop(token, None)

    def _drop_relation_index(self, relation: Relation) -> None:
        for token in self._relation_tokens(relation):
            bucket = self.relation_keyword_index.get(token)
            if not bucket:
                continue
            bucket.discard(relation.id)
            if not bucket:
                self.relation_keyword_index.pop(token, None)

    def upsert_entity(self, entity: Entity, mark_dirty: bool = True) -> None:
        old = self.entities_by_id.get(entity.id)
        if old:
            self._drop_entity_index(old)

        self.entities_by_id[entity.id] = entity
        for token in self._entity_tokens(entity):
            self.entity_keyword_index[token].add(entity.id)

        if mark_dirty:
            self.dirty_entities.add(entity.id)
            self.deleted_entities.discard(entity.id)

    def upsert_relation(self, relation: Relation, mark_dirty: bool = True) -> None:
        old = self.relations_by_id.get(relation.id)
        if old:
            self._drop_relation_index(old)
            self.adj_out.get(old.source_id, set()).discard(old.id)
            self.adj_in.get(old.target_id, set()).discard(old.id)

        self.relations_by_id[relation.id] = relation
        self.adj_out[relation.source_id].add(relation.id)
        self.adj_in[relation.target_id].add(relation.id)

        for token in self._relation_tokens(relation):
            self.relation_keyword_index[token].add(relation.id)

        if mark_dirty:
            self.dirty_relations.add(relation.id)
            self.deleted_relations.discard(relation.id)

    def remove_relation(self, relation_id: str, mark_deleted: bool = True) -> bool:
        relation = self.relations_by_id.pop(relation_id, None)
        if relation is None:
            return False

        self._drop_relation_index(relation)
        self.adj_out.get(relation.source_id, set()).discard(relation_id)
        self.adj_in.get(relation.target_id, set()).discard(relation_id)

        if mark_deleted:
            self.deleted_relations.add(relation_id)
            self.dirty_relations.discard(relation_id)
        return True

    def remove_entity(self, entity_id: str, mark_deleted: bool = True) -> list[str]:
        entity = self.entities_by_id.pop(entity_id, None)
        if entity is None:
            return []

        relation_ids = sorted(self.related_relation_ids(entity_id))
        for relation_id in relation_ids:
            self.remove_relation(relation_id, mark_deleted=mark_deleted)

        self._drop_entity_index(entity)
        self.adj_out.pop(entity_id, None)
        self.adj_in.pop(entity_id, None)

        if mark_deleted:
            self.deleted_entities.add(entity_id)
            self.dirty_entities.discard(entity_id)
        return relation_ids
