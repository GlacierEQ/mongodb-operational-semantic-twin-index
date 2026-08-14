"""Convert change-stream-style events into Operational Semantic Twin mutations."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


class ChangeStreamAdapterError(ValueError):
    pass


def _stable_id(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_stable_id(value).encode("utf-8")).hexdigest()


def events_to_mutations(
    events: Iterable[dict[str, Any]],
    *,
    semantic_fields: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Normalize insert/replace/update/delete events into versioned twin mutations.

    A full post-image is required for insert/replace/update so semantic state is
    always derived from authoritative document truth rather than a partial patch.
    ``document_version`` is deliberately required because inferring versions from
    event order would turn transport order into document authority.
    """
    mutations: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ChangeStreamAdapterError(f"event_{index}_not_object")
        operation = str(event.get("operationType", "")).strip().lower()
        if operation not in {"insert", "replace", "update", "delete"}:
            raise ChangeStreamAdapterError(f"event_{index}_operation_invalid")
        key = event.get("documentKey")
        if not isinstance(key, dict) or "_id" not in key:
            raise ChangeStreamAdapterError(f"event_{index}_document_key_missing")
        document_id = _stable_id(key["_id"])
        version = event.get("document_version")
        if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
            raise ChangeStreamAdapterError(f"event_{index}_document_version_invalid")

        resume_token = event.get("_id")
        if resume_token is None:
            raise ChangeStreamAdapterError(f"event_{index}_resume_token_missing")
        event_id = _digest(resume_token)
        if event_id in seen_event_ids:
            raise ChangeStreamAdapterError(f"duplicate_event:{event_id}")
        seen_event_ids.add(event_id)

        transaction_identity = {
            "lsid": event.get("lsid"),
            "txnNumber": event.get("txnNumber"),
            "clusterTime": event.get("clusterTime"),
        }
        transaction_id = _digest(transaction_identity)

        if operation == "delete":
            document = None
            twin_operation = "delete"
        else:
            document = event.get("fullDocument")
            if not isinstance(document, dict):
                raise ChangeStreamAdapterError(f"event_{index}_full_document_required")
            twin_operation = "upsert"

        mutations.append(
            {
                "operation": twin_operation,
                "document_id": document_id,
                "mutation_id": event_id,
                "transaction_id": transaction_id,
                "version": version,
                "document": document,
                "semantic_fields": semantic_fields,
                "change_stream_evidence": {
                    "operation_type": operation,
                    "resume_token_digest": event_id,
                    "transaction_digest": transaction_id,
                },
            }
        )
    if not mutations:
        raise ChangeStreamAdapterError("events_missing")
    return mutations
