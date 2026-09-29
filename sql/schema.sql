-- =====================================================================
-- schema.sql — Halo Card synthetic portfolio (DuckDB / Postgres compatible)
-- Grain reminder (say it out loud): accounts = 1 row per account,
-- account_months = 1 row per account per statement month.
-- =====================================================================

CREATE TABLE IF NOT EXISTS accounts (
    account_id            VARCHAR PRIMARY KEY,
    open_date             DATE NOT NULL,
    acquisition_channel   VARCHAR NOT NULL,      -- paid_search | affiliate | in_app | referral | partner
    region                VARCHAR NOT NULL,      -- fairness audit only, NOT a targeting input
    age_band              VARCHAR NOT NULL,      -- fairness audit only, NOT a targeting input
    credit_line_usd       DECIMAL(12,2) NOT NULL,
    apr_tier              VARCHAR NOT NULL,      -- promo_0 | low_15 | standard_22 | high_29
    fee_tier              VARCHAR NOT NULL,      -- none | basic_25 | premium_60
    premium_member        BOOLEAN NOT NULL,
    origination_risk_band VARCHAR NOT NULL,      -- A (best) .. E
    credit_score_band     VARCHAR NOT NULL       -- thin_file | fair | good | excellent
);

CREATE TABLE IF NOT EXISTS account_months (
    account_id            VARCHAR NOT NULL,
    stat_month            DATE NOT NULL,         -- first day of statement month
    is_active             BOOLEAN NOT NULL,      -- purchases_usd > 0 this month
    purchases_usd         DECIMAL(12,2) NOT NULL DEFAULT 0,
    payments_usd          DECIMAL(12,2) NOT NULL DEFAULT 0,
    avg_daily_balance_usd DECIMAL(12,2) NOT NULL DEFAULT 0,
    revolve_balance_usd   DECIMAL(12,2) NOT NULL DEFAULT 0,
    utilization_pct       DECIMAL(5,2)  NOT NULL DEFAULT 0,   -- 0..120 (over-limit allowed)
    interest_charged_usd  DECIMAL(12,2) NOT NULL DEFAULT 0,
    interchange_rev_usd   DECIMAL(12,2) NOT NULL DEFAULT 0,   -- net of rewards cost
    fee_rev_usd           DECIMAL(12,2) NOT NULL DEFAULT 0,
    promo_cost_usd        DECIMAL(12,2) NOT NULL DEFAULT 0,
    funding_cost_usd      DECIMAL(12,2) NOT NULL DEFAULT 0,   -- avg balance x funds transfer rate
    days_past_due         INTEGER NOT NULL DEFAULT 0,
    expected_loss_usd     DECIMAL(12,2) NOT NULL DEFAULT 0,   -- risk-model output (PD x LGD x EAD)
    chargeoff_usd         DECIMAL(12,2) NOT NULL DEFAULT 0,
    risk_band             VARCHAR NOT NULL,                   -- current risk band (may migrate)
    PRIMARY KEY (account_id, stat_month)
);

CREATE TABLE IF NOT EXISTS offer_exposures (
    offer_id    VARCHAR PRIMARY KEY,
    account_id  VARCHAR NOT NULL,
    offer_type  VARCHAR NOT NULL,   -- line_increase | apr_promo | fee_waiver | cashback_boost | control
    offer_value VARCHAR NOT NULL,   -- e.g. '+$2000 line', '0% for 12 months', '5% grocery cashback'
    exposed_at  DATE NOT NULL,
    channel     VARCHAR NOT NULL,
    in_holdout  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS marketing_spend (
    stat_month   DATE NOT NULL,
    channel      VARCHAR NOT NULL,
    spend_usd    DECIMAL(12,2) NOT NULL,
    new_accounts INTEGER NOT NULL,
    PRIMARY KEY (stat_month, channel)
);

-- Analyst-friendly view: monthly contribution margin per account (see metrics-playbook §1)
CREATE OR REPLACE VIEW v_account_margin AS
SELECT
    am.account_id,
    am.stat_month,
    a.acquisition_channel,
    a.origination_risk_band,
    a.premium_member,
    am.is_active,
    am.purchases_usd,
    am.revolve_balance_usd,
    am.utilization_pct,
    (am.interest_charged_usd + am.interchange_rev_usd + am.fee_rev_usd) AS revenue_usd,
    am.expected_loss_usd,
    (am.interest_charged_usd + am.interchange_rev_usd + am.fee_rev_usd
        - am.promo_cost_usd - am.expected_loss_usd - am.funding_cost_usd) AS contribution_margin_usd
FROM account_months am
JOIN accounts a USING (account_id);
