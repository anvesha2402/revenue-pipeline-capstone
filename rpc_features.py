"""
rpc_features.py - point-in-time feature builder for account-level models (churn, expansion).

Design rule: a feature for snapshot date t may only use records dated <= t.
`build_features(..., cap=t0)` re-computes everything from data truncated at t0; the leakage test in
03a_build_snapshots.py proves the features at t0 are identical with and without the future data.

Labels (added separately by add_labels) look 3 months FORWARD from t and are only defined when that
whole window lies inside the observed period.
"""
import numpy as np
import pandas as pd

CUTOFF = pd.Timestamp("2026-06-30")
HORIZON_M = 3
ME = pd.offsets.MonthEnd

NUM_FEATURES = [
    # contract & commercial
    "tenure_months", "contract_term_months", "months_to_renewal", "mrr", "mrr_ratio", "seats",
    "expansions_to_date", "contractions_to_date", "months_since_last_expansion",
    # product usage
    "login_3m", "login_slope_6m", "login_last", "users_chg_3m", "feat_3m", "feat_slope_6m", "feat_last",
    "util_3m", "util_last", "limit_hits_3m", "events_per_user_3m", "api_3m_growth", "integrations",
    # support
    "tickets_90d", "tickets_chg", "high_crit_90d", "esc_90d", "res_hours_90d", "csat_90d", "feature_req_90d",
]
CAT_FEATURES = ["account_tier", "industry", "size_band", "region"]


def _slope(y):
    m = ~np.isnan(y)
    if m.sum() < 4:
        return np.nan
    x = np.arange(len(y), dtype=float)[m]
    yy = y[m]
    x = x - x.mean()
    return float((x * (yy - yy.mean())).sum() / (x * x).sum())


