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

# Fail fast with actionable guidance rather than halfway through the pipeline.
# (The DuckDB *CLI* is not needed — loading runs through the Python module.)
if ! python3 -c "import duckdb" >/dev/null 2>&1; then
  echo "ERROR: the Python module 'duckdb' is not available to this interpreter." >&2
  echo >&2
  python3 scripts/requirements.py >&2 || true
  exit 1
fi

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
import os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))
from requirements import require
duckdb = require("duckdb")

con = duckdb.connect('credit.duckdb')
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
