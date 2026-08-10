"""Behavioral scaffold tests for OperationalSemanticTwinIndex.

Filling AI: keep allow/refuse polarity; deepen assertions as the real algorithm lands.
"""
from __future__ import annotations

from operational_semantic_twin_index import Decision, OperationalSemanticTwinIndex, OperationalSemanticTwinIndexRequest


def test_allow_path_returns_digest() -> None:
    mech = OperationalSemanticTwinIndex()
    receipt = mech.evaluate(
        OperationalSemanticTwinIndexRequest(subject_id="a", payload={"x": 1}, budget=1.0)
    )
    assert receipt.decision is Decision.ALLOW
    assert len(receipt.digest) == 64
    assert receipt.metrics.get("scaffold") is True


def test_refuse_missing_subject() -> None:
    mech = OperationalSemanticTwinIndex()
    receipt = mech.evaluate(OperationalSemanticTwinIndexRequest(subject_id="  ", payload={}, budget=1.0))
    assert receipt.decision is Decision.REFUSE
    assert "subject_id_missing" in receipt.reasons


def test_refuse_non_positive_budget() -> None:
    mech = OperationalSemanticTwinIndex()
    receipt = mech.evaluate(OperationalSemanticTwinIndexRequest(subject_id="a", payload={}, budget=0.0))
    assert receipt.decision is Decision.REFUSE
    assert "budget_non_positive" in receipt.reasons


def test_different_payloads_different_digests() -> None:
    mech = OperationalSemanticTwinIndex()
    a = mech.evaluate(OperationalSemanticTwinIndexRequest(subject_id="a", payload={"n": 1}, budget=1.0))
    b = mech.evaluate(OperationalSemanticTwinIndexRequest(subject_id="a", payload={"n": 2}, budget=1.0))
    assert a.digest != b.digest
