# Loan Profitability & Pricing — Findings

**Dataset:** LendingClub public loan performance data, 2019Q1 vintage — **115,675 loans**
(102,581 resolved), one row per loan with lifetime cash flows to the file's snapshot date.

**Why this dataset:** the UCI credit-card data used elsewhere in this project has real default
outcomes but **no revenue**. LendingClub carries actual interest collected, charged-off
principal, and recovery amounts — which makes true profit-and-loss, pricing-by-risk-grade, and
risk-adjusted return analysis possible.

**Source & license:** LendingClub public loan statistics files,
[lendingclub.com/info/download-data.action](https://www.lendingclub.com/info/download-data.action).
See [NOTICE.md](../NOTICE.md) for provenance details.

---

## The denominator trap (read this first)

**11.3% of loans in this file are still open** (Current, Late, In Grace Period). Any charge-off
rate computed over *all* loans is wrong, because it dilutes the denominator with loans that
have not had time to resolve:

| Base | Charge-off rate | Verdict |
| --- | --- | --- |
| All loans | 11.81% | **Wrong** — includes 13,094 unresolved loans |
| **Resolved only** (Fully Paid + Charged Off + Default) | **13.32%** | Correct |

That is a 13% relative understatement from a single denominator choice. Every risk rate in
[`sql/loan_analysis.sql`](../sql/loan_analysis.sql) is restricted to resolved loans for this
reason, and Q0 reports both figures so the size of the error stays visible.

---

## Finding 1 — Portfolio P&L: $1.64B principal returning 8.7%

| Metric | Value |
| --- | --- |
| Principal originated | **$1,636.8M** |
| Interest collected | $273.0M |
| Principal written off | $152.1M |
| Recoveries | $26.3M |
| **Net profit** | **$142.6M** |
| **Return on principal** | **8.71%** |
| Recovery rate on written-off principal | 17.3% |

Recovery is the quiet lever here: 17.3% of written-off principal came back, which is worth
$26.3M — nearly a fifth of net profit.

## Finding 2 — Risk-based pricing worked, and profitability rises with risk

| Grade | Loans | Avg rate | Charge-off rate | ROI | LGD |
| --- | --- | --- | --- | --- | --- |
| A | 35,133 | 7.7% | 6.00% | 7.16% | 55.1% |
| B | 28,290 | 11.6% | 11.84% | 9.11% | 61.7% |
| C | 23,348 | 15.3% | 18.11% | 9.47% | 64.9% |
| D | 12,697 | 20.3% | 24.65% | 9.80% | 68.7% |
| E | 3,066 | 25.1% | 27.46% | **12.87%** | 68.6% |

Charge-off rates rise **4.6x** from A to E, yet ROI *also* rises — higher rates more than
compensated for higher defaults in this vintage. Note loss-given-default rises with grade too
(55% → 69%), the opposite of what a naive view assumes.

## Finding 3 — The pricing broke down at 60 months

Pooling terms hides the real structure. Split by term:

| Term | Grade A | Grade C | Grade D | Grade E |
| --- | --- | --- | --- | --- |
| **36 months** | 7.16% | 10.60% | 12.40% | **15.19%** |
| **60 months** | 7.17% | 8.17% | **7.53%** | 9.90% |

**At 36 months, ROI rises monotonically with risk. At 60 months it collapses.** Grade D 60-month
loans return 7.53% versus 12.40% for the same grade at 36 months, and charge-off rates nearly
double (19.67% → 32.10%).

The mechanism: a longer term gives defaults more time to occur before the extra interest is
collected. The rate premium that prices 36-month risk is insufficient for 60-month risk —
**term is a risk factor that was not fully priced**, at least in this vintage.

*This is the single most actionable finding in the dataset, and it only appears once you split
by term. The pooled view (Finding 2) actively misleads.*

## Finding 4 — Loss concentration is extreme but the base rate explains why

| Metric | Value |
| --- | --- |
| Resolved loans with **zero** loss | 88,989 (**86.7%**) |
| Top 1% of loans by loss | 20.0% of all losses |
| Top 5% of loans by loss | 66.9% of all losses |
| Top 10% of loans by loss | **94.3%** of all losses |

Because 86.7% of loans paid in full, "top 10% by loss" is simply "the largest loss-making
loans" — every one of them charged off. Quoting 94.3% without the 86.7% base rate makes an
obvious fact sound dramatic, so both are reported together.

## Finding 5 — Losses scale with loan size; returns scale inversely

| Loan size | Loans | Charge-off rate | ROI |
| --- | --- | --- | --- |
| < $5k | 9,436 | 8.82% | **11.31%** |
| $5–10k | 20,788 | 10.33% | 10.07% |
| $10–20k | 38,085 | 13.62% | 9.23% |
| $20–30k | 19,073 | 16.31% | 8.45% |
| $30k+ | 15,199 | 15.72% | **7.93%** |

Charge-off rates roughly double with size while ROI falls by a third. Larger loans are riskier
per dollar *and* less profitable per dollar — so volume growth in this vintage came at the
expense of return quality.

## Finding 6 — Purpose matters: small business lending is the weak spot

| Purpose | Loans | Charge-off rate | ROI |
| --- | --- | --- | --- |
| Car | 962 | 8.42% | **11.80%** |
| Home improvement | 6,079 | 11.98% | 9.00% |
| Debt consolidation | 55,899 | 14.16% | 8.81% |
| Credit card | 28,165 | 12.13% | 8.66% |
| Medical | 1,220 | 13.44% | 7.84% |
| **Small business** | 982 | **17.52%** | **5.71%** |
| House | 673 | 15.90% | 5.24% |

Small business loans charge off at more than double the car-loan rate and return roughly half.
Debt consolidation dominates volume (54%) but sits mid-pack on return.

## Finding 7 — Recent credit inquiries are a strong negative signal

| Credit signal | Loans | Charge-off rate | ROI |
| --- | --- | --- | --- |
| ≥3 inquiries in 6 months | 1,548 | **20.99%** | **2.09%** |
| Prior derogatory marks | 26,204 | 13.53% | 9.42% |
| Clean | 74,829 | 13.09% | 8.61% |

Borrowers with ≥3 recent inquiries default at 1.6x the clean rate with **ROI of just 2.09%** —
less than a quarter of the portfolio average. Notably, *prior derogatory marks alone barely
separate risk* (13.53% vs 13.09%), while recent inquiry velocity does. A cheap, high-signal
screening feature.

---

## Method notes and limitations

- **This is a cohort snapshot, not a survival model.** Loan status is as of the file's
  publication date; loans are observed for varying lengths of time. A proper analysis would use
  vintage curves and hazard models.
- **No FICO scores in this vintage.** LendingClub dropped them from later public files, so
  credit-quality signals here are public records, delinquencies, inquiry counts, revolving
  utilization, and the assigned grade.
- **The 2019Q1 vintage is not representative** of all LendingClub originations, and the
  platform's underwriting changed substantially over time. Findings describe this vintage.
- **Grade F (n=30) and G (n=17) are too small to interpret** — their ROI figures are noise and
  are shown only for completeness.
- **`net_profit` for open loans is "earned so far"**, not lifetime, which is why it is excluded
  from every profitability figure above.
- **Geographic results (Q8) are a monitoring view**, not a targeting recommendation: state-level
  differences reflect lending law, borrower mix, and servicing practice as much as credit risk.
- **`loan_id` is a surrogate key** — LendingClub blanks borrower identifiers in public files.
