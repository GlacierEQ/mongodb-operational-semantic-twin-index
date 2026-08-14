# Operational-Semantic Twin Index

Independent GlacierEQ portfolio implementation aligned to **MongoDB** operating themes.

> **Not affiliated.** This repository is not affiliated with, endorsed by, employed by, or deployed at MongoDB. No proprietary access, production deployment, customer impact, or company partnership is claimed.

## Purpose

Keep operational document truth and semantic retrieval state from silently diverging.

Instead of treating the vector/semantic index as an independently mutable database, **Operational-Semantic Twin Index** derives every semantic projection from an authoritative document mutation and binds the result to the source document version, transaction id, mutation id, authoritative content digest, semantic-input digest, and projection digest.

## Implemented mechanism

`OperationalSemanticTwinIndex` supports two real operations.

### Apply mutations

- accepts ordered `upsert` / `delete` mutations;
- requires transaction and mutation identities;
- enforces exact per-document version continuity;
- derives semantic content only from declared semantic fields;
- emits content-addressed projection records;
- permits exact idempotent replay but refuses mutation-id reuse with different content;
- emits tombstones for deletes rather than silently leaving stale retrieval state.

### Verify authoritative state

Given a projection state and authoritative snapshot, the verifier exposes:

- missing projections;
- unexpected tombstones;
- projections that should have been tombstoned;
- version mismatch;
- authoritative content-digest mismatch.

Any divergence fails closed with `operational_semantic_divergence_detected`.

## Change-stream evidence adapter

`change_stream_adapter.events_to_mutations()` converts change-stream-style insert/replace/update/delete events into the twin's authoritative mutation contract.

The adapter deliberately preserves authority instead of inferring it from event order:

- every event must carry a stable resume token and explicit `document_version`;
- document identity is derived from `documentKey._id`;
- resume-token and transaction identities become deterministic SHA-256 mutation/transaction ids;
- insert/replace/update require a full post-image so semantic state is derived from authoritative document truth, not a partial patch;
- delete becomes an explicit tombstone mutation;
- duplicate resume tokens, missing versions, missing post-images, and unsupported operations fail closed.

This closes the gap between operational event records and the transaction/version semantics already enforced by the twin engine without claiming a proprietary MongoDB connection.

## Run

```bash
python -m pytest -q
python scripts/operate.py
```

Build and install:

```bash
python -m pip install build
python -m build
python -m pip install dist/*.whl
operational-semantic-twin
```

Evaluate a supplied mutation/verification request:

```bash
operational-semantic-twin --input request.json
```

## Proof surface

- `src/operational_semantic_twin_index.py` — projection and divergence engine
- `src/change_stream_adapter.py` — change-stream event normalization with version/full-post-image enforcement
- `src/operational_semantic_twin_cli.py` — installable execution surface
- `tests/test_operational_semantic_twin_index.py` — versioning, replay, tombstone and divergence behavior
- `tests/test_change_stream_adapter.py` — authoritative event adaptation and refusal behavior
- `tests/test_adversarial.py` — fail-closed adversarial coverage
- `.github/workflows/tests.yml` — tests + cold-start + wheel build/install + installed CLI
- `machine/` — existing Helix target/proof/authority surfaces remain preserved

## Current boundary

The system can now consume supplied change-stream-style event records with full post-images and explicit authoritative versions. It does not yet attach to a live MongoDB change stream or external semantic index, and it claims no proprietary MongoDB infrastructure access or production scale. The next depth step is a permitted live/disposable source-and-index adapter using these verified event semantics end-to-end.
