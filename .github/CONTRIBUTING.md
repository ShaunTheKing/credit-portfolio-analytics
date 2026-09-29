# Contributing

Thanks for taking a look. This is primarily a portfolio analysis project, but issues and
suggestions are welcome.

## Running locally

```bash
pip install duckdb xlrd

# Real-data analysis (downloads ~5 MB from UCI on first run)
python3 scripts/fetch_real_data.py
python3 scripts/run_real_analysis.py

# Synthetic pipeline (no external data)
./scripts/run_all.sh          # full
./scripts/run_all.sh --quick  # smoke test
```

## Before opening a PR

CI runs three jobs (see `.github/workflows/ci.yml`): the synthetic pipeline end to end, the
real-data pipeline, and a check that every SQL statement executes. Run them locally first:

- `./scripts/run_all.sh` completes and writes all `output/` deliverables
- `python3 scripts/run_real_analysis.py` produces 9 result sets
- No headline number regresses (loss rates monotonic across risk bands; default rate matches
  the published ~22.1% baseline)

## Conventions

- **Metrics must be defined before use.** Add new ones to `docs/metrics-playbook.md` with a
  formula, grain, and guardrail, then reference that line from the query.
- **State the denominator.** Any rate needs one, visible in the SQL.
- **Assumptions go in a view**, not inline in a query (`sql/pricing_sensitivity.sql` §1).
- **Comment CTEs with *why***, not what.
- **Fairness fields are audit-only.** Never introduce a protected attribute as a targeting input.
