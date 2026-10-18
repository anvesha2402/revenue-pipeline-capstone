#!/usr/bin/env python3
"""
04_export_and_figures.py
Builds the dashboard-ready tables, KPI file, model scorecard and the README figures from the model outputs.
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CLEAN, DOCS, EXPORTS, FIG = "data/clean", "docs", "exports", "figures"
CUTOFF = pd.Timestamp("2026-06-30")
rc = json.load(open(f"{DOCS}/results_churn_expansion.json"))
rl = json.load(open(f"{DOCS}/results_lead_deal_velocity.json"))

A = pd.read_csv(f"{CLEAN}/accounts.csv", parse_dates=["start_date"])
S = pd.read_csv(f"{CLEAN}/subscriptions.csv", parse_dates=["start_date", "renewal_date", "churn_date"])
E = pd.read_csv(f"{CLEAN}/subscription_events.csv", parse_dates=["event_date"])
sc = pd.read_csv(f"{EXPORTS}/account_scores.csv", parse_dates=["snapshot_date"])
sh = pd.read_csv(f"{EXPORTS}/account_drivers_shap.csv")

# ---------------------------------------------------------------- master account table
def drivers(model, k=3):
    d = sh[(sh["model"] == model) & (sh["rank"] <= k)].sort_values(["account_id", "rank"])
    return d.groupby("account_id")["label"].apply(lambda s: "; ".join(s)).rename(f"top_{model}_drivers")

meta = A[["account_id", "company_name", "csm_id", "start_date", "contract_term_months"]]
renew = S[["account_id", "renewal_date", "status"]]
M = sc.merge(meta, on="account_id", how="left").merge(renew, on="account_id", how="left") \
      .merge(drivers("churn"), on="account_id", how="left").merge(drivers("expansion"), on="account_id", how="left")
M = M.sort_values("expected_arr_loss_90d", ascending=False).reset_index(drop=True)
keep = ["account_id", "company_name", "account_tier", "industry", "size_band", "region", "csm_id", "start_date", "tenure_months",
        "renewal_date", "months_to_renewal", "arr", "churn_prob_90d", "churn_tier", "expected_arr_loss_90d",
        "expansion_prob_90d", "expansion_tier", "expected_expansion_arr_90d", "quadrant", "top_churn_drivers", "top_expansion_drivers",
        "login_3m", "feat_3m", "util_3m", "tickets_90d", "high_crit_90d", "csat_90d", "integrations", "seats"]
M[keep].to_csv(f"{EXPORTS}/dashboard_account_health.csv", index=False)

# ---------------------------------------------------------------- retention KPIs (trailing 12 months, from the MRR event log)
t0 = CUTOFF - pd.DateOffset(months=12)
def mrr_at(t):
    e = E[E["event_date"] <= t].sort_values("event_date")
    last = e.groupby("account_id").tail(1).set_index("account_id")["mrr_after"]
    return last
m0, m1 = mrr_at(t0), mrr_at(CUTOFF)
cohort = m0[m0 > 0].index
now = m1.reindex(cohort).fillna(0)
nrr = float(now.sum() / m0[cohort].sum())
grr = float(np.minimum(now, m0[cohort]).sum() / m0[cohort].sum())
logo_ret = float((now > 0).mean())

lb, pv = rc["live_book"], rl["pipeline_velocity"]
vel = pv["formula_inputs"]
fun = json.load(open(f"{EXPORTS}/funnel_counts.json"))
kpis = dict(
    as_of=str(CUTOFF.date()), data="synthetic",
    active_accounts=int((m1 > 0).sum()), active_arr=float(m1[m1 > 0].sum() * 12),
    scored_accounts=lb["active_accounts"], scored_arr=lb["active_arr"], scored_share_of_arr=float(lb["active_arr"] / (m1[m1 > 0].sum() * 12)),
    net_revenue_retention_12m=nrr, gross_revenue_retention_12m=grr, logo_retention_12m=logo_ret, retention_cohort_accounts=int(len(cohort)),
    open_opportunities=vel["open_opportunities"], open_pipeline=pv["open_value"], weighted_open_pipeline=vel["weighted_open_pipeline"],
    stalled_pipeline=pv["stalled_value"], win_rate_12m=vel["win_rate_12m"], avg_won_cycle_days=vel["avg_won_cycle_days"],
    pipeline_velocity_usd_per_day=vel["pipeline_velocity_usd_per_day"],
    high_churn_risk_accounts=lb["churn_high_n"], high_churn_risk_arr=lb["churn_high_arr"],
    expected_arr_loss_next_90d=lb["expected_arr_loss_90d"],
    high_expansion_accounts=lb["expansion_high_n"], high_expansion_arr=lb["expansion_high_arr"],
    expected_expansion_arr_next_90d=lb["expected_expansion_arr_90d"],
    quadrant_counts=lb["quadrant_counts"], funnel=fun)
json.dump(kpis, open(f"{EXPORTS}/dashboard_kpis.json", "w"), indent=2, default=float)
print(json.dumps({k: v for k, v in kpis.items() if k not in ("funnel", "quadrant_counts")}, indent=1, default=float))

# ---------------------------------------------------------------- model scorecard
rows = []
def add(model, target, split, p, extra=""):
    ci = p.get("roc_auc_ci95", [np.nan, np.nan])
    rows.append(dict(model=model, target=target, validation=split, algorithm_deployed=extra, roc_auc=p["roc_auc"], roc_auc_ci_low=ci[0],
                     roc_auc_ci_high=ci[1], pr_auc=p.get("pr_auc", np.nan), base_rate=p.get("base_rate", np.nan),
                     top10pct_lift=p.get("top10_lift", np.nan), n_scored=p.get("n", np.nan), positives=p.get("positives", np.nan)))
for name, key, tgt in [("Churn (90-day)", "churn", "churn within 90 days"), ("Expansion (90-day)", "expansion", "expansion within 90 days")]:
    P = rc[key]["pooled"]
    dep = P["deployed"]
    add(name, tgt, "forward-in-time, 4 folds, 3-month purge gap", P[dep], dep.upper())
for name, key, tgt in [("Lead scoring", "lead_scoring", "lead becomes opportunity within 75 days"),
                       ("Deal-win", "deal_win", "closed deal is won")]:
    P = rl[key]["pooled"]
    dep = P["deployed"]
    add(name, tgt, "forward-in-time, 4 folds", P[dep], dep.upper())
sc_df = pd.DataFrame(rows)
sc_df.to_csv(f"{EXPORTS}/model_scorecard.csv", index=False)
print(sc_df.round(3).to_string(index=False))

# ---------------------------------------------------------------- figures (dataviz skill: light surface, categorical slots 1-3, muted ink)
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SURF, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED,
                     "ytick.color": MUTED, "text.color": INK, "figure.facecolor": SURF, "axes.facecolor": SURF,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8})

# Fig 1: time-based vs random-row validation (the honesty chart)
fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=170)
labels = ["Churn", "Expansion"]
tb = [rc["churn"]["pooled"][rc["churn"]["pooled"]["deployed"]]["roc_auc"], rc["expansion"]["pooled"][rc["expansion"]["pooled"]["deployed"]]["roc_auc"]]
rr = [rc["churn"]["pooled"]["random_row_split_xgb_roc_auc"], rc["expansion"]["pooled"]["random_row_split_xgb_roc_auc"]]
x = np.arange(2); w = 0.34
b1 = ax.bar(x - w / 2 - 0.01, rr, w, color=ORANGE, label="Random-row split (leaky)")
b2 = ax.bar(x + w / 2 + 0.01, tb, w, color=BLUE, label="Forward-in-time (used)")
for bars in (b1, b2):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.008, f"{b.get_height():.3f}", ha="center", va="bottom", fontsize=9, color=INK)
ax.set_xticks(x, labels); ax.set_ylim(0.5, 0.95); ax.set_ylabel("ROC-AUC"); ax.grid(axis="x", visible=False)
ax.set_title("Random splitting overstates accuracy; the honest score is lower", loc="left", fontsize=11, color=INK)
ax.legend(frameon=False, fontsize=8.5, loc="upper right", ncols=2, bbox_to_anchor=(1, 1.02))
fig.tight_layout(); fig.savefig(f"{FIG}/validation_random_vs_forward.png"); plt.close(fig)

# Fig 2: calibration
fig, axs = plt.subplots(1, 2, figsize=(7.6, 3.5), dpi=170, sharey=False)
for ax, key, title, col in [(axs[0], "churn", "Churn (90-day)", BLUE), (axs[1], "expansion", "Expansion (90-day)", AQUA)]:
    r = pd.read_csv(f"{DOCS}/reliability_{key}.csv")
    mx = max(r["mean_predicted"].max(), r["observed_rate"].max()) * 1.08
    ax.plot([0, mx], [0, mx], color=AXIS, lw=1.2, ls="--")
    ax.plot(r["mean_predicted"], r["observed_rate"], color=col, lw=2); ax.scatter(r["mean_predicted"], r["observed_rate"], s=26, color=col, zorder=3, edgecolor=SURF, linewidth=1.2)
    ax.set_title(title, loc="left", fontsize=10); ax.set_xlabel("Predicted probability (decile mean)"); ax.set_xlim(0, mx); ax.set_ylim(0, mx)
axs[0].set_ylabel("Observed rate")
fig.suptitle("Raw model scores, predicted vs observed out-of-time (dashed = perfect)", x=0.01, ha="left", fontsize=11)
fig.tight_layout(); fig.savefig(f"{FIG}/calibration.png"); plt.close(fig)

# Fig 3: churn x expansion map of the live book
fig, ax = plt.subplots(figsize=(6.6, 4.6), dpi=170)
cols = {"Maintain": "#c3c2b7", "Protect": ORANGE, "Grow": BLUE, "Save & grow": AQUA}
for q in ["Maintain", "Protect", "Grow", "Save & grow"]:
    d = sc[sc["quadrant"] == q]
    ax.scatter(d["expansion_prob_90d"], d["churn_prob_90d"], s=14 if q != "Save & grow" else 34, color=cols[q], alpha=0.75 if q == "Maintain" else 0.9,
               edgecolor=SURF, linewidth=0.5, label=f"{q} ({len(d)})")
bc, be = rc["live_book"]["churn_base_rate_90d"], rc["live_book"]["expansion_base_rate_90d"]
ax.axhline(2 * bc, color=AXIS, lw=1, ls="--"); ax.axvline(2 * be, color=AXIS, lw=1, ls="--")
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Expansion probability, next 90 days (log)"); ax.set_ylabel("Churn probability, next 90 days (log)")
ax.set_title(f"Live book: {len(sc):,} scored accounts (dashed = 2x base rate)", loc="left", fontsize=11)
ax.legend(frameon=False, fontsize=8.5, loc="lower left")
fig.tight_layout(); fig.savefig(f"{FIG}/churn_expansion_map.png"); plt.close(fig)

# Fig 4: global drivers (top 8, churn and expansion)
fig, axs = plt.subplots(1, 2, figsize=(9.2, 3.8), dpi=170)
for ax, key, title, col in [(axs[0], "churn", "What drives churn risk", BLUE), (axs[1], "expansion", "What drives expansion", AQUA)]:
    g = pd.read_csv(f"{DOCS}/shap_global_{key}.csv").head(8).iloc[::-1]
    ax.barh(g["label"], g["mean_abs_shap"], color=col, height=0.62)
    ax.set_title(title, loc="left", fontsize=10); ax.grid(axis="y", visible=False); ax.tick_params(axis="y", labelsize=8, colors=INK2)
    ax.set_xlabel("Mean |SHAP| (impact on log-odds)")
fig.tight_layout(); fig.savefig(f"{FIG}/drivers.png"); plt.close(fig)
print("figures + exports written")
