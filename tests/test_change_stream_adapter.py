from __future__ import annotations

import pytest

from change_stream_adapter import ChangeStreamAdapterError, events_to_mutations
from operational_semantic_twin_index import OperationalSemanticTwinIndex


def event(operation: str, version: int, token: int, full_document=None):
    return {
        "_id": {"token": token},
        "operationType": operation,
        "documentKey": {"_id": "doc-1"},
        "document_version": version,
        "clusterTime": token,
        "fullDocument": full_document,
    }


def test_change_stream_events_apply_as_versioned_twin_mutations() -> None:
    events = [
        event("insert", 1, 1, {"title": "alpha", "body": "one"}),
        event("update", 2, 2, {"title": "alpha", "body": "two"}),
        event("delete", 3, 3),
    ]
    mutations = events_to_mutations(events, semantic_fields=["title", "body"])
    state, emitted = OperationalSemanticTwinIndex.apply_mutations({}, mutations)

    assert len(emitted) == 3
    assert state['"doc-1"']["source_version"] == 3
    assert state['"doc-1"']["tombstone"] is True
    assert all(len(row["mutation_id"]) == 64 for row in mutations)
    assert all(len(row["transaction_id"]) == 64 for row in mutations)


def test_partial_update_without_full_post_image_is_refused() -> None:
    with pytest.raises(ChangeStreamAdapterError, match="full_document_required"):
        events_to_mutations([event("update", 1, 1)])


def test_change_stream_adapter_refuses_inferred_versions_and_duplicate_tokens() -> None:
    missing_version = event("insert", 1, 1, {"x": 1})
    missing_version.pop("document_version")
    with pytest.raises(ChangeStreamAdapterError, match="document_version_invalid"):
        events_to_mutations([missing_version])

    duplicate = event("insert", 1, 1, {"x": 1})
    with pytest.raises(ChangeStreamAdapterError, match="duplicate_event"):
        events_to_mutations([duplicate, duplicate])
