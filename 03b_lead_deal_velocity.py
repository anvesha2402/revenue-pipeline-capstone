#!/usr/bin/env python3
"""
03b_lead_deal_velocity.py
Model 1  Lead scoring        - time-based expanding-window CV (purge = 75-day conversion horizon)
Model 2  Deal-win            - time-based expanding-window CV by close date; compared with the reps' own forecast
Model 3  Pipeline velocity   - descriptive stage analysis (no ML)

Deal-win note: v1 used the deal's stage as a feature. For a CLOSED deal the final stage IS the outcome
("Closed Won"/"Closed Lost", or how far a lost deal got), so it leaks. v2 uses only information that exists
when the deal is opened: size, competitor, decision-makers engaged, lead attributes, rep.
"""
import json
import os

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.metrics import roc_auc_score

from feature_labels import FEATURE_LABELS
from rpc_common import cluster_bootstrap_ci, expanding_cv, make_xgb, metrics, tune_xgb

CLEAN, DOCS, MODELS, EXPORTS = "data/clean", "docs", "models", "exports"
CUTOFF = pd.Timestamp("2026-06-30")
res = {}

L = pd.read_csv(f"{CLEAN}/leads.csv", parse_dates=["created_date"])
O = pd.read_csv(f"{CLEAN}/opportunities.csv", parse_dates=["created_date", "qualified_date", "discovery_date",
                                                           "proposal_date", "negotiation_date", "closed_date"])
E = pd.read_csv(f"{CLEAN}/subscription_events.csv", parse_dates=["event_date"])
A = pd.read_csv(f"{CLEAN}/accounts.csv", parse_dates=["start_date"])

# =============================================================== MODEL 1: LEAD SCORING
print("=== LEAD SCORING ===")
H_DAYS = 75
Ld = L[L["created_date"] <= CUTOFF - pd.Timedelta(days=H_DAYS)].copy().reset_index(drop=True)
Ld["log_employees"] = np.log1p(Ld["company_size_employees"])
num_l = ["demo_requested", "engagement_score", "log_employees"]
cat_l = ["lead_source", "contact_seniority", "size_band", "industry", "region"]
Xl = pd.get_dummies(Ld[num_l + cat_l], columns=cat_l, dtype=float)
W_L = [(pd.Timestamp("2025-04-01"), pd.Timestamp("2025-06-30")), (pd.Timestamp("2025-07-01"), pd.Timestamp("2025-09-30")),
       (pd.Timestamp("2025-10-01"), pd.Timestamp("2025-12-31")), (pd.Timestamp("2026-01-01"), CUTOFF - pd.Timedelta(days=H_DAYS))]
purge_l = lambda s: s - pd.Timedelta(days=H_DAYS)
folds_l, oof_l, _ = expanding_cv(Ld, "converted", "created_date", W_L, purge_l, num_l, cat_l, Xl.to_numpy())
folds_l.to_csv(f"{DOCS}/cv_folds_lead_scoring.csv", index=False)
print(folds_l[["fold", "test_start", "n_test", "test_positives", "lr_roc_auc", "xgb_roc_auc", "xgb_pr_auc"]].round(3).to_string(index=False))
m = oof_l["fold"].notna().to_numpy()
y = Ld.loc[m, "converted"].to_numpy(float)
pooled_l = {}
for nm in ("lr", "xgb"):
    p = oof_l.loc[m, nm].to_numpy(float)
    mt = metrics(y, p)
    mt["roc_auc_ci95"] = list(cluster_bootstrap_ci(y, p, Ld.loc[m, "lead_id"].to_numpy(), roc_auc_score))
    pooled_l[nm] = mt