def build_features(A, U, T, E, cap=CUTOFF):
    cap = pd.Timestamp(cap)
    U = U[U["month_end"] <= cap].copy()
    T = T[T["created_date"] <= cap].copy()
    E = E[E["event_date"] <= cap].copy()

    months = pd.date_range("2024-01-31", cap, freq="ME")
    acct = A[["account_id", "start_date", "contract_term_months"]].copy()
    acct["start_me"] = acct["start_date"] + ME(0)
    grid = acct.merge(pd.DataFrame({"month_end": months}), how="cross")
    grid = grid[grid["month_end"] >= grid["start_me"]].sort_values(["account_id", "month_end"]).reset_index(drop=True)

    u = U[["account_id", "month_end", "seats_licensed", "active_users", "login_rate", "features_adopted",
           "events_count", "api_calls", "integrations_connected", "peak_seat_utilization", "seat_utilization"]]
    grid = grid.merge(u, on=["account_id", "month_end"], how="left")

    # tickets, bucketed to month (anything created in month m is known by month-end m)
    T["month_end"] = T["created_date"] + ME(0)
    T["hc"] = T["severity"].isin(["High", "Critical"]).astype(int)
    T["fr"] = (T["ticket_type"] == "Feature Request").astype(int)
    Tm = T.groupby(["account_id", "month_end"]).agg(
        t_n=("ticket_id", "size"), t_hc=("hc", "sum"), t_esc=("is_escalated", "sum"), t_fr=("fr", "sum"),
        res_sum=("resolution_hours", "sum"), csat_sum=("csat_score", "sum"), csat_n=("csat_score", "count")).reset_index()
    grid = grid.merge(Tm, on=["account_id", "month_end"], how="left")
    for c in ["t_n", "t_hc", "t_esc", "t_fr", "res_sum", "csat_sum", "csat_n"]:
        grid[c] = grid[c].fillna(0)

    # contract events
    E["month_end"] = E["event_date"] + ME(0)
    Ex = E[E["event_type"].str.startswith("Expansion")].groupby(["account_id", "month_end"]).size().rename("n_exp")
    Ct = E[E["event_type"] == "Contraction"].groupby(["account_id", "month_end"]).size().rename("n_con")
    Mr = (E[E["event_type"] != "Churn"].sort_values("event_date").groupby(["account_id", "month_end"])["mrr_after"]
          .last().rename("mrr_m"))
    grid = grid.merge(Ex.reset_index(), on=["account_id", "month_end"], how="left") \
               .merge(Ct.reset_index(), on=["account_id", "month_end"], how="left") \
               .merge(Mr.reset_index(), on=["account_id", "month_end"], how="left")
    grid["n_exp"] = grid["n_exp"].fillna(0)
    grid["n_con"] = grid["n_con"].fillna(0)

    g = grid.groupby("account_id", sort=False)
    grid["seats"] = g["seats_licensed"].ffill()
    grid["integrations"] = g["integrations_connected"].ffill().fillna(0)
    grid["mrr"] = g["mrr_m"].ffill()
    grid["expansions_to_date"] = g["n_exp"].cumsum()
    grid["contractions_to_date"] = g["n_con"].cumsum()
    first_mrr = g["mrr"].transform("first")
    grid["mrr_ratio"] = grid["mrr"] / first_mrr
    last_exp = grid["month_end"].where(grid["n_exp"] > 0)
    grid["_last_exp"] = last_exp
    grid["_last_exp"] = grid.groupby("account_id", sort=False)["_last_exp"].ffill()
    grid["months_since_last_expansion"] = ((grid["month_end"] - grid["_last_exp"]).dt.days / 30.4375)

    # static / calendar
    grid["tenure_months"] = ((grid["month_end"].dt.year - grid["start_me"].dt.year) * 12
                             + grid["month_end"].dt.month - grid["start_me"].dt.month)
    msf = (grid["month_end"] - grid["start_date"]).dt.days / 30.4375
    term = grid["contract_term_months"].astype(float)
    grid["months_to_renewal"] = term * (np.floor(msf / term) + 1) - msf

    # usage windows (all backward-looking)
    g = grid.groupby("account_id", sort=False)
    grid["_ev_per_user"] = grid["events_count"] / grid["active_users"].replace(0, np.nan)
    grid["_limit"] = (grid["peak_seat_utilization"] >= 0.95).astype(float).where(grid["peak_seat_utilization"].notna())
    g = grid.groupby("account_id", sort=False)

    def rmean(col, w, mp=2):
        return g[col].transform(lambda s: s.rolling(w, min_periods=mp).mean())

    grid["login_3m"] = rmean("login_rate", 3)
    grid["feat_3m"] = rmean("features_adopted", 3)
    grid["util_3m"] = rmean("seat_utilization", 3)
    grid["events_per_user_3m"] = rmean("_ev_per_user", 3)
    grid["limit_hits_3m"] = g["_limit"].transform(lambda s: s.rolling(3, min_periods=2).sum())
    grid["login_last"] = grid["login_rate"]
    grid["feat_last"] = grid["features_adopted"]
    grid["util_last"] = grid["seat_utilization"]
    grid["login_slope_6m"] = g["login_rate"].transform(lambda s: s.rolling(6, min_periods=4).apply(_slope, raw=True))
    grid["feat_slope_6m"] = g["features_adopted"].transform(lambda s: s.rolling(6, min_periods=4).apply(_slope, raw=True))
    au_now = rmean("active_users", 3)
    au_prev = g["active_users"].transform(lambda s: s.shift(3).rolling(3, min_periods=2).mean())
    grid["users_chg_3m"] = au_now / au_prev.replace(0, np.nan) - 1
    api_now = rmean("api_calls", 3)
    api_prev = g["api_calls"].transform(lambda s: s.shift(3).rolling(3, min_periods=2).mean())
    grid["api_3m_growth"] = api_now / api_prev.replace(0, np.nan) - 1

    def rsum(col, w=3):
        return g[col].transform(lambda s: s.rolling(w, min_periods=1).sum())

    def rsum_prev(col, w=3):
        return g[col].transform(lambda s: s.shift(w).rolling(w, min_periods=1).sum())

    grid["tickets_90d"] = rsum("t_n")
    prev = rsum_prev("t_n")
    grid["tickets_chg"] = grid["tickets_90d"] - prev
    grid["high_crit_90d"] = rsum("t_hc")
    grid["esc_90d"] = rsum("t_esc")
    grid["feature_req_90d"] = rsum("t_fr")
    grid["res_hours_90d"] = rsum("res_sum") / grid["tickets_90d"].replace(0, np.nan)
    grid["csat_90d"] = rsum("csat_sum") / rsum("csat_n").replace(0, np.nan)

    # attributes
    attrs = A[["account_id", "account_tier", "industry", "size_band", "region"]]
    grid = grid.merge(attrs, on="account_id", how="left")
    churn_dt = E[E["event_type"] == "Churn"].groupby("account_id")["event_date"].min().rename("churn_date")
    grid = grid.merge(churn_dt.reset_index(), on="account_id", how="left")
    alive = grid["churn_date"].isna() | (grid["churn_date"] > grid["month_end"])
    snap = grid[alive & (grid["tenure_months"] >= 3)].copy()
    snap = snap.rename(columns={"month_end": "snapshot_date"})
    snap["arr"] = snap["mrr"] * 12
    keep = ["account_id", "snapshot_date", "arr"] + NUM_FEATURES + CAT_FEATURES
    return snap[keep].reset_index(drop=True)


def add_labels(df, E, cap=CUTOFF, horizon=HORIZON_M):
    df = df.copy()
    df["window_end"] = df["snapshot_date"] + ME(horizon)
    labeled = df["window_end"] <= cap
    ch = E[E["event_type"] == "Churn"].groupby("account_id")["event_date"].min()
    cd = df["account_id"].map(ch)
    y_ch = ((cd > df["snapshot_date"]) & (cd <= df["window_end"])).astype(float)
    ex = E[E["event_type"].str.startswith("Expansion")][["account_id", "event_date"]]
    m = df[["account_id", "snapshot_date", "window_end"]].reset_index().merge(ex, on="account_id")
    m = m[(m["event_date"] > m["snapshot_date"]) & (m["event_date"] <= m["window_end"])]
    y_ex = pd.Series(0.0, index=df.index)
    y_ex.loc[m["index"].unique()] = 1.0
    df["y_churn_90d"] = y_ch.where(labeled)
    df["y_expansion_90d"] = y_ex.where(labeled)
    return df
