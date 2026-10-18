#!/usr/bin/env python3
"""
03c_churn_expansion.py
Churn (90-day) and Expansion (90-day) models on point-in-time monthly snapshots.

Validation: expanding-window forward CV with a 3-month purge gap (4 folds, Apr-2025 .. Mar-2026).
Reported next to a naive random-row split to show how much random splitting would have overstated.
"""
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold

from feature_labels import FEATURE_LABELS
from rpc_common import (SEED, cluster_bootstrap_ci, calibration_slope, expanding_cv, make_lr, make_xgb, metrics,
                        reliability_table, tune_xgb)
from rpc_features import CAT_FEATURES, CUTOFF, NUM_FEATURES

CLEAN, DOCS, MODELS, EXPORTS = "data/clean", "docs", "models", "exports"
for d in (MODELS, EXPORTS):
    os.makedirs(d, exist_ok=True)
ME = pd.offsets.MonthEnd
snap = pd.read_csv(f"{CLEAN}/account_snapshots.csv", parse_dates=["snapshot_date", "window_end"])
E = pd.read_csv(f"{CLEAN}/subscription_events.csv", parse_dates=["event_date"])
A = pd.read_csv(f"{CLEAN}/accounts.csv")

Xall = pd.get_dummies(snap[NUM_FEATURES + CAT_FEATURES], columns=CAT_FEATURES, dtype=float)
xcols = list(Xall.columns)
lab_mask = snap["y_churn_90d"].notna()
lab = snap[lab_mask].copy()
Xlab = Xall.loc[lab.index].to_numpy()
score_set = snap[snap["snapshot_date"] == CUTOFF].copy()
Xscore = Xall.loc[score_set.index]

WINDOWS = [(pd.Timestamp("2025-04-30"), pd.Timestamp("2025-06-30")),
           (pd.Timestamp("2025-07-31"), pd.Timestamp("2025-09-30")),
           (pd.Timestamp("2025-10-31"), pd.Timestamp("2025-12-31")),
           (pd.Timestamp("2026-01-31"), pd.Timestamp("2026-03-31"))]
purge = lambda s: s - ME(3)

results = {"design": dict(
    snapshots_total=int(len(snap)), snapshots_labeled=int(len(lab)), accounts=int(snap["account_id"].nunique()),
    horizon_months=3, purge_gap_months=3, folds=len(WINDOWS),
    labeled_range=[str(lab["snapshot_date"].min().date()), str(lab["snapshot_date"].max().date())],
    scoring_snapshot=str(CUTOFF.date()), scoring_accounts=int(len(score_set)))}

