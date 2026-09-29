-- =====================================================================
-- pricing_sensitivity.sql — pricing / risk-return what-if (Q2)
-- Method: assumptions live in ONE table (§1) and are visible in every exhibit.
-- Scenarios are low/base/high — never a point estimate.
-- Every number here is a MODELED ESTIMATE under stated assumptions.
-- =====================================================================

-- ---------------------------------------------------------------------
-- §1. Assumptions table (edit here; queries below read from it)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_assumptions AS
SELECT * FROM (VALUES
    ('incremental_balance_pct_of_line', 0.10,  0.18,  0.26),   -- of added line drawn down
    ('revolve_rate_on_new_balance',     0.16,  0.22,  0.28),   -- share of drawn balance carried
    ('net_interest_margin',             0.16,  0.20,  0.24),   -- interest yield net of funding
    ('expected_loss_rate_new',          0.020, 0.035, 0.055),  -- annualized on new exposure
    ('cashback_cost_pct_of_spend',      0.008, 0.012, 0.016),  -- boost cost (e.g. +1% on 60% of spend)
    ('apr_promo_takeup',                0.25,  0.40,  0.55),   -- eligible accounts migrating balances
    ('churn_delta_from_offer',         -0.02,  0.00,  0.02)    -- retention effect (negative = churn down)
) AS a(name, low, base, high);

-- Pivot the assumption table into one row per scenario
CREATE OR REPLACE VIEW v_params AS
WITH p AS (
    SELECT 'low' AS scenario, low  AS v, name FROM v_assumptions
    UNION ALL
    SELECT 'base',             base,      name FROM v_assumptions
    UNION ALL
    SELECT 'high',             high,      name FROM v_assumptions
)
SELECT
    scenario,
    MAX(CASE WHEN name = 'incremental_balance_pct_of_line' THEN v END) AS draw_pct,
    MAX(CASE WHEN name = 'revolve_rate_on_new_balance'     THEN v END) AS revolve_pct,
    MAX(CASE WHEN name = 'net_interest_margin'             THEN v END) AS nim,
    MAX(CASE WHEN name = 'expected_loss_rate_new'          THEN v END) AS loss_rate,
    MAX(CASE WHEN name = 'cashback_cost_pct_of_spend'      THEN v END) AS cb_cost,
    MAX(CASE WHEN name = 'apr_promo_takeup'                THEN v END) AS takeup,
    MAX(CASE WHEN name = 'churn_delta_from_offer'          THEN v END) AS churn_delta
FROM p
GROUP BY scenario;

-- ---------------------------------------------------------------------
-- §2. Q2 head-to-head: 0% APR promo vs cashback boost (per 10K targeted accounts)
--    Both offers run through the same three-line test: cost -> benefit -> loss guardrail.
-- ---------------------------------------------------------------------
SELECT
    offer,
    ROUND(promo_cost_usd, 0)        AS promo_cost_usd,
    ROUND(modeled_benefit_usd, 0)   AS modeled_benefit_usd,
    ROUND(exp_loss_delta_usd, 0)    AS exp_loss_delta_usd,
    ROUND((modeled_benefit_usd - promo_cost_usd)
          / NULLIF(exp_loss_delta_usd, 0), 2) AS net_benefit_per_loss_dollar,
    verdict_rule
FROM (
    SELECT
        v_params.scenario,
        'APR promo (0% for 12 months)' AS offer,
        -- cost: interest deferred 12 months on migrated balances (avg $2,500 assumed)
        10000 * takeup * 2500 * nim                                   AS promo_cost_usd,
        -- benefit: 65% of migrated balances retained post-promo x NIM x 2 years
        10000 * takeup * 2500 * 0.65 * nim * 2                        AS modeled_benefit_usd,
        -- guardrail: expected loss on migrated balances
        10000 * takeup * 2500 * loss_rate * 2                         AS exp_loss_delta_usd,
        'payback ~month 14; guardrail: loss rate <= +15bps'           AS verdict_rule
    FROM v_params
    UNION ALL
    SELECT
        v_params.scenario,
        'Cashback boost (+1% grocery, 6 months)'                      AS offer,
        -- cost: boosted rewards on the targeted spend base ($4,200/yr assumed)
        10000 * 4200 * cb_cost                                        AS promo_cost_usd,
        -- benefit: 12% incremental spend x (interchange net + carry on new spend)
        10000 * 4200 * 1.12 * (0.017 + 0.22 * nim)                    AS modeled_benefit_usd,
        -- guardrail: loss on incremental revolving share of new spend
        10000 * 4200 * 1.12 * 0.30 * loss_rate                        AS exp_loss_delta_usd,
        'payback ~month 6; guardrail: rewards cost <= 1.6% of spend'  AS verdict_rule
    FROM v_params
) offers
ORDER BY offer, CASE scenario WHEN 'low' THEN 1 WHEN 'base' THEN 2 ELSE 3 END;

-- ---------------------------------------------------------------------
-- §3. Credit-line increase sensitivity (Q1's recommendation, quantified)
-- Eligible base from segmentation.sql; scenarios vary the three key drivers.
-- ---------------------------------------------------------------------
WITH eligible AS (
    SELECT COUNT(*) AS n, AVG(credit_line_usd) AS avg_line
    FROM accounts
    WHERE account_id IN (
        SELECT account_id FROM v_behavioral_segment
        WHERE segment = 'S2_revolver_headroom'
          AND stat_month = (SELECT MAX(stat_month) FROM account_months)
    )
)
SELECT
    v_params.scenario,
    eligible.n                                                        AS eligible_accounts,
    ROUND(eligible.n * eligible.avg_line * 0.20 * draw_pct, 0)        AS incremental_exposure_usd, -- +20% line
    ROUND(eligible.n * eligible.avg_line * 0.20 * draw_pct
          * revolve_pct * nim, 0)                                     AS modeled_margin_uplift_usd,
    ROUND(eligible.n * eligible.avg_line * 0.20 * draw_pct
          * loss_rate, 0)                                             AS exp_loss_delta_usd,
    ROUND((eligible.n * eligible.avg_line * 0.20 * draw_pct * revolve_pct * nim)
          / NULLIF(eligible.n * eligible.avg_line * 0.20 * draw_pct * loss_rate, 0), 2)
                                                                      AS margin_per_loss_dollar,
    'ship only if risk signs off on the loss guardrail'                AS decision_rule
FROM v_params, eligible
ORDER BY CASE v_params.scenario WHEN 'low' THEN 1 WHEN 'base' THEN 2 ELSE 3 END;

-- ---------------------------------------------------------------------
-- §4. Fairness audit (mandatory before recommending any targeting)
-- Compare eligibility rates ACROSS protected-class cuts; if the min/max
-- ratio < 0.80 (four-fifths rule), stop and escalate to legal/compliance.
-- These dimensions are audit-only — never targeting inputs (case-brief §6).
-- ---------------------------------------------------------------------
SELECT
    a.age_band,
    a.region,
    COUNT(*)                                                          AS accounts,
    AVG(CASE WHEN am.utilization_pct BETWEEN 30 AND 85
              AND am.days_past_due = 0 THEN 1.0 ELSE 0 END)           AS eligible_rate
FROM account_months am
JOIN accounts a USING (account_id)
WHERE am.stat_month = (SELECT MAX(stat_month) FROM account_months)
GROUP BY 1, 2
ORDER BY 1, 2;
