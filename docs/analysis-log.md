# Analysis Log — findings, QA, and bugs caught

This is the working record behind the numbers. Two reasons it exists:
1. **Traceability** — every figure in the memo traces to a query here.
2. **Error record** — the bugs found and fixed during development, because catching a bad
   number before it ships is the difference between analysis and plausible-looking output.

---

## 1. Headline results (12,000 accounts · 245,821 account-months · seeded `--seed 42`)

### Segment economics — revenue vs risk

| Segment | Accounts | Rev/acct | Exp. loss/acct | Loss rate | Margin/acct |
| --- | --- | --- | --- | --- | --- |
| S3_maxed_out | 207 | $44.77 | $10.88 | 9.07% | $28.35 |
| S2_revolver_headroom | 1,611 | $33.30 | $3.20 | 3.32% | $25.64 |
| S1_light_revolver | 4,462 | $21.52 | $1.01 | 1.48% | $17.35 |
| S0_transactor | 4,690 | $8.06 | $0.24 | n/a | $7.08 |
| S5_delinquent | 1,154 | $14.39 | $8.70 | 25.24% | $3.84 |
| S4_dormant | 4,874 | $1.16 | $0.00 | n/a | $1.16 |

### Credit-line increase (+20% line, 1,098 eligible S2 accounts)

| Scenario | Exposure added | Margin uplift | Expected-loss delta |
| --- | --- | --- | --- |
| low | $62,999 | $1,613 | $1,260 |
| base | $113,399 | $4,990 | $3,969 |
| high | $163,798 | $11,007 | $9,009 |

### Channel quality — CAC vs realized loss

| Channel | Accounts | CAC | Loss rate |
| --- | --- | --- | --- |
| paid_search | 3,581 | $145 | 4.59% |
| affiliate | 2,621 | $110 | 3.80% |
| partner | 970 | $90 | 3.31% |
| referral | 1,895 | $25 | 2.95% |
| in_app | 2,933 | $35 | 2.87% |

### Risk gradient by origination band (must rise A→E)

A 1.03% → B 1.98% → C 3.20% → D 6.28% → E 17.58%

### Portfolio calibration checks

| Check | Value | Realistic range | Verdict |
| --- | --- | --- | --- |
| Expected-loss rate (carried balance) | 3.57% | 3–8% | ✅ |
| Interest yield (carried balance) | 21.95% | 18–25% | ✅ |
| Interchange take rate | 1.70% | 1.5–2.0% net | ✅ |
| Revolve rate | 37.7% | 30–45% | ✅ |
| Spend per active account/month | $474 | $300–600 | ✅ |

---

## 2. Bugs found and fixed (the interesting part)

### Bug 1 — Expected loss was 60% annualized (17x too high)
The loss formula multiplied a *monthly* PD by 12 and applied it to the full balance every month,
compounding into absurdity: 60% portfolio loss, 193% for band E. It would have invalidated
every conclusion downstream, and it looked entirely plausible in the query output.

**Fix:** treat PD as a genuine annual rate and divide by 12 for the monthly accrual
(`ead × pd_annual × lgd / 12`), with a 6x multiplier for already-delinquent accounts.
**Result:** 3.57% — credible.

### Bug 2 — `avg_daily_balance_usd` and `revolve_balance_usd` were duplicates
The generator wrote the same number to both fields, so "revolve balance" carried no distinct
meaning and non-revolvers appeared to hold no balance at all (99.6% of balance sat on revolvers —
unrealistic).

**Fix:** model the two concepts separately — revolvers carry their balance; transactors hold
genuine mid-cycle float (25–60% of monthly spend). Interest accrues only on carried balances.
**Result:** the distinction is now real, and the memo's loss denominator is meaningful.

### Bug 3 — Loss rate had the wrong denominator (understated by ~2x)
KPIs divided expected loss by *average daily balance*, which includes transactor float that is
**never at risk of credit loss**. This produced a nonsensical 0.28% portfolio loss rate while
segments showed 1.5–25%.

**Fix:** standardize every loss rate on the **carried (revolving) balance**. Documented inline in
`sql/kpi_dashboard.sql` and in the dashboard footer.

### Bug 4 — Segmentation averaged all history instead of a trailing window
The first version grouped by `account_id, stat_month` with plain `AVG()`, so a segment reflected
an account's *entire* history rather than recent behavior — mislabeling accounts for months after
their behavior changed.

**Fix:** a true trailing 3-month window (`ROWS BETWEEN 2 PRECEDING AND CURRENT ROW`).

### Bug 5 — `trailing` is a reserved word; fairness audit had the wrong table
`WITH trailing AS (...)` failed to parse in DuckDB. The fairness audit selected `age_band`/`region`
from `account_months`, where those columns don't exist.

**Fix:** renamed the CTE to `roll3`; joined `accounts` for the audit dimensions; replaced
`AVG(boolean)` with `AVG(CASE WHEN ... THEN 1.0 ELSE 0.0 END)`.

### Bug 6 — Hypothesis H2 was wrong, and I corrected the memo rather than the data
The case brief predicted the maxed-out segment would be *margin-negative*. It isn't — it has the
*high* margin ($28.35) but also **2.7x the loss rate** of the headroom segment, on a base of only
207 accounts.

**Action:** rewrote the recommendation to argue on risk-adjusted grounds (capital at risk,
downturn sensitivity) instead of the false "negative margin" claim. Changing the conclusion to
fit the data is the whole point of stating hypotheses up front.

---

## 3. Validation checklist (all passing)

- [x] Row counts reconcile: 12,000 accounts; 245,821 account-months
- [x] Anti-join test: 0 orphan `account_months` rows (`sql/load.sql`)
- [x] Loss rate rises monotonically across risk bands A→E
- [x] All 11 SQL statements execute cleanly (`sql/*.sql`)
- [x] Interest accrues only on carried balances, not float
- [x] Scenario outputs report low/base/high, never a point estimate
- [x] Fairness audit runs before any targeting recommendation
- [x] Every memo number regenerates from `scripts/run_analysis.py`

## 4. Known limitations

- **Synthetic data**: correlations are designed, not discovered. Real data would add balance
  transfers, bureau refreshes, statement-cycle effects, and competing offers.
- **Latest-month KPI loss rate (0.34%) vs segment rates (1.5–25%)**: the KPI is a single month of
  a growing book, diluted by accounts not yet revolving. The segment cuts are the meaningful view;
  a 12-month rolling rate would be the production fix.
- **Elasticity assumptions** in the scenario model are illustrative. With real data I would
  calibrate draw-down and revolve rates from historical line-increase tests.
- **Fairness audit** is a four-fifths-style screen, not a legal disparate-impact analysis.