dep_l = "xgb" if pooled_l["xgb"]["pr_auc"] >= pooled_l["lr"]["pr_auc"] else "lr"
pooled_l["deployed"] = dep_l
p_dep = oof_l.loc[m, dep_l].to_numpy(float)
q = pd.qcut(pd.Series(p_dep).rank(method="first"), 5, labels=["Q5 (lowest)", "Q4", "Q3", "Q2", "Q1 (highest)"])
quint = pd.DataFrame({"q": q, "y": y}).groupby("q", observed=True).agg(leads=("y", "size"), conversion_rate=("y", "mean")).reset_index()
quint = quint.iloc[::-1].reset_index(drop=True)
ratio = float(quint.iloc[0]["conversion_rate"] / quint.iloc[-1]["conversion_rate"])
rng = np.random.default_rng(42)
bs = []
for _ in range(300):
    ii = rng.integers(0, len(y), len(y))
    qq = pd.qcut(pd.Series(p_dep[ii]).rank(method="first"), 5, labels=False)
    r_top, r_bot = y[ii][qq == 4].mean(), y[ii][qq == 0].mean()
    bs.append(r_top / r_bot)
pooled_l["top_vs_bottom_quintile_ratio"] = ratio
pooled_l["top_vs_bottom_quintile_ratio_ci95"] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
quint.to_csv(f"{DOCS}/lead_quintiles.csv", index=False)
print(f"  pooled: LR AUC {pooled_l['lr']['roc_auc']:.3f} | XGB AUC {pooled_l['xgb']['roc_auc']:.3f} "
      f"[{pooled_l['xgb']['roc_auc_ci95'][0]:.3f},{pooled_l['xgb']['roc_auc_ci95'][1]:.3f}] | deployed {dep_l} | "
      f"top/bottom quintile {ratio:.2f}x {np.round(pooled_l['top_vs_bottom_quintile_ratio_ci95'], 2)}")
print(quint.round(4).to_string(index=False))
prm_l, _ = tune_xgb(Xl.to_numpy(), Ld["converted"].to_numpy(float), Ld["created_date"], purge_l)
xg_l = make_xgb(**prm_l).fit(Xl.to_numpy(), Ld["converted"].to_numpy(float))
sv = shap.TreeExplainer(xg_l).shap_values(Xl.sample(3000, random_state=1).to_numpy())
cols = np.array(Xl.columns)
base_of = np.array([next((c for c in cat_l if col.startswith(c + "_")), col) for col in cols])
glob_l = pd.DataFrame(np.abs(sv), columns=cols).mean().groupby(base_of).sum().sort_values(ascending=False)
glob_l.rename("mean_abs_shap").reset_index().rename(columns={"index": "feature"}).to_csv(f"{DOCS}/shap_global_lead_scoring.csv", index=False)
print("  top drivers:", list(glob_l.index[:5]))
res["lead_scoring"] = dict(pooled=pooled_l, folds=folds_l.to_dict(orient="records"), top_drivers=list(glob_l.index[:6]),
                           n_leads=int(len(Ld)), conversion_rate=float(Ld["converted"].mean()))
joblib.dump(dict(model=xg_l, columns=list(Xl.columns), params=prm_l), f"{MODELS}/lead_scoring_model.joblib")

# =============================================================== MODEL 2: DEAL-WIN
print("\n=== DEAL-WIN ===")
lead_attr = L.set_index("lead_id")[["demo_requested", "engagement_score", "lead_source", "contact_seniority", "industry"]]
D = O[O["outcome"].isin(["Won", "Lost"])].merge(lead_attr, left_on="lead_id", right_index=True, how="left")
for c in ["lead_source", "contact_seniority", "industry"]:
    D[c] = D[c].fillna("Unknown")
D["demo_requested"] = D["demo_requested"].fillna(0)
D["won"] = (D["outcome"] == "Won").astype(float)
D["log_deal_size"] = np.log(D["deal_size"])
D = D.sort_values("closed_date").reset_index(drop=True)
num_d = ["log_deal_size", "competitor_present", "decision_makers_engaged", "decision_makers_missing", "deal_size_imputed",
         "demo_requested", "engagement_score"]
