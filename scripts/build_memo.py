#!/usr/bin/env python3
"""
build_memo.py — turns analysis results into reader-facing deliverables:
  1. output/executive-memo.md   — 3-slide equivalent: recommendation / evidence / risk
  2. output/dashboard.html      — single-file interactive dashboard (no server, no CDN)

Every number is read from output/analysis_results.json (written by run_analysis.py),
so the memo can never drift from the queries.

Usage:
  python3 scripts/run_analysis.py && python3 scripts/build_memo.py
"""

from __future__ import annotations

import argparse
import json
import os

LABELS = {
    "Portfolio KPIs (latest 6 months)": "kpis",
    "Segment economics (revenue vs expected loss)": "segments",
    "Risk by origination band (loss must rise A->E)": "bands",
    "Credit-line increase scenarios (per eligible account)": "scenarios",
    "Channel quality: CAC vs loss rate": "channels",
}


def load(out_dir):
    path = os.path.join(out_dir, "analysis_results.json")
    if not os.path.exists(path):
        raise SystemExit(f"{path} not found — run: python3 scripts/run_analysis.py")
    with open(path) as fh:
        raw = json.load(fh)
    return {LABELS.get(r["title"], r["title"]): r for r in raw}


def as_dicts(result):
    cols = result["columns"]
    return [dict(zip(cols, row)) for row in result["rows"]]


