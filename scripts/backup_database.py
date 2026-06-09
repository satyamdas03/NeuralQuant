"""NeuralQuant Database Backup Script

Creates a compressed SQL dump of the entire Supabase PostgreSQL database.
Requires `pg_dump` in PATH (install via `choco install postgresql` on Windows,
`brew install libpq` on macOS, or `apt-get install postgresql-client` on Linux).

Usage:
    python scripts/backup_database.py

Output:
    backups/nq_backup_YYYY-MM-DD_HHMMSS.sql.gz
"""
from __future__ import annotations

import gzip
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ───────────────────────────────────────────────────────────
DB_URL = os.environ.get(
    "SUPABASE_DB_URL",
    # Production DB URL (from apps/api/.env)
    "postgresql://postgres:Thomasarthurpolly08%23@db.ajkhyayrbqiuvnsmqrdz.supabase.co:5432/postgres",
)

BACKUP_DIR = Path(__file__).resolve().parents[1] / "backups"

# Tables that are safe to skip (ephemeral / regenerable) to reduce dump size
SKIP_DATA_TABLES = [
    "enrichment_cache",      # 1h TTL, regenerated on demand
    "news_classifications",  # Claude-classified, regenerated
]


def _run_pg_dump(output_path: Path, db_url: str) -> bool:
    """Run pg_dump and compress to gzip. Returns True on success."""

    # Build pg_dump command
    cmd = [
        "pg_dump",
        "--dbname", db_url,
        "--format", "plain",          # SQL text format (most portable)
        "--verbose",
        "--no-owner",                  # skip ownership commands
        "--no-privileges",             # skip privilege grants
    ]

    # Exclude data-only for ephemeral tables (keep schema, skip rows)
    for tbl in SKIP_DATA_TABLES:
        cmd.extend(["--exclude-table-data", tbl])

    print(f"Running: {' '.join(cmd[:5])} ...")
    print(f"Database: {db_url.split('@')[-1]}")
    print(f"Output:   {output_path}")
    print()

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,  # binary for gzip
        )
    except FileNotFoundError:
        print("ERROR: pg_dump not found in PATH.")
        print()
        print("Install instructions:")
        print("  Windows:  choco install postgresql")
        print("  macOS:    brew install libpq")
        print("  Linux:    sudo apt-get install postgresql-client")
        print()
        print("Alternatively, use Docker (no install needed):")
        print('  docker run --rm postgres:17-alpine pg_dump "DB_URL" | gzip > backup.sql.gz')
        print()
        return False

    # Compress stdout on-the-fly
    with gzip.open(output_path, "wb", compresslevel=6) as gz:
        while True:
            chunk = proc.stdout.read(256 * 1024)  # 256KB chunks
            if not chunk:
                break
            gz.write(chunk)

    proc.wait()

    if proc.returncode != 0:
        stderr = proc.stderr.read().decode("utf-8", errors="replace")[:2000]
        print(f"ERROR: pg_dump failed (exit {proc.returncode})")
        print(stderr)
        # Clean up partial file
        if output_path.exists():
            output_path.unlink()
        return False

    return True


def main() -> int:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    out_file = BACKUP_DIR / f"nq_backup_{ts}.sql.gz"

    print("=" * 60)
    print("NeuralQuant Database Backup")
    print("=" * 60)
    print()

    if not _run_pg_dump(out_file, DB_URL):
        return 1

    # Verify file
    size_mb = out_file.stat().st_size / (1024 * 1024)
    print(f"✅ Backup complete: {out_file.name}")
    print(f"   Size: {size_mb:.2f} MB")
    print()
    print("IMPORTANT: Keep this file safe. It contains ALL production data.")
    print("Store it in a secure location (password manager, encrypted drive).")
    print()
    print(f"To restore later:")
    print(f"   gunzip < {out_file.name} | psql {DB_URL}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
