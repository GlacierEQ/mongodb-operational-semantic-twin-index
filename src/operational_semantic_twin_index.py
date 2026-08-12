"""Operational-Semantic Twin Index.

Derives deterministic semantic projections directly from authoritative document
mutations. Every projection is bound to document version, transaction id,
mutation id and authoritative content digest so retrieval state cannot silently
drift from operational state.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


class Decision(str, Enum):
    ALLOW = "ALLOW"
    REFUSE = "REFUSE"


@dataclass(frozen=True)
class OperationalSemanticTwinIndexRequest:
    subject_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    budget: float = 1.0
    grant_id: str | None = None
    not_after: float | None = None


@dataclass(frozen=True)
class OperationalSemanticTwinIndexReceipt:
    decision: Decision
    reasons: tuple[str, ...]
    digest: str
    metrics: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"decision": self.decision.value, "reasons": list(self.reasons), "digest": self.digest, "metrics": self.metrics}


class TwinIndexError(ValueError):
    pass


class OperationalSemanticTwinIndex:
    MIN_BUDGET = 0.0
    OPERATIONS = frozenset({"upsert", "delete"})

    @staticmethod
    def _positive_int(value: Any, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise TwinIndexError(f"{label}_invalid")
        return value

    @staticmethod
    def _id(value: Any, label: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise TwinIndexError(f"{label}_missing")
        return value

    @classmethod
    def _projection(cls, raw: Any, document_id: str) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise TwinIndexError(f"projection_not_object:{document_id}")
        version = cls._positive_int(raw.get("source_version"), f"projection_version:{document_id}")
        authoritative_digest = str(raw.get("authoritative_digest", "")).strip()
        semantic_digest = str(raw.get("semantic_digest", "")).strip()
        projection_digest = str(raw.get("projection_digest", "")).strip()
        if not SHA256_RE.fullmatch(authoritative_digest):
            raise TwinIndexError(f"authoritative_digest_invalid:{document_id}")
        if not SHA256_RE.fullmatch(semantic_digest):
            raise TwinIndexError(f"semantic_digest_invalid:{document_id}")
        if projection_digest and not SHA256_RE.fullmatch(projection_digest):
            raise TwinIndexError(f"projection_digest_invalid:{document_id}")
        return {
            "document_id": document_id,
            "source_version": version,
            "transaction_id": cls._id(raw.get("transaction_id"), f"projection_transaction_id:{document_id}"),
            "mutation_id": cls._id(raw.get("mutation_id"), f"projection_mutation_id:{document_id}"),
            "authoritative_digest": authoritative_digest,
            "semantic_digest": semantic_digest,
            "tombstone": bool(raw.get("tombstone", False)),
            "projection_digest": projection_digest,
        }

    @classmethod
    def _state(cls, raw: Any) -> dict[str, dict[str, Any]]:
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise TwinIndexError("projection_state_not_object")
        return {str(doc_id): cls._projection(value, str(doc_id)) for doc_id, value in sorted(raw.items())}

    @staticmethod
    def _semantic_payload(document: dict[str, Any], fields: list[str] | None) -> dict[str, Any]:
        if fields is None:
            return document
        if not isinstance(fields, list) or not fields or any(not str(x).strip() for x in fields):
            raise TwinIndexError("semantic_fields_invalid")
        names = sorted(set(str(x).strip() for x in fields))
        return {name: document.get(name) for name in names}

    @classmethod
    def _mutation(cls, raw: Any, index: int) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise TwinIndexError(f"mutation_{index}_not_object")
        operation = str(raw.get("operation", "")).strip().lower()
        if operation not in cls.OPERATIONS:
            raise TwinIndexError(f"mutation_{index}_operation_invalid")
        document_id = cls._id(raw.get("document_id"), f"mutation_{index}_document_id")
        mutation_id = cls._id(raw.get("mutation_id"), f"mutation_{index}_mutation_id")
        transaction_id = cls._id(raw.get("transaction_id"), f"mutation_{index}_transaction_id")
        version = cls._positive_int(raw.get("version"), f"mutation_{index}_version")
        document = raw.get("document")
        if operation == "upsert" and not isinstance(document, dict):
            raise TwinIndexError(f"mutation_{index}_document_missing")
        if operation == "delete" and document not in (None, {}):
            raise TwinIndexError(f"mutation_{index}_delete_carries_document")
        return {
            "operation": operation,
            "document_id": document_id,
            "mutation_id": mutation_id,
            "transaction_id": transaction_id,
            "version": version,
            "document": document,
            "semantic_fields": raw.get("semantic_fields"),
        }

    @classmethod
    def _derive(cls, mutation: dict[str, Any]) -> dict[str, Any]:
        tombstone = mutation["operation"] == "delete"
        authoritative = None if tombstone else mutation["document"]
        semantic = {"tombstone": True} if tombstone else cls._semantic_payload(mutation["document"], mutation["semantic_fields"])
        body = {
            "document_id": mutation["document_id"],
            "source_version": mutation["version"],
            "transaction_id": mutation["transaction_id"],
            "mutation_id": mutation["mutation_id"],
            "authoritative_digest": _digest(authoritative),
            "semantic_digest": _digest(semantic),
            "tombstone": tombstone,
        }
        return {**body, "projection_digest": _digest(body)}

    @classmethod
    def apply_mutations(cls, state: dict[str, dict[str, Any]], raw_mutations: Any) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        if not isinstance(raw_mutations, list) or not raw_mutations:
            raise TwinIndexError("mutations_missing")
        next_state = {k: dict(v) for k, v in state.items()}
        emitted: list[dict[str, Any]] = []
        seen_mutations: set[str] = {v["mutation_id"] for v in state.values()}
        for index, raw in enumerate(raw_mutations):
            mutation = cls._mutation(raw, index)
            if mutation["mutation_id"] in seen_mutations:
                current = next_state.get(mutation["document_id"])
                candidate = cls._derive(mutation)
                if current and current.get("projection_digest") == candidate["projection_digest"]:
                    emitted.append({**candidate, "idempotent_replay": True})
                    continue
                raise TwinIndexError(f"mutation_id_reused:{mutation['mutation_id']}")
            current = next_state.get(mutation["document_id"])
            expected_version = 1 if current is None else int(current["source_version"]) + 1
            if mutation["version"] != expected_version:
                raise TwinIndexError(f"version_gap:{mutation['document_id']}:expected_{expected_version}:got_{mutation['version']}")
            projection = cls._derive(mutation)
            next_state[mutation["document_id"]] = projection
            emitted.append(projection)
            seen_mutations.add(mutation["mutation_id"])
        return next_state, emitted

    @classmethod
    def verify_snapshot(cls, state: dict[str, dict[str, Any]], authoritative: Any) -> list[dict[str, Any]]:
        if not isinstance(authoritative, dict):
            raise TwinIndexError("authoritative_snapshot_not_object")
        divergences: list[dict[str, Any]] = []
        all_ids = sorted(set(state) | set(str(k) for k in authoritative))
        for document_id in all_ids:
            projection = state.get(document_id)
            record = authoritative.get(document_id)
            if record is None:
                if projection and not projection["tombstone"]:
                    divergences.append({"document_id": document_id, "kind": "projection_not_tombstoned"})
                continue
            if not isinstance(record, dict):
                raise TwinIndexError(f"authoritative_record_not_object:{document_id}")
            version = cls._positive_int(record.get("version"), f"authoritative_version:{document_id}")
            document = record.get("document")
            if not isinstance(document, dict):
                raise TwinIndexError(f"authoritative_document_missing:{document_id}")
            digest = _digest(document)
            if projection is None:
                divergences.append({"document_id": document_id, "kind": "projection_missing"})
            elif projection["tombstone"]:
                divergences.append({"document_id": document_id, "kind": "unexpected_tombstone"})
            elif projection["source_version"] != version:
                divergences.append({"document_id": document_id, "kind": "version_mismatch", "authoritative_version": version, "projection_version": projection["source_version"]})
            elif projection["authoritative_digest"] != digest:
                divergences.append({"document_id": document_id, "kind": "content_digest_mismatch"})
        return divergences

    def evaluate(self, req: OperationalSemanticTwinIndexRequest) -> OperationalSemanticTwinIndexReceipt:
        reasons: list[str] = []
        if not str(req.subject_id or "").strip():
            reasons.append("subject_id_missing")
        if isinstance(req.budget, bool) or not isinstance(req.budget, (int, float)) or not math.isfinite(float(req.budget)) or float(req.budget) <= self.MIN_BUDGET:
            reasons.append("budget_non_positive_or_invalid")
        payload = req.payload if isinstance(req.payload, dict) else {}
        if not isinstance(req.payload, dict):
            reasons.append("payload_not_object")
        result: dict[str, Any] | None = None
        try:
            state = self._state(payload.get("projection_state"))
            mode = str(payload.get("mode", "apply")).strip().lower()
            if mode == "apply":
                next_state, emitted = self.apply_mutations(state, payload.get("mutations"))
                result = {
                    "mode": "apply",
                    "emitted": emitted,
                    "projection_state": next_state,
                    "state_digest": _digest(next_state),
                }
            elif mode == "verify":
                divergences = self.verify_snapshot(state, payload.get("authoritative_snapshot"))
                result = {"mode": "verify", "divergences": divergences, "state_digest": _digest(state)}
                if divergences:
                    reasons.append("operational_semantic_divergence_detected")
            else:
                raise TwinIndexError("mode_invalid")
        except TwinIndexError as exc:
            reasons.append(str(exc))
        decision = Decision.REFUSE if reasons else Decision.ALLOW
        metrics = {"result": result, "projection_count": len(result.get("projection_state", {})) if result else 0}
        body = {"subject_id": req.subject_id, "decision": decision.value, "reasons": reasons, "metrics": metrics}
        return OperationalSemanticTwinIndexReceipt(decision, tuple(reasons or ["semantic_twin_consistent"]), _digest(body), metrics)


Mechanism = OperationalSemanticTwinIndex
