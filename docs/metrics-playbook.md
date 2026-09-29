# Metrics Playbook

A metric nobody defined is a metric nobody trusts. This playbook is the single source of
truth for the project. **Rule: every dashboard number links to a line here.**

## 1. Unit economics (the tree everything hangs from)

```
Contribution margin per account (monthly)
  = + interest_charged_usd          (revolve revenue; balances × APR tier)
  + + interchange_rev_usd           (spend × take rate, net of rewards cost)
  + + fee_rev_usd                   (annual/membership/late fees)
  − − promo_cost_usd                (offer cost allocated to the month)
  − − expected_loss_usd             (risk-model output: PD × LGD × EAD)
  − − funding_cost_usd              (avg balance × funds transfer rate)   [assumption table]
```

Portfolio value of an initiative = **Δmargin per affected account × eligible accounts**,
always reported against its **expected-loss delta** — that pairing *is* the "risk-return
trade-off" the JD asks for.

## 2. KPI dictionary

| KPI | Definition (formula) | Grain | Owner | Guardrail / common pitfall |
| --- | --- | --- | --- | --- |
| Activation rate | % of new accounts with purchases > $0 within 30 days of open | monthly vintage | Growth | Compare only same-maturity vintages; immature vintages bias it down |
| Spend per active account | Σ purchases ÷ count(accounts with purchases > 0) | month | Growth | Winsorize outliers (huge one-off purchases); report median alongside mean |
| Revolve rate | % of active accounts with revolve_balance > 0 at statement close | month | Credit | Don't mix with utilization; an account can revolve at 5% or 95% util |
| Utilization | revolve_balance ÷ credit_line | account × month | Credit | Segment bands: 0 / 1–30 / 30–70 / 70–85 / 85+ |
| Interest revenue / account | Σ interest_charged_usd ÷ accounts | month | Finance | APR promos distort trend — flag promo cohort separately |
| Interchange take rate | interchange_rev_usd ÷ purchases_usd | month | Finance | Rewards cost must be netted before calling it revenue |
| Revenue / account | (interest + interchange + fees) ÷ accounts | month | Finance | Never present without the expected-loss line beside it |
| Expected-loss rate | Σ expected_loss_usd ÷ Σ avg exposure | month / vintage | Risk | Consumes a risk-model output; changes when the model version changes — note it |
| 30+ DPD rate | % accounts with days_past_due ≥ 30 | month | Risk | Roll-rate view (30→60→90) tells more than the level |
| Charge-off rate | Σ chargeoff_usd ÷ Σ exposure (annualized) | vintage | Risk | Lagging indicator; pair with early delinquency for action |
| Contribution margin / account | §1 formula | month / segment | Finance | The one number a VP should remember |
| CAC | marketing spend ÷ new accounts | month × channel | Growth | Include promo cost in blended CAC or you'll overstate payback |
| 12/24-mo CLV | Σ discounted future contribution margin per cohort | cohort | Finance | State the discount rate and churn assumption *in the exhibit* |

## 3. Standard cuts (make these the dashboard defaults)

- **Cohort/vintage** (open month) × **acquisition channel** × **risk band at origination**
- **Behavioral segment** (see segmentation.sql) for targeting questions
- **Offer exposure** (treatment vs holdout) for efficacy questions
- Always: **this month vs same month last year** (seasonality: Nov–Dec spend lift, Jan payments)

## 4. Validation checklist ("how I know my numbers are right")

Run and record these — QA discipline is a differentiator:

1. **Reconciliation:** revenue components sum to total revenue; account counts in every query
   tie back to `accounts`.
2. **Anti-join test:** any account appearing in `account_months` must exist in `accounts`.
3. **Balance identity:** opening + purchases − payments ± fees ≈ closing (tolerance for
   interest/fees posting).
4. **Distribution sanity:** utilization in [0, 1.2] (allowing over-limit), DPD in {0..120+},
   negative values only where expected (payments/credits).
5. **Pretrend check** before any causal claim (efficacy analysis): treatment and holdout must
   be parallel pre-exposure.
6. **Sensitivity:** no recommendation ships on a single point estimate — low/base/high.

## 5. Language discipline (how analysts write)

- "Modeled estimate under stated assumptions" — not "will".
- Every recommendation carries: **the number, the assumption it leans on, the guardrail metric,
  and what result would change my mind.**
- Separate **observation** ("revolve rate +120 bps YoY in the 70–85% util band") from
  **interpretation** ("consistent with balance migration after the APR promo expired") from
  **recommendation** ("test a targeted cashback offer with a holdout").
