#!/usr/bin/env python3
"""
fetch_real_data.py — loads the UCI "Default of Credit Card Clients" dataset and
reshapes it into the same table structure the analytics SQL expects.

Dataset: Yeh, I. (2009). Default of Credit Card Clients [Dataset].
         UCI Machine Learning Repository. https://doi.org/10.24432/C55S3H
License: CC BY 4.0 — free to share and adapt with attribution (see NOTICE.md).
Content: 30,000 real credit-card clients (Taiwan, 2005), 23 features, and the
         actual "default payment next month" outcome.

Why this matters for the portfolio: the synthetic portfolio demonstrates I can
build a clean data model and reason about risk-return. This dataset adds what
synthetic data cannot — real default outcomes, real behavioral correlations,
and real data-quality problems (undocumented category codes, censored values).

Structure:
  The source is a WIDE table (one row per client, 6 months of columns).
  The analytics pack wants a LONG panel (account x month). We melt the six
  monthly bill/payment/status columns into 6 rows per client.

Output: data_real/ with the same four CSVs consumed by sql/load_real.sql
  accounts.csv, account_months.csv, offer_exposures.csv, marketing_spend.csv

Usage:
  python3 scripts/fetch_real_data.py                 # downloads from UCI
  python3 scripts/fetch_real_data.py --xls path.xls  # use a local copy
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import urllib.request
import zipfile

UCI_ZIP = "https://archive.ics.uci.edu/static/public/350/default+of+credit+card+clients.zip"
UCI_PAGE = "https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients"
CITATION = ("Yeh, I. (2009). Default of Credit Card Clients [Dataset]. "
            "UCI Machine Learning Repository. https://doi.org/10.24432/C55S3H")

# Source column order, in months-ago order (1 = most recent statement, Sept 2005)
BILL_COLS = ["BILL_AMT1", "BILL_AMT2", "BILL_AMT3", "BILL_AMT4", "BILL_AMT5", "BILL_AMT6"]
PAY_COLS = ["PAY_AMT1", "PAY_AMT2", "PAY_AMT3", "PAY_AMT4", "PAY_AMT5", "PAY_AMT6"]
STATUS_COLS = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]

# The source covers Apr-Sep 2005. Statement months are reconstructed as
# 2005-09 back through 2005-04 so the panel sorts correctly in SQL.
STATEMENT_MONTHS = ["2005-09-01", "2005-08-01", "2005-07-01",
                    "2005-06-01", "2005-05-01", "2005-04-01"]

# Documented category codes from the UCI variable table
EDUCATION = {1: "graduate", 2: "university", 3: "high_school", 4: "other",
             0: "undocumented", 5: "undocumented", 6: "undocumented"}
MARRIAGE = {1: "married", 2: "single", 3: "other", 0: "undocumented"}

# Assumptions required to map this dataset onto card economics.
# The source has no revenue, channel, or fee fields, so those must be modeled.
# Every assumption is stated here AND surfaced in the memo/report.
ASSUMPTIONS = {
    "interchange_rate": 0.017,      # net take rate on purchases
    "funding_rate_annual": 0.045,   # cost of funds on carried balance
    "apr_annual": 0.1999,           # representative card APR for interest revenue
    "lgd": 0.75,                    # loss given default on defaulted balance
    # Annual PD by delinquency depth, accrued monthly. Only 12.8% of this
    # dataset's account-months carry a balance, so a loss rate expressed
    # against revolve_balance (24.5%) excludes 87% of the book. The comparable
    # headline figure is loss against TOTAL exposure (avg_daily_balance) = 3.6%,
    # which is the number to quote and the one the memo uses.
    "pd_annual_by_dpd": {0: 0.012, 30: 0.12, 60: 0.25, 90: 0.40, 120: 0.60},
}
# Source has no acquisition channel; assign a documented synthetic split so the
# channel view remains usable, and label it clearly as modeled.
CHANNEL_SPLIT = [("undisclosed_source", 1.0)]


def download(dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    zip_path = os.path.join(dest_dir, "uci_credit_card.zip")
    if not os.path.exists(zip_path):
        print(f"  downloading {UCI_ZIP}")
        urllib.request.urlretrieve(UCI_ZIP, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    xls = os.path.join(dest_dir, "default of credit card clients.xls")
    if not os.path.exists(xls):
        for name in os.listdir(dest_dir):
            if name.lower().endswith(".xls"):
                xls = os.path.join(dest_dir, name)
                break
    return xls


def read_xls(path: str):
    try:
        import xlrd
    except ImportError:
        sys.exit("xlrd is required to read this .xls file:\n"
                 "  python3 -m pip install --target .tools/pylibs xlrd\n"
                 "  PYTHONPATH=.tools/pylibs python3 scripts/fetch_real_data.py")
    book = xlrd.open_workbook(path)
    sheet = book.sheet_by_index(0)
    header = [str(h).strip() for h in sheet.row_values(1)]  # row 0 is a title row
    rows = [sheet.row_values(r) for r in range(2, sheet.nrows)]
    return header, rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xls", help="path to a local .xls copy (skips download)")
    ap.add_argument("--out", default="data_real", help="output directory")
    ap.add_argument("--cache", default=".cache", help="download cache directory")
    args = ap.parse_args()

    xls = args.xls or download(args.cache)
    print(f"  reading {xls}")

    header, rows = read_xls(xls)
    idx = {name: i for i, name in enumerate(header)}
    for required in ["LIMIT_BAL", "BILL_AMT1", "PAY_AMT1", "PAY_0", "default payment next month"]:
        if required not in idx:
            sys.exit(f"unexpected schema: missing column {required!r}")

    os.makedirs(args.out, exist_ok=True)
    accounts, months, offers, spend = [], [], [], []

    for r in rows:
        client_id = int(r[idx["ID"]])
        account_id = f"UCI{client_id:06d}"
        limit = max(0.0, float(r[idx["LIMIT_BAL"]]))
        age = int(r[idx["AGE"]])
        sex = int(r[idx["SEX"]])
        edu = int(r[idx["EDUCATION"]])
        mar = int(r[idx["MARRIAGE"]])
        defaulted = int(float(r[idx["default payment next month"]]))

        # Risk band derived from the SOURCE's own delinquency status (PAY_0 =
        # September 2005 repayment status). This is an observed clinical signal,
        # not a modeled score: negative = paying duly, positive = months delayed.
        pay0 = float(r[idx["PAY_0"]])
        if pay0 <= 0:
            band = "A_current"
        elif pay0 == 1:
            band = "B_1mo_late"
        elif pay0 == 2:
            band = "C_2mo_late"
        elif pay0 <= 4:
            band = "D_3-4mo_late"
        else:
            band = "E_5mo_plus_late"

        # NOTE ON FAIRNESS: SEX / EDUCATION / MARRIAGE / AGE are present in the
        # real dataset. They are carried for AUDIT ONLY and are never used as
        # targeting inputs in the analysis — see sql/real_fairness.sql.
        accounts.append({
            "account_id": account_id,
            "open_date": "2005-04-01",
            "acquisition_channel": "undisclosed_source",
            "region": "Taiwan",
            "age_band": f"{(age // 10) * 10}s",
            "credit_line_usd": f"{limit:.2f}",
            "apr_tier": "standard_20",
            "fee_tier": "none",
            "premium_member": "false",
            "origination_risk_band": band,
            "credit_score_band": band,
            "source_sex_code": sex,
            "source_education": EDUCATION.get(edu, "undocumented"),
            "source_marriage": MARRIAGE.get(mar, "undocumented"),
            "source_age": age,
            "defaulted_next_month": defaulted,
        })

        for i, month in enumerate(STATEMENT_MONTHS):
            bill = float(r[idx[BILL_COLS[i]]])
            paid = float(r[idx[PAY_COLS[i]]])
            status = float(r[idx[STATUS_COLS[i]]])

            # Real-data semantics: bill amount is the statement balance carried.
            # Negative bills occur in the source (credit balances / refunds).
            carried = max(0.0, bill)
            # The source has no per-month purchase detail, so spend is only known
            # for the newest statement. "Active" therefore means the account had
            # activity this month: either a bill to carry or a payment made.
            # (Deriving activity from spend alone would mark 5 of 6 months inactive
            # and silently break any cross-month activity metric.)
            purchases = max(0.0, bill) if i == 0 else 0.0
            is_active = carried > 0 or paid > 0
            utilization = (carried / limit) if limit > 0 else 0.0
            utilization = min(utilization, 1.5)             # allow over-limit

            # Status -> days past due mapping (source is months-delayed buckets)
            if status <= 0:
                dpd = 0
            elif status == 1:
                dpd = 30
            elif status == 2:
                dpd = 60
            elif status <= 4:
                dpd = 90
            else:
                dpd = 120

            interest = carried * (ASSUMPTIONS["apr_annual"] / 12.0) if status > 0 else 0.0
            interchange = purchases * ASSUMPTIONS["interchange_rate"]
            funding = carried * (ASSUMPTIONS["funding_rate_annual"] / 12.0)

            # Loss fields must be CONSISTENT across months or any ratio over them
            # is meaningless. Two distinct concepts:
            #   expected_loss_usd : a monthly FLOW accrual for every month, based on
            #                       the delinquency status recorded IN THAT MONTH.
            #   chargeoff_usd     : a one-time STOCK event when the observed default
            #                       outcome actually lands (the source records the
            #                       outcome one month after the last statement).
            # Booking the real default as "expected loss" in September only would
            # mix a stock into a flow column and produce absurd rates (>1000%).
            if dpd >= 30:
                # Delinquent: forward PD rises with delinquency depth. These are
                # ANNUAL probabilities of loss, converted to a monthly accrual by
                # dividing by 12 — otherwise a 1-month-late account would accrue
                # ~96% of its balance a year and annualized rates exceed 100%.
                pd_annual = ASSUMPTIONS["pd_annual_by_dpd"].get(dpd, 0.60)
                expected_loss = carried * pd_annual * ASSUMPTIONS["lgd"] / 12.0
            else:
                # Performing: baseline annual PD of ~1.2% accrued monthly
                expected_loss = (carried * ASSUMPTIONS["pd_annual_by_dpd"][0]
                                 * ASSUMPTIONS["lgd"] / 12.0)

            # The real observed default settles against the newest statement
            is_default = defaulted == 1 and i == 0
            chargeoff = carried * ASSUMPTIONS["lgd"] if is_default else 0.0

            months.append({
                "account_id": account_id,
                "stat_month": month,
                "is_active": str(is_active).lower(),
                "purchases_usd": f"{purchases:.2f}",
                "payments_usd": f"{paid:.2f}",
                "avg_daily_balance_usd": f"{carried:.2f}",
                "revolve_balance_usd": f"{carried:.2f}" if status > 0 else "0.00",
                "utilization_pct": f"{utilization * 100:.2f}",
                "interest_charged_usd": f"{interest:.2f}",
                "interchange_rev_usd": f"{interchange:.2f}",
                "fee_rev_usd": "0.00",
                "promo_cost_usd": "0.00",
                "funding_cost_usd": f"{funding:.2f}",
                "days_past_due": str(dpd),
                "expected_loss_usd": f"{expected_loss:.2f}",
                "chargeoff_usd": f"{chargeoff:.2f}",
                "risk_band": band,
            })

    # The source has no offer or channel data — emit empty (schema-compatible)
    # files so sql/load_real.sql can run unchanged.
    with open(os.path.join(args.out, "offer_exposures.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["offer_id", "account_id", "offer_type",
                                           "offer_value", "exposed_at", "channel", "in_holdout"])
        w.writeheader()
    with open(os.path.join(args.out, "marketing_spend.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["stat_month", "channel", "spend_usd", "new_accounts"])
        w.writeheader()
        w.writerow({"stat_month": "2005-04-01", "channel": "undisclosed_source",
                    "spend_usd": "0.00", "new_accounts": len(accounts)})

    def dump(name, rows_, fields):
        path = os.path.join(args.out, name)
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows_)
        print(f"  {path}: {len(rows_):,} rows")

    dump("accounts.csv", accounts, list(accounts[0].keys()))
    dump("account_months.csv", months, list(months[0].keys()))

    print(f"\nSource: {CITATION}")
    print(f"License: CC BY 4.0 ({UCI_PAGE})")
    print(f"\nReal dataset: {len(accounts):,} clients, {len(months):,} client-months.")
    print("Next:  python3 scripts/run_real_analysis.py")


if __name__ == "__main__":
    main()
