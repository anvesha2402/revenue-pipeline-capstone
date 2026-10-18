#!/usr/bin/env python3
"""
06_export_powerbi.py - exports the star schema for Power BI (CSV files in powerbi/data).

Star schema
  Dimensions : dim_date, dim_region, dim_industry, dim_account, dim_rep, dim_stage
  Facts      : fact_arr_monthly (account x month-end ARR and ARR movements)
               fact_account_health (one row per active account: model scores at the as-of date)
               fact_driver (top-5 score drivers per scored account and model)
               fact_opportunity (one row per deal)
               fact_lead (one row per lead, with funnel flags)
  Reference  : ref_model_scorecard, ref_lead_bands, ref_funnel, ref_bridge (small lookup tables used by charts)
"""
import json
import os

import joblib
import numpy as np
import pandas as pd

CLEAN, EXPORTS, DOCS, MODELS = "data/clean", "exports", "docs", "models"
OUT = "powerbi/data"
os.makedirs(OUT, exist_ok=True)
AS_OF = pd.Timestamp("2026-06-30")

A = pd.read_csv(f"{CLEAN}/accounts.csv", parse_dates=["start_date"])
S = pd.read_csv(f"{CLEAN}/subscriptions.csv", parse_dates=["start_date", "renewal_date", "churn_date"])
E = pd.read_csv(f"{CLEAN}/subscription_events.csv", parse_dates=["event_date"])
L = pd.read_csv(f"{CLEAN}/leads.csv", parse_dates=["created_date"])
O = pd.read_csv(f"{CLEAN}/opportunities.csv", parse_dates=["created_date", "qualified_date", "discovery_date",
                                                           "proposal_date", "negotiation_date", "closed_date"])
H = pd.read_csv(f"{EXPORTS}/dashboard_account_health.csv", parse_dates=["start_date", "renewal_date"])
SH = pd.read_csv(f"{EXPORTS}/account_drivers_shap.csv")
SC = pd.read_csv(f"{EXPORTS}/model_scorecard.csv")
LQ = pd.read_csv(f"{EXPORTS}/lead_quintiles.csv")
DW = pd.read_csv(f"{EXPORTS}/stage_dwell.csv").set_index("stage")


def save(df, name):
    df.to_csv(f"{OUT}/{name}.csv", index=False, date_format="%Y-%m-%d")
    print(f"  {name:22s} {len(df):>7,} rows  {df.shape[1]} cols")


# ------------------------------------------------------------------ dimensions
d = pd.DataFrame({"date": pd.date_range("2024-01-01", AS_OF, freq="D")})
d["year"] = d["date"].dt.year
d["quarter"] = "Q" + d["date"].dt.quarter.astype(str)
d["year_quarter"] = d["year"].astype(str) + " " + d["quarter"]
d["month_number"] = d["date"].dt.month
d["month_name"] = d["date"].dt.strftime("%b")
d["month_label"] = d["date"].dt.strftime("%b %Y")
d["year_month_sort"] = d["year"] * 100 + d["month_number"]
d["month_start"] = d["date"].values.astype("datetime64[M]")
d["month_end"] = d["date"] + pd.offsets.MonthEnd(0)
d["is_month_end"] = (d["date"] == d["month_end"]).astype(int)
save(d, "dim_date")

regions = sorted(set(A.region) | set(L.region.dropna()) | set(O.region.dropna()))
dim_region = pd.DataFrame({"region_key": range(1, len(regions) + 1), "region": regions})
rk = dict(zip(dim_region.region, dim_region.region_key))
save(dim_region, "dim_region")

lead_ind = L.set_index("lead_id")["industry"]
O["industry"] = O["lead_id"].map(lead_ind).fillna("Unknown")
inds = sorted(set(A.industry) | set(L.industry.dropna()) | set(O.industry))
dim_industry = pd.DataFrame({"industry_key": range(1, len(inds) + 1), "industry": inds})
ik = dict(zip(dim_industry.industry, dim_industry.industry_key))
save(dim_industry, "dim_industry")

reps = sorted(O.sales_rep_id.unique())
dim_rep = pd.DataFrame({"rep_key": range(1, len(reps) + 1), "sales_rep": reps})
rpk = dict(zip(dim_rep.sales_rep, dim_rep.rep_key))
save(dim_rep, "dim_rep")

stages = ["Qualified", "Discovery", "Proposal", "Negotiation", "Closed Won", "Closed Lost"]
dim_stage = pd.DataFrame({"stage_key": range(1, 7), "stage": stages, "stage_order": range(1, 7),
                          "stage_group": ["Open"] * 4 + ["Won", "Lost"]})
