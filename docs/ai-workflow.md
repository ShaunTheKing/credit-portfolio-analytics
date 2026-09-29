# AI-Assisted Analysis Workflow

How AI tools were used to build this project faster *and* safely. In credit analytics a
confident wrong number is expensive, so the verification checklist is the real product here —
AI accelerates the work, it does not own the output.

## 1. Where AI accelerates the work (and where it must not decide)

| Stage | AI's role | Human's role (mandatory) |
| --- | --- | --- |
| Data modeling | Draft schema/DDL, propose grain, generate synthetic-data code | Choose grain & metrics; review every column's meaning |
| SQL | Draft queries from natural language, explain unfamiliar syntax, refactor CTEs | Validate against schema; run and reconcile; own the numbers |
| QA | Generate validation checks, adversarial reads ("what could make this chart lie?") | Run the checks; record results in the playbook |
| Synthesis | First drafts of insight bullets, alternative explanations, devil's advocate | Pick the interpretation; separate observation / interpretation / recommendation |
| Memo | Structure, tighten prose, cut to the point | The recommendation and its guardrails |

**Never:** paste confidential or proprietary data into public tools · accept SQL you haven't
run · let AI invent metrics (it must cite [metrics-playbook.md](metrics-playbook.md)) · ship a
number that fails the validation checklist below.

## 2. Prompt library

1. **Schema draft** — "Design a star schema for a credit-card portfolio analysis: accounts,
   monthly statements, offer exposures, marketing spend. State the grain of each table and 10
   fields per table. Flag anything a credit analyst would need that's missing."
2. **SQL from intent** — "Using this schema [paste], write SQL for monthly revolve rate and
   contribution margin per account. Comment every CTE with *why*. Do not invent columns not in
   the schema."
3. **Query review** — "Act as a skeptical reviewer. Find grain errors, cohort-mixing bugs,
   division-by-zero risks, and survivorship bias in this query [paste]. List issues by severity."
4. **Metric skeptic** — "Here is my metrics dictionary [paste]. Where could two reasonable
   people compute different numbers? Propose canonical formulas and one QA check per metric."
5. **Devil's advocate** — "Here is my finding [paste finding + number]. Give me the three
   strongest alternative explanations and what analysis would distinguish them."
6. **Memo tightening** — "Cut this to a short executive memo: recommendation first, one number
   per claim, one guardrail per recommendation, one falsifier. Kill every hedge word."

## 3. Verification checklist (applied to every AI-assisted deliverable)

- [ ] Ran the SQL personally; totals reconcile to the metrics playbook definitions
- [ ] No column or table referenced that isn't in the schema
- [ ] At least one independent check (row counts, balance identity, anti-join)
- [ ] Interpretations cross-checked against a second explanation (devil's advocate prompt)
- [ ] Numbers in the deliverable equal numbers in the query result
- [ ] Language says "modeled estimate under stated assumptions" where uncertainty is real
- [ ] Magnitudes sanity-checked against known industry ranges

## 4. What this workflow actually caught

The checklist earned its place. Three of the bugs documented in
[analysis-log.md](analysis-log.md) and [real-data-findings.md](real-data-findings.md) were
found by sanity-checking outputs rather than by re-reading code:

- A loss formula producing **60% annualized loss** (17x too high).
- A one-time write-off booked into a column of monthly accruals (>1000% rates).
- Annual PD applied monthly, charging annual-loss magnitudes twelve times a year.

An adversarial-review prompt also surfaced grain errors in drafted SQL. The pattern is
consistent: **AI produced plausible-looking queries and numbers, and the human-owned checks
caught what was wrong.** That division of labor is the point.

## 5. Practice

- Re-run the checklist on any new metric before it appears in a deliverable.
- Keep assumptions parameterized in a view (`sql/pricing_sensitivity.sql` §1) so they can be
  inspected and varied, never buried in a query.
- Report the falsifier alongside every recommendation — the result that would change the answer.
