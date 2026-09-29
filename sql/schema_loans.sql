-- =====================================================================
-- schema_loans.sql — schema for the LendingClub loan-level dataset
--
-- Source: LendingClub public loan performance files
-- Grain: one row per loan, lifetime performance to the file's snapshot date.
-- =====================================================================

DROP TABLE IF EXISTS loans;

CREATE TABLE loans (
    loan_id              VARCHAR PRIMARY KEY,
    loan_amnt            DECIMAL(12,2) NOT NULL,
    term_months          INTEGER,                 -- 36 or 60
    int_rate             DECIMAL(8,6),            -- stored as a fraction (0.0774 = 7.74%)
    grade                VARCHAR,                 -- assigned risk grade A..G
    sub_grade            VARCHAR,
    purpose              VARCHAR,
    home_ownership       VARCHAR,
    annual_inc           DECIMAL(14,2),
    dti                  DECIMAL(8,2),
    pub_rec              INTEGER,                 -- derogatory public records
    delinq_2yrs          INTEGER,                 -- delinquencies in past 2 years
    inq_last_6mths       INTEGER,                 -- credit inquiries, last 6 months
    revol_util           DECIMAL(8,6),            -- revolving utilization (fraction)
    emp_length           VARCHAR,
    verification_status  VARCHAR,
    addr_state           VARCHAR,
    issue_month          DATE,
    loan_status          VARCHAR,
    -- Outcome flags. is_resolved is the gate for every risk rate in the analysis.
    is_resolved          BOOLEAN NOT NULL,
    is_charged_off       BOOLEAN NOT NULL,
    is_fully_paid        BOOLEAN NOT NULL,
    -- Cash flows
    outstanding_principal DECIMAL(12,2),
    principal_received   DECIMAL(12,2),
    interest_received    DECIMAL(12,2),
    late_fees_received   DECIMAL(12,2),
    recoveries           DECIMAL(12,2),
    collection_fees      DECIMAL(12,2),
    -- Derived economics
    principal_lost       DECIMAL(12,2),           -- written-off principal (charged-off only)
    net_profit           DECIMAL(12,2)            -- interest + fees + recoveries - losses - collection costs
);

-- Convenience view: resolved loans with the economics already assembled.
CREATE OR REPLACE VIEW v_resolved_loans AS
SELECT
    l.*,
    (interest_received + late_fees_received + recoveries - collection_fees) AS gross_revenue,
    (loan_amnt - principal_lost)                                            AS principal_at_work
FROM loans l
WHERE is_resolved;
