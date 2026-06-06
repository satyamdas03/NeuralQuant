#!/usr/bin/env python3
"""Nightly QuantFactor enrichment data refresh — GHA / CLI entry point.

Usage:
    python scripts/nightly_anjali.py [--market US|IN|BOTH] [--universe SP500|SP400|SP600|NIFTY200|ALL]
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "data" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "signals" / "src"))
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from nq_api.jobs.nightly_anjali import main

if __name__ == "__main__":
    main()