cat_d = ["lead_source", "contact_seniority", "size_band", "industry", "region", "sales_rep_id"]
D["deal_size_imputed"] = D["deal_size_imputed"].astype(float)
Xd = pd.get_dummies(D[num_d + cat_d], columns=cat_d, dtype=float)
W_D = [(pd.Timestamp("2025-07-01"), pd.Timestamp("2025-09-30")), (pd.Timestamp("2025-10-01"), pd.Timestamp("2025-12-31")),
       (pd.Timestamp("2026-01-01"), pd.Timestamp("2026-03-31")), (pd.Timestamp("2026-04-01"), CUTOFF)]
purge_d = lambda s: s - pd.Timedelta(days=1)       # outcome is known on the close date
folds_d, oof_d, _ = expanding_cv(D, "won", "closed_date", W_D, purge_d, num_d, cat_d, Xd.to_numpy(),
                                 extra_scores={"rep_forecast": D["rep_forecast_pct"].to_numpy()})
folds_d.to_csv(f"{DOCS}/cv_folds_deal_win.csv", index=False)
print(folds_d[["fold", "test_start", "n_test", "test_positives", "lr_roc_auc", "xgb_roc_auc", "rep_forecast_roc_auc"]].round(3).to_string(index=False))
m = oof_d["fold"].notna().to_numpy()
y = D.loc[m, "won"].to_numpy(float)
pooled_d = {}
for nm in ("lr", "xgb"):
    p = oof_d.loc[m, nm].to_numpy(float)
    mt = metrics(y, p)
    mt["roc_auc_ci95"] = list(cluster_bootstrap_ci(y, p, D.loc[m, "opportunity_id"].to_numpy(), roc_auc_score))
    pooled_d[nm] = mt
fc = D.loc[m, "rep_forecast_pct"].to_numpy(float)
ok = ~np.isnan(fc)
pooled_d["rep_forecast"] = dict(roc_auc=float(roc_auc_score(y[ok], fc[ok])), n=int(ok.sum()), coverage=float(ok.mean()))
pooled_d["deployed"] = "xgb" if pooled_d["xgb"]["pr_auc"] >= pooled_d["lr"]["pr_auc"] else "lr"
# does the rep add information the model lacks?
D["rep_forecast_filled"] = D["rep_forecast_pct"].fillna(D["rep_forecast_pct"].median())
num_d2 = num_d + ["rep_forecast_filled"]
Xd2 = pd.get_dummies(D[num_d2 + cat_d], columns=cat_d, dtype=float)
folds_d2, oof_d2, _ = expanding_cv(D, "won", "closed_date", W_D, purge_d, num_d2, cat_d, Xd2.to_numpy())
m2 = oof_d2["fold"].notna().to_numpy()
pooled_d["model_plus_rep_forecast_xgb_roc_auc"] = float(roc_auc_score(D.loc[m2, "won"], oof_d2.loc[m2, "xgb"]))
print(f"  pooled: LR {pooled_d['lr']['roc_auc']:.3f} | XGB {pooled_d['xgb']['roc_auc']:.3f} "
      f"[{pooled_d['xgb']['roc_auc_ci95'][0]:.3f},{pooled_d['xgb']['roc_auc_ci95'][1]:.3f}] | "
      f"rep forecast alone {pooled_d['rep_forecast']['roc_auc']:.3f} | model+forecast {pooled_d['model_plus_rep_forecast_xgb_roc_auc']:.3f}")
