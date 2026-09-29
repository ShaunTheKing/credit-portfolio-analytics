# Real-Data Findings — UCI Credit Card Default Dataset

**Dataset:** 30,000 real credit-card clients (Taiwan, Apr–Sep 2005), 180,000 client-months.
**Source/license:** [UCI ML Repository #350](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients),
CC BY 4.0 — Yeh, I. (2009), doi:10.24432/C55S3H. Full attribution in [NOTICE.md](../NOTICE.md).

**Why this exists:** synthetic data proves I can build a model. Real data proves I can find
something true in data I didn't design. This is the difference between a class project and
analyst work.

**Validation against published facts:** the overall default rate computes to **22.12%**,
matching the dataset's documented ~22.1% baseline — confirming the ETL is correct before any
analysis is trusted.

---

## Finding 1 — Repayment status is the dominant risk signal

| Repayment status (Sept 2005) | Clients | Observed default rate |
| --- | --- | --- |
| Current (paying duly) | 23,182 | **13.83%** |
| 1 month late | 3,688 | 33.95% |
| 2 months late | 2,667 | 69.14% |
| 3–4 months late | 398 | 74.37% |
| 5+ months late | 65 | 56.92% |

Default risk rises **5x** from current to 3–4 months late. The 5+ bucket dips to 56.9% —
a **small-sample artifact (n=65)**, not a real reversal. Reporting that honestly matters:
an analyst who silently drops the inconvenient bucket is hiding a limitation, not cleaning data.

## Finding 2 — Lower credit limits carry much higher risk

| Credit limit (NT$) | Clients | Observed default rate | Avg utilization |
| --- | --- | --- | --- |
| < 50,000 | 4,311 | **36.07%** | 63.4% |
| 50,000–100,000 | 7,139 | 26.01% | 59.5% |
| 100,000–200,000 | 7,400 | 20.77% | 40.4% |
| 200,000–400,000 | 9,075 | 15.86% | 24.7% |
| 400,000+ | 2,075 | **11.95%** | 20.4% |

A perfectly monotonic gradient: **default risk falls 3x as limits rise**, and the two move
together with utilization. Limit is set *from* risk — so this is confirmation the portfolio
is tiered sensibly, not a causal claim that raising limits reduces default. (Distinguishing
"the model works" from "the limit causes lower risk" is the trap here.)

## Finding 3 — Utilization is a *weaker* signal than I assumed

| Utilization band | Clients | Observed default rate |
| --- | --- | --- |
| 0% | 2,604 | 24.77% |
| < 30% | 12,187 | **16.93%** |
| 30–70% | 5,686 | 24.01% |
| 70–85% | 2,420 | 27.69% |
| 85%+ | 7,103 | 26.65% |

The relationship is **not monotonic**: the zero-utilization bucket defaults *more* than the
low-utilization bucket (24.8% vs 16.9%), and 85%+ is only slightly worse than 30–70%.

**This corrected my synthetic-data instinct.** On the synthetic portfolio, the maxed-out
segment looked distinctly risky. On real data, utilization alone is a blunt instrument —
repayment *behavior* (Finding 4) separates risk far more sharply.

## Finding 4 — Payment behavior separates risk more sharply than utilization

| Payment behavior | Clients | Observed default rate |
| --- | --- | --- |
| No payment made | 3,495 | **39.77%** |
| Minimum only | 8,228 | 19.43% |
| Partial | 9,071 | 21.99% |
| Most of bill | 2,737 | **14.94%** |
| Paid in full | 3,871 | 15.50% |
| No balance | 2,598 | 24.75% |

Clients who make **no payment** default at **39.8%**, roughly **2.7x** the rate of those who
pay most of the bill. Behavior beats balance-based proxies — the practical implication is
that *"did they pay anything?"* is a cheap, high-signal monitoring feature.

## Finding 5 — Risk concentrated in a small share of accounts

| Segment | Share of total expected loss |
| --- | --- |
| Top 10% of accounts | **76.72%** |
| Top 20% of accounts | **87.86%** |
| Bottom 50% of accounts | 1.84% |

Textbook credit-risk concentration: **the top 10% of accounts drive ~77% of expected loss**,
while half the book contributes under 2%. This is the strongest argument for pooling
collection resources on a narrow, identifiable population.

*A definitional note: this share moves with how you define loss.
Booking each observed default as a one-time write-off gives ~85%; accruing expected loss
monthly across the panel gives ~77%. Neither is "wrong" — but quoting one without saying which
is how analysts get into arguments they can't win.*

## Finding 6 — Portfolio deterioration is visible over the six months

| Statement month | Delinquent share | Carried balance (NT$) | Avg utilization |
| --- | --- | --- | --- |
| 2005-04 | 10.26% | 152.8M | 31.8% |
| 2005-05 | 9.89% | 147.1M | 33.3% |
| 2005-06 | 11.70% | 165.7M | 35.9% |
| 2005-07 | 14.04% | 199.4M | 39.0% |
| 2005-08 | 14.79% | 225.6M | 40.9% |
| 2005-09 | **22.73%** | **297.7M** | 42.1% |

Delinquency **more than doubled** (9.9% → 22.7%) while carried balances **nearly doubled**
($147M → $298M) in six months. A real book showing that trajectory would trigger an
immediate risk review — and it is exactly the early-warning pattern a monitoring dashboard
should surface.

## Finding 7 — Fairness audit (audit only; never targeting inputs)

| Sex code | Education | Clients | Observed default rate |
| --- | --- | --- | --- |
| 1 | graduate school | 4,354 | 20.81% |
| 1 | university | 5,374 | 26.20% |
| 1 | high school | 1,990 | 27.39% |
| 2 | graduate school | 6,231 | 18.14% |
| 2 | university | 8,656 | 22.20% |
| 2 | high school | 2,927 | 23.64% |

Default rates differ across demographic groups, and credit limit tracks education strongly
(a confound: limit reflects modeled risk, not group risk). **These fields are excluded from
all targeting logic in this project.** In a regulated setting, any model using them would
require a documented disparate-impact analysis and legal sign-off before deployment —
collecting the audit numbers is the beginning of that process, not the end.

---

## Finding 8 — The loss model itself was broken

Asking the basic question "what is the portfolio loss rate?" returned **430%**. Two
compounding errors in the ETL:

1. **A stock booked into a flow column.** The real default outcome was recorded as
   `expected_loss` in September only, while every other month held a small monthly accrual.
   Summing that mixed column over the panel and annualizing produced >1000%.
   *Fix:* `expected_loss_usd` is now a consistent monthly accrual every month; the observed
   default is booked separately as a one-time `chargeoff_usd` event.
2. **Annual PD applied monthly.** Delinquent accounts accrued 6–24% of balance *per month* —
   annual-loss magnitudes charged twelve times a year.
   *Fix:* PD values are annual and divided by 12 for the monthly accrual.

**The denominator lesson.** Only **12.8%** of account-months carry a balance, so dividing loss
by carried balance excludes ~87% of the book:

| Denominator | Annualized loss rate | Verdict |
| --- | --- | --- |
| Carried (revolving) balance | 24.45% | Overstates — ignores most of the book |
| **Total exposure** (avg daily balance) | **3.59%** | Comparable, and the number quoted |

**Why this belongs in the repo:** I caught it by sanity-checking an output against a known
industry range, not by re-reading code. The same instinct caught the 60% loss rate on the
synthetic side. Two independent datasets, two instances of the same failure mode — which is
exactly why the checklist in [metrics-playbook.md](metrics-playbook.md) exists.

---

## What real data changed about my conclusions

| Question | Synthetic finding | Real-data finding | Verdict |
| --- | --- | --- | --- |
| Is high utilization a strong risk flag? | Yes — maxed-out segment carried 2.7x the loss rate | **No — non-monotonic**, and weaker than payment behavior | ❌ Synthetic instinct was wrong |
| Is repayment behavior informative? | Assumed | **Yes — 39.8% vs 14.9%** across payment behavior | ✅ Confirmed, strengthened |
| Does risk concentrate? | Not tested | **Top 10% = 85% of expected loss** | ✅ New, actionable |
| Does limit correlate with risk? | Assumed (risk bands) | **Yes — monotonic, 36% → 12%** | ✅ Confirmed |

**The honest headline:** my synthetic model overstated utilization as a risk signal. Real
data showed repayment behavior and limit tiering matter more. That correction — and being
willing to write it down — is the most valuable thing in this repo.

## Limitations (state these proactively)

- **Cross-sectional, 2005, one market.** Six months of history, no outcome beyond the next
  month; cannot speak to recovery, cure rates, or vintage performance over time.
- **No revenue data.** Interest, interchange, and fees are modeled from stated assumptions
  (`fetch_real_data.py::ASSUMPTIONS`), so *margin* figures here are illustrative while
  *default-rate* figures are real.
- **Expected loss for non-defaulters is a proxy** derived from delinquency status, not a
  calibrated PD model.
- **Default is a 1-month-ahead label**, so all rates are a snapshot, not an annualized
  lifetime loss rate.
- **Small buckets** (E band n=65; some education cells n<100) should not be over-read.
