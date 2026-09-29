#!/usr/bin/env python3
"""
generate_synthetic_data.py — Halo Card synthetic credit-card portfolio generator.

Standard library only (no pandas/numpy needed). Fully seeded and reproducible.

Correlations encoded (see docs/case-brief.md §4):
  - origination risk band -> utilization -> expected loss -> charge-off
  - acquisition channel  -> CAC -> activation quality
  - premium membership   -> higher spend, lower price sensitivity
  - revolve behavior     -> interest revenue
  - seasonality          -> Nov/Dec purchase lift, Jan payment surge
  - vintage effect       -> 2026 vintages carry slightly higher loss than 2025

Output: CSVs in data/ ready to load into DuckDB:
  accounts.csv, account_months.csv, offer_exposures.csv, marketing_spend.csv

Usage:
  python3 scripts/generate_synthetic_data.py                 # defaults: 12k accounts, 24 months
  python3 scripts/generate_synthetic_data.py --accounts 2000 --months 12 --out data
"""

from __future__ import annotations

import argparse
import csv
import os
import random
from datetime import date

# --------------------------------------------------------------------------
# Configuration: the "economics" the synthetic world must obey
# --------------------------------------------------------------------------

CHANNELS = {
    # channel: (share, cac_usd, activation_quality, early_loss_multiplier)
    "paid_search": (0.30, 145.0, 0.72, 1.25),
    "affiliate":   (0.22, 110.0, 0.68, 1.15),
    "in_app":      (0.24,  35.0, 0.85, 0.90),
    "referral":    (0.16,  25.0, 0.88, 0.85),
    "partner":     (0.08,  90.0, 0.80, 1.00),
}

# risk band: (share, line_usd range, apr_tier, base_utilization, loss_multiplier)
RISK_BANDS = {
    "A": (0.28, (6000, 15000), "low_15",      0.18, 0.45),
    "B": (0.30, (3500,  9000), "standard_22", 0.28, 0.85),
    "C": (0.24, (2000,  6000), "standard_22", 0.38, 1.30),
    "D": (0.13, (1200,  3500), "high_29",     0.50, 2.10),
    "E": (0.05, ( 800,  2000), "high_29",     0.62, 3.40),
}

SCORE_BANDS = {"A": "excellent", "B": "good", "C": "fair", "D": "fair", "E": "thin_file"}

APR_BY_TIER = {"promo_0": 0.0, "low_15": 0.1599, "standard_22": 0.2199, "high_29": 0.2899}

AGE_BANDS = [("18-24", 0.22), ("25-34", 0.38), ("35-44", 0.22), ("45-54", 0.12), ("55+", 0.06)]
REGIONS = [("Northeast", 0.24), ("South", 0.31), ("Midwest", 0.20), ("West", 0.25)]

INTERCHANGE_RATE = 0.017          # net of base rewards cost
FUNDING_RATE_ANNUAL = 0.045       # funds transfer rate on carried balances
ANNUAL_FEE_BY_TIER = {"none": 0.0, "basic_25": 25.0, "premium_60": 60.0}

START_MONTH = date(2025, 1, 1)


def weighted_choice(rng: random.Random, pairs):
    total = sum(w for _, w in pairs)
    r = rng.random() * total
    upto = 0.0
    for value, w in pairs:
        upto += w
        if r <= upto:
            return value
    return pairs[-1][0]


def month_seq(start: date, n: int):
    y, m = start.year, start.month
    for _ in range(n):
        yield date(y, m, 1)
        m += 1
        if m > 12:
            m = 1
            y += 1


def add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, 1)


