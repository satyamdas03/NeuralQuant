"""Ingest Anjali Excel data into Supabase.

Usage:
    python scripts/ingest_anjali_excel.py --path path/to/US_Stock_Analysis_Coloured.xlsx [--sheet sp500|smallmidcap|nse100|all] [--method direct|dataframe]

Methods:
    direct    — Read cell colors with openpyxl, build dicts, DELETE+INSERT per market (default)
    dataframe — Read with pandas, compute scores, then ingest via ingestor module
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure anjali subpackage on path WITHOUT importing full nq_data package
# (nq_data.__init__ imports pydantic, duckdb, etc. which aren't needed here)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "data" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "data" / "src" / "nq_data"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("anjali_excel_ingest")


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest Anjali Excel data into Supabase")
    ap.add_argument("--path", required=True, help="Path to US_Stock_Analysis_Coloured.xlsx")
    ap.add_argument("--sheet", choices=["sp500", "smallmidcap", "nse100", "all"], default="all",
                    help="Which sheet to ingest (default: all)")
    ap.add_argument("--method", choices=["direct", "dataframe"], default="direct",
                    help="Ingestion method: direct (openpyxl+Supabase) or dataframe (pandas+ingestor)")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.exists():
        logger.error(f"File not found: {path}")
        return 1

    # Check env vars
    import os
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")):
        logger.error("SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required")
        return 2

    if args.method == "direct":
        # Direct path: openpyxl reads cell colors, builds record dicts, DELETE+INSERT per market
        from supabase import create_client, Client
        from anjali.excel_ingestor import ExcelIngestor

        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        supabase: Client = create_client(url, key)

        ingestor = ExcelIngestor(supabase)
        stats = ingestor.ingest(str(path))
        for sheet, count in stats.items():
            logger.info("  %s: %d rows ingested", sheet, count)
        total = sum(stats.values())
        logger.info("Ingestion complete: %d total rows across %d sheets", total, len(stats))
        return 0 if total > 0 else 1

    else:
        # Dataframe path: pandas read + ingestor module
        if args.sheet == "all":
            from anjali.excel_ingestor import ingest_excel_to_supabase
            counts = ingest_excel_to_supabase(str(path))
            for key, count in counts.items():
                print(f"  {key}: {count} rows")
            total = sum(counts.values())
            print(f"TOTAL: {total} rows ingested")
            return 0 if total > 0 else 1
        else:
            from anjali.excel_ingestor import read_anjali_sheet
            from anjali.ingestor import ingest_to_supabase
            sheet_map = {
                "sp500": ("S&P 500 Analysis", "US"),
                "smallmidcap": ("SmallMidCap Analysis", "US"),
                "nse100": ("NSE 100 Analysis", "IN"),
            }
            sheet_name, market = sheet_map[args.sheet]
            df = read_anjali_sheet(str(path), sheet=sheet_name, market=market)
            count = ingest_to_supabase(df, market=market)
            print(f"Ingested {count} rows from {sheet_name}")
            return 0 if count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())