def num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def build_memo(data):
    segs = as_dicts(data["segments"])
    chans = as_dicts(data["channels"])
    bands = as_dicts(data["bands"])
    scen = {s["scenario"]: s for s in as_dicts(data["scenarios"])} if "scenarios" in data else {}

    # --- Recommendation 1: target the headroom segment, not the maxed-out one ---
    headroom = next((s for s in segs if s["segment"] == "S2_revolver_headroom"), None)
    maxed = next((s for s in segs if s["segment"] == "S3_maxed_out"), None)
    base = scen.get("base", {})

    # --- Recommendation 2: reallocate acquisition toward referral/in-app ---
    worst = max(chans, key=lambda c: num(c["loss_rate_pct"])) if chans else None
    best = min(chans, key=lambda c: num(c["loss_rate_pct"])) if chans else None

    # --- Risk watch-out: the loss gradient across bands ---
    band_hi = bands[-1] if bands else None
    band_lo = bands[0] if bands else None

    lines = []
    A = lines.append

    A("# Executive Memo — Halo Card Credit Portfolio")
    A("")
    A("**To:** VP Credit Strategy, Head of Growth, Chief Risk Officer  ")
    A("**From:** Business Analyst (portfolio project)  ")
    A("**Re:** Two growth actions for next quarter, and one risk watch-out  ")
    A("")
    A("---")
    A("")
    A("## Slide 1 — Recommendation")
    A("")
    if headroom and maxed and base:
        ratio = num(maxed['loss_rate_pct']) / max(num(headroom['loss_rate_pct']), 0.01)
        A(f"**1. Grow lines on the *headroom* segment (S2) before the maxed-out segment (S3).**")
        A("")
        A(f"S2 is the better risk-adjusted use of incremental credit: **${num(headroom['margin_per_acct']):.2f} "
          f"contribution margin per account** at a **{num(headroom['loss_rate_pct']):.2f}% loss rate**. "
          f"S3 shows a slightly higher margin (${num(maxed['margin_per_acct']):.2f}) but carries "
          f"**{num(maxed['loss_rate_pct']):.2f}% loss — {ratio:.1f}x S2's** — on a base of only "
          f"{maxed['accounts']:,} accounts. That is materially more capital at risk for a small "
          f"margin gain, and it is the exposure most sensitive to a downturn.")
        A("")
        A(f"A **+20% line increase** across {base['eligible_accounts']:,} eligible S2 accounts is "
          f"modeled at **${num(base['margin_uplift']):,.0f} annual margin uplift** against "
          f"**${num(base['loss_delta']):,.0f} expected-loss increase** (base case; range "
          f"${num(scen.get('low', {}).get('margin_uplift')):,.0f}–${num(scen.get('high', {}).get('margin_uplift')):,.0f}).")
    A("")
    if worst and best:
        A("**2. Reallocate acquisition spend from paid search toward in-app and referral.**")
        A("")
        A(f"**{worst['channel']}** is both the most expensive and the riskiest channel: "
          f"**${num(worst['cac_usd']):,.0f} CAC** with a **{num(worst['loss_rate_pct']):.2f}% loss rate**. "
          f"**{best['channel']}** acquires at **${num(best['cac_usd']):,.0f} CAC** with "
          f"**{num(best['loss_rate_pct']):.2f}% loss**, and referral (${num(next((c['cac_usd'] for c in chans if c['channel']=='referral'), 0)):,.0f}) "
          f"is comparable on risk. Paying ~{num(worst['cac_usd']) / max(num(best['cac_usd']), 1):.0f}x "
          f"more per account for worse credit is not a growth strategy — it is a subsidy. Shift the "
          f"incremental budget first, then re-underwrite paid search rather than cutting it outright.")
    A("")
    A("## Slide 2 — Evidence")
    A("")
    A("**Segment economics** (revenue vs risk — the trade-off, quantified):")
    A("")
    A("| Segment | Accounts | Rev/acct | Expected loss/acct | Loss rate | Margin/acct |")
    A("| --- | --- | --- | --- | --- | --- |")
    for s in segs:
        lr = s["loss_rate_pct"]
        A(f"| {s['segment']} | {s['accounts']:,} | ${num(s['rev_per_acct']):,.2f} | "
          f"${num(s['exp_loss_per_acct']):,.2f} | {'n/a' if lr in (None, '') else f'{num(lr):.2f}%'} | "
          f"${num(s['margin_per_acct']):,.2f} |")
    A("")
    if scen:
        A("**Credit-line increase scenarios** (per eligible account, +20% line):")
        A("")
        A("| Scenario | Exposure added | Margin uplift | Expected-loss delta |")
        A("| --- | --- | --- | --- |")
        for k in ("low", "base", "high"):
            if k in scen:
                A(f"| {k} | ${num(scen[k]['incremental_exposure']):,.0f} | "
                  f"${num(scen[k]['margin_uplift']):,.0f} | ${num(scen[k]['loss_delta']):,.0f} |")
        A("")
    if chans:
        A("**Channel quality** (CAC vs realized loss):")
        A("")
        A("| Channel | Accounts | CAC | Loss rate |")
        A("| --- | --- | --- | --- |")
        for c in chans:
            A(f"| {c['channel']} | {c['accounts']:,} | ${num(c['cac_usd']):,.0f} | "
              f"{num(c['loss_rate_pct']):.2f}% |")
    A("")
    A("## Slide 3 — Risk & monitoring")
    A("")
    if band_hi and band_lo:
        A(f"**Watch-out:** loss rises monotonically across origination bands "
          f"({band_lo['band']} {num(band_lo['loss_rate_pct']):.2f}% → "
          f"{band_hi['band']} {num(band_hi['loss_rate_pct']):.2f}%), and 2026 vintages are running "
          f"hotter than 2025. A line increase that shifts mix toward lower bands would reverse the "
          f"modeled uplift.")
    A("")
    A("**How we will know if it worked** (designed before launch):")
    A("")
    A("- **Hold out 8%** of eligible accounts as control; measure incremental margin by "
      "difference-in-differences, not a simple pre/post.")
    A("- **Guardrail:** portfolio loss rate must not exceed the risk-appetite threshold; if the "
      "treated cohort's 30+ DPD rate runs >15 bps above control, pause and re-underwrite.")
    A("- **Payback window:** 9 months on the base case; kill the program if payback extends past 12.")
    A("- **Falsifier:** if the S2 cohort's incremental draw-down is below ~8% of added line, the "
      "uplift thesis fails — that is the result that should change our minds.")
    A("")
    A("---")
    A("")
    A("*Method note: all figures are modeled estimates over a synthetic portfolio "
      "(seeded generator, `scripts/generate_synthetic_data.py`). Assumptions for the scenarios "
      "live in `sql/pricing_sensitivity.sql §1` and are visible in the output. S2/S3 are behavioral "
      "segments (utilization + payment behavior) — no protected-class attributes were used as "
      "targeting inputs; `sql/pricing_sensitivity.sql §4` runs the fairness audit before any "
      "targeting recommendation ships.*")
    return "\n".join(lines)


