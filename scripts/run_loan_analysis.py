#!/usr/bin/env python3
"""
run_loan_analysis.py — executes sql/loan_analysis.sql against the LendingClub
loan dataset and writes findings to output/loans/.

Prerequisites:
  python3 scripts/fetch_loan_data.py

Usage:
  python3 scripts/run_loan_analysis.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from requirements import require  # noqa: E402

duckdb = require("duckdb")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_analysis import split_statements  # noqa: E402  (shared SQL splitter)

EXPECTED_LOANS = 115675


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="loans.duckdb")
    ap.add_argument("--data", default="data_loans")
    ap.add_argument("--out", default="output/loans")
    args = ap.parse_args()

    src = os.path.join(args.data, "loans.csv")
    if not os.path.exists(src):
        sys.exit(f"{src} not found — run: python3 scripts/fetch_loan_data.py")

    # Start clean so a previous run cannot mix with this one
    if os.path.exists(args.db):
        os.remove(args.db)
    con = duckdb.connect(args.db)
    con.execute(open("sql/schema_loans.sql").read())
    con.execute(f"COPY loans FROM '{src}' (HEADER, AUTO_DETECT TRUE)")

    n_all = con.execute("SELECT COUNT(*) FROM loans").fetchone()[0]
    n_res = con.execute("SELECT COUNT(*) FROM loans WHERE is_resolved").fetchone()[0]
    print(f"Loaded LOAN data: {n_all:,} loans ({n_res:,} resolved)")
    if n_all != EXPECTED_LOANS:
        print(f"  WARNING: expected {EXPECTED_LOANS:,} loans, got {n_all:,}")

    sql_text = open("sql/loan_analysis.sql").read()
    labels = re.findall(r"--\s*(Q\d+)\.", sql_text)

    results = []
    for i, stmt in enumerate(split_statements(sql_text), 1):
        if not stmt.strip():
            continue
        try:
            rows = con.execute(stmt).fetchall()
        except Exception as exc:
            print(f"  query #{i} FAILED: {str(exc)[:220]}")
            continue
        cols = [d[0] for d in con.description]
        title = labels[i - 1] if i - 1 < len(labels) else f"statement_{i}"
        print(f"\n=== {title} ===")
        print("  " + " | ".join(cols))
        for r in rows[:14]:
            print("  " + " | ".join(
                "" if v is None else
                (f"{v:,.2f}" if isinstance(v, float) else f"{v:,}" if isinstance(v, int) else str(v))
                for v in r))
        results.append({
            "query": title,
            "columns": cols,
            "rows": [[v.isoformat() if hasattr(v, "isoformat") else v for v in r] for r in rows],
        })

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "loan_results.json"), "w") as fh:
        json.dump(results, fh, indent=2, default=str)
    print(f"\nWrote {args.out}/loan_results.json ({len(results)} result sets)")


if __name__ == "__main__":
    main()