TARGETS = {
    "churn": dict(y="y_churn_90d", naive=lambda d: (-d["months_to_renewal"]).to_numpy(), naive_name="renewal_proximity_only"),
    "expansion": dict(y="y_expansion_90d", naive=lambda d: d["limit_hits_3m"].fillna(0).to_numpy(), naive_name="seat_limit_hits_only"),
}
oof_all = lab[["account_id", "snapshot_date", "arr", "y_churn_90d", "y_expansion_90d"]].copy()
final = {}
for tgt, cfg in TARGETS.items():
    print(f"\n=== {tgt.upper()} ===")
    y = lab[cfg["y"]].to_numpy(float)
    folds, oof, params = expanding_cv(lab, cfg["y"], "snapshot_date", WINDOWS, purge, NUM_FEATURES, CAT_FEATURES, Xlab,
                                      extra_scores={cfg["naive_name"]: cfg["naive"](lab)})
    folds.to_csv(f"{DOCS}/cv_folds_{tgt}.csv", index=False)
    print(folds[["fold", "test_start", "n_test", "test_positives", "xgb_params", "lr_roc_auc", "xgb_roc_auc", "xgb_pr_auc",
                 f"{cfg['naive_name']}_roc_auc"]].round(3).to_string(index=False))
    m = oof["fold"].notna().to_numpy()
    yy, groups = y[m], lab.loc[m, "account_id"].to_numpy()
    pooled = {}
    for name in ("lr", "xgb"):
        p = oof.loc[m, name].to_numpy(float)
        mt = metrics(yy, p)
        lo, hi = cluster_bootstrap_ci(yy, p, groups, roc_auc_score)
        mt["roc_auc_ci95"] = [lo, hi]
        pooled[name] = mt
    naive = cfg["naive"](lab)[m]
    pooled["naive"] = dict(name=cfg["naive_name"], roc_auc=float(roc_auc_score(yy, naive)),
                           pr_auc=float(average_precision_score(yy, naive)))
    deployed = "xgb" if pooled["xgb"]["pr_auc"] >= pooled["lr"]["pr_auc"] else "lr"   # pre-specified rule
    pooled["deployed"] = deployed
    print(f"  pooled OOF  LR  AUC {pooled['lr']['roc_auc']:.3f} (PR {pooled['lr']['pr_auc']:.3f}) | "
          f"XGB AUC {pooled['xgb']['roc_auc']:.3f} [{pooled['xgb']['roc_auc_ci95'][0]:.3f}, {pooled['xgb']['roc_auc_ci95'][1]:.3f}] "
          f"(PR {pooled['xgb']['pr_auc']:.3f}) | naive {pooled['naive']['roc_auc']:.3f} | base {yy.mean():.3%} | deployed={deployed}")

    # naive random-row split (what you would get WITHOUT time-based validation)
    skf = StratifiedKFold(5, shuffle=True, random_state=SEED)
    pr = np.zeros(len(lab))
    for tr, te in skf.split(Xlab, y):
        pr[te] = make_xgb(3, 300).fit(Xlab[tr], y[tr]).predict_proba(Xlab[te])[:, 1]
    pooled["random_row_split_xgb_roc_auc"] = float(roc_auc_score(y, pr))
    print(f"  random-row split XGB AUC (leaky, for comparison only): {pooled['random_row_split_xgb_roc_auc']:.3f}")

    # calibration of the deployed model on pooled OOF
    pdep = oof.loc[m, deployed].to_numpy(float)
    slope, icpt = calibration_slope(yy, pdep)
    rel = reliability_table(yy, pdep)
    rel.to_csv(f"{DOCS}/reliability_{tgt}.csv", index=False)
    pooled["calibration_slope"], pooled["calibration_intercept"] = slope, icpt
    print(f"  calibration slope {slope:.2f} intercept {icpt:.2f}  (1.0 / 0.0 = perfect)")
    results[tgt] = dict(pooled=pooled, folds=folds.to_dict(orient="records"))
    oof_all[f"{tgt}_p_lr"] = oof["lr"]; oof_all[f"{tgt}_p_xgb"] = oof["xgb"]; oof_all[f"{tgt}_fold"] = oof["fold"]

    # ---- final model on ALL labeled snapshots, params tuned on an inner purged split
    prm, _ = tune_xgb(Xlab, y, lab["snapshot_date"], purge)
    base_rate = float(y.mean())
    if deployed == "xgb":
        model = make_xgb(**prm).fit(Xlab, y)
        p_score = model.predict_proba(Xscore.to_numpy())[:, 1]
    else:
        model = make_lr(NUM_FEATURES, CAT_FEATURES).fit(lab[NUM_FEATURES + CAT_FEATURES], y)
        p_score = model.predict_proba(score_set[NUM_FEATURES + CAT_FEATURES])[:, 1]
    xgb_final = make_xgb(**prm).fit(Xlab, y)          # always keep an XGB for SHAP
    # Platt recalibration learned on out-of-time predictions only (monotone: ranking unchanged)
    z = np.log(np.clip(p_score, 1e-6, 1 - 1e-6) / (1 - np.clip(p_score, 1e-6, 1 - 1e-6)))
    p_cal = 1 / (1 + np.exp(-(slope * z + icpt)))
    final[tgt] = dict(model=model, xgb=xgb_final, params=prm, base_rate=base_rate, p_score=p_cal, p_raw=p_score,
                      deployed=deployed, cal=(slope, icpt))
    joblib.dump(dict(model=model, xgb=xgb_final, columns=xcols, num=NUM_FEATURES, cat=CAT_FEATURES, params=prm,
                     base_rate=base_rate, deployed=deployed, calibration=dict(slope=slope, intercept=icpt)),
                f"{MODELS}/{tgt}_model.joblib")
    results[tgt]["final_params"] = prm

