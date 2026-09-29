-- =====================================================================
-- real_analysis.sql — analytics over the REAL UCI credit-card dataset
--
-- Same analytical questions as the synthetic pack, adapted to what this
-- dataset actually supports. Read alongside docs/real-data-findings.md.
--
-- Key difference from synthetic: we have REAL default outcomes, so we can
-- measure observed risk directly instead of modeling it.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Q0. Expected-loss rate — the "denominator" question, answered explicitly.
-- Only 12.8% of this dataset's account-months carry a balance, so a loss rate
-- expressed against revolve_balance excludes ~87% of the book and overstates.
-- The comparable headline figure uses TOTAL exposure (avg_daily_balance).
-- Both are shown so the choice is visible rather than hidden.
-- ---------------------------------------------------------------------
SELECT
    ROUND(SUM(expected_loss_usd), 0)                                        AS total_expected_loss,
    ROUND(SUM(revolve_balance_usd), 0)                                      AS carried_balance,
    ROUND(SUM(avg_daily_balance_usd), 0)                                    AS total_exposure,
    ROUND(100.0 * SUM(expected_loss_usd) / NULLIF(SUM(revolve_balance_usd), 0) * 12, 2)
                                                                            AS ann_rate_on_carried_pct,
    ROUND(100.0 * SUM(expected_loss_usd) / NULLIF(SUM(avg_daily_balance_usd), 0) * 12, 2)
                                                                            AS ann_rate_on_total_exposure_pct,
    ROUND(100.0 * AVG(CASE WHEN revolve_balance_usd > 0 THEN 1.0 ELSE 0.0 END), 1)
                                                                            AS pct_months_revolving
FROM account_months;

-- ---------------------------------------------------------------------
-- Q1. Observed risk by repayment status (the real, unmodeled signal)
-- The source's PAY_0 is the September 2005 repayment status:
--   <=0 paying duly; 1 = 1 month delayed; ... ; 8+ = 8+ months delayed.
-- ---------------------------------------------------------------------
SELECT
    a.origination_risk_band                          AS repayment_status,
    COUNT(DISTINCT a.account_id)                     AS clients,
    ROUND(100.0 * AVG(a.defaulted_next_month), 2)    AS observed_default_rate_pct,
    ROUND(AVG(a.credit_line_usd), 0)                 AS avg_credit_limit,
    ROUND(AVG(m.utilization_pct), 1)                 AS avg_utilization_pct,
    ROUND(100.0 * AVG(CASE WHEN m.days_past_due >= 30 THEN 1.0 ELSE 0.0 END), 1) AS dpd30_share_pct
FROM accounts a
JOIN account_months m ON m.account_id = a.account_id AND m.stat_month = '2005-09-01'
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------
-- Q2. Utilization bands vs observed default — is high utilization risky?
-- Tests the hypothesis I formed on synthetic data.
-- ---------------------------------------------------------------------
WITH sept AS (
    SELECT a.account_id, a.defaulted_next_month,
           m.utilization_pct,
           CASE
             WHEN m.utilization_pct = 0            THEN '0_zero'
             WHEN m.utilization_pct < 30           THEN '1_low_<30'
             WHEN m.utilization_pct < 70           THEN '2_mid_30-70'
             WHEN m.utilization_pct < 85           THEN '3_high_70-85'
             ELSE '4_maxed_85plus'
           END AS util_band
    FROM accounts a
    JOIN account_months m
      ON m.account_id = a.account_id AND m.stat_month = '2005-09-01'
)
SELECT
    util_band,
    COUNT(*)                                         AS clients,
    ROUND(100.0 * AVG(defaulted_next_month), 2)      AS observed_default_rate_pct
FROM sept
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------
-- Q3. Payment behavior vs default — does paying more reduce risk?
-- payment_ratio = amount paid / bill carried
-- ---------------------------------------------------------------------
WITH sept AS (
    SELECT a.account_id, a.defaulted_next_month,
           CASE WHEN m.avg_daily_balance_usd > 0
                THEN m.payments_usd / m.avg_daily_balance_usd END AS pay_ratio
    FROM accounts a
    JOIN account_months m
      ON m.account_id = a.account_id AND m.stat_month = '2005-09-01'
)
SELECT
    CASE
      WHEN pay_ratio IS NULL       THEN 'n/a_no_balance'
      WHEN pay_ratio = 0           THEN '0_no_payment'
      WHEN pay_ratio < 0.05        THEN '1_minimum_only'
      WHEN pay_ratio < 0.30        THEN '2_partial'
      WHEN pay_ratio < 1.0         THEN '3_most_of_bill'
      ELSE '4_paid_in_full'
    END                                              AS payment_behavior,
    COUNT(*)                                         AS clients,
    ROUND(100.0 * AVG(defaulted_next_month), 2)      AS observed_default_rate_pct
