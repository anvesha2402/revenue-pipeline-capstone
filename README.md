# Revenue Pipeline Capstone

*A full-funnel B2B SaaS revenue pipeline system — five connected models, one dashboard, acquisition through retention and expansion.*

**Live dashboard:** https://revenue-pipeline-capstone-avskp88e7hdebnxahry7gu.streamlit.app/

> **Headline insight:** $106,013 in ARR sits at risk across just 11 accounts, flagged by declining feature adoption weeks before any cancellation signal appears — while a separate $1.93M in expansion revenue is sitting in accounts showing the exact opposite pattern.

## Architecture

Five model layers share one synthetic-but-consistent dataset (leads to opportunities to accounts to subscriptions to usage/support), all traceable through account_id: Leads to Deal-Win Probability to Pipeline Velocity to Churn-Retention to Expansion Propensity, with expansion looping back in as new pipeline.

## The Five Business Questions — Answered

1. **Lead Scoring** — With limited SDR hours, which leads should get worked first? Top-quintile leads convert at 2.0x the rate of bottom-quintile leads (53.8% vs 27.1%). Demo requests and pricing-page visits are the strongest signals.
2. **Deal-Win Probability** — Which open deals will actually close? Deal stage carries almost no predictive signal (SHAP roughly zero) — competitor presence dominates instead. ROC-AUC 0.731.
3. **Pipeline Velocity** — Where do deals stall, and how much is stuck? Qualified is the real bottleneck (36-day median dwell vs 15/15/8 elsewhere) — $7.3M sitting past-median in that stage alone. Slower deals aren't lower-quality — win rate is nearly identical either way (50.7% vs 49.9%) — so this is a process/SLA fix, not a forecasting flag.
4. **Retention/Churn** — Which accounts are about to churn, and how much ARR? $106,013 in ARR at risk across 11 of 389 active accounts. ROC-AUC 0.967, driven almost entirely by feature-adoption and usage-decline trends.
5. **Expansion/Upsell** — Which accounts are ready to buy more, and what? $1.93M in expansion revenue potential, split into seat-growth vs feature-adoption-growth accounts with a specific pitch for each. (ROC-AUC 1.000 here — flagged and explained below as a synthetic-data artifact, not a real-world claim.)

**Cross-model check:** churn risk and expansion propensity show zero overlap in this dataset — a real finding, caused by a data-design limitation (each account got one lifetime trajectory, not one that can shift), explained in full in docs/business_insights.md.

## Tech Stack

Python, pandas, scikit-learn, XGBoost, SHAP, Streamlit (deployed on Streamlit Community Cloud), GitHub.

One consistent stack across all five models on purpose — a standardized workflow, not five one-off scripts.

## Key Results

| Model | Metric | Result |
|---|---|---|
| Lead Scoring | ROC-AUC | 0.637 (baseline) vs 0.617 (XGBoost) — baseline wins |
| Deal-Win Probability | ROC-AUC | 0.731 (tied) |
| Pipeline Velocity | Bottleneck | Qualified, 36-day median dwell, $7.3M stuck |
| Retention/Churn | ROC-AUC | 0.967 (tied with baseline) |
| Expansion/Upsell | ROC-AUC | 1.000 — see synthetic-data note below |

Where XGBoost ties or loses to a plain Logistic Regression baseline, that's reported as-is rather than hidden — several of these relationships are mostly linear, and a simpler model is the honest choice.

## Synthetic Data — Disclosed

All data here is synthetic (faker plus scripted business logic), generated deliberately messy: missing values, duplicate records, inconsistent labels, and data-entry errors, mimicking real CRM export quality rather than a clean textbook dataset. Full details in data/data_dictionary.md.

One caveat found during modeling: the Expansion model's near-perfect ROC-AUC (1.000) traces to a generation-logic gap — features_adopted was built as a fully deterministic function of trajectory for growing/declining accounts (no random noise, unlike usage data which had plus/minus 15% noise), making the classes artificially separable. Reported honestly rather than presented at face value — see docs/business_insights.md for the investigation.

## How to Run Locally

    git clone https://github.com/anvesha2402/revenue-pipeline-capstone.git
    cd revenue-pipeline-capstone
    pip install -r requirements.txt
    streamlit run dashboard/app.py

## What I'd Do Differently With Real CRM Data

- Pull from a live Salesforce/HubSpot export instead of synthetic generation
- Build point-in-time feature snapshots (not full-lifetime aggregates) to avoid any temporal leakage in a production churn/expansion model
- Add a real rep-forecast field to properly test the Deal-Win hypothesis (stage-based confidence was used here as a documented stand-in)
- Model trajectories that can shift or blend mid-lifecycle, so the churn-and-expansion cross-check can actually surface overlapping accounts
- Re-validate whether Expansion's near-perfect signal survives real, noisier usage data (expect it to drop substantially — see the caveat above)

## Status
- [x] Data architecture + synthetic dataset (6 tables, deliberately messy)
- [x] Model layer (5 models + business insights + cross-model check)
- [x] Dashboard (live, deployed)
- [ ] Portfolio packaging (video, LinkedIn post, CV line) — in progress
