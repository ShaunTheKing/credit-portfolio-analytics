# Case Brief — Synthetic Credit Card Portfolio

## 1. Setting

**"Halo Card"** (fictional): a credit card from a consumer fintech — no annual-fee base tier,
a paid "premium" membership tier, cashback rewards, and a mobile-first customer base. Growth
targets are set, losses are within risk appetite but rising in new vintages, and promo budget
is contested.

This setting exists because the real dataset used elsewhere in this project has no revenue,
acquisition, or offer fields. Modeling a synthetic portfolio with those dimensions makes the
complete analytical workflow demonstrable: unit economics, segmentation, pricing trade-offs,
and experiment design.

> **On synthetic data:** its correlations are *designed* rather than *discovered*, so
> conclusions drawn from it are hypotheses, not findings. Two of them were corrected once real
> data was introduced — see [real-data-findings.md](real-data-findings.md).

## 2. The three questions (each = one project deliverable)

| # | Question | Skill tested | Deliverable |
| --- | --- | --- | --- |
| Q1 | "Which customers should get credit-line increases next quarter?" | Segmentation, risk-return trade-offs | Segment heatmap + ranked recommendation with loss guardrail |
| Q2 | "We can afford one: 0% APR promo for 12 months, or a cashback boost — which pays back better?" | Pricing, economic modeling | What-if model + assumptions + sensitivity |
| Q3 | "How will we know if the offer program actually worked?" | Program efficacy | Measurement design (holdout, payback window) + efficacy dashboard spec |

**Hypotheses to test (stated before querying, so results can falsify them):**

- H1: Revolvers with utilization **30–70%** and clean payment history drive most contribution
  margin; they are the best line-increase audience.
- H2: Very-high-utilization (>85%) accounts show high revenue but **margin-negative** outcomes
  after expected loss — revenue alone would mislead.
- H3: 0% APR promos shift balances cheaply but back-book revenue collapses at promo expiry;
  cashback boosts cost more upfront but retain behavior → different payback windows.

## 3. Data model (grain definitions)

| Table | Grain | Key fields |
| --- | --- | --- |
| `accounts` | account | open_date, acquisition_channel, region, age_band, credit_line_usd, apr_tier, fee_tier, premium_member, origination_risk_band, credit_score_band |
| `account_months` | account × month | purchases, payments, avg_daily_balance, revolve_balance, interest_charged, interchange_rev, fee_rev, promo_cost, utilization_pct, days_past_due, expected_loss_usd, chargeoff_usd, current risk_band |
| `offer_exposures` | offer × account | offer_type (line_increase / apr_promo / fee_waiver / cashback_boost / control), offer_value, exposed_at, channel, in_holdout |
| `marketing_spend` | month × channel | spend_usd, new_accounts → CAC |

`expected_loss_usd` is treated as a **risk-model output (PD × LGD × EAD)** — the analyst
*consumes* it; we never invent risk scores and never build adverse-action logic. That framing
is itself a governance position: the analyst consumes risk outputs rather than substituting
judgment for the risk function's.

## 4. Synthetic data spec (Week 0 build)

Generate with a seeded script (`scripts/generate_synthetic_data.py`, ~200 lines of numpy/pandas)
so every number is reproducible. Correlations to encode (realism = credible insights):

| Relationship | Direction to encode |
| --- | --- |
| Origination risk band ↔ utilization ↔ loss | Lower bands: higher utilization, higher revolve, higher expected loss and charge-offs |
| Acquisition channel ↔ CAC ↔ quality | Paid search: high CAC, mixed quality; referral/in-app: low CAC, better activation |
| Premium membership ↔ spend | Higher purchase volume, lower price sensitivity |
| Revolve behavior ↔ interest revenue | ~35–45% of accounts revolve in a month; interest scales with balance × APR tier |
| Promo exposure ↔ behavior | APR promo: balance migration up, interest down during promo; cashback boost: purchase lift, small margin cost |
| Seasonality | Nov–Dec purchase lift; Jan payments surge (tax/holiday) |
| Vintage effect | 2026 vintages slightly higher loss than 2025 (the "rising losses" tension) |

Size: ~12K accounts × 24 months ≈ 290K account-months — big enough for SQL to feel real,
small enough for DuckDB on a laptop.

## 5. Program efficacy framework (Q3)

1. **Design first:** every offer gets a **holdout (5–10%)** and a pre-registered success metric
   and payback window (e.g. "incremental contribution margin covers promo cost within 9 months").
2. **Estimate:** incremental = exposed − holdout (difference-in-differences on pre-period
   behavior to correct for selection bias; report pretrend check).
3. **Guardrails:** expected-loss rate and delinquency roll rates may not breach risk appetite
   even if margin passes.
4. **Dashboard:** weekly cohort view — offer response rate, incremental margin per exposed
   account, payback progress bar, loss guardrail status (green/amber/red).
5. **The analyst's job** per the JD: "execute key strategic initiatives and **monitor program
   efficacy**" — this artifact is that skill.

## 6. Fair-lending & ethics guardrails (built into the analysis)

- Segments are **behavioral** (utilization, payment behavior, engagement) — never age, region,
  or other protected-class proxies as targeting criteria; use them only for **fairness audits**
  ("does the recommendation produce disparate impact?").
- Recommendations are **human decisions**: the model ranks opportunity; it never decides
  individual credit actions (no adverse-action logic).
- Document assumptions where a wrong elasticity estimate could hurt customers (e.g. line
  increases that invite over-extension) — mitigation: stepped increases + spend monitoring.

## 7. What would change with richer data

Given transaction-level data → true balance
transfers/migration, statement-cycle effects, bureau refreshes and score migration, competing
offers in market, contact-center signals, and true CLV with funding cost. I'd also want the
risk team's vintage curves to calibrate my expected-loss consumption and a finance sign-off on
margin definitions — same framework, better inputs.
