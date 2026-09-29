# Design Note — Where Jev (TypeSafe AI) Would Fit

**Status:** design note, not implemented. No Jev code ships in this repo, and no API key is
needed to run anything here.

This documents a concrete, tested-in-design integration of [Jev](https://docs.typesafe.ai)
(TypeSafe AI's decision model) into this project — including why it fits one part of the
analysis and would be actively harmful in the rest.

---

## 1. What Jev is, precisely

Jev is a **decision model, not a text generator**. One request carries a `state` (string, JSON
object, or array) plus a map of typed questions; every question is answered in parallel against
the same state, and every answer returns as a calibrated probability distribution. It never
writes prose or explanations.

| Primitive | Asks | Answer |
| --- | --- | --- |
| `noul` | Probability a yes/no statement is true | `noul` in [0, 1] |
| `choice` | Pick one of N unordered options | `choice`, `probabilities`, `confidence` |
| `score` | Position on an ordered rubric (2–10 described levels) | `score` (probability-weighted mean, fractional) |

**Request shape** (verified live — an unauthenticated call returns
`403 {"error_type":"authentication_error"}`, confirming the contract):

```
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer $TYPESAFE_API_KEY
Content-Type: application/json

{
  "state": { ... },
  "model": "jev-latest",
  "questions": { "<id>": { "type": "noul" | "choice" | "score", ... } }
}
```

Runnable through a gateway by swapping base URL, key, and model — e.g. Vercel AI Gateway at
`https://ai-gateway.vercel.sh/typesafe` with model `typesafe-ai/jev`, or OpenRouter with
`~typesafe/jev-latest`. **Chat-completion clients do not work with the decision endpoint.**

## 2. The architectural rule this project already follows

This repo's analyses split cleanly into two kinds of work, and that split decides where Jev
belongs:

| Kind of work | Example in this repo | Right tool |
| --- | --- | --- |
| **Exact** — arithmetic, comparisons, counting, joins, thresholds | Loss rates, ROI, denominators, concentration | **SQL.** Deterministic, auditable, already tested |
| **Judgment over meaning** in unstructured text | "Is this job title income-stable?" | **Jev** |

Jev's own guidance is explicit that math, counting, date ordering, and exact magnitudes belong
in code. Every headline finding in this repo is arithmetic. **Putting Jev anywhere near them
would replace a precise, verifiable number with a probability — strictly worse.**

## 3. Where Jev genuinely fits: `emp_title`

The one genuinely unstructured field with real signal in this repo is LendingClub's
`emp_title` — the borrower's self-reported job title:

- **96,160 loans (83.1%)** have a non-empty value
- **36,477 distinct strings** — free text, no controlled vocabulary
- Whitespace/casing/abbreviation chaos: `'rn'` (724), `'RN'`, `'registered nurse'` (1,306),
  `'Nurse'`, `'AUTO REPAIR'`, `'Lay up technician'`, `'DevOps Specialist'`, `'Tax Director'`

Why this is a real problem, not a toy: the existing analysis buckets income stability using
`emp_length` — a *tenure* field. Two borrowers both showing "10+ years" may be a tenured
physician and a gig driver. Tenure is not income stability or volatility, and the numeric
pipeline cannot tell them apart because the distinction lives in the text.

### Proposed question module (single request per loan)

```python
QUESTIONS = {
    # Ordered spectrum -> Score, never Noul (0.5 would mean "equally likely", not "medium")
    "income_stability": Score(
        instructions="How stable and predictable is the income from this occupation?",
        criteria=[
            "Highly irregular or gig-based income (driver, freelance, seasonal, unemployed)",
            "Variable hours or commission-driven, but continuous work",
            "Steady salaried or hourly employment with predictable income",
            "Salaried professional role with strong income security",
            "Tenured, licensed, or tenured-credentialed professional (physician, tenured academic)",
        ],
    ),
    # Armed-forces/pension and public-sector stability are separate judgments,
    # not points on the same spectrum
    "is_public_sector": Noul(
        instructions="Is this occupation in government, military, or public-sector employment?",
    ),
    "is_high_volatility": Noul(
        instructions="Is this occupation typically characterized by irregular or unpredictable earnings?",
        raw={"true": "gig, commission-only, seasonal, or tip-dependent work",
             "false": "predictable salaried, hourly, or contract income"},
    ),
    # Escape hatch so a forced choice cannot silently misroute an odd title
    "occupation_class": Choice(
        instructions="What broad occupational class best fits this title?",
        criteria={
            "healthcare": "Clinical and medical roles at any seniority",
            "skilled_trade": "Licensed or trained manual trades",
            "professional": "Office, technical, or managerial professional roles",
            "service": "Retail, food, hospitality, personal service",
            "transport": "Driving and logistics roles",
            "education": "Teaching and academic roles",
            "other": "Does not fit any category above, including unclear or blank titles",
        },
    ),
}
```

Design decisions that matter, and why:

- **`score` for stability, never `noul`.** A Noul of 0.5 means "equally likely yes or no" — it
  is not a midpoint. Graded concepts require `score`.
- **Levels describe *situations*, not degrees.** Jev judges each level independently and never
  sees its number or its neighbours, so "high" / "medium" / "low" are meaningless to it.
- **`other` is present in every Choice**, so an odd or blank title cannot be forced into a
  wrong category.
- **Blanks are handled in code**, not sent to Jev: 19,515 loans (16.9%) have an empty
  `emp_title`, and "classify this empty string" is exactly the judgment waste Jev's own
  guidance warns about.
- **One request per loan, questions fanned out.** Questions are parallel and cheap; a second
  request is only justified when its state depends on the first answer.
- **State stays minimal** — job title plus `emp_length`, nothing else. Accuracy falls as
  irrelevant state grows, and passing the whole loan record would also leak financial detail
  into a decision call for no benefit.

### How it would be consumed and validated

Jev supplies one input; SQL still owns the analysis:

```
Jev → income_stability (0..1 normalised), occupation_class
SQL → joins to loan outcomes, compares charge-off and ROI across stability bands,
      and checks whether the Jev signal separates risk BEYOND emp_length alone
```

The validation is the interesting part, and it is only possible because this repo already has
real outcomes: if Jev's stability signal does not separate charge-off rates after controlling
for `emp_length`, it has not earned its place. That is a testable claim, not a demo.

## 4. Where Jev must not go in this repo

| Candidate | Why not |
| --- | --- |
| Loss rates, ROI, concentration (Q0–Q8) | Pure arithmetic. Jev explicitly refuses math and counting; SQL is exact and auditable |
| The denominator decision | A definitional choice a human owns, not a judgment to delegate |
| Grade / term / purpose bucketing | Already-structured categoricals — a `CASE` statement is exact and free |
| Any adverse-action logic | Credit decisions require determinism, documented reasons, and human accountability |
| Fairness audits | Protected attributes must be handled by explicit rule, never by a model's inference |

The last two matter most. In a regulated credit setting, a model output cannot be the reason a
borrower is denied or charged more. Jev's role here is strictly **enrichment of an analyst-facing
signal**, never an automated decision.

## 5. If this were implemented

- **Key handling:** `TYPESAFE_API_KEY` from the environment only — never committed, never in a
  notebook cell, never in a prompt.
- **Cost control:** one request per loan × 96,160 loans requires deliberate batching. A sample
  (e.g. 2,000 loans stratified by grade) would test the signal before any full run.
- **Determinism:** pin a versioned model ID rather than an alias, because an alias moving
  silently changes results without a code change.
- **CI:** the API path cannot run in GitHub Actions without a secret, so CI would use
  **recorded response fixtures** — the same pattern already used for the mock-Jev client in the
  sibling project. The analysis must remain reproducible with zero API access.
- **Caching:** responses cached by `(title_normalised, model_version)` — the same title recurs
  thousands of times, so a naive implementation would pay for `'teacher'` 2,465 times.

## 6. Why this is documented rather than shipped

Deliberately choosing *not* to add Jev says more than adding it would:

1. **Every headline finding here is exact arithmetic.** Adding a probability model to exact
   work would make the analysis less trustworthy, not more.
2. **A key-gated path that CI cannot exercise** turns a reproducible pipeline into one that
   only works on the author's machine. This repo's value is that a stranger can clone it and
   regenerate every number.
3. **The fit is narrow and honest.** Jev does one real job here — reading 36,477 messy job
   titles — and a design note can state that precisely, whereas a three-line demo integration
   would imply far more than it delivers.

## References

- [TypeSafe Jev documentation](https://docs.typesafe.ai) · [API primitives](https://docs.typesafe.ai/primitives) · [models & limits](https://docs.typesafe.ai/models)
- [Vercel AI Gateway — TypeSafe clients and Jev HTTP API](https://vercel.com/changelog/ai-gateway-now-supports-typesafe-clients-and-http-api-for-jev)
- [TypeSafe Jev on LiteLLM](https://docs.litellm.ai/blog/typesafe_jev)
- [OpenRouter — Jev decision model](https://openrouter.ai/docs/guides/community/jev)
- [TypeSafe SDKs — JavaScript and Python](https://docs.typesafe.ai/sdk)
