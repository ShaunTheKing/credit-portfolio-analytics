#!/usr/bin/env bash
# One-command setup: generate the synthetic portfolio and load it into DuckDB.
#
# Usage:
#   ./scripts/setup.sh              # default dataset (12K accounts x 24 months)
#   ./scripts/setup.sh --quick      # smoke-test dataset (2K accounts x 12 months)
#
# Requires: python3, duckdb CLI (brew install duckdb)

set -euo pipefail

cd "$(dirname "$0")/.."

GEN_ARGS=()
if [ "${1:-}" = "--quick" ]; then
  GEN_ARGS=(--accounts 2000 --months 12)
  DUMP_SQL="sql/load_quick.sql"
else
  DUMP_SQL="sql/load.sql"
fi

echo "==> Generating synthetic data..."
python3 scripts/generate_synthetic_data.py "${GEN_ARGS[@]}"

if ! command -v duckdb >/dev/null 2>&1; then
  echo
  echo "duckdb CLI not found. Either install it (brew install duckdb), or use Python:"
  echo "  python3 -m pip install duckdb"
  echo
  echo "CSVs are ready in data/ — load them with sql/schema.sql + sql/load.sql"
  exit 0
fi

echo "==> Loading into DuckDB (credit.duckdb)..."
rm -f credit.duckdb
duckdb credit.duckdb < sql/schema.sql
duckdb credit.duckdb < "$DUMP_SQL"

echo
echo "==> Ready. Try:"
echo "    duckdb credit.duckdb \"SELECT * FROM v_account_margin LIMIT 5;\""
echo "    duckdb credit.duckdb < sql/kpi_dashboard.sql"