FROM sept
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------
-- Q4. Credit limit vs risk — do lower limits carry higher default risk?
-- Credit line is the closest thing this dataset has to a risk tier.
-- ---------------------------------------------------------------------
SELECT
    CASE
      WHEN a.credit_line_usd < 50000  THEN '1_<50k'
      WHEN a.credit_line_usd < 100000 THEN '2_50-100k'
      WHEN a.credit_line_usd < 200000 THEN '3_100-200k'
      WHEN a.credit_line_usd < 400000 THEN '4_200-400k'
      ELSE '5_400k+'
    END                                              AS limit_band,
    COUNT(*)                                         AS clients,
    ROUND(100.0 * AVG(a.defaulted_next_month), 2)    AS observed_default_rate_pct,
    ROUND(AVG(m.utilization_pct), 1)                 AS avg_utilization_pct
FROM accounts a
JOIN account_months m ON m.account_id = a.account_id AND m.stat_month = '2005-09-01'
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------
-- Q5. Delinquency trend across the six months (the real panel payoff)
-- Share of clients delinquent in each statement month.
-- ---------------------------------------------------------------------
SELECT
    m.stat_month,
    COUNT(*)                                         AS clients,
    ROUND(100.0 * AVG(CASE WHEN m.days_past_due >= 30 THEN 1.0 ELSE 0.0 END), 2) AS delinquent_share_pct,
    ROUND(SUM(m.revolve_balance_usd) / 1e6, 1)       AS carried_balance_millions,
    ROUND(AVG(m.utilization_pct), 1)                 AS avg_utilization_pct
FROM account_months m
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------
-- Q6. Expected-loss concentration — where does portfolio risk actually sit?
-- Classic credit insight: a small share of accounts drives most of the loss.
-- ---------------------------------------------------------------------
WITH scored AS (
    SELECT a.account_id, a.defaulted_next_month,
           m.expected_loss_usd,
           ROW_NUMBER() OVER (ORDER BY m.expected_loss_usd DESC) AS rn,
           COUNT(*) OVER () AS total
    FROM accounts a
    JOIN account_months m ON m.account_id = a.account_id AND m.stat_month = '2005-09-01'
),
totals AS (
    SELECT SUM(expected_loss_usd) AS total_el FROM scored
)
SELECT
    'Top 10% of accounts'  AS segment,
    ROUND(100.0 * SUM(CASE WHEN rn <= total * 0.10 THEN expected_loss_usd END)
          / MAX(t.total_el), 1)                      AS share_of_expected_loss_pct
FROM scored, totals t
UNION ALL
SELECT
    'Top 20% of accounts',
    ROUND(100.0 * SUM(CASE WHEN rn <= total * 0.20 THEN expected_loss_usd END)
          / MAX(t.total_el), 1)
FROM scored, totals t
UNION ALL
SELECT
    'Bottom 50% of accounts',
    ROUND(100.0 * SUM(CASE WHEN rn > total * 0.50 THEN expected_loss_usd END)
          / MAX(t.total_el), 1)
FROM scored, totals t;

-- ---------------------------------------------------------------------
-- Q7. FAIRNESS AUDIT (audit only — these are never targeting inputs)
-- Observed default rates across the source's demographic fields. In a real
-- credit setting, materially different rates here require legal review
-- before any model using these fields could be deployed.
-- ---------------------------------------------------------------------
SELECT
    a.source_sex_code                                AS sex_code,
    a.source_education                               AS education,
    COUNT(*)                                         AS clients,
    ROUND(100.0 * AVG(a.defaulted_next_month), 2)    AS observed_default_rate_pct,
    ROUND(AVG(a.credit_line_usd), 0)                 AS avg_credit_limit
FROM accounts a
GROUP BY 1, 2
ORDER BY 1, 2;

-- ---------------------------------------------------------------------
-- Q8. Age-band audit (same purpose as Q7)
-- ---------------------------------------------------------------------
SELECT
    a.age_band,
    COUNT(*)                                         AS clients,
    ROUND(100.0 * AVG(a.defaulted_next_month), 2)    AS observed_default_rate_pct,
    ROUND(AVG(a.credit_line_usd), 0)                 AS avg_credit_limit,
    ROUND(AVG(m.utilization_pct), 1)                 AS avg_utilization_pct
FROM accounts a
JOIN account_months m ON m.account_id = a.account_id AND m.stat_month = '2005-09-01'
GROUP BY 1
ORDER BY 1;
