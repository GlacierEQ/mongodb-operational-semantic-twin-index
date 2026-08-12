#!/usr/bin/env python3
"""Cold-start a real operational-to-semantic projection."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operational_semantic_twin_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
