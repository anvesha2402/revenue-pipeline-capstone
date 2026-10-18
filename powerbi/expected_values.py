"""Re-computes every headline measure in pandas, following the same logic as the DAX, for several filter settings.
Output: validation/expected_values.csv and a printed table. These are the numbers the Power BI cards must show."""
import json, os
import numpy as np, pandas as pd

D = "data"
rd = lambda n, **k: pd.read_csv(f"{D}/{n}.csv", **k)
dim_region, dim_ind = rd("dim_region"), rd("dim_industry")
acc, arr, hl, drv = rd("dim_account", parse_dates=["customer_since"]), rd("fact_arr_monthly", parse_dates=["month_end_date"]), rd("fact_account_health", parse_dates=["renewal_date"]), rd("fact_driver")
opp = rd("fact_opportunity", parse_dates=["created_date", "closed_date"])
lead = rd("fact_lead")
sc = rd("ref_model_scorecard"); lb = rd("ref_lead_bands")
ASOF = pd.Timestamp("2026-06-30")

def run(region=None, industry=None, tier=None, segment=None):
    a = acc.copy()
    o, l = opp.copy(), lead.copy()
    if region:
        k = int(dim_region.loc[dim_region.region == region, "region_key"].iloc[0]); a = a[a.region_key == k]; o = o[o.region_key == k]; l = l[l.region_key == k]
    if industry:
        k = int(dim_ind.loc[dim_ind.industry == industry, "industry_key"].iloc[0]); a = a[a.industry_key == k]; o = o[o.industry_key == k]; l = l[l.industry_key == k]
    if tier: a = a[a.account_tier == tier]
    if segment: a = a[a.segment == segment]
    ids = set(a.account_id)
    f = arr[arr.account_id.isin(ids)]; h = hl[hl.account_id.isin(ids)]
    r = {}
    # pipeline (not affected by tier / segment)
    op = o[o.outcome == "Open"]
    r["Open Pipeline"] = op.deal_size.sum(); r["Open Deals"] = len(op)
    r["Avg Open Deal Size"] = op.deal_size.mean()
    st = ASOF - pd.DateOffset(months=12)
    cl = o[o.outcome.isin(["Won", "Lost"]) & (o.closed_date > st) & (o.closed_date <= ASOF)]
    won = cl[cl.outcome == "Won"]
    r["Won Deals 12M"] = len(won); r["Closed Deals 12M"] = len(cl); r["Win Rate 12M"] = len(won) / len(cl)
    r["Avg Sales Cycle Days"] = won.sales_cycle_days.mean()
    r["Pipeline Velocity per Day"] = r["Open Deals"] * r["Avg Open Deal Size"] * r["Win Rate 12M"] / r["Avg Sales Cycle Days"]
    r["Weighted Pipeline Flat"] = r["Open Pipeline"] * r["Win Rate 12M"]
    r["Weighted Pipeline Model"] = (op.deal_size * op.model_win_prob).sum()
    r["Stalled Pipeline"] = op[op.is_stalled == 1].deal_size.sum(); r["Stalled Deals"] = int((op.is_stalled == 1).sum())
    r["Stalled Share"] = r["Stalled Pipeline"] / r["Open Pipeline"]
    c = o[o.outcome.isin(["Won", "Lost"])]
    r["Win Rate All Closed"] = (c.outcome == "Won").mean()
    # funnel
    r["Leads"] = len(l); r["Opportunities"] = int(l.became_opportunity.sum()); r["Reached Discovery"] = int(l.reached_discovery.sum())
    r["Reached Proposal"] = int(l.reached_proposal.sum()); r["Reached Negotiation"] = int(l.reached_negotiation.sum()); r["Closed Won Leads"] = int(l.closed_won.sum())
    # revenue
    last = f[f.month_end_date == ASOF]
    r["ARR"] = last.arr_end.sum(); r["Customers"] = int((last.arr_end > 0).sum())
    s0 = pd.Timestamp("2025-06-30")
    start = f[f.month_end_date == s0].set_index("account_id").arr_end
    now = last.set_index("account_id").arr_end
    r["ARR 12M Ago"] = start.sum()
    w = f[(f.month_end_date > s0) & (f.month_end_date <= ASOF)]
    r["New ARR 12M"] = w.new_arr.sum(); r["Expansion ARR 12M"] = w.expansion_arr.sum(); r["Contraction ARR 12M"] = w.contraction_arr.sum(); r["Churned ARR 12M"] = w.churn_arr.sum()
    r["Bridge check (start+movements-end)"] = r["ARR 12M Ago"] + r["New ARR 12M"] + r["Expansion ARR 12M"] + r["Contraction ARR 12M"] + r["Churned ARR 12M"] - r["ARR"]
    coh = start[start > 0].index
    n = now.reindex(coh).fillna(0); s = start[coh]
    r["Net Revenue Retention 12M"] = n.sum() / s.sum(); r["Gross Revenue Retention 12M"] = np.minimum(n, s).sum() / s.sum(); r["Logo Retention 12M"] = (n > 0).mean()
    # risk
    r["Expected ARR Loss 90D"] = h.expected_loss_90d.sum(); r["Expected Expansion 90D"] = h.expected_expansion_90d.sum()
    r["Scored ARR"] = h.arr_scored.sum(); r["Scored Accounts"] = int((h.is_scored == 1).sum())
    r["Scored Share of ARR"] = r["Scored ARR"] / r["ARR"]
    hh = h.merge(a[["account_id", "churn_risk", "expansion_potential"]], on="account_id")
    r["High Churn Risk Accounts"] = int((hh.churn_risk == "High").sum()); r["High Churn Risk ARR"] = hh[hh.churn_risk == "High"].arr.sum()
    r["High Expansion Accounts"] = int((hh.expansion_potential == "High").sum()); r["High Expansion ARR"] = hh[hh.expansion_potential == "High"].arr.sum()
    r["ARR Renewing Next 90D"] = h[h.renews_within_90d == 1].arr.sum()
    r["Avg Churn Probability"] = h.churn_prob_90d.mean()
    return r

