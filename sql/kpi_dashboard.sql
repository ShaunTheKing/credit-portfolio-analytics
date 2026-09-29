-- =====================================================================
-- kpi_dashboard.sql — monthly KPI pack (backing query for the dashboard)
-- Definitions: docs/metrics-playbook.md §2. Every metric is named after
-- its playbook row so a reviewer can audit in one hop.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Q1. Monthly portfolio KPIs (the top of the dashboard)
-- ---------------------------------------------------------------------
WITH monthly AS (
    SELECT
        stat_month,
        COUNT(*)                                                        AS accounts,
        SUM(CASE WHEN is_active THEN 1 ELSE 0 END)                      AS active_accounts,
        -- spend per active account (metric: Spend per active account)
        SUM(purchases_usd) / NULLIF(SUM(CASE WHEN is_active THEN 1 ELSE 0 END), 0)
                                                                        AS spend_per_active,
        -- revolve rate (metric: Revolve rate)
        AVG(CASE WHEN revolve_balance_usd > 0 THEN 1.0 ELSE 0 END)      AS revolve_rate,
        -- utilization: report median via percentile in BI tool; mean shown here
        AVG(utilization_pct)                                            AS util_mean,
        -- revenue per account (metric: Revenue / account)
        SUM(interest_charged_usd + interchange_rev_usd + fee_rev_usd)
            / COUNT(*)                                                  AS revenue_per_account,
        -- Expected-loss rate. Denominator = CARRIED balance (revolve), not average
        -- daily balance: transactor float is never at risk of credit loss, so
        -- including it would understate the loss rate by roughly half.
        SUM(expected_loss_usd)
            / NULLIF(SUM(revolve_balance_usd), 0)                       AS expected_loss_rate,
        -- contribution margin per account (metric: Contribution margin / account)
        SUM(interest_charged_usd + interchange_rev_usd + fee_rev_usd
            - promo_cost_usd - expected_loss_usd - funding_cost_usd)
            / COUNT(*)                                                  AS margin_per_account,
        -- early risk signal (metric: 30+ DPD rate)
        AVG(CASE WHEN days_past_due >= 30 THEN 1.0 ELSE 0 END)          AS dpd30_rate
    FROM account_months
    GROUP BY stat_month
)
SELECT
    stat_month,
    accounts,
    active_accounts,
    ROUND(spend_per_active, 2)                                          AS spend_per_active_usd,
    ROUND(100.0 * revolve_rate, 1)                                      AS revolve_rate_pct,
    ROUND(util_mean, 1)                                                 AS util_pct_mean,
    ROUND(revenue_per_account, 2)                                       AS revenue_per_acct_usd,
    ROUND(100.0 * expected_loss_rate, 2)                                AS expected_loss_rate_pct,
    ROUND(margin_per_account, 2)                                        AS margin_per_acct_usd,
    ROUND(100.0 * dpd30_rate, 1)                                        AS dpd30_rate_pct,
    -- YoY comparisons (seasonality: Nov-Dec spend lift, Jan payments surge)
    ROUND(revenue_per_account
        - LAG(revenue_per_account, 12) OVER (ORDER BY stat_month), 2)   AS revenue_yoy_delta_usd
FROM monthly
ORDER BY stat_month;

-- ---------------------------------------------------------------------
-- Q2. Vintage x channel cohort table (metric: Activation rate, CAC, CLV-2)
-- Rule: only compare same-maturity vintages (activation uses 30-day window).
-- ---------------------------------------------------------------------
SELECT
    a.open_date AS vintage_month,                    -- DATE_TRUNC('month', a.open_date) in Postgres
    a.acquisition_channel,
    COUNT(*)                                                                    AS new_accounts,
    -- activation: first statement month with purchases > 0
    AVG(CASE WHEN am.purchases_usd > 0 THEN 1.0 ELSE 0 END)                     AS activation_rate_30d,
    -- CAC (metric: CAC)
    MAX(ms.spend_usd) / NULLIF(COUNT(*), 0)                                     AS cac_usd,
    -- first-year contribution margin per new account (CLV proxy)
    SUM(am.interest_charged_usd + am.interchange_rev_usd + am.fee_rev_usd
        - am.promo_cost_usd - am.expected_loss_usd - am.funding_cost_usd)
        / COUNT(*)                                                              AS cm_per_new_acct_12m_usd
FROM accounts a
JOIN account_months am
    ON am.account_id = a.account_id
   AND am.stat_month < a.open_date + INTERVAL '12 months'
LEFT JOIN marketing_spend ms
    ON ms.channel = a.acquisition_channel
   AND ms.stat_month = a.open_date
GROUP BY 1, 2
ORDER BY 1, 2;

-- ---------------------------------------------------------------------
-- Q3. Risk trend: early delinquency by vintage (metric: 30+ DPD / roll view)
-- Early-DPD in the first 3 statements predicts charge-offs; watch vintages, not just levels.
-- ---------------------------------------------------------------------
SELECT
    a.open_date                                                        AS vintage_month,
    a.origination_risk_band,
    COUNT(DISTINCT a.account_id)                                       AS accounts,
    AVG(CASE WHEN am.days_past_due >= 30 THEN 1.0 ELSE 0 END)          AS dpd30_rate,
    SUM(am.chargeoff_usd) / NULLIF(SUM(am.revolve_balance_usd), 0)      AS chargeoff_rate
FROM accounts a
JOIN account_months am
    ON am.account_id = a.account_id
   AND am.stat_month < a.open_date + INTERVAL '12 months'
GROUP BY 1, 2
ORDER BY 1, 2;
