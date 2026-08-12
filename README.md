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
- `src/operational_semantic_twin_cli.py` — installable execution surface
- `tests/test_operational_semantic_twin_index.py` — versioning, replay, tombstone and divergence behavior
- `tests/test_adversarial.py` — fail-closed adversarial coverage
- `.github/workflows/tests.yml` — tests + cold-start + wheel build/install + installed CLI
- `machine/` — existing Helix target/proof/authority surfaces remain preserved

## Current boundary

This is a vendor-neutral deterministic projection engine. It does not connect to proprietary MongoDB infrastructure or claim production scale. The next depth step is a permitted adapter for real change-stream/event records plus a disposable semantic index so the same transaction/version contract can be proven end-to-end against an external store.
