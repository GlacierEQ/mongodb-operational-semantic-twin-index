from __future__ import annotations

from operational_semantic_twin_index import Decision, OperationalSemanticTwinIndex, OperationalSemanticTwinIndexRequest


def mutation(mid: str, version: int, *, doc_id: str = "doc-1", operation: str = "upsert", document: dict | None = None, tx: str | None = None) -> dict:
    return {
        "mutation_id": mid,
        "transaction_id": tx or f"tx-{version}",
        "document_id": doc_id,
        "version": version,
        "operation": operation,
        "document": ({"title": f"v{version}", "body": "semantic text", "counter": version} if document is None and operation == "upsert" else document),
        "semantic_fields": ["title", "body"] if operation == "upsert" else None,
    }


def evaluate(payload: dict):
    return OperationalSemanticTwinIndex().evaluate(
        OperationalSemanticTwinIndexRequest(subject_id="collection-a", payload=payload, budget=1.0)
    )


def test_upsert_derives_transaction_linked_semantic_projection() -> None:
    receipt = evaluate({"mode": "apply", "mutations": [mutation("m1", 1)]})
    assert receipt.decision is Decision.ALLOW
    projection = receipt.metrics["result"]["projection_state"]["doc-1"]
    assert projection["source_version"] == 1
    assert projection["transaction_id"] == "tx-1"
    assert projection["mutation_id"] == "m1"
    assert projection["tombstone"] is False
    assert len(projection["authoritative_digest"]) == 64
    assert len(projection["semantic_digest"]) == 64
    assert len(projection["projection_digest"]) == 64


def test_next_version_advances_from_existing_projection() -> None:
    first = evaluate({"mode": "apply", "mutations": [mutation("m1", 1)]})
    state = first.metrics["result"]["projection_state"]
    second = evaluate({"mode": "apply", "projection_state": state, "mutations": [mutation("m2", 2)]})
    assert second.decision is Decision.ALLOW
    assert second.metrics["result"]["projection_state"]["doc-1"]["source_version"] == 2


def test_version_gap_fails_closed() -> None:
    first = evaluate({"mode": "apply", "mutations": [mutation("m1", 1)]})
    receipt = evaluate({"mode": "apply", "projection_state": first.metrics["result"]["projection_state"], "mutations": [mutation("m3", 3)]})
    assert receipt.decision is Decision.REFUSE
    assert any(reason.startswith("version_gap:doc-1") for reason in receipt.reasons)


def test_exact_mutation_replay_is_idempotent() -> None:
    first = evaluate({"mode": "apply", "mutations": [mutation("m1", 1)]})
    state = first.metrics["result"]["projection_state"]
    replay = evaluate({"mode": "apply", "projection_state": state, "mutations": [mutation("m1", 1)]})
    assert replay.decision is Decision.ALLOW
    assert replay.metrics["result"]["emitted"][0]["idempotent_replay"] is True
    assert replay.metrics["result"]["projection_state"] == state


def test_mutation_id_reuse_with_different_content_is_refused() -> None:
    first = evaluate({"mode": "apply", "mutations": [mutation("m1", 1)]})
    changed = mutation("m1", 1, document={"title": "different", "body": "semantic text", "counter": 1})
    receipt = evaluate({"mode": "apply", "projection_state": first.metrics["result"]["projection_state"], "mutations": [changed]})
    assert receipt.decision is Decision.REFUSE
    assert "mutation_id_reused:m1" in receipt.reasons


def test_delete_emits_tombstone_and_verify_accepts_absence() -> None:
    first = evaluate({"mode": "apply", "mutations": [mutation("m1", 1)]})
    deleted = evaluate({
        "mode": "apply",
        "projection_state": first.metrics["result"]["projection_state"],
        "mutations": [mutation("m2", 2, operation="delete", document=None)],
    })
    state = deleted.metrics["result"]["projection_state"]
    assert state["doc-1"]["tombstone"] is True
    verified = evaluate({"mode": "verify", "projection_state": state, "authoritative_snapshot": {}})
    assert verified.decision is Decision.ALLOW
    assert verified.metrics["result"]["divergences"] == []


def test_verify_detects_content_divergence_even_at_same_version() -> None:
    first = evaluate({"mode": "apply", "mutations": [mutation("m1", 1)]})
    snapshot = {"doc-1": {"version": 1, "document": {"title": "tampered", "body": "semantic text", "counter": 1}}}
    receipt = evaluate({"mode": "verify", "projection_state": first.metrics["result"]["projection_state"], "authoritative_snapshot": snapshot})
    assert receipt.decision is Decision.REFUSE
    assert "operational_semantic_divergence_detected" in receipt.reasons
    assert receipt.metrics["result"]["divergences"][0]["kind"] == "content_digest_mismatch"


def test_semantic_projection_can_remain_stable_while_authoritative_digest_changes() -> None:
    first = evaluate({"mode": "apply", "mutations": [mutation("m1", 1, document={"title": "same", "body": "same", "counter": 1})]})
    state1 = first.metrics["result"]["projection_state"]
    second = evaluate({"mode": "apply", "projection_state": state1, "mutations": [mutation("m2", 2, document={"title": "same", "body": "same", "counter": 2})]})
    state2 = second.metrics["result"]["projection_state"]
    assert state1["doc-1"]["semantic_digest"] == state2["doc-1"]["semantic_digest"]
    assert state1["doc-1"]["authoritative_digest"] != state2["doc-1"]["authoritative_digest"]
