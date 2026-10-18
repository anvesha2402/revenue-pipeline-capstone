"""
Revenue Pipeline Capstone - Streamlit dashboard (v2)

Reads only pre-computed files from ../exports (no model is run inside the app), so it starts fast and
needs just streamlit, pandas, numpy and matplotlib. All data is synthetic.
"""
import json
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

BASE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(BASE, "..", "exports")

st.set_page_config(page_title="Revenue Pipeline Capstone", page_icon=None, layout="wide")

BLUE, ORANGE, AQUA, INK, INK2, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#0b0b0b", "#52514e", "#e1e0d9"
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#c3c2b7",
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.facecolor": "#fcfcfb",
                     "figure.facecolor": "#fcfcfb", "xtick.color": "#898781", "ytick.color": "#898781",
                     "axes.labelcolor": INK2, "text.color": INK})


def money(x):
    x = float(x)
    if abs(x) >= 1e6:
        return f"${x / 1e6:,.1f}M"
    if abs(x) >= 1e3:
        return f"${x / 1e3:,.0f}K"
    return f"${x:,.0f}"


@st.cache_data
def load():
    k = json.load(open(os.path.join(EXP, "dashboard_kpis.json")))
    acc = pd.read_csv(os.path.join(EXP, "dashboard_account_health.csv"), parse_dates=["start_date", "renewal_date"])
    drv = pd.read_csv(os.path.join(EXP, "account_drivers_shap.csv"))
    stage = pd.read_csv(os.path.join(EXP, "open_pipeline_by_stage.csv"))
    dwell = pd.read_csv(os.path.join(EXP, "stage_dwell.csv"))
    score = pd.read_csv(os.path.join(EXP, "model_scorecard.csv"))
    quint = pd.read_csv(os.path.join(EXP, "lead_quintiles.csv"))
    comp = pd.read_csv(os.path.join(EXP, "stage_funnel_closed_deals.csv"))
    return k, acc, drv, stage, dwell, score, quint, comp


k, acc, drv, stage, dwell, score, quint, comp = load()

st.title("Revenue Pipeline Capstone")
st.caption(f"Five connected models on one synthetic B2B SaaS dataset. Figures as of {k['as_of']}. "
           "All data is simulated: dollar values illustrate the method, they are not market findings.")

# ------------------------------------------------------------------ KPIs
st.subheader("Pipeline")
c = st.columns(5)
c[0].metric("Open pipeline", money(k["open_pipeline"]), f"{k['open_opportunities']} deals", delta_color="off")
c[1].metric("Weighted pipeline", money(k["weighted_open_pipeline"]), "open value x 12-mo win rate", delta_color="off")
c[2].metric("Win rate (12 mo)", f"{k['win_rate_12m']:.0%}")
c[3].metric("Avg sales cycle (won)", f"{k['avg_won_cycle_days']:.0f} days")
c[4].metric("Pipeline velocity", f"{money(k['pipeline_velocity_usd_per_day'])}/day")

st.subheader("Customers")
c = st.columns(5)
c[0].metric("Active ARR", money(k["active_arr"]), f"{k['active_accounts']:,} customers; {k['scored_share_of_arr']:.0%} of ARR scored", delta_color="off")
c[1].metric("Net revenue retention (12 mo)", f"{k['net_revenue_retention_12m']:.0%}",
            f"gross {k['gross_revenue_retention_12m']:.0%}", delta_color="off")
c[2].metric("Expected ARR loss, next 90 days", money(k["expected_arr_loss_next_90d"]),
            f"{k['high_churn_risk_accounts']} high-risk accounts, {money(k['high_churn_risk_arr'])} ARR", delta_color="off")
c[3].metric("Expected expansion, next 90 days", money(k["expected_expansion_arr_next_90d"]),
            f"{k['high_expansion_accounts']} high-propensity accounts", delta_color="off")
q = k["quadrant_counts"]
c[4].metric("Save & grow accounts", f"{q.get('Save & grow', 0)}", "high churn risk and high expansion propensity", delta_color="off")

