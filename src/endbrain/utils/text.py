from __future__ import annotations


def normalize_keyword(value: str) -> str:
    return value.strip().lower()


def normalize_keywords(values: list[str] | tuple[str, ...] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = normalize_keyword(value)
        if not token or token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return normalized