sk = dict(zip(dim_stage.stage, dim_stage.stage_key))
save(dim_stage, "dim_stage")

# ------------------------------------------------------------------ ARR monthly fact (from the subscription event log)
E = E.sort_values(["account_id", "event_date"]).copy()
E["arr_change"] = (E["mrr_after"] - E.groupby("account_id")["mrr_after"].shift(1).fillna(0.0)) * 12   # consistent with the running MRR
E["kind"] = np.select([E.event_type == "New", E.event_type.str.startswith("Expansion"), E.event_type == "Contraction",
                       E.event_type == "Churn"], ["new_arr", "expansion_arr", "contraction_arr", "churn_arr"], "other")
assert (E.kind != "other").all()
E["month_end"] = E["event_date"] + pd.offsets.MonthEnd(0)
mv = E.pivot_table(index=["account_id", "month_end"], columns="kind", values="arr_change", aggfunc="sum", fill_value=0.0).reset_index()
for c in ["new_arr", "expansion_arr", "contraction_arr", "churn_arr"]:
    if c not in mv:
        mv[c] = 0.0
mv["net_change"] = mv[["new_arr", "expansion_arr", "contraction_arr", "churn_arr"]].sum(axis=1)
first = mv.groupby("account_id")["month_end"].min()
churn_m = mv[mv.churn_arr != 0].groupby("account_id")["month_end"].min()
rows = []
last_month = AS_OF + pd.offsets.MonthEnd(0)
for acc, g in mv.groupby("account_id"):
    end = churn_m.get(acc, last_month)
    grid = pd.DataFrame({"month_end": pd.date_range(first[acc], end, freq="ME")})
    g = grid.merge(g.drop(columns="account_id"), on="month_end", how="left").fillna(0.0)
    g["account_id"] = acc
    g["arr_end"] = g["net_change"].cumsum()
    rows.append(g)
F = pd.concat(rows, ignore_index=True)
F["arr_end"] = F["arr_end"].round(2).clip(lower=0)
F.loc[F["arr_end"].abs() < 0.005, "arr_end"] = 0.0
for c in ["new_arr", "expansion_arr", "contraction_arr", "churn_arr"]:
    F[c] = F[c].round(2)
F = F[F.month_end <= AS_OF][["account_id", "month_end", "arr_end", "new_arr", "expansion_arr", "contraction_arr", "churn_arr"]]
# reconcile against the event log's own running MRR
chk = E[E.event_date <= AS_OF].groupby("account_id").tail(1).set_index("account_id")["mrr_after"] * 12
now = F[F.month_end == AS_OF].set_index("account_id")["arr_end"]
assert abs(now.sum() - chk.sum()) < 1, (now.sum(), chk.sum())
save(F.rename(columns={"month_end": "month_end_date"}), "fact_arr_monthly")

# ------------------------------------------------------------------ account health snapshot
arr_now = chk.rename("arr_now")
S2 = S.set_index("account_id")
active_ids = S.loc[S.status == "Active", "account_id"]
Hs = H.set_index("account_id")
rows = []
for acc in active_ids:
    r = S2.loc[acc]
    a = float(arr_now.get(acc, 0.0))
    scored = acc in Hs.index
    renew = r["renewal_date"]
    if scored:
        h = Hs.loc[acc]
        assert abs(h["arr"] - a) < 0.5, (acc, h["arr"], a)
        rows.append(dict(account_id=acc, as_of_date=AS_OF, is_scored=1, arr_now=a, renewal_date=renew,
                         months_to_renewal=h["months_to_renewal"], churn_prob_90d=h["churn_prob_90d"],
                         expected_loss_90d=h["expected_arr_loss_90d"], expansion_prob_90d=h["expansion_prob_90d"],
                         expected_expansion_90d=h["expected_expansion_arr_90d"], login_rate_3m=h["login_3m"],
                         features_adopted_3m=h["feat_3m"], seat_utilization_3m=h["util_3m"], tickets_90d=h["tickets_90d"],
                         csat_90d=h["csat_90d"], integrations=h["integrations"], seats=h["seats"]))
    else:
        rows.append(dict(account_id=acc, as_of_date=AS_OF, is_scored=0, arr_now=a, renewal_date=renew,
                         months_to_renewal=(renew - AS_OF).days / 30.4375))
FH = pd.DataFrame(rows)
FH["renews_within_90d"] = ((FH.renewal_date > AS_OF) & (FH.renewal_date <= AS_OF + pd.Timedelta(days=90))).astype(int)
FH["arr_scored"] = np.where(FH.is_scored == 1, FH.arr_now, 0.0)
FH = FH.rename(columns={"arr_now": "arr"})
save(FH, "fact_account_health")

