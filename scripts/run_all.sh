#!/usr/bin/env bash
# End-to-end pipeline: generate data -> load DuckDB -> run analysis -> build deliverables.
#
# Usage:
#   ./scripts/run_all.sh            # full dataset (12K accounts x 24 months)
#   ./scripts/run_all.sh --quick    # smoke test (2K accounts x 12 months)
#
# Requires: python3, and the duckdb Python package (pip install duckdb).
# The duckdb *CLI* is not needed — loading goes through Python.

set -euo pipefail
cd "$(dirname "$0")/.."

QUICK=0
[ "${1:-}" = "--quick" ] && QUICK=1

if [ "$QUICK" = "1" ]; then
  GEN_ARGS=(--accounts 2000 --months 12)
  echo "==> [quick mode] small dataset"
else
  GEN_ARGS=(--accounts 12000 --months 24)
fi

echo "==> 1/4 Generating synthetic portfolio..."
python3 scripts/generate_synthetic_data.py "${GEN_ARGS[@]}" --out data

echo "==> 2/4 Loading into DuckDB..."
# Start from a clean database. Reusing an existing file would silently mix a
# previous run's rows with this one (and `COPY` would fail or double-count).
rm -f credit.duckdb
python3 - <<'PY'
import duckdb, sys
try:
    con = duckdb.connect('credit.duckdb')
except Exception as e:
    sys.exit(f"duckdb unavailable ({e}). Install: python3 -m pip install duckdb")
con.execute(open('sql/schema.sql').read())
con.execute(open('sql/load.sql').read())
n = con.execute("SELECT COUNT(*) FROM account_months").fetchone()[0]
a = con.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
print(f"    loaded {a:,} accounts, {n:,} account-months")
# Guard against a partial load silently producing a thin dataset downstream
if a < 1000:
    sys.exit(f"ERROR: only {a:,} accounts loaded — expected thousands")
PY

echo "==> 3/4 Running analytics..."
python3 scripts/run_analysis.py --db credit.duckdb --out output

echo "==> 4/4 Building memo + dashboard..."
python3 scripts/build_memo.py --out output

echo
echo "Done. Deliverables:"
echo "  output/executive-memo.md   — 3-slide executive memo"
echo "  output/dashboard.html      — open in a browser (single file, no dependencies)"
echo "  output/analysis_results.json"