# ------------------------------------------------------------------ funnel & velocity
st.divider()
left, right = st.columns(2)
with left:
    st.markdown("**Revenue funnel**")
    f = k["funnel"]
    labels = ["Leads (deduplicated)", "Became opportunity", "Closed won", "Active customers today"]
    vals = [f["leads"], f["leads_converted_to_opp"], f["opportunities_won"], f["accounts_active_now"]]
    fig, ax = plt.subplots(figsize=(5.6, 3.2), dpi=150)
    ax.barh(labels[::-1], vals[::-1], color=BLUE, height=0.55)
    for i, v in enumerate(vals[::-1]):
        ax.text(v + max(vals) * 0.01, i, f"{v:,}", va="center", fontsize=9)
    ax.set_xlim(0, max(vals) * 1.15); ax.grid(axis="y", visible=False)
    st.pyplot(fig, clear_figure=True)
with right:
    st.markdown("**Open pipeline by stage: on track vs stalled**")
    st.caption("Stalled = already longer in its stage than 75% of comparable deals took.")
    fig, ax = plt.subplots(figsize=(5.6, 3.2), dpi=150)
    on_track = (stage["open_value"] - stage["stalled_value"]) / 1e6
    stalled = stage["stalled_value"] / 1e6
    y = np.arange(len(stage))
    ax.barh(y, on_track, color=BLUE, height=0.55, label="On track")
    ax.barh(y, stalled, left=on_track + 0.06, color=ORANGE, height=0.55, label="Stalled")
    ax.set_yticks(y, stage["stage"]); ax.invert_yaxis(); ax.set_xlabel("Open deal value ($M)"); ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    st.pyplot(fig, clear_figure=True)

with st.expander("Stage timing and conversion"):
    a, b = st.columns(2)
    d = dwell.copy()
    d.columns = ["Stage", "Deals measured", "Median days", "75th pct days", "Mean days"]
    a.dataframe(d.round(1), hide_index=True, width="stretch")
    cf = comp.copy()
    cf["pct_of_prev"] = (cf["pct_of_prev"] * 100).round(0)
    cf.columns = ["Stage reached (closed deals)", "Deals", "% of previous stage"]
    b.dataframe(cf, hide_index=True, width="stretch")

# ------------------------------------------------------------------ model scorecard
st.divider()
st.subheader("Model scorecard (forward-in-time validation)")
sc = score.copy()
sc["ROC-AUC (95% CI)"] = [f"{r.roc_auc:.3f} ({r.roc_auc_ci_low:.3f}-{r.roc_auc_ci_high:.3f})" for r in sc.itertuples()]
sc["Base rate"] = (sc["base_rate"] * 100).round(1).astype(str) + "%"
sc["Top-10% lift"] = sc["top10pct_lift"].round(1).astype(str) + "x"
sc = sc.rename(columns={"model": "Model", "target": "What it predicts", "validation": "Validation", "algorithm_deployed": "Algorithm"})
st.dataframe(sc[["Model", "What it predicts", "Algorithm", "ROC-AUC (95% CI)", "Base rate", "Top-10% lift", "Validation"]],
             hide_index=True, width="stretch")
st.caption("Each model is trained only on the past and tested on the next period, with a gap so no training label overlaps the "
           "test window. Scores are lower than random-split numbers on purpose.")
lq = quint.copy()
lq["conversion_rate"] = (lq["conversion_rate"] * 100).round(1).astype(str) + "%"
lq.columns = ["Lead score band", "Leads", "Became an opportunity"]
with st.expander("Lead scoring: conversion by score band (out-of-time)"):
    st.dataframe(lq, hide_index=True, width="stretch")

