
import streamlit as st
import pandas as pd
import json
import joblib
import matplotlib.pyplot as plt
import shap
import os

st.set_page_config(page_title="Revenue Pipeline Capstone", layout="wide")

COLOR_BLUE = "#2a78d6"
COLOR_GOOD = "#0ca30c"
COLOR_CRITICAL = "#d03b3b"
COLOR_MUTED = "#898781"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")

@st.cache_data
def load_data():
    master = pd.read_csv(os.path.join(DATA_DIR, "dashboard_master_table.csv"))
    with open(os.path.join(DATA_DIR, "dashboard_kpis.json")) as f:
        kpis = json.load(f)
    with open(os.path.join(DATA_DIR, "funnel_counts.json")) as f:
        funnel = json.load(f)
    churn_feat = pd.read_csv(os.path.join(DATA_DIR, "churn_features_matrix.csv"))
    exp_feat = pd.read_csv(os.path.join(DATA_DIR, "expansion_features_matrix.csv"))
    return master, kpis, funnel, churn_feat, exp_feat

@st.cache_resource
def load_models():
    churn_model = joblib.load(os.path.join(MODELS_DIR, "churn_model.pkl"))
    exp_model = joblib.load(os.path.join(MODELS_DIR, "expansion_model.pkl"))
    with open(os.path.join(MODELS_DIR, "churn_features.json")) as f:
        churn_cols = json.load(f)
    with open(os.path.join(MODELS_DIR, "expansion_features.json")) as f:
        exp_cols = json.load(f)
    return churn_model, exp_model, churn_cols, exp_cols

master, kpis, funnel, churn_feat, exp_feat = load_data()
churn_model, exp_model, churn_cols, exp_cols = load_models()

st.title("Revenue Pipeline Capstone")
st.caption("Full-funnel B2B SaaS revenue pipeline -- acquisition through retention and expansion")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Pipeline Value", f"${kpis['total_pipeline_value']:,.0f}")
c2.metric("Win Rate", f"{kpis['win_rate']*100:.1f}%")
c3.metric("Bottleneck Stage Dwell", f"{kpis['avg_deal_cycle_days']:.0f} days")
c4.metric("Churn-Risk $ Exposure", f"${kpis['churn_risk_exposure']:,.0f}")
c5.metric("Expansion Revenue Potential", f"${kpis['expansion_revenue_potential']:,.0f}")

st.divider()
st.subheader("Funnel: Leads to Closed-Won")
stages = list(funnel.keys())
values = list(funnel.values())
fig, ax = plt.subplots(figsize=(10, 3))
ax.barh(stages[::-1], values[::-1], color=COLOR_BLUE)
for i, v in enumerate(values[::-1]):
    ax.text(v, i, f" {v:,}", va="center", color="#0b0b0b")
ax.set_xlabel("Count")
ax.spines[["top", "right"]].set_visible(False)
st.pyplot(fig)

conv_lines = []
for i in range(1, len(stages)):
    prev, cur = values[i-1], values[i]
    pct = (cur / prev * 100) if prev else 0
    conv_lines.append(f"{stages[i-1]} -> {stages[i]}: {pct:.1f}%")
st.caption(" | ".join(conv_lines))

st.divider()
st.subheader("Account Health")
col_f1, col_f2 = st.columns(2)
tier_options = master["risk_tier"].dropna().unique().tolist()
tier_filter = col_f1.multiselect("Risk tier", options=tier_options, default=tier_options)
action_options = master["recommended_action"].unique().tolist()
action_filter = col_f2.multiselect("Recommended action", options=action_options, default=action_options)

filtered = master[
    (master["risk_tier"].isin(tier_filter) | master["risk_tier"].isna()) &
    (master["recommended_action"].isin(action_filter))
]
display_cols = ["account_id", "account_tier", "mrr", "churn_probability", "risk_tier",
                 "expansion_score", "recommended_action"]
st.dataframe(
    filtered[display_cols].sort_values("churn_probability", ascending=False, na_position="last"),
    use_container_width=True, height=350
)

st.divider()
st.subheader("Account Drill-Down")
account_options = master[master["status"] == "Active"]["account_id"].tolist()
selected = st.selectbox("Select an account", account_options)
acc_row = master[master["account_id"] == selected].iloc[0]
st.write(
    f"Risk tier: {acc_row['risk_tier']} | Churn probability: {acc_row['churn_probability']:.2f} | "
    f"Expansion score: {acc_row['expansion_score']:.2f}"
)
st.info(f"Recommended action: {acc_row['recommended_action']}")

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("**Why this churn score?**")
    row_feat = churn_feat[churn_feat["account_id"] == selected][churn_cols]
    if not row_feat.empty:
        explainer = shap.TreeExplainer(churn_model)
        sv = explainer.shap_values(row_feat)[0]
        top = pd.Series(sv, index=churn_cols).sort_values(key=abs, ascending=False).head(5)
        colors = [COLOR_CRITICAL if v > 0 else COLOR_GOOD for v in top.values]
        fig2, ax2 = plt.subplots(figsize=(5, 3))
        ax2.barh(top.index[::-1], top.values[::-1], color=colors[::-1])
        ax2.axvline(0, color=COLOR_MUTED, linewidth=1)
        ax2.spines[["top", "right"]].set_visible(False)
        st.pyplot(fig2)
        st.caption("Red = pushes churn risk up | Green = pushes it down")

with col_b:
    st.markdown("**Why this expansion score?**")
    row_feat_e = exp_feat[exp_feat["account_id"] == selected][exp_cols]
    if not row_feat_e.empty:
        explainer_e = shap.TreeExplainer(exp_model)
        sv_e = explainer_e.shap_values(row_feat_e)[0]
        top_e = pd.Series(sv_e, index=exp_cols).sort_values(key=abs, ascending=False).head(5)
        colors_e = [COLOR_BLUE if v > 0 else COLOR_MUTED for v in top_e.values]
        fig3, ax3 = plt.subplots(figsize=(5, 3))
        ax3.barh(top_e.index[::-1], top_e.values[::-1], color=colors_e[::-1])
        ax3.axvline(0, color=COLOR_MUTED, linewidth=1)
        ax3.spines[["top", "right"]].set_visible(False)
        st.pyplot(fig3)
        st.caption("Blue = pushes expansion score up")