# ---------------------------------------------------------------- cross-model overlap (the former "zero overlap" artifact)
print("\n=== CROSS-MODEL OVERLAP (churn x expansion) ===")
m = oof_all["churn_fold"].notna().to_numpy()
oo = oof_all[m].copy()
dep_c, dep_e = results["churn"]["pooled"]["deployed"], results["expansion"]["pooled"]["deployed"]
oo["pc"], oo["pe"] = oo[f"churn_p_{dep_c}"], oo[f"expansion_p_{dep_e}"]
rho = float(oo[["pc", "pe"]].corr(method="spearman").iloc[0, 1])
tc, te_ = oo["pc"].quantile(0.8), oo["pe"].quantile(0.8)
hc, he = oo["pc"] >= tc, oo["pe"] >= te_
joint, exp_joint = float((hc & he).mean()), float(hc.mean() * he.mean())
quad = pd.DataFrame({"quadrant": np.select([hc & he, hc & ~he, ~hc & he], ["Save & grow", "Protect", "Grow"], "Maintain"),
                     "y_churn": oo["y_churn_90d"], "y_exp": oo["y_expansion_90d"]})
qt = quad.groupby("quadrant").agg(snapshots=("y_churn", "size"), churn_rate=("y_churn", "mean"), expansion_rate=("y_exp", "mean")).round(4)
print(f"  Spearman(churn score, expansion score) = {rho:.3f}")
print(f"  top-20% on BOTH: {joint:.2%} of snapshots vs {exp_joint:.2%} expected if independent")
print(qt.to_string())
results["overlap"] = dict(spearman=rho, joint_top20_share=joint, expected_if_independent=exp_joint,
                          quadrants=qt.reset_index().to_dict(orient="records"))

# ---------------------------------------------------------------- score the live book, tiers, $ exposure, SHAP drivers
print("\nscoring live book @", CUTOFF.date())
sc = score_set[["account_id", "snapshot_date", "arr", "account_tier", "industry", "size_band", "region",
                "months_to_renewal", "tenure_months"] + NUM_FEATURES[3:]].copy()
sc = sc.loc[:, ~sc.columns.duplicated()]
sc["churn_prob_90d"] = final["churn"]["p_score"]
sc["expansion_prob_90d"] = final["expansion"]["p_score"]
bc, be = final["churn"]["base_rate"], final["expansion"]["base_rate"]
tier = lambda p, b: np.where(p >= 2 * b, "High", np.where(p >= b, "Medium", "Low"))
sc["churn_tier"], sc["expansion_tier"] = tier(sc["churn_prob_90d"], bc), tier(sc["expansion_prob_90d"], be)
ev = E[E["event_type"].str.startswith("Expansion")].merge(A[["account_id", "account_tier"]], on="account_id")
ev["uplift"] = ev["mrr_change"] / (ev["mrr_after"] - ev["mrr_change"])
uplift_by_tier = ev.groupby("account_tier")["uplift"].mean().to_dict()
sc["expected_uplift_pct"] = sc["account_tier"].map(uplift_by_tier).fillna(ev["uplift"].mean())
sc["expected_arr_loss_90d"] = sc["churn_prob_90d"] * sc["arr"]
sc["expected_expansion_arr_90d"] = sc["expansion_prob_90d"] * sc["expected_uplift_pct"] * sc["arr"]
hi_c, hi_e = sc["churn_tier"] == "High", sc["expansion_tier"] == "High"
sc["quadrant"] = np.select([hi_c & hi_e, hi_c, hi_e], ["Save & grow", "Protect", "Grow"], "Maintain")