# ------------------------------------------------------------------ account health
st.divider()
st.subheader("Account health")
f1, f2, f3, f4 = st.columns(4)
tiers = f1.multiselect("Plan tier", sorted(acc["account_tier"].unique()))
regions = f2.multiselect("Region", sorted(acc["region"].unique()))
quads = f3.multiselect("Segment", ["Protect", "Grow", "Save & grow", "Maintain"])
churn_t = f4.multiselect("Churn risk", ["High", "Medium", "Low"])
view = acc.copy()
if tiers: view = view[view["account_tier"].isin(tiers)]
if regions: view = view[view["region"].isin(regions)]
if quads: view = view[view["quadrant"].isin(quads)]
if churn_t: view = view[view["churn_tier"].isin(churn_t)]
st.caption(f"{len(view):,} accounts, {money(view['arr'].sum())} ARR, expected 90-day loss {money(view['expected_arr_loss_90d'].sum())}. "
           "Sorted by expected ARR loss.")
show = view[["account_id", "company_name", "account_tier", "region", "industry", "arr", "months_to_renewal", "churn_prob_90d",
             "churn_tier", "expansion_prob_90d", "expansion_tier", "quadrant"]].copy()
show["churn_prob_90d"] *= 100; show["expansion_prob_90d"] *= 100
st.dataframe(show, hide_index=True, width="stretch", height=360, column_config={
    "account_id": "Account", "company_name": "Company", "account_tier": "Tier", "region": "Region", "industry": "Industry",
    "arr": st.column_config.NumberColumn("ARR", format="$%,.0f"),
    "months_to_renewal": st.column_config.NumberColumn("Months to renewal", format="%.1f"),
    "churn_prob_90d": st.column_config.NumberColumn("Churn prob. (90d)", format="%.1f%%"),
    "churn_tier": "Churn risk",
    "expansion_prob_90d": st.column_config.NumberColumn("Expansion prob. (90d)", format="%.1f%%"),
    "expansion_tier": "Expansion", "quadrant": "Segment"})

# ------------------------------------------------------------------ drill-down
st.divider()
st.subheader("Account drill-down")
options = view["account_id"].tolist() or acc["account_id"].tolist()
labels = {r.account_id: f"{r.account_id}  {r.company_name}  ({money(r.arr)})" for r in acc.itertuples()}
pick = st.selectbox("Account", options, format_func=lambda a: labels.get(a, a))
r = acc[acc["account_id"] == pick].iloc[0]
m = st.columns(5)
m[0].metric("ARR", money(r["arr"]), f"{r['account_tier']} | {r['region']}", delta_color="off")
m[1].metric("Churn probability (90d)", f"{r['churn_prob_90d']:.1%}", r["churn_tier"] + " risk", delta_color="off")
m[2].metric("Expected ARR loss", money(r["expected_arr_loss_90d"]))
m[3].metric("Expansion probability (90d)", f"{r['expansion_prob_90d']:.1%}", r["expansion_tier"] + " propensity", delta_color="off")
m[4].metric("Segment", r["quadrant"], f"renews in {r['months_to_renewal']:.1f} months", delta_color="off")

cc = st.columns(2)
for col, model, title in [(cc[0], "churn", "Why this churn score"), (cc[1], "expansion", "Why this expansion score")]:
    d = drv[(drv["account_id"] == pick) & (drv["model"] == model)].sort_values("rank")
    with col:
        st.markdown(f"**{title}**")
        fig, ax = plt.subplots(figsize=(5.4, 2.8), dpi=150)
        colors = [ORANGE if s > 0 else BLUE for s in d["shap"]]
        ax.barh(d["label"][::-1], d["shap"][::-1], color=colors[::-1], height=0.55)
        ax.axvline(0, color="#898781", lw=1)
        ax.set_xlabel("Raises the score (orange) or lowers it (blue)"); ax.grid(axis="y", visible=False); ax.tick_params(axis="y", labelsize=8.5)
        st.pyplot(fig, clear_figure=True)
st.caption(f"Usage snapshot: login rate {r['login_3m']:.0%} | features adopted {r['feat_3m']:.1f} of 12 | seat utilization {r['util_3m']:.0%} | "
           f"tickets (90d) {r['tickets_90d']:.0f} | integrations {r['integrations']:.0f}")
