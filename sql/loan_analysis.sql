-- =====================================================================
-- loan_analysis.sql — profitability and pricing analysis of LendingClub loans
--
-- Source: LendingClub public loan performance files (see NOTICE.md)
-- Grain: one row per loan, with lifetime performance to the file's snapshot date.
--
-- THE CENTRAL CAVEAT, enforced throughout:
--   ~11% of loans are still open. A charge-off rate computed over ALL loans is
--   wrong because it dilutes the denominator with loans that have not had time to
--   resolve. Every risk rate below is restricted to RESOLVED loans
--   (Fully Paid + Charged Off + Default). The naive figure is shown once in Q0
--   so the size of the error is visible rather than hidden.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Q0. The denominator trap, quantified.
-- Same portfolio, two defensible-looking answers, ~13% apart in relative terms.
-- ---------------------------------------------------------------------
SELECT
    COUNT(*)                                                          AS all_loans,
    SUM(CASE WHEN is_resolved THEN 1 ELSE 0 END)                      AS resolved_loans,
    SUM(CASE WHEN NOT is_resolved THEN 1 ELSE 0 END)                  AS open_loans,
    ROUND(100.0 * AVG(is_charged_off::INT), 2)                        AS chargeoff_rate_all_pct,
    ROUND(100.0 * AVG(CASE WHEN is_resolved THEN is_charged_off::INT END), 2)
                                                                      AS chargeoff_rate_resolved_pct
FROM loans;

-- ---------------------------------------------------------------------
-- Q1. Portfolio profit and loss (resolved loans only)
-- Interest collected vs principal written off — the economics in one row.
-- ---------------------------------------------------------------------
SELECT
    COUNT(*)                                                          AS loans,
    ROUND(SUM(loan_amnt) / 1e6, 1)                                    AS principal_millions,
    ROUND(SUM(interest_received) / 1e6, 1)                            AS interest_millions,
    ROUND(SUM(principal_lost) / 1e6, 1)                               AS principal_lost_millions,
    ROUND(SUM(recoveries) / 1e6, 1)                                   AS recoveries_millions,
    ROUND(SUM(net_profit) / 1e6, 1)                                   AS net_profit_millions,
    ROUND(100.0 * SUM(net_profit) / SUM(loan_amnt), 2)                AS return_on_principal_pct,
    -- Recovery effectiveness: how much of written-off principal came back
    ROUND(100.0 * SUM(recoveries) / NULLIF(SUM(principal_lost), 0), 1) AS recovery_rate_pct
FROM loans
WHERE is_resolved;

-- ---------------------------------------------------------------------
-- Q2. Risk-based pricing: does a higher rate actually pay for the risk?
-- THE headline question. If ROI rises with grade, pricing is working; if it
-- falls, the lender is underpricing risk.
-- ---------------------------------------------------------------------
SELECT
    grade,
    COUNT(*)                                                          AS loans,
    ROUND(AVG(int_rate) * 100, 1)                                     AS avg_rate_pct,
    ROUND(100.0 * AVG(is_charged_off::INT), 2)                        AS chargeoff_rate_pct,
    ROUND(100.0 * SUM(net_profit) / SUM(loan_amnt), 2)                AS roi_pct,
    -- Loss given default: the share of principal never recovered on a bad loan
    ROUND(100.0 * SUM(principal_lost) / NULLIF(SUM(CASE WHEN is_charged_off
          THEN loan_amnt ELSE 0 END), 0), 1)                          AS lgd_pct
FROM loans
WHERE is_resolved
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------
-- Q3. The pricing breakdown: risk-based pricing works at 36 months, not at 60.
-- Splitting by term exposes what the pooled view hides — longer exposure lets
-- defaults accumulate before the extra interest is collected.
-- ---------------------------------------------------------------------
SELECT
    term_months,
    grade,
    COUNT(*)                                                          AS loans,
    ROUND(AVG(int_rate) * 100, 1)                                     AS avg_rate_pct,
    ROUND(100.0 * AVG(is_charged_off::INT), 2)                        AS chargeoff_rate_pct,
    ROUND(100.0 * SUM(net_profit) / SUM(loan_amnt), 2)                AS roi_pct
FROM loans
WHERE is_resolved AND grade IN ('A', 'B', 'C', 'D', 'E')
GROUP BY 1, 2
ORDER BY 1, 2;

