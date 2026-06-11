#!/bin/bash
# Load the bundled demo snapshot into Postgres at first boot.
# Runs inside the official postgres image (docker-entrypoint-initdb.d).
set -e

for f in /demo_data/*.csv; do
  table=$(basename "$f" .csv)
  cols=$(head -1 "$f")
  echo "demo_seed: loading $table"
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -c "\copy \"$table\"($cols) FROM '$f' WITH (FORMAT csv, HEADER true)"
done
echo "demo_seed: done"