scen = {"No filters": {}, "Region = EMEA": dict(region="EMEA"), "Region = APAC, Industry = SaaS": dict(region="APAC", industry="SaaS"),
        "Plan Tier = Enterprise": dict(tier="Enterprise"), "Segment = Protect": dict(segment="Protect")}
res = {k: run(**v) for k, v in scen.items()}
tab = pd.DataFrame(res)
os.makedirs("validation", exist_ok=True)
tab.round(4).to_csv("validation/expected_values.csv")
scal = {"Churn Model AUC": float(sc.loc[sc.model_name == "Churn (90-day)", "roc_auc"].iloc[0]),
        "Expansion Model AUC": float(sc.loc[sc.model_name == "Expansion (90-day)", "roc_auc"].iloc[0]),
        "Deal Win Model AUC": float(sc.loc[sc.model_name == "Deal-win", "roc_auc"].iloc[0]),
        "Lead Score Lift": float(lb.loc[lb.band_order == 1, "conversion_rate"].iloc[0] / lb.loc[lb.band_order == 5, "conversion_rate"].iloc[0])}
json.dump(scal, open("validation/expected_model_cards.json", "w"), indent=1)
pd.set_option("display.float_format", lambda x: f"{x:,.4f}"); pd.set_option("display.width", 250)
print(tab); print(scal)
# cross-check against the independent Streamlit KPIs
k = json.load(open("../exports/dashboard_kpis.json"))
t = res["No filters"]
chk = {"Open Pipeline": k["open_pipeline"], "Open Deals": k["open_opportunities"], "Win Rate 12M": k["win_rate_12m"], "Avg Sales Cycle Days": k["avg_won_cycle_days"],
       "Pipeline Velocity per Day": k["pipeline_velocity_usd_per_day"], "Weighted Pipeline Flat": k["weighted_open_pipeline"], "Stalled Pipeline": k["stalled_pipeline"],
       "Net Revenue Retention 12M": k["net_revenue_retention_12m"], "Gross Revenue Retention 12M": k["gross_revenue_retention_12m"], "Logo Retention 12M": k["logo_retention_12m"],
       "Scored ARR": k["active_arr"], "Expected ARR Loss 90D": k["expected_arr_loss_next_90d"], "Expected Expansion 90D": k["expected_expansion_arr_next_90d"],
       "High Churn Risk Accounts": k["high_churn_risk_accounts"], "High Churn Risk ARR": k["high_churn_risk_arr"], "High Expansion Accounts": k["high_expansion_accounts"],
       "High Expansion ARR": k["high_expansion_arr"], "Scored Accounts": k["active_accounts"]}
print("\ncross-check vs Streamlit KPIs (max relative diff):")
for kk, v in chk.items():
    print(f"  {kk:32s} pbi {t[kk]:>16,.4f}  streamlit {v:>16,.4f}  rel diff {abs(t[kk]-v)/abs(v):.2e}")
