from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from endbrain.utils.text import normalize_keywords
from endbrain.utils.time import utc_now_iso


JSONDict = dict[str, Any]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(slots=True)
class Entity:
    id: str
    name: str
    entity_type: str
    keywords: list[str] = field(default_factory=list)
    weight: float = 0.5
    importance: float = 0.5
    metadata: JSONDict = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    last_access_at: str = field(default_factory=utc_now_iso)
    access_count: int = 0

    def __post_init__(self) -> None:
        self.keywords = normalize_keywords(self.keywords)
        self.weight = _clamp01(self.weight)
        self.importance = _clamp01(self.importance)

    def touch(self) -> None:
        self.last_access_at = utc_now_iso()
        self.access_count += 1

    def to_dict(self) -> JSONDict:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "keywords": list(self.keywords),
            "weight": self.weight,
            "importance": self.importance,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_access_at": self.last_access_at,
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, payload: JSONDict) -> "Entity":
        return cls(
            id=str(payload["id"]),
            name=str(payload.get("name", "")),
            entity_type=str(payload.get("entity_type", "")),
            keywords=list(payload.get("keywords", [])),
            weight=float(payload.get("weight", 0.5)),
            importance=float(payload.get("importance", 0.5)),
            metadata=dict(payload.get("metadata", {})),
            created_at=str(payload.get("created_at", utc_now_iso())),
            updated_at=str(payload.get("updated_at", utc_now_iso())),
            last_access_at=str(payload.get("last_access_at", utc_now_iso())),
            access_count=int(payload.get("access_count", 0)),
        )


@dataclass(slots=True)
class Relation:
    id: str
    source_id: str
    target_id: str
    relation_type: str
    keywords: list[str] = field(default_factory=list)
    weight: float = 0.5
    importance: float = 0.5
    metadata: JSONDict = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    last_access_at: str = field(default_factory=utc_now_iso)
    access_count: int = 0

    def __post_init__(self) -> None:
        self.keywords = normalize_keywords(self.keywords)
        self.weight = _clamp01(self.weight)
        self.importance = _clamp01(self.importance)

    def touch(self) -> None:
        self.last_access_at = utc_now_iso()
        self.access_count += 1

    def to_dict(self) -> JSONDict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "keywords": list(self.keywords),
            "weight": self.weight,
            "importance": self.importance,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_access_at": self.last_access_at,
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, payload: JSONDict) -> "Relation":
        return cls(
            id=str(payload["id"]),
            source_id=str(payload.get("source_id", "")),
            target_id=str(payload.get("target_id", "")),
            relation_type=str(payload.get("relation_type", "")),
            keywords=list(payload.get("keywords", [])),
            weight=float(payload.get("weight", 0.5)),
            importance=float(payload.get("importance", 0.5)),
            metadata=dict(payload.get("metadata", {})),
            created_at=str(payload.get("created_at", utc_now_iso())),
            updated_at=str(payload.get("updated_at", utc_now_iso())),
            last_access_at=str(payload.get("last_access_at", utc_now_iso())),
            access_count=int(payload.get("access_count", 0)),
        )
