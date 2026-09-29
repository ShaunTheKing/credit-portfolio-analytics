#!/usr/bin/env python3
"""
run_analysis.py — executes the SQL analytics pack and writes results to output/.

This is the reproducibility layer: one command regenerates every number that
appears in the dashboard and the executive memo, so any figure can be traced
back to a query. (See docs/metrics-playbook.md §4.)

Usage:
  python3 scripts/run_analysis.py                    # uses credit.duckdb
  python3 scripts/run_analysis.py --db credit.duckdb --out output

Requires duckdb:  pip install duckdb
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from requirements import require  # noqa: E402

duckdb = require("duckdb")


def split_statements(text: str):
    """Split a SQL file into statements, ignoring -- comments and quoted semicolons."""
    out, cur, in_str, i = [], [], False, 0
    while i < len(text):
        ch = text[i]
        if not in_str and text[i:i + 2] == "--":
            j = text.find("\n", i)
            i = len(text) if j < 0 else j
            continue
        if ch == "'" and (i == 0 or text[i - 1] != "\\"):
            in_str = not in_str
        if ch == ";" and not in_str:
            out.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    if "".join(cur).strip():
        out.append("".join(cur))
    return [s.strip() for s in out if s.strip()]


def table(con, title, sql):
    rows = con.execute(sql).fetchall()
    cols = [d[0] for d in con.description]
    print(f"\n=== {title} ===")
    print("  " + " | ".join(cols))
    for r in rows[:15]:
        print("  " + " | ".join("" if v is None else
                                (f"{v:,.2f}" if isinstance(v, float) else f"{v:,}" if isinstance(v, int) else str(v))
                                for v in r))
    return {"title": title, "columns": cols,
            "rows": [[v if not hasattr(v, "isoformat") else v.isoformat() for v in r] for r in rows]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="credit.duckdb")
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        sys.exit(f"{args.db} not found. Run: python3 scripts/generate_synthetic_data.py "
                 f"&& duckdb {args.db} < sql/schema.sql && duckdb {args.db} < sql/load.sql")

    # Views are created on this connection, so it must be read-write
    con = duckdb.connect(args.db)
    os.makedirs(args.out, exist_ok=True)

    # Build the views the analysis depends on
    for f in ("sql/schema.sql", "sql/segmentation.sql", "sql/pricing_sensitivity.sql"):
        for stmt in split_statements(open(f).read()):
            if stmt.upper().lstrip().startswith("CREATE OR REPLACE VIEW"):
                con.execute(stmt)

    results = []

    results.append(table(con, "Portfolio KPIs (latest 6 months)", """
        SELECT stat_month, accounts, active_accounts,
               ROUND(spend_per_active, 2) AS spend_per_active,
               ROUND(revolve_rate_pct, 1) AS revolve_rate_pct,
               ROUND(revenue_per_acct, 2) AS revenue_per_acct,
               ROUND(expected_loss_rate_pct, 2) AS loss_rate_pct,
               ROUND(margin_per_acct, 2) AS margin_per_acct
        FROM (
            SELECT stat_month, COUNT(*) AS accounts,
                   SUM(CASE WHEN is_active THEN 1 ELSE 0 END) AS active_accounts,
                   SUM(purchases_usd)/NULLIF(SUM(CASE WHEN is_active THEN 1 ELSE 0 END),0) AS spend_per_active,
                   100.0*AVG(CASE WHEN revolve_balance_usd>0 THEN 1.0 ELSE 0 END) AS revolve_rate_pct,
                   SUM(interest_charged_usd+interchange_rev_usd+fee_rev_usd)/COUNT(*) AS revenue_per_acct,
                   100.0*SUM(expected_loss_usd)/NULLIF(SUM(revolve_balance_usd),0) AS expected_loss_rate_pct,
                   SUM(interest_charged_usd+interchange_rev_usd+fee_rev_usd-promo_cost_usd
                       -expected_loss_usd-funding_cost_usd)/COUNT(*) AS margin_per_acct
            FROM account_months GROUP BY stat_month
        ) ORDER BY stat_month DESC LIMIT 6
    """))

    results.append(table(con, "Segment economics (revenue vs expected loss)", """
        SELECT vs.segment,
               COUNT(DISTINCT vs.account_id) AS accounts,
               ROUND(SUM(m.interest_charged_usd+m.interchange_rev_usd+m.fee_rev_usd)/COUNT(*),2) AS rev_per_acct,
               ROUND(SUM(m.expected_loss_usd)/COUNT(*),2) AS exp_loss_per_acct,
               ROUND(SUM(m.expected_loss_usd)/NULLIF(SUM(m.revolve_balance_usd),0)*12*100,2) AS loss_rate_pct,
               ROUND(SUM(m.interest_charged_usd+m.interchange_rev_usd+m.fee_rev_usd
                   -m.promo_cost_usd-m.expected_loss_usd-m.funding_cost_usd)/COUNT(*),2) AS margin_per_acct
        FROM v_behavioral_segment vs
        JOIN account_months m ON m.account_id=vs.account_id AND m.stat_month=vs.stat_month
        GROUP BY 1 ORDER BY margin_per_acct DESC
    """))

    results.append(table(con, "Risk by origination band (loss must rise A->E)", """
        SELECT a.origination_risk_band AS band, COUNT(DISTINCT a.account_id) AS accounts,
               ROUND(SUM(m.expected_loss_usd)/NULLIF(SUM(m.revolve_balance_usd),0)*12*100,2) AS loss_rate_pct
        FROM accounts a JOIN account_months m USING (account_id)
        GROUP BY 1 ORDER BY 1
    """))

    results.append(table(con, "Credit-line increase scenarios (per eligible account)", """
        WITH eligible AS (
            SELECT COUNT(*) AS n, AVG(credit_line_usd) AS avg_line FROM accounts
            WHERE account_id IN (SELECT account_id FROM v_behavioral_segment
                WHERE segment='S2_revolver_headroom'
                  AND stat_month=(SELECT MAX(stat_month) FROM account_months))
        )
        SELECT v_params.scenario, eligible.n AS eligible_accounts,
               ROUND(eligible.n*eligible.avg_line*0.20*draw_pct,0) AS incremental_exposure,
               ROUND(eligible.n*eligible.avg_line*0.20*draw_pct*revolve_pct*nim,0) AS margin_uplift,
               ROUND(eligible.n*eligible.avg_line*0.20*draw_pct*loss_rate,0) AS loss_delta
        FROM v_params, eligible ORDER BY 1
    """))

    results.append(table(con, "Channel quality: CAC vs loss rate", """
        SELECT a.acquisition_channel AS channel, COUNT(DISTINCT a.account_id) AS accounts,
               ROUND(SUM(ms.spend_usd)/NULLIF(SUM(ms.new_accounts),0),2) AS cac_usd,
               ROUND(SUM(m.expected_loss_usd)/NULLIF(SUM(m.revolve_balance_usd),0)*12*100,2) AS loss_rate_pct
        FROM accounts a JOIN account_months m USING (account_id)
        JOIN marketing_spend ms ON ms.channel=a.acquisition_channel AND ms.stat_month=a.open_date
        GROUP BY 1 ORDER BY loss_rate_pct DESC
    """))

    with open(os.path.join(args.out, "analysis_results.json"), "w") as fh:
        json.dump(results, fh, indent=2, default=str)
    print(f"\nWrote {args.out}/analysis_results.json ({len(results)} result sets)")


if __name__ == "__main__":
    main()
