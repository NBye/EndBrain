from __future__ import annotations

import pytest


def _seed(brain) -> None:
    brain.add_entity("e1", "Python", "technology", keywords=["python", "backend"], weight=0.9, importance=0.9)
    brain.add_entity("e2", "FastAPI", "framework", keywords=["python", "api"], weight=0.7, importance=0.7)
    brain.add_entity("e3", "Golang", "technology", keywords=["go"], weight=0.6, importance=0.6)
    brain.add_relation("r1", "e2", "e1", "built_on", keywords=["dependency"], weight=0.8, importance=0.8)


def test_query_entities_and_top_k(brain) -> None:
    _seed(brain)
    results = brain.query_entities(["python"], top_k=2)

    assert len(results) == 2
    assert results[0]["match_weight"] >= results[1]["match_weight"]
    assert all(0.0 <= item["match_weight"] <= 1.0 for item in results)


def test_query_relations(brain) -> None:
    _seed(brain)
    results = brain.query_relations(["built_on"], top_k=5)

    assert len(results) >= 1
    assert results[0]["id"] == "r1"


def test_query_graph_depth_rules(brain) -> None:
    _seed(brain)

    d0 = brain.query_graph(["python"], depth=0)
    d1 = brain.query_graph(["python"], depth=1)
    d9 = brain.query_graph(["python"], depth=9)

    assert len(d1["relations"]) >= len(d0["relations"])
    assert d9["depth"] == 3

    with pytest.raises(ValueError):
        brain.query_graph(["python"], depth=-1)


def test_empty_keywords_return_empty(brain) -> None:
    _seed(brain)
    assert brain.query_entities([]) == []
    assert brain.query_relations([]) == []
