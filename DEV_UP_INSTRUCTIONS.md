# DEV_UP_INSTRUCTIONS — implementation record

**Repository:** `GlacierEQ/mongodb-operational-semantic-twin-index`  
**Independent company lens:** MongoDB  
**Innovation:** Operational-Semantic Twin Index

## Mission

Derive retrieval/semantic state from authoritative application mutations so duplicated state cannot silently become a second source of truth.

## Implemented

The generic scaffold has been replaced by a deterministic transaction-linked projection engine.

`src/operational_semantic_twin_index.py` now:

- derives semantic projections from authoritative `upsert` and `delete` mutations;
- binds source version, transaction id, mutation id, authoritative digest and semantic digest;
- enforces contiguous per-document versions;
- allows exact idempotent replay while refusing mutation-id reuse with changed content;
- emits explicit delete tombstones;
- verifies projection state against an authoritative snapshot;
- exposes missing, stale, untombstoned, version-mismatched and content-divergent projections;
- emits deterministic state/projection/decision digests.

`src/operational_semantic_twin_cli.py` and `scripts/operate.py` execute the mechanism directly. The project is packaged with the `operational-semantic-twin` console command.

## Verification contract

Behavioral tests cover initial projection, version advancement, version-gap refusal, idempotent replay, mutation-id conflict, delete/tombstone consistency, content divergence, and semantic-vs-authoritative digest behavior. Existing adversarial coverage remains active.

CI must pass native tests, cold-start operation, wheel build/install and installed CLI execution before Helix may mint source-bound promotion evidence.

## Truth boundary

No MongoDB affiliation, proprietary access, production deployment, customer impact, or company partnership is claimed. The current engine consumes normalized mutations/snapshots; an external change-stream/index adapter remains a further end-to-end depth step.