def seasonality_factor(month: date) -> float:
    """Nov/Dec spend lift; Jan payment surge; Feb trough."""
    return {1: 0.88, 2: 0.93, 3: 1.00, 4: 1.00, 5: 1.02, 6: 1.00,
            7: 1.03, 8: 0.99, 9: 1.00, 10: 1.03, 11: 1.12, 12: 1.20}[month.month]


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate Halo Card synthetic portfolio CSVs.")
    ap.add_argument("--accounts", type=int, default=12000, help="number of accounts")
    ap.add_argument("--months", type=int, default=24, help="statement months per account")
    ap.add_argument("--out", default="data", help="output directory for CSVs")
    ap.add_argument("--seed", type=int, default=42, help="random seed (reproducibility)")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    os.makedirs(args.out, exist_ok=True)
    months = list(month_seq(START_MONTH, args.months))

    accounts_rows, account_months_rows = [], []
    offer_rows = []
    spend_by_month_channel: dict[tuple[str, str], dict[str, float]] = {}

    band_pairs = [(b, RISK_BANDS[b][0]) for b in RISK_BANDS]
    channel_pairs = [(c, CHANNELS[c][0]) for c in CHANNELS]

    for i in range(args.accounts):
        account_id = f"ACC{i + 1:07d}"
        # Acquisitions spread across the first third of the window so vintages mature
        open_idx = rng.randrange(0, max(1, args.months // 3))
        open_date = months[open_idx]

        channel = weighted_choice(rng, channel_pairs)
        _, cac, act_quality, loss_mult = CHANNELS[channel]
        band = weighted_choice(rng, band_pairs)
        _, (lo, hi), apr_tier, base_util, band_loss_mult = RISK_BANDS[band]

        credit_line = round(rng.uniform(lo, hi), -1)
        premium = rng.random() < (0.38 if band in ("A", "B") else 0.18)
        fee_tier = "premium_60" if premium else ("basic_25" if rng.random() < 0.25 else "none")
        age_band = weighted_choice(rng, AGE_BANDS)
        region = weighted_choice(rng, REGIONS)

        # Vintage effect: 2026 opens carry slightly worse loss experience
        vintage_loss_adj = 1.18 if open_date.year >= 2026 else 1.0

        accounts_rows.append({
            "account_id": account_id,
            "open_date": open_date.isoformat(),
            "acquisition_channel": channel,
            "region": region,
            "age_band": age_band,
            "credit_line_usd": f"{credit_line:.2f}",
            "apr_tier": apr_tier,
            "fee_tier": fee_tier,
            "premium_member": str(premium).lower(),
            "origination_risk_band": band,
            "credit_score_band": SCORE_BANDS[band],
        })

        key = (open_date.isoformat(), channel)
        bucket = spend_by_month_channel.setdefault(key, {"spend": 0.0, "accounts": 0.0})
        bucket["spend"] += cac
        bucket["accounts"] += 1

        # Monthly behavior
        base_spend = rng.uniform(180, 520) * (1.45 if premium else 1.0)
        activated = rng.random() < act_quality
        balance = 0.0
        dpd = 0
        is_revolver = rng.random() < (0.42 + (base_util - 0.18) * 0.5)

        for mi, month in enumerate(months):
            if month < open_date:
                continue
            tenure = (month.year - open_date.year) * 12 + (month.month - open_date.month)
            seasonal = seasonality_factor(month)
            is_active = activated and (tenure > 0 or rng.random() < act_quality)
            purchases = base_spend * seasonal * rng.uniform(0.65, 1.35) if is_active else 0.0

            # Payments: transactors clear; revolvers pay partially (Jan surge)
            if is_revolver:
                pay_ratio = rng.uniform(0.10, 0.45) * (1.35 if month.month == 1 else 1.0)
            else:
                pay_ratio = rng.uniform(0.95, 1.10)
            payments = max(0.0, (balance + purchases) * pay_ratio)

            balance = max(0.0, balance + purchases - payments)
            utilization = min(1.20, balance / credit_line) if credit_line else 0.0

            # Two DIFFERENT balance concepts (a real card book distinguishes these):
            #  - revolve_balance_usd   : balance actually carried past the due date
            #                            (only revolvers; this is what earns interest)
            #  - avg_daily_balance_usd : average balance held across the cycle
            #                            (everyone has float between purchase and payment)
            revolve_balance = balance if is_revolver else 0.0
            if is_revolver:
                avg_daily = balance
            else:
                # transactors hold roughly 25-60% of monthly spend as mid-cycle float
                avg_daily = purchases * rng.uniform(0.25, 0.60)

            apr = APR_BY_TIER[apr_tier]
            interest = revolve_balance * (apr / 12.0)          # only carried balances pay interest
            interchange = purchases * INTERCHANGE_RATE
            fees = (ANNUAL_FEE_BY_TIER[fee_tier] / 12.0) if tenure < 12 else 0.0
            funding_cost = avg_daily * (FUNDING_RATE_ANNUAL / 12.0)

            # Delinquency: probability scales with utilization, band risk, vintage
            pd_base = 0.004 * band_loss_mult * loss_mult * vintage_loss_adj
            pd_month = pd_base * (1.0 + 3.5 * max(0.0, utilization - 0.5))
            if dpd == 0 and rng.random() < pd_month:
                dpd = rng.choice([30, 60, 90])
            elif dpd in (30, 60) and rng.random() < 0.35:
                dpd += 30
            elif dpd == 90 and rng.random() < 0.12:
                dpd = 0  # cure

            # Expected loss (monthly, PRC-style): PD_annual x LGD x EAD / 12.
            # Real card portfolios run ~3-8% annualized loss, rising with risk band.
            # EAD is the carried exposure (transactor float is not at risk of loss).
            ead = revolve_balance if revolve_balance > 0 else min(avg_daily, purchases * 0.5)
            lgd = 0.85 if dpd >= 90 else 0.72
            pd_ann = (0.022 * band_loss_mult * loss_mult * vintage_loss_adj
                      * (1.0 + 1.8 * max(0.0, utilization - 0.5)))
            if dpd >= 30:
                pd_ann *= 6.0      # already delinquent -> much higher forward loss
            expected_loss = min(ead, ead * pd_ann * lgd / 12.0)
            chargeoff = revolve_balance * 0.65 if dpd >= 120 else 0.0

            promo_cost = 0.0
            if is_active and rng.random() < 0.02:
                promo_cost = purchases * 0.012
                offer_rows.append({
                    "offer_id": f"OFF{len(offer_rows) + 1:08d}",
                    "account_id": account_id,
                    "offer_type": rng.choice(["cashback_boost", "apr_promo", "fee_waiver"]),
                    "offer_value": rng.choice(["+1% grocery 6mo", "0% for 12 months", "fee waiver 12mo"]),
                    "exposed_at": month.isoformat(),
                    "channel": rng.choice(["email", "in_app", "push"]),
                    "in_holdout": str(rng.random() < 0.08).lower(),
                })

            account_months_rows.append({
                "account_id": account_id,
                "stat_month": month.isoformat(),
                "is_active": str(is_active).lower(),
                "purchases_usd": f"{purchases:.2f}",
                "payments_usd": f"{payments:.2f}",
                "avg_daily_balance_usd": f"{avg_daily:.2f}",
                "revolve_balance_usd": f"{revolve_balance:.2f}",
                "utilization_pct": f"{utilization * 100:.2f}",
                "interest_charged_usd": f"{interest:.2f}",
                "interchange_rev_usd": f"{interchange:.2f}",
                "fee_rev_usd": f"{fees:.2f}",
                "promo_cost_usd": f"{promo_cost:.2f}",
                "funding_cost_usd": f"{funding_cost:.2f}",
                "days_past_due": str(dpd),
                "expected_loss_usd": f"{expected_loss:.2f}",
                "chargeoff_usd": f"{chargeoff:.2f}",
                "risk_band": band,
            })

    spend_rows = [
        {"stat_month": m, "channel": c, "spend_usd": f"{v['spend']:.2f}",
         "new_accounts": int(v["accounts"])}
        for (m, c), v in sorted(spend_by_month_channel.items())
    ]

    def dump(name, rows, fields):
        path = os.path.join(args.out, name)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print(f"  {path}: {len(rows):,} rows")

    dump("accounts.csv", accounts_rows, list(accounts_rows[0].keys()))
    dump("account_months.csv", account_months_rows, list(account_months_rows[0].keys()))
    dump("offer_exposures.csv", offer_rows, list(offer_rows[0].keys()) if offer_rows else
         ["offer_id", "account_id", "offer_type", "offer_value", "exposed_at", "channel", "in_holdout"])
    dump("marketing_spend.csv", spend_rows, ["stat_month", "channel", "spend_usd", "new_accounts"])

    print(f"\nDone. {len(accounts_rows):,} accounts, {len(account_months_rows):,} account-months.")
    print("Load with:  duckdb credit.duckdb '.read sql/schema.sql'")
    # DuckDB can read CSVs directly:
    print("Then:  COPY accounts FROM 'data/accounts.csv' (HEADER, AUTO_DETECT TRUE);")


if __name__ == "__main__":
    main()