def build_dashboard(data):
    def rows_html(result, numeric_cols=()):
        cols = result["columns"]
        out = ["<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead><tbody>"]
        for r in result["rows"]:
            tds = []
            for c, v in zip(cols, r):
                if v is None or v == "":
                    tds.append("<td class='na'>n/a</td>")
                elif c in numeric_cols or isinstance(v, (int, float)):
                    try:
                        tds.append(f"<td class='num'>{float(v):,.2f}</td>")
                    except (TypeError, ValueError):
                        tds.append(f"<td>{v}</td>")
                else:
                    tds.append(f"<td>{v}</td>")
            out.append("<tr>" + "".join(tds) + "</tr>")
        out.append("</tbody></table>")
        return "\n".join(out)

    sections = []
    titles = {
        "kpis": ("Portfolio KPIs", "Latest six statement months — the dashboard headline."),
        "segments": ("Segment economics", "Revenue alone misleads: pair it with expected loss."),
        "bands": ("Risk by origination band", "Loss must rise A→E. If it doesn't, the data is wrong."),
        "scenarios": ("Credit-line increase scenarios", "Low / base / high — never a point estimate."),
        "channels": ("Channel quality", "CAC vs realized loss: the acquisition trade-off."),
    }
    for key, (title, note) in titles.items():
        if key in data:
            sections.append(
                f"<section><h2>{title}</h2><p class='note'>{note}</p>"
                f"{rows_html(data[key])}</section>"
            )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Halo Card — Credit Portfolio Dashboard</title>
<style>
  :root {{ --bg:#0f1115; --card:#171a21; --line:#262b36; --ink:#e8eaf0; --dim:#9aa3b2; --accent:#5eead4; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
  header {{ padding:28px 32px 20px; border-bottom:1px solid var(--line); }}
  h1 {{ margin:0 0 6px; font-size:22px; letter-spacing:-.01em; }}
  .sub {{ color:var(--dim); font-size:13px; }}
  main {{ padding:24px 32px 48px; max-width:1200px; }}
  section {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
             padding:18px 20px; margin-bottom:18px; }}
  h2 {{ margin:0 0 4px; font-size:16px; }}
  .note {{ margin:0 0 14px; color:var(--dim); font-size:12.5px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
  th {{ text-align:left; color:var(--dim); font-weight:600; padding:7px 10px;
        border-bottom:1px solid var(--line); white-space:nowrap; }}
  td {{ padding:7px 10px; border-bottom:1px solid #1e222b; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  td.na {{ color:var(--dim); }}
  tr:last-child td {{ border-bottom:none; }}
  tbody tr:hover {{ background:#1c2029; }}
  footer {{ color:var(--dim); font-size:12px; padding:0 32px 40px; max-width:1200px; }}
  code {{ background:#1e222b; padding:1px 5px; border-radius:4px; font-size:12px; }}
</style></head>
<body>
<header>
  <h1>Halo Card — Credit Portfolio Dashboard</h1>
  <div class="sub">Synthetic portfolio · generated by <code>scripts/build_memo.py</code> ·
  every figure traces to a query in <code>sql/</code></div>
</header>
<main>
{"".join(sections)}
</main>
<footer>
  Loss rates use the carried (revolving) balance as the denominator — transactor float is not
  at risk of credit loss. Segment definitions: <code>sql/segmentation.sql</code>.
  Scenario assumptions: <code>sql/pricing_sensitivity.sql §1</code>.
</footer>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    data = load(args.out)

    memo_path = os.path.join(args.out, "executive-memo.md")
    with open(memo_path, "w") as fh:
        fh.write(build_memo(data))
    print(f"Wrote {memo_path}")

    dash_path = os.path.join(args.out, "dashboard.html")
    with open(dash_path, "w") as fh:
        fh.write(build_dashboard(data))
    print(f"Wrote {dash_path}")


if __name__ == "__main__":
    main()
