# Executive Memo — Halo Card Credit Portfolio

**To:** VP Credit Strategy, Head of Growth, Chief Risk Officer  
**From:** Business Analyst (portfolio project)  
**Re:** Two growth actions for next quarter, and one risk watch-out  

---

## Slide 1 — Recommendation

**1. Grow lines on the *headroom* segment (S2) before the maxed-out segment (S3).**

S2 is the better risk-adjusted use of incremental credit: **$25.64 contribution margin per account** at a **3.32% loss rate**. S3 shows a slightly higher margin ($28.35) but carries **9.07% loss — 2.7x S2's** — on a base of only 207 accounts. That is materially more capital at risk for a small margin gain, and it is the exposure most sensitive to a downturn.

A **+20% line increase** across 1,098 eligible S2 accounts is modeled at **$4,990 annual margin uplift** against **$3,969 expected-loss increase** (base case; range $1,613–$11,007).

**2. Reallocate acquisition spend from paid search toward in-app and referral.**

**paid_search** is both the most expensive and the riskiest channel: **$145 CAC** with a **4.59% loss rate**. **in_app** acquires at **$35 CAC** with **2.87% loss**, and referral ($25) is comparable on risk. Paying ~4x more per account for worse credit is not a growth strategy — it is a subsidy. Shift the incremental budget first, then re-underwrite paid search rather than cutting it outright.

## Slide 2 — Evidence

**Segment economics** (revenue vs risk — the trade-off, quantified):

| Segment | Accounts | Rev/acct | Expected loss/acct | Loss rate | Margin/acct |
| --- | --- | --- | --- | --- | --- |
| S3_maxed_out | 207 | $44.77 | $10.88 | 9.07% | $28.35 |
| S2_revolver_headroom | 1,611 | $33.30 | $3.20 | 3.32% | $25.64 |
| S1_light_revolver | 4,462 | $21.52 | $1.01 | 1.48% | $17.35 |
| S0_transactor | 4,690 | $8.06 | $0.24 | n/a | $7.08 |
| S5_delinquent | 1,154 | $14.39 | $8.70 | 25.24% | $3.84 |
| S4_dormant | 4,874 | $1.16 | $0.00 | n/a | $1.16 |

**Credit-line increase scenarios** (per eligible account, +20% line):

| Scenario | Exposure added | Margin uplift | Expected-loss delta |
| --- | --- | --- | --- |
| low | $62,999 | $1,613 | $1,260 |
| base | $113,399 | $4,990 | $3,969 |
| high | $163,798 | $11,007 | $9,009 |

**Channel quality** (CAC vs realized loss):

| Channel | Accounts | CAC | Loss rate |
| --- | --- | --- | --- |
| paid_search | 3,581 | $145 | 4.59% |
| affiliate | 2,621 | $110 | 3.80% |
| partner | 970 | $90 | 3.31% |
| referral | 1,895 | $25 | 2.95% |
| in_app | 2,933 | $35 | 2.87% |

## Slide 3 — Risk & monitoring

**Watch-out:** loss rises monotonically across origination bands (A 1.03% → E 17.58%), and 2026 vintages are running hotter than 2025. A line increase that shifts mix toward lower bands would reverse the modeled uplift.

**How we will know if it worked** (designed before launch):

- **Hold out 8%** of eligible accounts as control; measure incremental margin by difference-in-differences, not a simple pre/post.
- **Guardrail:** portfolio loss rate must not exceed the risk-appetite threshold; if the treated cohort's 30+ DPD rate runs >15 bps above control, pause and re-underwrite.
- **Payback window:** 9 months on the base case; kill the program if payback extends past 12.
- **Falsifier:** if the S2 cohort's incremental draw-down is below ~8% of added line, the uplift thesis fails — that is the result that should change our minds.

---

*Method note: all figures are modeled estimates over a synthetic portfolio (seeded generator, `scripts/generate_synthetic_data.py`). Assumptions for the scenarios live in `sql/pricing_sensitivity.sql §1` and are visible in the output. S2/S3 are behavioral segments (utilization + payment behavior) — no protected-class attributes were used as targeting inputs; `sql/pricing_sensitivity.sql §4` runs the fairness audit before any targeting recommendation ships.*