#!/usr/bin/env python3
"""
run_real_analysis.py — executes sql/real_analysis.sql against the REAL UCI
credit-card dataset and writes findings to output/real/.

Prerequisites:
  python3 scripts/fetch_real_data.py        # requires xlrd

Usage:
  python3 scripts/run_real_analysis.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

try:
    import duckdb
except ImportError:
    sys.exit("duckdb required: python3 -m pip install duckdb")

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from run_analysis import split_statements  # noqa: E402  (shared SQL splitter)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="credit_real.duckdb")
    ap.add_argument("--data", default="data_real")
    ap.add_argument("--out", default="output/real")
    args = ap.parse_args()

    if not os.path.exists(os.path.join(args.data, "accounts.csv")):
        sys.exit(f"{args.data}/accounts.csv not found — run scripts/fetch_real_data.py first")

    # Start clean so a previous run's rows cannot mix with this one
    if os.path.exists(args.db):
        os.remove(args.db)
    con = duckdb.connect(args.db)
    con.execute(open("sql/schema_real.sql").read())
    for name in ("accounts", "account_months", "offer_exposures", "marketing_spend"):
        con.execute(f"COPY {name} FROM '{args.data}/{name}.csv' (HEADER, AUTO_DETECT TRUE)")

    n_acc = con.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    n_mon = con.execute("SELECT COUNT(*) FROM account_months").fetchone()[0]
    print(f"Loaded REAL data: {n_acc:,} clients, {n_mon:,} client-months")
    if n_acc != 30000:
        print(f"  WARNING: expected 30,000 clients, got {n_acc:,}")

    results = []
    sql_text = open("sql/real_analysis.sql").read()
    # split_statements() strips comments, so capture the labels from the raw text
    # first. This keeps each result labelled with the query number documented in
    # the SQL file itself, so the two can never drift apart.
    labels = re.findall(r"--\s*(Q\d+)\.", sql_text)
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
        for r in rows[:12]:
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
    with open(os.path.join(args.out, "real_results.json"), "w") as fh:
        json.dump(results, fh, indent=2, default=str)
    print(f"\nWrote {args.out}/real_results.json ({len(results)} result sets)")


if __name__ == "__main__":
    main()