# SHAP drivers (XGB, per account), categorical dummies aggregated back to their variable
def shap_long(tgt, label):
    xg = final[tgt]["xgb"]
    sv = shap.TreeExplainer(xg).shap_values(Xscore.to_numpy())
    cols = np.array(xcols)
    base_of = np.array([next((c for c in CAT_FEATURES if col.startswith(c + "_")), col) for col in cols])
    agg = pd.DataFrame(sv, columns=cols).T.groupby(base_of).sum().T
    glob = agg.abs().mean().sort_values(ascending=False)
    rows = []
    for i, aid in enumerate(score_set["account_id"].to_numpy()):
        top = agg.iloc[i].reindex(agg.iloc[i].abs().sort_values(ascending=False).index)[:5]
        for r, (f, v) in enumerate(top.items(), 1):
            val = score_set.iloc[i][f] if f in score_set.columns else np.nan
            rows.append(dict(account_id=aid, model=label, rank=r, feature=f, label=FEATURE_LABELS.get(f, f),
                             value=val, shap=float(v), direction="raises" if v > 0 else "lowers"))
    return pd.DataFrame(rows), glob

sh_c, g_c = shap_long("churn", "churn")
sh_e, g_e = shap_long("expansion", "expansion")
pd.concat([sh_c, sh_e]).to_csv(f"{EXPORTS}/account_drivers_shap.csv", index=False)
pd.DataFrame({"feature": g_c.index, "label": [FEATURE_LABELS.get(f, f) for f in g_c.index], "mean_abs_shap": g_c.values}) \
    .to_csv(f"{DOCS}/shap_global_churn.csv", index=False)
pd.DataFrame({"feature": g_e.index, "label": [FEATURE_LABELS.get(f, f) for f in g_e.index], "mean_abs_shap": g_e.values}) \
    .to_csv(f"{DOCS}/shap_global_expansion.csv", index=False)
print("  top churn drivers    :", ", ".join(f"{FEATURE_LABELS.get(f, f)}" for f in g_c.index[:6]))
print("  top expansion drivers:", ", ".join(f"{FEATURE_LABELS.get(f, f)}" for f in g_e.index[:6]))

# internal check: do scores track the hidden generator drivers? (never shown to users, stays in docs/_internal)
gtp = f"{DOCS}/_ground_truth_latents_monthly.csv"
if os.path.exists(gtp):
    gt = pd.read_csv(gtp, parse_dates=["month_end"])
    gt = gt[gt["month_end"] == CUTOFF][["account_id", "H_health", "G_growth"]]
    chk = sc.merge(gt, on="account_id")
    results["internal_validation_vs_hidden_drivers"] = dict(
        spearman_churn_score_vs_minus_H=float(chk[["churn_prob_90d", "H_health"]].corr(method="spearman").iloc[0, 1] * -1),
        spearman_expansion_score_vs_G=float(chk[["expansion_prob_90d", "G_growth"]].corr(method="spearman").iloc[0, 1]),
        spearman_expansion_score_vs_H=float(chk[["expansion_prob_90d", "H_health"]].corr(method="spearman").iloc[0, 1]),
        corr_H_G_live_book=float(chk[["H_health", "G_growth"]].corr().iloc[0, 1]))
    print("  internal validation vs hidden drivers:", json.dumps(results["internal_validation_vs_hidden_drivers"]))

sc.to_csv(f"{EXPORTS}/account_scores.csv", index=False)
oof_all.to_csv(f"{EXPORTS}/oof_predictions_accounts.csv", index=False)
summ = dict(
    active_accounts=int(len(sc)), active_arr=float(sc["arr"].sum()),
    churn_high_n=int(hi_c.sum()), churn_high_arr=float(sc.loc[hi_c, "arr"].sum()),
    expected_arr_loss_90d=float(sc["expected_arr_loss_90d"].sum()),
    expansion_high_n=int(hi_e.sum()), expansion_high_arr=float(sc.loc[hi_e, "arr"].sum()),
    expected_expansion_arr_90d=float(sc["expected_expansion_arr_90d"].sum()),
    quadrant_counts=sc["quadrant"].value_counts().to_dict(),
    churn_base_rate_90d=bc, expansion_base_rate_90d=be, uplift_by_tier=uplift_by_tier)
results["live_book"] = summ
print("\nlive book:", json.dumps(summ, indent=1, default=float))
json.dump(results, open(f"{DOCS}/results_churn_expansion.json", "w"), indent=2, default=float)
print("saved results_churn_expansion.json")
