# Credit Portfolio Analytics

SQL-first analytics for consumer credit portfolios: KPI definition, behavioral segmentation,
risk-return modeling, and program measurement — applied to a **real** public dataset and a
synthetic one built to stress-test the method.

[![SQL](https://img.shields.io/badge/SQL-DuckDB-fff000?logo=duckdb&logoColor=black)](#)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776ab?logo=python&logoColor=white)](#)
[![Data](https://img.shields.io/badge/Data-CC%20BY%204.0-4c9f70)](#data--attribution)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

---

## What this is

Three datasets, one analytical toolkit:

| | **UCI credit cards** | **LendingClub loans** | **Synthetic portfolio** |
| --- | --- | --- | --- |
| Nature | Real | Real | Generated |
| Scale | 30,000 clients · 180,000 client-months | 115,675 loans · $1.64B principal | 12,000 accounts · 246,000 account-months |
| Has revenue? | No | **Yes — interest, losses, recoveries** | Yes |
| Answers | Who defaults, and why | **Does risk-based pricing pay?** | Offers, channels, CAC, CLV |
| Findings | [real-data-findings.md](docs/real-data-findings.md) | [loan-findings.md](docs/loan-findings.md) | [analysis-log.md](docs/analysis-log.md) |

The synthetic portfolio exists to fill what neither real dataset provides — acquisition cost,
offer exposure, and channel mix — so the full workflow, including unit economics and experiment
design, can be demonstrated end to end.

**Everything is reproducible.** All three pipelines run from a clean clone and regenerate every
figure quoted below.

---

## Findings

### LendingClub loans (115,675 loans, $1.64B principal)

**Risk-based pricing worked at 36 months and broke down at 60.** This is the most actionable
result in the project, and it only appears when you split by term:

| Term | Grade A | Grade C | Grade D | Grade E |
| --- | --- | --- | --- | --- |
| **36 months** | 7.16% | 10.60% | 12.40% | **15.19%** |
| **60 months** | 7.17% | 8.17% | **7.53%** | 9.90% |

At 36 months ROI rises monotonically with risk. At 60 months it collapses — grade D returns
7.53% versus 12.40% for the same grade at 36 months, with charge-off rates nearly doubling
(19.67% → 32.10%). Longer terms give defaults more time to occur before the rate premium is
collected. **The pooled view actively misleads** (see [loan-findings.md](docs/loan-findings.md)).

**Portfolio result:** $142.6M net profit on $1,636.8M principal — an **8.71%** return, with
recoveries returning 17.3% of written-off principal.

**The denominator trap:** 11.3% of loans are still open. Charge-off rate is **13.32%** among
resolved loans but **11.81%** across all loans — a 13% relative understatement from one
denominator choice.

**Larger loans are worse on both axes:** charge-off rates roughly double from <$5k to $30k+
(8.82% → 15.72%) while ROI falls by a third (11.31% → 7.93%).

### UCI credit cards (30,000 clients, Apr–Sep 2005)

**Repayment behavior is a sharper risk signal than utilization.**

| Payment behavior | Clients | Observed default rate |
| --- | --- | --- |
| Made no payment | 3,495 | **39.77%** |
| Partial payment | 17,299 | 20.78% |
| Paid most of bill | 2,737 | **14.94%** |
| Paid in full | 3,871 | 15.50% |

Utilization, by contrast, is **not monotonic** across buckets (0% utilization defaults at
24.77%, below-30% at 16.93%, 85%+ at 26.65%) — it is a blunt instrument on its own.

**Risk is highly concentrated.** The top 10% of accounts by expected loss carry **76.7%** of
total expected loss; the bottom half carries 1.84%. Collection resources belong on a narrow,
identifiable population.

**Risk falls monotonically with credit limit** — 36.07% default below 50,000 (NT$) down to
11.95% above 400,000. This reflects limits being *set from* risk, not a causal effect of
raising limits; the distinction matters.

**Repayment status dominates everything.** Default rates run 13.83% (paying duly) → 74.37%
(3–4 months late), a 5x spread.

### Synthetic portfolio (12,000 accounts)

**Revenue and margin point in different directions.** The maxed-out utilization segment posts
the highest revenue per account ($44.77) but carries **2.7x the loss rate** of the revolver
segment (9.07% vs 3.32%) — ranking on revenue alone selects the wrong target.

**Acquisition quality varies sharply by channel.** Paid search costs **$145 CAC** with a
**4.59%** loss rate; in-app acquisition costs $35 at 2.87%. Paying four times more per account
for worse credit is a subsidy, not growth.

**A modeled line-increase program** returns **$4,990** annual margin against **$3,969**
expected-loss increase (base case; $1,613–$11,007 range across assumptions).

Full write-ups: [real-data-findings.md](docs/real-data-findings.md) ·
[analysis-log.md](docs/analysis-log.md).

---

## Quickstart

```bash
git clone https://github.com/ShaunTheKing/credit-portfolio-analytics.git
cd credit-portfolio-analytics
pip install duckdb xlrd

# LendingClub loans — downloads ~20 MB, includes profit & loss
python3 scripts/fetch_loan_data.py
python3 scripts/run_loan_analysis.py         # -> output/loans/

# UCI credit cards — downloads ~5 MB
python3 scripts/fetch_real_data.py
python3 scripts/run_real_analysis.py         # -> output/real/

# Synthetic portfolio — no external data
./scripts/run_all.sh                         # -> output/
./scripts/run_all.sh --quick                 # smoke test, ~2 seconds
```

Outputs land in `output/`: an executive memo, a dashboard, and raw result JSON.

> The DuckDB CLI is optional — loading runs through Python. Generated data and downloaded
> datasets are git-ignored; everything regenerates on demand.

---

## Layout

```
credit-portfolio-analytics/
├── docs/
│   ├── metrics-playbook.md       # KPI dictionary, unit-economics tree, validation checklist
│   ├── loan-findings.md          # Findings: LendingClub profitability & pricing
│   ├── real-data-findings.md     # Findings: UCI credit-card default risk
│   ├── analysis-log.md           # Synthetic findings + QA record + bugs found and fixed
│   ├── case-brief.md             # Business context, data model, hypotheses
│   ├── ai-workflow.md            # AI-assisted analysis workflow and verification checklist
│   └── jev-integration.md        # Design note: where a decision model fits, and where it must not
├── scripts/
│   ├── fetch_loan_data.py        # Download + clean the LendingClub loan files
│   ├── fetch_real_data.py        # Download + reshape the UCI dataset into a panel
│   ├── generate_synthetic_data.py# Seeded portfolio generator (standard library only)
│   ├── run_loan_analysis.py      # Executes the loan SQL pack
│   ├── run_real_analysis.py      # Executes the UCI SQL pack
│   ├── run_all.sh                # generate -> load -> analyze -> build
│   ├── run_analysis.py           # Executes the synthetic SQL pack
│   └── build_memo.py             # Renders memo + single-file dashboard
├── sql/
│   ├── schema.sql, load.sql      # Synthetic schema + load with QA checks
│   ├── schema_real.sql           # UCI schema (adds audit-only demographics)
│   ├── schema_loans.sql          # LendingClub loan schema + resolved-loan view
│   ├── loan_analysis.sql         # 9 profit/pricing queries incl. term-split analysis
│   ├── kpi_dashboard.sql         # Monthly KPI pack
│   ├── segmentation.sql          # Trailing-3-month behavioral segments
│   ├── pricing_sensitivity.sql   # Assumptions table, scenarios, fairness audit
│   └── real_analysis.sql         # 9 queries incl. loss-rate denominator and fairness audit
└── output/                       # Generated deliverables
    ├── loans/                    # LendingClub results
    └── real/                     # UCI results
```

---

## Design decisions

**Metrics are defined before they're computed.** [metrics-playbook.md](docs/metrics-playbook.md)
is the single source of truth: every dashboard number traces to a defined formula, grain, and
guardrail. A rate without a stated denominator is not a metric.

**Loss rates state their denominator explicitly.** Only 12.8% of the real dataset's
account-months carry a balance. Annualized expected loss is **24.45%** against carried balances
and **3.59%** against total exposure. The second is comparable across portfolios; both are
reported so the choice is visible (`sql/real_analysis.sql`, Q0).

**Policy lives in code, judgment lives in models.** Thresholds, routing, and approvals are
deterministic SQL. The expected-loss and pricing models produce inputs; they don't decide.

**Fairness fields are audit-only.** Sex, education, marriage, and age appear in the real dataset
and are carried solely for fairness auditing. They are never targeting inputs. Any production
model using them would require a documented disparate-impact analysis and legal review.

**Assumptions are visible and parameterized.** Every scenario reads from an assumptions table
(`sql/pricing_sensitivity.sql` §1) and reports low/base/high rather than a point estimate.

**Judgment models stay out of the arithmetic.** Every headline finding here is exact
computation, so no probabilistic model touches it. [jev-integration.md](docs/jev-integration.md)
documents the one place a decision model *would* earn its keep — reading 36,477 messy free-text
job titles — and the places it would make the analysis worse.

---

## QA and validation

Sanity-checking outputs against known ranges, not just re-reading code.

- **Real-data ETL validated against the published baseline**: computed default rate is
  **22.12%**, matching the dataset's documented ~22.1%.
- **Row-count and anti-join checks** run on every load (`sql/load.sql`).
- **Loss rates verified monotonic** across delinquency depth (9.0% → 45.0% annualized).
- **All 22 SQL statements execute** (9 real-data + 13 synthetic-pipeline).

Three bugs found and fixed during development, documented in
[analysis-log.md](docs/analysis-log.md) and [real-data-findings.md](docs/real-data-findings.md):

1. **A loss formula producing 60% annualized loss** (17x too high) — a monthly probability was
   being compounded annually.
2. **A one-time write-off booked into a column of monthly accruals**, mixing a stock into a
   flow and annualizing to >1000%.
3. **Annual PD applied monthly**, charging annual-loss magnitudes twelve times a year.

The recurring lesson, and the reason the validation checklist exists: *a plausible-looking wrong
number is more dangerous than an obvious one.*

---

## Limitations

- **The real dataset is cross-sectional** — six months, one market, 2005, with a one-month-ahead
  default label. No recovery, cure, or lifetime-loss analysis is possible from it.
- **It carries no revenue fields**, so interest, interchange, and fee figures on the real side
  are modeled from stated assumptions (`scripts/fetch_real_data.py::ASSUMPTIONS`). Default
  rates are real; margin figures are illustrative.
- **Expected loss for non-defaulters is a proxy** derived from delinquency status, not a
  calibrated PD model.
- **Small buckets** (e.g. 65 clients in the deepest delinquency band) should not be over-read.
- **The synthetic portfolio's correlations are designed, not discovered** — it demonstrates
  method, and its conclusions were partly corrected by the real data.

---

## Data & attribution

Real dataset, licensed **CC BY 4.0**:

> Yeh, I. (2009). *Default of Credit Card Clients* [Dataset]. UCI Machine Learning Repository.
> https://doi.org/10.24432/C55S3H

The raw file is downloaded on demand rather than redistributed here. Full provenance, license
terms, and a map of which artifacts use which dataset: [NOTICE.md](NOTICE.md).

---

## License

Code: [MIT](LICENSE). Documentation and analysis: CC BY 4.0.