# ------------------------------------------------------------------ dim_account (descriptive + current-state attributes)
da = A[["account_id", "company_name", "account_tier", "size_band", "csm_id", "start_date", "region", "industry"]].copy()
da = da.merge(S[["account_id", "status", "churn_date", "churn_reason"]], on="account_id", how="left")
da["region_key"] = da.region.map(rk)
da["industry_key"] = da.industry.map(ik)
hh = H.set_index("account_id")
da["segment"] = np.where(da.status == "Churned", "Churned", da.account_id.map(hh["quadrant"]))
da["segment"] = da["segment"].fillna("New (not yet scored)")
da["churn_risk"] = np.where(da.status == "Churned", "Churned", da.account_id.map(hh["churn_tier"]))
da["churn_risk"] = da["churn_risk"].fillna("Not scored")
da["expansion_potential"] = np.where(da.status == "Churned", "Churned", da.account_id.map(hh["expansion_tier"]))
da["expansion_potential"] = da["expansion_potential"].fillna("Not scored")
da["customer_status"] = da["status"]
da = da.rename(columns={"start_date": "customer_since"})
da["tier_order"] = da["account_tier"].map({"Starter": 1, "Growth": 2, "Enterprise": 3})
da["segment_order"] = da["segment"].map({"Protect": 1, "Grow": 2, "Save & grow": 3, "Maintain": 4, "New (not yet scored)": 5, "Churned": 6})
assert da[["tier_order", "segment_order"]].notna().all().all()
# company names repeat across accounts (175 active accounts share a name), so tables and drill-downs use a unique label
da["customer_label"] = da["company_name"] + " (" + da["account_id"] + ")"
assert da["customer_label"].is_unique
da = da[["account_id", "company_name", "customer_label", "account_tier", "tier_order", "size_band", "csm_id", "customer_since", "customer_status", "churn_date",
         "churn_reason", "segment", "segment_order", "churn_risk", "expansion_potential", "region_key", "industry_key"]]
save(da, "dim_account")

# ------------------------------------------------------------------ drivers
dr = SH.copy()
dr["model"] = dr["model"].map({"churn": "Churn", "expansion": "Expansion"})
dr["direction"] = dr["direction"].map({"raises": "Raises the score", "lowers": "Lowers the score"})
dr = dr.rename(columns={"label": "driver", "shap": "impact"})[["account_id", "model", "rank", "driver", "impact", "direction"]]
dr["impact"] = dr["impact"].round(4)
save(dr, "fact_driver")

# ------------------------------------------------------------------ opportunities
OP = O.copy()
STG = ["qualified_date", "discovery_date", "proposal_date", "negotiation_date"]
OP["stage_name"] = OP["stage"]
OP["is_open"] = (OP["outcome"] == "Open").astype(int)
cur_col = {"Qualified": "qualified_date", "Discovery": "discovery_date", "Proposal": "proposal_date", "Negotiation": "negotiation_date"}
days = []
for _, r in OP.iterrows():
    if r["outcome"] == "Open" and r["stage"] in cur_col and pd.notna(r[cur_col[r["stage"]]]):
        days.append((AS_OF - r[cur_col[r["stage"]]]).days)
    else:
        days.append(np.nan)
OP["days_in_stage"] = days
OP["stage_p75_days"] = OP["stage"].map(DW["p75_days"])
OP["is_stalled"] = ((OP.is_open == 1) & (OP.days_in_stage > OP.stage_p75_days)).astype(int)
OP["sales_cycle_days"] = np.where(OP.outcome == "Won", (OP.closed_date - OP.created_date).dt.days, np.nan)
OP["competitor"] = np.where(OP.competitor_present == 1, "Competitor present", "No competitor")
# model win probability for OPEN deals (the saved deal-win model, applied to deals still open)
mdl = joblib.load(f"{MODELS}/deal_win_model.joblib")
lead_attr = L.set_index("lead_id")[["demo_requested", "engagement_score", "lead_source", "contact_seniority"]]
X = OP[OP.is_open == 1].merge(lead_attr, left_on="lead_id", right_index=True, how="left")
for c in ["lead_source", "contact_seniority"]:
    X[c] = X[c].fillna("Unknown")
X["demo_requested"] = X["demo_requested"].fillna(0)
X["log_deal_size"] = np.log(X["deal_size"])
X["deal_size_imputed"] = X["deal_size_imputed"].astype(float)
num_d = ["log_deal_size", "competitor_present", "decision_makers_engaged", "decision_makers_missing", "deal_size_imputed",
         "demo_requested", "engagement_score"]
