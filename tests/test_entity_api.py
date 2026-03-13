from __future__ import annotations

import pytest


def test_add_get_update_delete_entity(brain) -> None:
    created = brain.add_entity(
        "e1",
        "Python",
        "technology",
        keywords=["python", "backend"],
        weight=0.9,
        importance=0.95,
        metadata={"source": "manual", "tags": ["lang"]},
    )

    assert created["id"] == "e1"
    assert created["metadata"]["source"] == "manual"

    loaded = brain.get_entity("e1")
    assert loaded is not None
    assert loaded["name"] == "Python"

    updated = brain.update_entity("e1", name="Python3", metadata={"source": "edit"})
    assert updated["name"] == "Python3"
    assert updated["metadata"]["source"] == "edit"

    assert brain.delete_entity("e1") is True
    assert brain.get_entity("e1") is None


def test_add_entity_clamps_weight_and_importance(brain) -> None:
    created = brain.add_entity(
        "e2",
        "BadRange",
        "test",
        weight=9,
        importance=-3,
    )
    assert created["weight"] == 1.0
    assert created["importance"] == 0.0


def test_metadata_must_be_json_serializable(brain) -> None:
    with pytest.raises(ValueError):
        brain.add_entity(
            "e3",
            "Nope",
            "test",
            metadata={"x": object()},
        )
