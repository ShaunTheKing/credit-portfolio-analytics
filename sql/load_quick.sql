-- load.sql — load the generated CSVs into DuckDB (after sql/schema.sql)
-- Run:  duckdb credit.duckdb < sql/schema.sql && duckdb credit.duckdb < sql/load.sql

COPY accounts        FROM 'data/accounts.csv'        (HEADER, AUTO_DETECT TRUE);
COPY account_months  FROM 'data/account_months.csv'  (HEADER, AUTO_DETECT TRUE);
COPY offer_exposures FROM 'data/offer_exposures.csv' (HEADER, AUTO_DETECT TRUE);
COPY marketing_spend FROM 'data/marketing_spend.csv' (HEADER, AUTO_DETECT TRUE);

-- Row-count sanity check (record this in notes/calculations.md — see metrics-playbook §4)
SELECT 'accounts' AS table_name, COUNT(*) AS rows FROM accounts
UNION ALL SELECT 'account_months',  COUNT(*) FROM account_months
UNION ALL SELECT 'offer_exposures', COUNT(*) FROM offer_exposures
UNION ALL SELECT 'marketing_spend', COUNT(*) FROM marketing_spend;

-- QA: anti-join test — every account_month must have a parent account (expect 0)
SELECT COUNT(*) AS orphan_rows
FROM account_months am
LEFT JOIN accounts a USING (account_id)
WHERE a.account_id IS NULL;