prm_d, _ = tune_xgb(Xd.to_numpy(), D["won"].to_numpy(float), D["closed_date"], purge_d)
xg_d = make_xgb(**prm_d).fit(Xd.to_numpy(), D["won"].to_numpy(float))
sv = shap.TreeExplainer(xg_d).shap_values(Xd.sample(min(3000, len(Xd)), random_state=1).to_numpy())
cols = np.array(Xd.columns)
base_of = np.array([next((c for c in cat_d if col.startswith(c + "_")), col) for col in cols])
glob_d = pd.DataFrame(np.abs(sv), columns=cols).mean().groupby(base_of).sum().sort_values(ascending=False)
glob_d.rename("mean_abs_shap").reset_index().rename(columns={"index": "feature"}).to_csv(f"{DOCS}/shap_global_deal_win.csv", index=False)
print("  top drivers:", list(glob_d.index[:6]))
wr_comp = D.groupby("competitor_present")["won"].agg(["mean", "size"]).rename(index={0: "no competitor", 1: "competitor present"})
print(wr_comp.round(3).to_string())
res["deal_win"] = dict(pooled=pooled_d, folds=folds_d.to_dict(orient="records"), top_drivers=list(glob_d.index[:6]),
                       win_rate_closed=float(D["won"].mean()), n_closed=int(len(D)),
                       win_rate_by_competitor={k: dict(win_rate=float(v["mean"]), deals=int(v["size"])) for k, v in wr_comp.iterrows()})
joblib.dump(dict(model=xg_d, columns=list(Xd.columns), params=prm_d), f"{MODELS}/deal_win_model.joblib")

# =============================================================== MODEL 3: PIPELINE VELOCITY (descriptive)
print("\n=== PIPELINE VELOCITY ===")
STAGES = ["Qualified", "Discovery", "Proposal", "Negotiation"]
ecol = {"Qualified": "qualified_date", "Discovery": "discovery_date", "Proposal": "proposal_date", "Negotiation": "negotiation_date"}
nxt = {"Qualified": "discovery_date", "Discovery": "proposal_date", "Proposal": "negotiation_date", "Negotiation": "closed_date"}
Oc = O.copy()
dw = {}
for s in STAGES:
    ok = Oc[ecol[s]].notna() & Oc[nxt[s]].notna() & ~(Oc["close_date_reconstructed"] & (s == "Negotiation"))
    dw[s] = (Oc.loc[ok, nxt[s]] - Oc.loc[ok, ecol[s]]).dt.days
dwell = pd.DataFrame({"stage": STAGES, "deals_measured": [len(dw[s]) for s in STAGES],
                      "median_days": [dw[s].median() for s in STAGES], "p75_days": [dw[s].quantile(.75) for s in STAGES],
                      "mean_days": [dw[s].mean() for s in STAGES]})
op = O[O["outcome"] == "Open"].copy()
op["days_in_stage"] = [(CUTOFF - r[ecol[r["stage"]]]).days if r["stage"] in ecol and pd.notna(r[ecol[r["stage"]]]) else np.nan for _, r in op.iterrows()]
op = op.merge(dwell[["stage", "median_days", "p75_days"]], on="stage", how="left")
op["stalled"] = op["days_in_stage"] > op["p75_days"]
op_stage = op.groupby("stage").agg(open_deals=("opportunity_id", "size"), open_value=("deal_size", "sum"),
                                   stalled_deals=("stalled", "sum"),
                                   stalled_value=("deal_size", lambda s: s[op.loc[s.index, "stalled"]].sum())).reindex(STAGES).reset_index()
op_stage["stalled_share_of_stage_value"] = op_stage["stalled_value"] / op_stage["open_value"]
print(dwell.round(1).to_string(index=False)); print(op_stage.round(3).to_string(index=False))
closed = O[O["outcome"].isin(["Won", "Lost"])]
reach = {"Qualified": len(closed)}
for s in STAGES[1:]:
    reach[s] = int(closed[ecol[s]].notna().sum())
reach["Closed Won"] = int((closed["outcome"] == "Won").sum())
funnel_stage = pd.DataFrame({"stage": list(reach.keys()), "closed_deals_reaching": list(reach.values())})
funnel_stage["pct_of_prev"] = funnel_stage["closed_deals_reaching"] / funnel_stage["closed_deals_reaching"].shift(1)
print(funnel_stage.round(3).to_string(index=False))
# conditional on reaching Proposal: does time spent EARLY (Qualified+Discovery) relate to winning?
pp = closed[closed["proposal_date"].notna()].copy()
pp["early_days"] = (pp["proposal_date"] - pp["qualified_date"]).dt.days
pp["speed_tercile"] = pd.qcut(pp["early_days"], 3, labels=["fastest third", "middle third", "slowest third"])
sp = pp.groupby("speed_tercile", observed=True).agg(deals=("outcome", "size"), win_rate=("outcome", lambda s: (s == "Won").mean())).reset_index()
sp["ci95_halfwidth"] = 1.96 * np.sqrt(sp["win_rate"] * (1 - sp["win_rate"]) / sp["deals"])
print(sp.round(3).to_string(index=False))

