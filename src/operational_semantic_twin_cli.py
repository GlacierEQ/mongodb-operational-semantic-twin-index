from __future__ import annotations

import argparse
import json
from pathlib import Path

from operational_semantic_twin_index import Decision, OperationalSemanticTwinIndex, OperationalSemanticTwinIndexRequest


def demo_payload() -> dict:
    return {
        "mode": "apply",
        "mutations": [{
            "mutation_id": "m-1",
            "transaction_id": "tx-42",
            "document_id": "customer-7",
            "version": 1,
            "operation": "upsert",
            "document": {"title": "Service ticket", "body": "compressor vibration", "status": "open"},
            "semantic_fields": ["title", "body"],
        }],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive or verify transaction-linked semantic projections")
    parser.add_argument("--input", type=Path, help="JSON request payload; defaults to a deterministic demo")
    parser.add_argument("--subject", default="semantic-twin-demo")
    parser.add_argument("--budget", type=float, default=1.0)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text()) if args.input else demo_payload()
    receipt = OperationalSemanticTwinIndex().evaluate(OperationalSemanticTwinIndexRequest(args.subject, payload, args.budget))
    print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    return 0 if receipt.decision is Decision.ALLOW else 2


if __name__ == "__main__":
    raise SystemExit(main())
