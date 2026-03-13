from __future__ import annotations

import math
from typing import Any

from endbrain.model.records import Entity, Relation
from endbrain.utils.text import normalize_keywords
from endbrain.utils.time import iso_to_ts


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def normalize_query_keywords(keywords: list[str] | None) -> list[str]:
    return normalize_keywords(keywords)


def _keyword_hit_ratio(query_keywords: list[str], candidate_keywords: list[str]) -> float:
    if not query_keywords:
        return 0.0
    if not candidate_keywords:
        return 0.0
    candidate = set(normalize_keywords(candidate_keywords))
    hit = sum(1 for token in query_keywords if token in candidate)
    return hit / max(1, len(query_keywords))


def score_entity(entity: Entity, query_keywords: list[str]) -> tuple[float, str]:
    if not query_keywords:
        return 0.0, "empty_query"

    name = entity.name.strip().lower()
    exact = any(token == name for token in query_keywords)
    contains = any(token in name for token in query_keywords)
    keyword_ratio = _keyword_hit_ratio(query_keywords, entity.keywords)

    keyword_match_score = _clamp01((0.55 * keyword_ratio) + (0.35 * float(exact)) + (0.10 * float(contains)))
    final_weight = _clamp01((0.35 * entity.weight) + (0.45 * keyword_match_score) + (0.20 * entity.importance))

    if exact:
        reason = "name_exact"
    elif contains:
        reason = "name_contains"
    elif keyword_ratio > 0:
        reason = "keyword_hit"
    else:
        reason = "weak_match"
    return final_weight, reason


def score_relation(relation: Relation, query_keywords: list[str]) -> tuple[float, str]:
    if not query_keywords:
        return 0.0, "empty_query"

    relation_type = relation.relation_type.strip().lower()
    exact = any(token == relation_type for token in query_keywords)
    contains = any(token in relation_type for token in query_keywords)
    keyword_ratio = _keyword_hit_ratio(query_keywords, relation.keywords)

    keyword_match_score = _clamp01((0.55 * keyword_ratio) + (0.35 * float(exact)) + (0.10 * float(contains)))
    final_weight = _clamp01((0.35 * relation.weight) + (0.45 * keyword_match_score) + (0.20 * relation.importance))

    if exact:
        reason = "relation_exact"
    elif contains:
        reason = "relation_contains"
    elif keyword_ratio > 0:
        reason = "keyword_hit"
    else:
        reason = "weak_match"
    return final_weight, reason


def retain_score(record: Entity | Relation, now_ts: float, topology_degree: int) -> float:
    age_seconds = max(0.0, now_ts - iso_to_ts(record.last_access_at))
    recency_score = 1.0 / (1.0 + (age_seconds / 86_400.0))
    frequency_score = min(1.0, math.log1p(record.access_count) / math.log1p(64))
    topology_score = min(1.0, topology_degree / 10.0)

    return _clamp01(
        (0.30 * recency_score)
        + (0.20 * frequency_score)
        + (0.20 * record.importance)
        + (0.20 * record.weight)
        + (0.10 * topology_score)
    )


def serialize_match_payload(payload: dict[str, Any], score: float, reason: str) -> dict[str, Any]:
    out = dict(payload)
    out["match_weight"] = round(score, 6)
    out["match_reason"] = reason
    return out