-- ---------------------------------------------------------------------
-- Q4. Where the risk concentrates.
-- IMPORTANT: 86.7% of resolved loans have ZERO loss (they paid in full), so
-- "top 10% by loss" is really "the largest loss-making loans" — every one of
-- them a charged-off loan. Two complementary framings are given, plus the
-- base rates needed to read them honestly.
-- ---------------------------------------------------------------------
WITH ranked AS (
    SELECT loan_id, principal_lost, is_charged_off,
           ROW_NUMBER() OVER (ORDER BY principal_lost DESC) AS rn,
           COUNT(*) OVER () AS n
    FROM loans WHERE is_resolved
)
SELECT
    (SELECT COUNT(*) FROM loans WHERE is_resolved)                    AS resolved_loans,
    (SELECT COUNT(*) FROM loans WHERE is_resolved AND principal_lost = 0)
                                                                      AS loans_with_zero_loss,
    ROUND(100.0 * (SELECT AVG(CASE WHEN principal_lost = 0 THEN 1.0 ELSE 0.0 END)
                   FROM loans WHERE is_resolved), 1)                  AS pct_zero_loss,
    ROUND(100.0 * SUM(CASE WHEN rn <= n * 0.01 THEN principal_lost END)
          / SUM(principal_lost), 1)                                   AS top1pct_share_of_losses,
    ROUND(100.0 * SUM(CASE WHEN rn <= n * 0.05 THEN principal_lost END)
          / SUM(principal_lost), 1)                                   AS top5pct_share_of_losses,
    ROUND(100.0 * SUM(CASE WHEN rn <= n * 0.10 THEN principal_lost END)
          / SUM(principal_lost), 1)                                   AS top10pct_share_of_losses
FROM ranked;

-- ---------------------------------------------------------------------
-- Q5. Purpose-level performance — which loan purposes pay for themselves?
-- ---------------------------------------------------------------------
SELECT
    purpose,
    COUNT(*)                                                          AS loans,
    ROUND(AVG(int_rate) * 100, 1)                                     AS avg_rate_pct,
    ROUND(100.0 * AVG(is_charged_off::INT), 2)                        AS chargeoff_rate_pct,
    ROUND(100.0 * SUM(net_profit) / SUM(loan_amnt), 2)                AS roi_pct
FROM loans
WHERE is_resolved
GROUP BY 1
HAVING COUNT(*) >= 500          -- suppress noise from thin categories
ORDER BY roi_pct DESC;

-- ---------------------------------------------------------------------
-- Q6. Default by loan size — do larger loans carry different risk?
-- ---------------------------------------------------------------------
SELECT
    CASE
      WHEN loan_amnt < 5000  THEN '1_<5k'
      WHEN loan_amnt < 10000 THEN '2_5-10k'
      WHEN loan_amnt < 20000 THEN '3_10-20k'
      WHEN loan_amnt < 30000 THEN '4_20-30k'
      ELSE '5_30k+'
    END                                                               AS size_band,
    COUNT(*)                                                          AS loans,
    ROUND(100.0 * AVG(is_charged_off::INT), 2)                        AS chargeoff_rate_pct,
    ROUND(100.0 * SUM(net_profit) / SUM(loan_amnt), 2)                AS roi_pct
FROM loans
WHERE is_resolved
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------
-- Q7. Credit-quality signals available in this vintage (no FICO fields).
-- Public records and recent delinquencies should separate risk.
-- ---------------------------------------------------------------------
SELECT
    CASE
      WHEN pub_rec > 0 OR delinq_2yrs > 0 THEN 'prior_derogatory'
      WHEN inq_last_6mths >= 3            THEN 'high_recent_inquiries'
      ELSE 'clean'
    END                                                               AS credit_signal,
    COUNT(*)                                                          AS loans,
    ROUND(100.0 * AVG(is_charged_off::INT), 2)                        AS chargeoff_rate_pct,
    ROUND(100.0 * SUM(net_profit) / SUM(loan_amnt), 2)                AS roi_pct
FROM loans
WHERE is_resolved
GROUP BY 1
ORDER BY chargeoff_rate_pct DESC;

-- ---------------------------------------------------------------------
-- Q8. Geographic concentration — state-level risk and return.
-- NOTE: geography correlates with state lending law and borrower mix; this is
-- a monitoring view, not a targeting recommendation.
-- ---------------------------------------------------------------------
SELECT
    addr_state,
    COUNT(*)                                                          AS loans,
    ROUND(100.0 * AVG(is_charged_off::INT), 2)                        AS chargeoff_rate_pct,
    ROUND(100.0 * SUM(net_profit) / SUM(loan_amnt), 2)                AS roi_pct
FROM loans
WHERE is_resolved
GROUP BY 1
HAVING COUNT(*) >= 1000
ORDER BY roi_pct ASC
LIMIT 10;