cat_d = ["lead_source", "contact_seniority", "size_band", "industry", "region", "sales_rep_id"]
Xd = pd.get_dummies(X[num_d + cat_d], columns=cat_d, dtype=float).reindex(columns=mdl["columns"], fill_value=0.0)
p = mdl["model"].predict_proba(Xd.to_numpy())[:, 1]
OP["model_win_prob"] = np.nan
OP.loc[X.index, "model_win_prob"] = p
print(f"  open-deal model win probability: mean {p.mean():.3f}  (closed-deal win rate {(O.outcome=='Won').sum()/O.outcome.isin(['Won','Lost']).sum():.3f})")
FO = pd.DataFrame({
    "opportunity_id": OP.opportunity_id, "created_date": OP.created_date, "closed_date": OP.closed_date,
    "region_key": OP.region.map(rk), "industry_key": OP.industry.map(ik), "rep_key": OP.sales_rep_id.map(rpk),
    "stage_key": OP.stage.map(sk), "outcome": OP.outcome, "deal_size": OP.deal_size, "discount_pct": OP.discount_pct,
    "competitor": OP.competitor, "decision_makers_engaged": OP.decision_makers_engaged, "rep_forecast_pct": OP.rep_forecast_pct,
    "loss_reason": OP.loss_reason, "days_in_stage": OP.days_in_stage, "stage_p75_days": np.where(OP.is_open == 1, OP.stage_p75_days, np.nan),
    "is_stalled": OP.is_stalled, "sales_cycle_days": OP.sales_cycle_days, "model_win_prob": OP.model_win_prob.round(4)})
FO["deal_label"] = OP["opportunity_id"] + " | " + OP["sales_rep_id"] + " | " + OP["region"]
save(FO, "fact_opportunity")

# ------------------------------------------------------------------ leads with funnel flags (lead-cohort funnel)
reach = pd.DataFrame({"lead_id": OP.lead_id})
rank = np.select([OP.outcome.eq("Won"), OP.negotiation_date.notna(), OP.proposal_date.notna(), OP.discovery_date.notna()],
                 [5, 4, 3, 2], 1)       # 1 qualified, 2 discovery, 3 proposal, 4 negotiation, 5 closed won
reach["furthest"] = rank
reach = reach.dropna(subset=["lead_id"]).groupby("lead_id")["furthest"].max()
FL = L[["lead_id", "created_date", "region", "industry", "lead_source", "contact_seniority", "demo_requested", "engagement_score"]].copy()
FL["furthest"] = FL.lead_id.map(reach).fillna(0).astype(int)
FL["became_opportunity"] = (FL.furthest >= 1).astype(int)
FL["reached_discovery"] = (FL.furthest >= 2).astype(int)
FL["reached_proposal"] = (FL.furthest >= 3).astype(int)
FL["reached_negotiation"] = (FL.furthest >= 4).astype(int)
FL["closed_won"] = (FL.furthest >= 5).astype(int)
FL["region_key"] = FL.region.map(rk)
FL["industry_key"] = FL.industry.map(ik)
FL["demo_requested"] = FL["demo_requested"].fillna(0).astype(int)
FL = FL[["lead_id", "created_date", "region_key", "industry_key", "lead_source", "contact_seniority", "demo_requested", "engagement_score",
         "became_opportunity", "reached_discovery", "reached_proposal", "reached_negotiation", "closed_won"]]
save(FL, "fact_lead")

# ------------------------------------------------------------------ reference tables
sc = SC.rename(columns={"model": "model_name", "target": "predicts", "algorithm_deployed": "algorithm", "roc_auc": "roc_auc",
                        "roc_auc_ci_low": "roc_auc_low", "roc_auc_ci_high": "roc_auc_high", "top10pct_lift": "top10_lift"})
save(sc[["model_name", "predicts", "validation", "algorithm", "roc_auc", "roc_auc_low", "roc_auc_high", "base_rate", "top10_lift", "n_scored"]],
     "ref_model_scorecard")
lq = LQ.copy()
lq["band_order"] = range(1, len(lq) + 1)
lq = lq.rename(columns={"q": "score_band"})
save(lq, "ref_lead_bands")
save(pd.DataFrame({"step_order": range(1, 7), "step": ["Leads", "Became an opportunity", "Reached Discovery", "Reached Proposal",
                                                        "Reached Negotiation", "Closed won"]}), "ref_funnel")
save(pd.DataFrame({"step_order": range(1, 6), "step": ["Starting ARR (12 months ago)", "New customers", "Expansion", "Contraction", "Churn"]}),
     "ref_bridge")
print("done")
