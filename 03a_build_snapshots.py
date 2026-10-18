#!/usr/bin/env python3
"""
03a_build_snapshots.py
Builds the account x month-end snapshot table (features + 90-day forward labels) and runs the
point-in-time (no-leakage) test.

Leakage test: pick a snapshot date t0. Recompute all features from data TRUNCATED at t0 (future rows
physically removed). Features for t0 must match the full-data features exactly. If any feature
used a future record, the two tables would differ.
"""
import json
import sys

import numpy as np
import pandas as pd

from rpc_features import CUTOFF, NUM_FEATURES, CAT_FEATURES, add_labels, build_features

CLEAN = sys.argv[1] if len(sys.argv) > 1 else "data/clean"
DOCS = sys.argv[2] if len(sys.argv) > 2 else "docs"

A = pd.read_csv(f"{CLEAN}/accounts.csv", parse_dates=["start_date"])
U = pd.read_csv(f"{CLEAN}/usage_events.csv", parse_dates=["month_end"])
T = pd.read_csv(f"{CLEAN}/support_tickets.csv", parse_dates=["created_date"])
E = pd.read_csv(f"{CLEAN}/subscription_events.csv", parse_dates=["event_date"])

print("building full snapshot table ...")
snap = build_features(A, U, T, E, CUTOFF)
snap = add_labels(snap, E)
print(f"  snapshots: {len(snap):,} | accounts: {snap['account_id'].nunique():,} | "
      f"{snap['snapshot_date'].min().date()} .. {snap['snapshot_date'].max().date()}")

lab = snap[snap["y_churn_90d"].notna()]
print(f"  labeled: {len(lab):,} | churn_90d rate {lab['y_churn_90d'].mean():.3%} | "
      f"expansion_90d rate {lab['y_expansion_90d'].mean():.3%} | "
      f"both: {((lab['y_churn_90d']==1)&(lab['y_expansion_90d']==1)).sum()}")

# ---------------- point-in-time test
report = {}
for t0 in [pd.Timestamp("2025-03-31"), pd.Timestamp("2025-09-30"), pd.Timestamp("2026-01-31")]:
    trunc = build_features(A, U[U["month_end"] <= t0], T[T["created_date"] <= t0], E[E["event_date"] <= t0], t0)
    a = trunc[trunc["snapshot_date"] == t0].set_index("account_id").sort_index()
    b = snap[snap["snapshot_date"] == t0].set_index("account_id").sort_index()
    # churn eligibility uses events up to t0 only, so the account sets must match too
    same_accounts = list(a.index) == list(b.index)
    cols = NUM_FEATURES + ["arr"]
    diff = (a[cols].astype(float) - b[cols].astype(float)).abs()
    both_nan = a[cols].isna() & b[cols].isna()
    diff = diff.where(~both_nan, 0).fillna(np.inf)
    ok = same_accounts and bool((diff.to_numpy() < 1e-9).all())
    report[str(t0.date())] = dict(rows=int(len(a)), same_accounts=same_accounts,
                                  max_abs_diff=float(np.nanmax(diff.replace(np.inf, np.nan).to_numpy())) if len(a) else 0.0,
                                  passed=bool(ok))
    print(f"  point-in-time test @ {t0.date()}: rows={len(a):,} accounts_match={same_accounts} passed={ok}")
    assert ok, f"LEAKAGE: features at {t0.date()} change when future data is removed"

snap.to_csv(f"{CLEAN}/account_snapshots.csv", index=False)
json.dump(report, open(f"{DOCS}/leakage_test.json", "w"), indent=2)
print("saved account_snapshots.csv, leakage_test.json")
