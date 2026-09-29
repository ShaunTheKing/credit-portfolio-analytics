-- =====================================================================
-- segmentation.sql — behavioral segments + economics per segment (Q1)
-- Segments are BEHAVIORAL by design (case-brief §6 fairness guardrails):
-- never segment on age_band/region; those appear only in the fairness audit.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Step 1: assign each account-month a behavioral segment from trailing 3-month behavior
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_behavioral_segment AS
WITH base AS (
    SELECT
        account_id,
        stat_month,
        is_active::INT                        AS active_flag,
        revolve_balance_usd,
        utilization_pct,
        days_past_due,
        (interest_charged_usd + interchange_rev_usd + fee_rev_usd
            - promo_cost_usd - expected_loss_usd - funding_cost_usd) AS margin_usd
    FROM account_months
),
-- True trailing 3-month window: average behavior over the current month
-- and the two prior months, so a segment reflects recent behavior rather
-- than an account's entire history. (Index-based window keeps it simple
-- and avoids gaps when an account has missing months.)
roll3 AS (
    SELECT
        account_id,
        stat_month,
        AVG(active_flag)        OVER w AS active_rate_3m,
        AVG(revolve_balance_usd) OVER w AS revolve_avg_3m,
        AVG(utilization_pct)    OVER w AS util_avg_3m,
        MAX(days_past_due)      OVER w AS max_dpd_3m,
        AVG(margin_usd)         OVER w AS margin_avg_3m
    FROM base
    WINDOW w AS (
        PARTITION BY account_id
        ORDER BY stat_month
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    )
)
SELECT
    account_id,
    stat_month,
    active_rate_3m,
    revolve_avg_3m,
    util_avg_3m,
    max_dpd_3m,
    margin_avg_3m,
    CASE
        WHEN max_dpd_3m >= 30                                  THEN 'S5_delinquent'
        WHEN active_rate_3m = 0                                THEN 'S4_dormant'
        WHEN util_avg_3m >= 85                                 THEN 'S3_maxed_out'
        WHEN util_avg_3m >= 30 AND revolve_avg_3m > 0          THEN 'S2_revolver_headroom'
        WHEN revolve_avg_3m > 0                                THEN 'S1_light_revolver'
        ELSE 'S0_transactor'                                     -- active, pays in full
    END AS segment
FROM roll3;

-- ---------------------------------------------------------------------
-- Step 2: segment economics — the heatmap row for the memo
-- Interpretation guide: high margin + controlled loss = growth audience;
-- high revenue + high expected loss = watchlist, not target.
-- ---------------------------------------------------------------------
SELECT
    vs.segment,
    COUNT(DISTINCT vs.account_id)                                          AS accounts,
    AVG(m.purchases_usd)                                                   AS purchases_per_acct,
    AVG(m.revolve_balance_usd)                                             AS revolve_per_acct,
    SUM(m.interest_charged_usd + m.interchange_rev_usd + m.fee_rev_usd)
        / COUNT(*)                                                         AS revenue_per_acct,
    SUM(m.expected_loss_usd) / COUNT(*)                                    AS exp_loss_per_acct,
    SUM(m.interest_charged_usd + m.interchange_rev_usd + m.fee_rev_usd
        - m.promo_cost_usd - m.expected_loss_usd - m.funding_cost_usd)
        / COUNT(*)                                                         AS margin_per_acct,
    AVG(CASE WHEN m.days_past_due >= 30 THEN 1.0 ELSE 0.0 END)             AS dpd30_rate
FROM v_behavioral_segment vs
JOIN account_months m
    ON m.account_id = vs.account_id
   AND m.stat_month = vs.stat_month
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------
-- Step 3: line-increase opportunity ranking (risk-return trade-off)
-- Signal: utilization 30-85% (headroom demand) + clean payment history
-- + positive margin. Eligibility is a BUSINESS rule; the model ranks, humans decide.
-- ---------------------------------------------------------------------
WITH eligibility AS (
    SELECT
        vs.account_id,
        vs.segment,
        a.credit_line_usd,
        vs.util_avg_3m,
        vs.margin_avg_3m,
        m.expected_loss_usd AS latest_expected_loss,
        CASE WHEN vs.max_dpd_3m = 0 AND vs.margin_avg_3m > 0
              AND vs.util_avg_3m BETWEEN 30 AND 85
             THEN TRUE ELSE FALSE END AS eligible
    FROM v_behavioral_segment vs
    JOIN accounts a   USING (account_id)
    JOIN account_months m
      ON m.account_id = vs.account_id
     AND m.stat_month = vs.stat_month
    WHERE vs.stat_month = (SELECT MAX(stat_month) FROM account_months)
)
SELECT
    segment,
    COUNT(*) FILTER (WHERE eligible)                                    AS eligible_accounts,
    -- modeled uplift: eligible accounts draw down ~18% of the added line at
    -- revolve rates per assumptions table (see pricing_sensitivity.sql §1)
    ROUND(SUM(CASE WHEN eligible
                   THEN credit_line_usd * 0.18 * 0.22 * 0.20 END), 0)  AS modeled_margin_uplift_usd,
    ROUND(AVG(CASE WHEN eligible THEN latest_expected_loss END), 2)     AS avg_exp_loss_usd,
    -- fair-lending audit cut (guardrail, not a targeting input):
    -- run the same eligibility rate by age_band / region and report min/max ratio
    'audited separately'                                                AS fairness_check
FROM eligibility
GROUP BY 1
ORDER BY 2 DESC;
