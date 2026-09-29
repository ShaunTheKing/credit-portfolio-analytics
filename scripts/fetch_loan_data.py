#!/usr/bin/env python3
"""
fetch_loan_data.py — downloads LendingClub loan data and reshapes it into a
loan-level table for profitability and pricing analysis.

Source: LendingClub public loan statistics files
        https://www.lendingclub.com/info/download-data.action
        (LoanStats_<quarter>.csv.zip — publicly published loan performance data)

Why this dataset: the UCI credit-card data used elsewhere in this project has real
default outcomes but NO revenue. LendingClub carries actual interest received,
charged-off principal, and recovery amounts, which makes true profit-and-loss,
pricing-by-risk-grade, and risk-adjusted return analysis possible.

IMPORTANT DATA NOTES
  1. Two junk rows precede the real header; the final line is a footer.
  2. ~11% of loans are still open (Current / Late / In Grace Period). Any
     charge-off rate computed over ALL loans is wrong — it dilutes the denominator
     with loans that haven't had time to resolve. Resolved-only is the correct base.
  3. Loan status is a snapshot from the file's publication date, not a fixed
     observation window, so results are a cohort view rather than a survival model.

Usage:
  python3 scripts/fetch_loan_data.py                          # latest supported quarter
  python3 scripts/fetch_loan_data.py --quarter 2019Q1
  python3 scripts/fetch_loan_data.py --csv path/to/file.csv   # use a local copy
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import urllib.request
import zipfile

DEFAULT_QUARTER = "2019Q1"
BASE_URL = "https://resources.lendingclub.com/LoanStats_{quarter}.csv.zip"

# Columns we keep. Everything else (140+ fields) is dropped to keep the repo
# reviewable; these are the fields the analysis actually uses.
# Note: LendingClub's public files stopped including FICO score columns in later
# vintages, so credit-quality signals here are pub_rec, delinq_2yrs, inq_last_6mths,
# revol_util and the assigned grade — all present in this file.
KEEP = [
    "loan_amnt", "funded_amnt", "term", "int_rate", "installment", "grade",
    "sub_grade", "emp_length", "home_ownership", "annual_inc", "verification_status",
    "issue_d", "loan_status", "purpose", "addr_state", "dti", "delinq_2yrs",
    "inq_last_6mths", "open_acc", "pub_rec", "revol_bal", "revol_util", "total_acc",
    "out_prncp", "total_rec_prncp", "total_rec_int", "total_rec_late_fee",
    "recoveries", "collection_recovery_fee", "last_pymnt_amnt",
]

# Loan status -> analysis buckets. A loan is "resolved" when it has reached a
# terminal state; only resolved loans belong in a charge-off denominator.
RESOLVED_BAD = {"Charged Off", "Default"}
RESOLVED_GOOD = {"Fully Paid"}
OPEN_STATUSES = {
    "Current", "In Grace Period", "Late (16-30 days)", "Late (31-120 days)",
    "Issued",  # appears in some quarters
}


def download(quarter: str, cache_dir: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    url = BASE_URL.format(quarter=quarter)
    zip_path = os.path.join(cache_dir, f"LoanStats_{quarter}.csv.zip")
    if not os.path.exists(zip_path):
        print(f"  downloading {url}")
        urllib.request.urlretrieve(url, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(cache_dir)
    csv_path = os.path.join(cache_dir, f"LoanStats_{quarter}.csv")
    if not os.path.exists(csv_path):
        for name in os.listdir(cache_dir):
            if name.startswith(f"LoanStats_{quarter}") and name.endswith(".csv"):
                csv_path = os.path.join(cache_dir, name)
                break
    return csv_path


def to_float(v, pct=False):
    if v is None:
        return None
    s = str(v).strip().replace("%", "").replace(",", "").replace("$", "")
    if s in ("", "n/a", "NA", "None"):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return f / 100.0 if pct else f


def parse_issue_date(v):
    """'Dec-2018' -> '2018-12-01'."""
    s = str(v).strip()
    if not s:
        return None
    try:
        mon, yr = s.split("-")
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{int(yr):04d}-{months.index(mon) + 1:02d}-01"
    except (ValueError, IndexError):
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarter", default=DEFAULT_QUARTER)
    ap.add_argument("--csv", help="path to a local LoanStats CSV (skips download)")
    ap.add_argument("--out", default="data_loans")
    ap.add_argument("--cache", default=".cache")
    args = ap.parse_args()

    path = args.csv or download(args.quarter, args.cache)
    print(f"  reading {path}")

    csv.field_size_limit(10 ** 9)
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.reader(fh)
        next(reader)                      # row 0: "Notes offered by Prospectus..."
        header = next(reader)             # row 1: the real header
        idx = {h: i for i, h in enumerate(header)}
        missing = [c for c in KEEP if c not in idx]
        if missing:
            sys.exit(f"unexpected schema — missing columns: {missing}")

        rows = []
        skipped = 0
        for raw in reader:
            if len(raw) != len(header):   # trailing footer rows
                skipped += 1
                continue
            rows.append(raw)

    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, "loans.csv")
    fields = [
        "loan_id", "loan_amnt", "term_months", "int_rate", "grade", "sub_grade",
        "purpose", "home_ownership", "annual_inc", "dti", "pub_rec", "delinq_2yrs",
        "inq_last_6mths", "revol_util", "emp_length", "verification_status",
        "addr_state", "issue_month",
        "loan_status", "is_resolved", "is_charged_off", "is_fully_paid",
        "outstanding_principal", "principal_received", "interest_received",
        "late_fees_received", "recoveries", "collection_fees",
        # Derived economics
        "principal_lost", "net_profit",
    ]

    # LendingClub blanks the id/member_id columns in public files (borrower
    # privacy), so a stable surrogate key is generated from row order instead.
    # It is only an identifier — never used as a feature in any analysis.
    kept = 0
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for raw in rows:
            g = lambda c: raw[idx[c]] if c in idx else ""
            status = g("loan_status").strip()
            if not status:
                continue

            amt = to_float(g("funded_amnt")) or to_float(g("loan_amnt")) or 0.0
            prn_rec = to_float(g("total_rec_prncp")) or 0.0
            int_rec = to_float(g("total_rec_int")) or 0.0
            late = to_float(g("total_rec_late_fee")) or 0.0
            recov = to_float(g("recoveries")) or 0.0
            coll = to_float(g("collection_recovery_fee")) or 0.0
            out_prn = to_float(g("out_prncp")) or 0.0

            is_co = status in RESOLVED_BAD
            is_fp = status in RESOLVED_GOOD
            resolved = is_co or is_fp

            # Principal never recovered: only meaningful once resolved.
            # For charged-off loans this is what was written off.
            principal_lost = max(0.0, amt - prn_rec - recov) if is_co else 0.0

            # Net profit to the lender: interest + fees + recoveries collected
            # minus principal written off and collection costs. For open loans
            # this is "earned so far", not lifetime, which is why it is only
            # compared across loans within the same status bucket.
            net_profit = int_rec + late + recov - coll - principal_lost

            w.writerow({
                "loan_id": f"LC{kept + 1:08d}",
                "loan_amnt": f"{amt:.2f}",
                "term_months": (g("term").strip().split()[0] or "").strip(),
                "int_rate": f"{to_float(g('int_rate'), pct=True) or 0:.6f}",
                "grade": g("grade").strip(),
                "sub_grade": g("sub_grade").strip(),
                "purpose": g("purpose").strip().replace("_", " "),
                "home_ownership": g("home_ownership").strip(),
                "annual_inc": f"{to_float(g('annual_inc')) or 0:.2f}",
                "dti": f"{to_float(g('dti')) or 0:.2f}",
                "pub_rec": f"{to_float(g('pub_rec')) or 0:.0f}",
                "delinq_2yrs": f"{to_float(g('delinq_2yrs')) or 0:.0f}",
                "inq_last_6mths": f"{to_float(g('inq_last_6mths')) or 0:.0f}",
                "revol_util": f"{to_float(g('revol_util'), pct=True) or 0:.6f}",
                "emp_length": g("emp_length").strip(),
                "verification_status": g("verification_status").strip(),
                "addr_state": g("addr_state").strip(),
                "issue_month": parse_issue_date(g("issue_d")) or "",
                "loan_status": status,
                "is_resolved": str(resolved).lower(),
                "is_charged_off": str(is_co).lower(),
                "is_fully_paid": str(is_fp).lower(),
                "outstanding_principal": f"{out_prn:.2f}",
                "principal_received": f"{prn_rec:.2f}",
                "interest_received": f"{int_rec:.2f}",
                "late_fees_received": f"{late:.2f}",
                "recoveries": f"{recov:.2f}",
                "collection_fees": f"{coll:.2f}",
                "principal_lost": f"{principal_lost:.2f}",
                "net_profit": f"{net_profit:.2f}",
            })
            kept += 1

    print(f"  {out_path}: {kept:,} loans written"
          + (f" ({skipped} malformed rows skipped)" if skipped else ""))
    print("Next:  python3 scripts/run_loan_analysis.py")


if __name__ == "__main__":
    main()
