-- =====================================================================
-- schema_real.sql — schema for the REAL UCI credit-card dataset.
--
-- Source: Yeh, I. (2009). Default of Credit Card Clients [Dataset].
--         UCI Machine Learning Repository. https://doi.org/10.24432/C55S3H
-- License: CC BY 4.0 (attribution required — see NOTICE.md)
--
-- Differences from the synthetic schema (sql/schema.sql):
--   * accounts carries the source's real demographic + outcome fields,
--     used for AUDIT ONLY (never as targeting inputs)
--   * expected_loss_usd for defaulted clients reflects the REAL observed
--     default outcome rather than a modeled probability
-- =====================================================================

DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS account_months;
DROP TABLE IF EXISTS offer_exposures;
DROP TABLE IF EXISTS marketing_spend;
DROP VIEW  IF EXISTS v_account_margin;
DROP VIEW  IF EXISTS v_behavioral_segment;
DROP VIEW  IF EXISTS v_assumptions;
DROP VIEW  IF EXISTS v_params;

CREATE TABLE accounts (
    account_id            VARCHAR PRIMARY KEY,
    open_date             DATE NOT NULL,
    acquisition_channel   VARCHAR NOT NULL,
    region                VARCHAR NOT NULL,
    age_band              VARCHAR NOT NULL,      -- AUDIT ONLY
    credit_line_usd       DECIMAL(12,2) NOT NULL,
    apr_tier              VARCHAR NOT NULL,
    fee_tier              VARCHAR NOT NULL,
    premium_member        BOOLEAN NOT NULL,
    origination_risk_band VARCHAR NOT NULL,      -- derived from real PAY_0 status
    credit_score_band     VARCHAR NOT NULL,
    -- Real dataset extras (audit only; never targeting inputs)
    source_sex_code       INTEGER,
    source_education      VARCHAR,
    source_marriage       VARCHAR,
    source_age            INTEGER,
    defaulted_next_month  INTEGER               -- the REAL observed outcome
);

CREATE TABLE account_months (
    account_id            VARCHAR NOT NULL,
    stat_month            DATE NOT NULL,
    is_active             BOOLEAN NOT NULL,
    purchases_usd         DECIMAL(12,2) NOT NULL DEFAULT 0,
    payments_usd          DECIMAL(12,2) NOT NULL DEFAULT 0,
    avg_daily_balance_usd DECIMAL(12,2) NOT NULL DEFAULT 0,
    revolve_balance_usd   DECIMAL(12,2) NOT NULL DEFAULT 0,
    utilization_pct       DECIMAL(5,2)  NOT NULL DEFAULT 0,
    interest_charged_usd  DECIMAL(12,2) NOT NULL DEFAULT 0,
    interchange_rev_usd   DECIMAL(12,2) NOT NULL DEFAULT 0,
    fee_rev_usd           DECIMAL(12,2) NOT NULL DEFAULT 0,
    promo_cost_usd        DECIMAL(12,2) NOT NULL DEFAULT 0,
    funding_cost_usd      DECIMAL(12,2) NOT NULL DEFAULT 0,
    days_past_due         INTEGER NOT NULL DEFAULT 0,
    expected_loss_usd     DECIMAL(12,2) NOT NULL DEFAULT 0,
    chargeoff_usd         DECIMAL(12,2) NOT NULL DEFAULT 0,
    risk_band             VARCHAR NOT NULL,
    PRIMARY KEY (account_id, stat_month)
);

-- Kept for schema compatibility (the real source has neither)
CREATE TABLE offer_exposures (
    offer_id    VARCHAR,
    account_id  VARCHAR,
    offer_type  VARCHAR,
    offer_value VARCHAR,
    exposed_at  DATE,
    channel     VARCHAR,
    in_holdout  BOOLEAN
);

CREATE TABLE marketing_spend (
    stat_month   DATE,
    channel      VARCHAR,
    spend_usd    DECIMAL(12,2),
    new_accounts INTEGER
);

CREATE OR REPLACE VIEW v_account_margin AS
SELECT
    am.account_id, am.stat_month, a.acquisition_channel, a.origination_risk_band,
    a.premium_member, am.is_active, am.purchases_usd, am.revolve_balance_usd,
    am.utilization_pct,
    (am.interest_charged_usd + am.interchange_rev_usd + am.fee_rev_usd) AS revenue_usd,
    am.expected_loss_usd,
    (am.interest_charged_usd + am.interchange_rev_usd + am.fee_rev_usd
        - am.promo_cost_usd - am.expected_loss_usd - am.funding_cost_usd) AS contribution_margin_usd
FROM account_months am
JOIN accounts a USING (account_id);