# velocity formula (standard): open opportunities x average deal size x win rate / average sales-cycle days = $ of new ARR created per day
t12 = CUTOFF - pd.DateOffset(months=12)
c12 = closed[closed["closed_date"] > t12]
wr12 = float((c12["outcome"] == "Won").mean())
won12 = c12[c12["outcome"] == "Won"]
cycle = float((won12["closed_date"] - won12["created_date"]).dt.days.mean())
velocity = dict(open_opportunities=int(len(op)), avg_open_deal_size=float(op["deal_size"].mean()), win_rate_12m=wr12,
                avg_won_cycle_days=cycle, weighted_open_pipeline=float(op["deal_size"].sum() * wr12),
                pipeline_velocity_usd_per_day=float(len(op) * op["deal_size"].mean() * wr12 / cycle))
print("  velocity:", json.dumps(velocity, default=float))

# dashboard tables
rep_tbl = D.groupby("sales_rep_id").agg(deals=("won", "size"), win_rate=("won", "mean"), avg_deal=("deal_size", "mean")).reset_index()
reg_tbl = D.groupby("region").agg(deals=("won", "size"), win_rate=("won", "mean"), avg_deal=("deal_size", "mean")).reset_index()
book = E[E["event_type"] == "New"].copy()
book["month"] = book["event_date"].dt.to_period("M").dt.to_timestamp()
bookings = book.groupby("month")["mrr_after"].sum().mul(12).rename("new_arr").reset_index()
dwell.to_csv(f"{EXPORTS}/stage_dwell.csv", index=False); op_stage.to_csv(f"{EXPORTS}/open_pipeline_by_stage.csv", index=False)
funnel_stage.to_csv(f"{EXPORTS}/stage_funnel_closed_deals.csv", index=False); sp.to_csv(f"{EXPORTS}/winrate_by_early_speed.csv", index=False)
rep_tbl.to_csv(f"{EXPORTS}/winrate_by_rep.csv", index=False); reg_tbl.to_csv(f"{EXPORTS}/winrate_by_region.csv", index=False)
bookings.to_csv(f"{EXPORTS}/new_arr_by_month.csv", index=False); quint.to_csv(f"{EXPORTS}/lead_quintiles.csv", index=False)
res["pipeline_velocity"] = dict(
    dwell=dwell.to_dict(orient="records"), open_by_stage=op_stage.to_dict(orient="records"),
    open_deals=int(len(op)), open_value=float(op["deal_size"].sum()), stalled_value=float(op.loc[op["stalled"], "deal_size"].sum()),
    stalled_rule="days in current stage > 75th percentile of that stage's completed dwell times",
    funnel_closed_deals=funnel_stage.to_dict(orient="records"), early_speed_vs_win=sp.to_dict(orient="records"),
    formula_inputs=velocity)
json.dump(res, open(f"{DOCS}/results_lead_deal_velocity.json", "w"), indent=2, default=float)

# lead->opp->won->active funnel counts for the dashboard
fun = dict(leads=int(len(L)), leads_converted_to_opp=int(L["converted"].sum()), opportunities=int(len(O)),
           opportunities_closed=int(len(closed)), opportunities_won=int((closed["outcome"] == "Won").sum()),
           opportunities_open=int((O["outcome"] == "Open").sum()),
           accounts_total=int(len(A)), accounts_active_now=int((~A["account_id"].isin(E.loc[E["event_type"] == "Churn", "account_id"])).sum()))
json.dump(fun, open(f"{EXPORTS}/funnel_counts.json", "w"), indent=2)
print("saved.")
