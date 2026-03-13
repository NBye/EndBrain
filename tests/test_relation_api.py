from __future__ import annotations

import pytest


def test_add_relation_requires_existing_entities(brain) -> None:
    brain.add_entity("e1", "Python", "technology")

    with pytest.raises(KeyError):
        brain.add_relation("r1", "e1", "e404", "depends_on")


def test_relation_crud_and_cascade_delete(brain) -> None:
    brain.add_entity("e1", "Python", "technology")
    brain.add_entity("e2", "FastAPI", "framework")

    created = brain.add_relation(
        "r1",
        "e2",
        "e1",
        "built_on",
        keywords=["dependency"],
        metadata={"source": "manual"},
    )
    assert created["id"] == "r1"

    loaded = brain.get_relation("r1")
    assert loaded is not None
    assert loaded["metadata"]["source"] == "manual"

    updated = brain.update_relation("r1", relation_type="uses")
    assert updated["relation_type"] == "uses"

    assert brain.delete_entity("e2") is True
    assert brain.get_relation("r1") is None
