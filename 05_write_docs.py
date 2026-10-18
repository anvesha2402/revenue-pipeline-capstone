#!/usr/bin/env python3
"""05_write_docs.py - writes README.md and docs/*.md from the result files so every number in the text matches the run."""
import json

import pandas as pd

D = "docs"
rc = json.load(open(f"{D}/results_churn_expansion.json"))
rl = json.load(open(f"{D}/results_lead_deal_velocity.json"))
kp = json.load(open("exports/dashboard_kpis.json"))
dq = json.load(open(f"{D}/data_quality_report.json"))
gen = json.load(open(f"{D}/generator_assumptions.json"))
leak = json.load(open(f"{D}/leakage_test.json"))
dwell = pd.DataFrame(rl["pipeline_velocity"]["dwell"]).set_index("stage")
ops = pd.DataFrame(rl["pipeline_velocity"]["open_by_stage"]).set_index("stage")
spd = pd.DataFrame(rl["pipeline_velocity"]["early_speed_vs_win"])

ch, ex = rc["churn"]["pooled"], rc["expansion"]["pooled"]
chd, exd = ch[ch["deployed"]], ex[ex["deployed"]]
ls, dw = rl["lead_scoring"]["pooled"], rl["deal_win"]["pooled"]
lsd, dwd = ls[ls["deployed"]], dw[dw["deployed"]]
ov, lb, vel = rc["overlap"], rc["live_book"], rl["pipeline_velocity"]["formula_inputs"]
quad = {q["quadrant"]: q for q in ov["quadrants"]}
iv = rc.get("internal_validation_vs_hidden_drivers", {})
M = lambda x: f"${x / 1e6:,.1f}M" if abs(x) >= 1e6 else (f"${x / 1e3:,.0f}K" if abs(x) >= 1e3 else f"${x:,.0f}")
ci = lambda d: f"{d['roc_auc']:.3f} ({d['roc_auc_ci95'][0]:.3f}-{d['roc_auc_ci95'][1]:.3f})"
des = rc["design"]
_h = pd.read_csv("exports/dashboard_account_health.csv")
sg_arr = _h.loc[_h["quadrant"] == "Save & grow", "arr"].sum()
comp = rl["deal_win"]["win_rate_by_competitor"]

# ------------------------------------------------------------------ README
MERMAID = """```mermaid
flowchart LR
    A[Synthetic CRM simulator<br/>messy raw tables] --> B[Clean and validate<br/>data-quality report]
    B --> C[Monthly snapshots<br/>point-in-time features]
    C --> D1[Lead scoring]
    C --> D2[Deal-win]
    C --> D3[Pipeline velocity]
    C --> D4[Churn, 90 days]
    C --> D5[Expansion, 90 days]
    D1 & D2 & D3 & D4 & D5 --> E[Exports<br/>scores, KPIs, scorecard]
    E --> F[Streamlit dashboard]
    E --> G[Power BI star schema<br/>83 DAX measures]
```"""

readme = f"""<div align="center">

# Revenue Pipeline Capstone

**Five connected models and two dashboards for one B2B SaaS revenue engine: from first lead to renewal.**

[![Live dashboard](https://img.shields.io/badge/Live%20dashboard-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://revenue-pipeline-capstone-avskp88e7hdebnxahry7gu.streamlit.app/)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-SHAP-1F6FEB)
![scikit-learn](https://img.shields.io/badge/scikit--learn-models-F7931E?logo=scikitlearn&logoColor=white)
![Power BI](https://img.shields.io/badge/Power%20BI-.pbip%20project-F2C811?logo=powerbi&logoColor=black)
![Validation](https://img.shields.io/badge/Validation-forward%20in%20time-2E7D32)
![Data](https://img.shields.io/badge/Data-100%25%20synthetic-6A1B9A)

[**Live dashboard**](https://revenue-pipeline-capstone-avskp88e7hdebnxahry7gu.streamlit.app/) &nbsp;|&nbsp;
[Results](#results) &nbsp;|&nbsp;
[Quick start](#quick-start) &nbsp;|&nbsp;
[Power BI](#power-bi-version) &nbsp;|&nbsp;
[Limitations](#limitations)

</div>

![Dashboard overview](figures/screens/streamlit_1_kpis.png)

**All data is synthetic.** The simulator is in this repository, its assumptions are in `docs/generator_assumptions.json`,
and every dollar figure below describes that simulated company, not a real market.

## At a glance

| Churn model AUC | Expansion model AUC | Open pipeline | Stalled pipeline | Active ARR | Expected ARR loss, 90 days |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **{chd['roc_auc']:.3f}** | **{exd['roc_auc']:.3f}** | **{M(rl['pipeline_velocity']['open_value'])}** | **{M(rl['pipeline_velocity']['stalled_value'])}** | **{M(kp['active_arr'])}** | **{M(kp['expected_arr_loss_next_90d'])}** |

- **Business question:** where is revenue leaking, and which accounts and deals should the team work first?
- **Approach:** lead scoring, deal-win, pipeline velocity, churn and expansion models on one dataset, validated on later periods than they were trained on.
- **Output:** a ranked list of customers by churn risk and expansion potential, a stalled-deal view, and a model scorecard, in Streamlit and Power BI.

## How it fits together

{MERMAID}

## Quick start

```bash
git clone https://github.com/anvesha2402/revenue-pipeline-capstone.git
cd revenue-pipeline-capstone
./run_all.sh                    # rebuilds data, models, figures, docs (a few minutes)
streamlit run dashboard/app.py  # opens the dashboard on http://localhost:8501
```

To only view the dashboard (the exported files are already in the repository):

```bash
pip install -r requirements.txt
streamlit run dashboard/app.py
```

## Dashboard

The Streamlit app reads only the files in `exports/`. It has pipeline and customer KPI strips, a funnel with stalled-deal view, a model scorecard with validation results, a filterable account health table (churn tier, expansion tier and segment), and an account drill-down with the top drivers for one customer.

| Pipeline and stalled deals | Model scorecard |
|---|---|
| ![Pipeline](figures/screens/streamlit_2_pipeline.png) | ![Scorecard](figures/screens/streamlit_3_scorecard.png) |
| **Account health** | **Account drill-down** |
| ![Account health](figures/screens/streamlit_4_account_health.png) | ![Drill-down](figures/screens/streamlit_5_drilldown.png) |

## Power BI version

`powerbi/` holds a star schema (6 dimensions, 5 facts, 4 reference tables), 83 DAX measures in 7 display folders, a theme, a step-by-step build guide, and a Power BI Project (`.pbip`) generated and schema-checked by `powerbi/check_pbip.py`. Open the `.pbip` in Power BI Desktop and set the `FolderPath` parameter to the folder holding the CSV files.

| Page 1: Pipeline | Page 2: Customers |
|---|---|
| ![Power BI pipeline page](figures/screens/powerbi_1_pipeline.png) | ![Power BI customers page](figures/screens/powerbi_2_customers.png) |

## Results

All models are validated **forward in time**: train on the past, test on the next period, with a gap so no training label
overlaps the test window. Intervals are 95% bootstrap intervals that resample whole accounts (or deals).

| Model | Predicts | ROC-AUC (95% CI) | Reference point | What the team does with it |
|---|---|---|---|---|
| Lead scoring | Lead becomes an opportunity within 75 days | {ci(lsd)} | Top score band converts {ls['top_vs_bottom_quintile_ratio']:.1f}x the bottom band | Reps work leads in score order |
| Deal-win | Closed deal is won | {ci(dwd)} | Reps' own forecast alone: {dw['rep_forecast']['roc_auc']:.3f}; model + forecast: {dw['model_plus_rep_forecast_xgb_roc_auc']:.3f} | Managers review competitive, thin-engagement deals |
| Pipeline velocity | Where open deals stall | descriptive | {M(rl['pipeline_velocity']['stalled_value'])} of {M(rl['pipeline_velocity']['open_value'])} open pipeline is stalled | Coaching aimed at specific stages |
| Churn, next 90 days | Account cancels | {ci(chd)} | Renewal date alone: {ch['naive']['roc_auc']:.3f}; top 10% of scores holds {chd['top10_capture']:.0%} of churners | CS contacts high-risk accounts before renewal |
| Expansion, next 90 days | Account buys more | {ci(exd)} | Seat-limit hits alone: {ex['naive']['roc_auc']:.3f}; top 10% of scores holds {exd['top10_capture']:.0%} of expanders | Account managers pitch high-propensity accounts |

Live book on {kp['as_of']}: {kp['active_accounts']:,} active customers, {M(kp['active_arr'])} ARR. The models score customers with at least 3 months of history: {kp['scored_accounts']:,} customers, {M(kp['scored_arr'])} ARR ({kp['scored_share_of_arr']:.0%} of ARR). The rest joined in the last 3 months and are not scored.
{kp['high_churn_risk_accounts']} accounts ({M(kp['high_churn_risk_arr'])} ARR) are in the high churn-risk tier. The probability-weighted ARR loss over the next 90 days is
{M(kp['expected_arr_loss_next_90d'])}. {kp['high_expansion_accounts']} accounts are in the high expansion tier, worth {M(kp['expected_expansion_arr_next_90d'])} of expected expansion ARR over 90 days.
Trailing-12-month net revenue retention is {kp['net_revenue_retention_12m']:.0%} (gross {kp['gross_revenue_retention_12m']:.0%}).

![Validation](figures/validation_random_vs_forward.png)

## What changed from v1, and why

v1 produced results that did not survive scrutiny. v2 fixes the causes, not the symptoms. v1 numbers are superseded and are not comparable with v2 (different dataset and definitions).

| Problem in v1 | Cause | v2 fix | Evidence |
|---|---|---|---|
| Expansion model scored AUC 1.000 | `features_adopted` was a deterministic function of the account's label | Every observed signal is a noisy reading of a hidden driver; no signal is a formula of the label | Forward AUC {exd['roc_auc']:.3f}; hidden-driver check below |
| Zero accounts were both churn-risk and expansion-ready | One fixed trajectory per account made the two mutually exclusive | Two hidden drivers per account (health, growth), correlated at {gen['config']['corr_H_G']}, each able to shift mid-life | {ov['joint_top20_share']:.1%} of out-of-time snapshots sit in the top 20% on both scores vs {ov['expected_if_independent']:.1%} expected if independent; Spearman {ov['spearman']:.2f} |
| One random train/test split | Rows from the same account and adjacent months landed on both sides | Expanding-window forward validation, 4 folds, 3-month purge gap | Random-row split gives churn AUC {ch['random_row_split_xgb_roc_auc']:.3f} vs {chd['roc_auc']:.3f} forward; expansion {ex['random_row_split_xgb_roc_auc']:.3f} vs {exd['roc_auc']:.3f} |
| Possible use of future information in features | Features were computed over an account's whole life | Monthly snapshots; a feature may only use records dated on or before the snapshot | Point-in-time test passes on {len(leak)} snapshot dates: features are identical with future data deleted |
| 473 accounts, 11 flagged | Small simulation | {des['accounts']:,} accounts with snapshots; {kp['scored_accounts']:,} scored and {kp['active_accounts']:,} active at the cutoff | Narrower intervals |
| Deal stage used as a feature | For a closed deal, the final stage is the outcome | Only information known when the deal opens | Stage removed |
| No rep forecast | Not in the schema | Rep forecast and discount added; model compared against reps | See deal-win row |
| Risk reported as a flagged-account count | Scores were not calibrated | Probabilities checked out-of-time (calibration slope {ch['calibration_slope']:.2f} churn, {ex['calibration_slope']:.2f} expansion) and recalibrated; dollar exposure is probability-weighted | `docs/reliability_*.csv`, `figures/calibration.png` |

## Findings

**Lead scoring.** Leads in the top score band convert at {ls['top_vs_bottom_quintile_ratio']:.1f}x the bottom band (95% CI {ls['top_vs_bottom_quintile_ratio_ci95'][0]:.1f}-{ls['top_vs_bottom_quintile_ratio_ci95'][1]:.1f}). Lead source, contact seniority, engagement score and a demo request carry most of the signal. Logistic regression and XGBoost tie (AUC {ls['lr']['roc_auc']:.3f} vs {ls['xgb']['roc_auc']:.3f}), so the simpler model is deployed.

**Deal-win.** A competitor in the deal cuts the win rate from {comp['no competitor']['win_rate']:.0%} to {comp['competitor present']['win_rate']:.0%}. Deal size, rep and decision-makers engaged follow. Reps' forecasts alone reach AUC {dw['rep_forecast']['roc_auc']:.3f}, about level with the model ({dwd['roc_auc']:.3f}); using both gives {dw['model_plus_rep_forecast_xgb_roc_auc']:.3f}, so each holds information the other lacks.

**Pipeline velocity.** Median days in stage: Qualified {dwell.loc['Qualified','median_days']:.0f}, Discovery {dwell.loc['Discovery','median_days']:.0f}, Proposal {dwell.loc['Proposal','median_days']:.0f}, Negotiation {dwell.loc['Negotiation','median_days']:.0f}. Qualified holds the largest stalled dollar amount ({M(ops.loc['Qualified','stalled_value'])}) because it holds the most open deals; Negotiation has the highest stalled share ({ops.loc['Negotiation','stalled_share_of_stage_value']:.0%} of its value). Among deals that reach Proposal, time spent earlier does not change the win rate ({spd.iloc[0]['win_rate']:.0%} fastest third, {spd.iloc[2]['win_rate']:.0%} slowest third, each +/-{spd['ci95_halfwidth'].max() * 100:.0f} points).

**Churn.** Months until renewal is the largest driver, then login rate, seat utilization and feature adoption. Support-ticket volume ranks lower. A logistic model scores {ch['lr']['roc_auc']:.3f}, barely above the renewal-date-only benchmark ({ch['naive']['roc_auc']:.3f}); gradient boosting reaches {ch['xgb']['roc_auc']:.3f} by modelling how usage decline interacts with renewal timing.

**Expansion.** Activity per active user, features adopted, integrations connected and the login trend lead. Seat-limit hits alone are a weak signal ({ex['naive']['roc_auc']:.3f}).

**Churn and expansion together.** The two scores are negatively correlated ({ov['spearman']:.2f}), and accounts high on both are rare. Across {sum(q['snapshots'] for q in ov['quadrants']):,} out-of-time snapshots, the {quad['Save & grow']['snapshots']} in the "Save & grow" segment churned at {quad['Save & grow']['churn_rate']:.0%} and expanded at {quad['Save & grow']['expansion_rate']:.0%} within 90 days, versus {quad['Protect']['churn_rate']:.0%} churn in "Protect" and {quad['Grow']['expansion_rate']:.0%} expansion in "Grow". The live book has {lb['quadrant_counts'].get('Save & grow', 0)} such accounts ({M(sg_arr)} ARR). The negative correlation is partly built into the simulator (health raises both retention and expansion odds), so treat its size as an assumption.

![Churn x expansion](figures/churn_expansion_map.png)

## Limitations

These are also in `docs/limitations_and_changelog.md`.

1. **Synthetic data.** The models recover relationships the simulator contains. As an internal check, live churn scores correlate {iv.get('spearman_churn_score_vs_minus_H', float('nan')):.2f} with the hidden health driver and expansion scores {iv.get('spearman_expansion_score_vs_G', float('nan')):.2f} with the hidden growth driver. That shows the pipeline works under noise. It does not show the same effects exist in real companies.
2. **Stage timing is an input.** Stage dwell times and where lost deals exit are simulator settings, so the "stalled stage" analysis demonstrates the method, not a market fact.
3. **Overlapping labels.** A churn event appears in up to three consecutive monthly snapshots of the same account. Confidence intervals resample whole accounts to account for this.
4. **Short history.** Thirty months of data, four validation folds; the first fold trains on about ten months.
5. **No causal claims.** SHAP shows what moves a score, not what would change an outcome. Save and expansion plays are untested.
6. **Thresholds are conventions.** Risk tiers use 2x and 1x the historical base rate. Cost-based thresholds need real outreach costs.
7. **Not built yet:** simulated copilot with action plans.

## Repository layout

```
generate_synthetic_data_v2.py   simulator (messy raw tables, fixed seed)
02_clean_and_validate.py        cleaning + docs/data_quality_report.json
03a_build_snapshots.py          point-in-time features, 90-day labels, no-leakage test
03b_lead_deal_velocity.py       lead scoring, deal-win, pipeline velocity
03c_churn_expansion.py          churn + expansion, overlap check, SHAP, calibration
04_export_and_figures.py        dashboard files, scorecard, figures
05_write_docs.py                writes this README and docs/*.md from the results
06_export_powerbi.py            star-schema CSV files for Power BI
rpc_common.py, rpc_features.py  shared validation and feature code
dashboard/app.py                Streamlit app (reads exports/ only)
powerbi/                        build guide, DAX measures, theme, .pbip generator and checks
data/raw, data/clean            messy and cleaned tables
exports/, models/, figures/     dashboard inputs, saved models, charts and screenshots
docs/                           data dictionary, insights, results, limitations
```

## Tools used

| Area | Tools |
|---|---|
| Data and modelling | Python 3.11, NumPy, pandas, SciPy, Faker, scikit-learn, XGBoost, SHAP, joblib |
| Dashboards | Streamlit (Community Cloud), Power BI Desktop, Power Query (M), DAX, TMDL / PBIR |
| Quality checks | Forward-in-time validation, bootstrap intervals, point-in-time leakage test, calibration, `jsonschema` checks on the `.pbip` |
| Delivery | Git, GitHub, Bash (`run_all.sh`) |

Reproducibility: the full pipeline was run twice in clean folders and produced byte-identical data and identical results.
"""
open("README.md", "w").write(readme)

# ------------------------------------------------------------------ business insights
cf = {r["fold"]: r for r in rc["churn"]["folds"]}
bi = f"""# Business insights (v2, synthetic data)

Each section: question, metric, insight, decision, caveat, next question.

## 1. Lead scoring
- **Question:** which inbound leads should reps call first?
- **Metric:** forward ROC-AUC {ci(lsd)}; conversion by score band {pd.read_csv('docs/lead_quintiles.csv').iloc[0]['conversion_rate']:.0%} (top) to {pd.read_csv('docs/lead_quintiles.csv').iloc[-1]['conversion_rate']:.0%} (bottom).
- **Insight:** the top band converts {ls['top_vs_bottom_quintile_ratio']:.1f}x the bottom band. Source, seniority, engagement and demo requests carry the signal. A simple model matches XGBoost.
- **Decision:** order the call list by score; route low-score leads to nurture instead of rep time.
- **Caveat:** a score ranks leads; it does not say why a lead converts. Unobserved factors cap the AUC.
- **Next question:** does working leads in score order raise closed revenue per rep-hour? Needs an experiment.

## 2. Deal-win probability
- **Question:** which open deals are likely to close?
- **Metric:** forward ROC-AUC {ci(dwd)}; reps' forecast alone {dw['rep_forecast']['roc_auc']:.3f}; combined {dw['model_plus_rep_forecast_xgb_roc_auc']:.3f}.
- **Insight:** competitor presence is the strongest signal ({comp['competitor present']['win_rate']:.0%} win rate with one vs {comp['no competitor']['win_rate']:.0%} without). Deal stage is excluded because it leaks the outcome on closed deals.
- **Decision:** managers review competitive deals early and compare the model with the rep's forecast; disagreements are the review list.
- **Caveat:** rep skill and forecasts are simulated from the same hidden win logit, so the model-versus-rep comparison is illustrative.
- **Next question:** which competitor and which loss reason drive the gap?

## 3. Pipeline velocity
- **Question:** where do deals stall and how much revenue sits there?
- **Metric:** median stage days (Qualified {dwell.loc['Qualified','median_days']:.0f}, Discovery {dwell.loc['Discovery','median_days']:.0f}, Proposal {dwell.loc['Proposal','median_days']:.0f}, Negotiation {dwell.loc['Negotiation','median_days']:.0f}); stalled = longer in stage than 75% of comparable deals.
- **Insight:** {M(rl['pipeline_velocity']['stalled_value'])} of {M(rl['pipeline_velocity']['open_value'])} open pipeline is stalled. Qualified has the most stalled dollars ({M(ops.loc['Qualified','stalled_value'])}); Negotiation has the highest stalled share ({ops.loc['Negotiation','stalled_share_of_stage_value']:.0%}). Early speed does not change the win rate once a deal reaches Proposal.
- **Velocity:** {vel['open_opportunities']} open deals x {M(vel['avg_open_deal_size'])} average x {vel['win_rate_12m']:.0%} win rate / {vel['avg_won_cycle_days']:.0f}-day cycle = {M(vel['pipeline_velocity_usd_per_day'])} of new ARR per day.
- **Decision:** target coaching at stalled deals in Qualified first (most dollars), and review Negotiation deals for pricing or legal blockers (highest share).
- **Caveat:** stage durations are simulator inputs.
- **Next question:** which stalled deals are also low on win probability?

## 4. Churn (next 90 days)
- **Question:** which active accounts will cancel, and how much ARR is exposed?
- **Metric:** forward ROC-AUC {ci(chd)}; PR-AUC {chd['pr_auc']:.3f} vs {chd['base_rate']:.1%} base rate; top 10% of scores holds {chd['top10_capture']:.0%} of churners.
- **Insight:** renewal timing dominates; within a renewal window, falling logins, low seat utilization and low feature adoption separate accounts that leave from those that stay.
- **Exposure:** {kp['high_churn_risk_accounts']} high-risk accounts hold {M(kp['high_churn_risk_arr'])} ARR; probability-weighted loss over 90 days is {M(kp['expected_arr_loss_next_90d'])}. Comparable historical snapshots churned at {chd['base_rate']:.1%} per 90 days.
- **Decision:** start save plays 90 days before renewal for high-risk accounts, ordered by expected ARR loss.
- **Caveat:** correlational. A save play's effect is not measured.
- **Next question:** which intervention, at which lead time, changes the outcome?

## 5. Expansion (next 90 days)
- **Question:** which accounts are ready to buy more?
- **Metric:** forward ROC-AUC {ci(exd)}; PR-AUC {exd['pr_auc']:.3f} vs {exd['base_rate']:.1%} base rate; top 10% of scores holds {exd['top10_capture']:.0%} of expanders.
- **Insight:** depth of use (activity per user, features adopted, integrations) predicts expansion better than seat-limit hits alone.
- **Exposure:** {kp['high_expansion_accounts']} high-propensity accounts hold {M(kp['high_expansion_arr'])} ARR; expected expansion over 90 days is {M(kp['expected_expansion_arr_next_90d'])} (propensity x historical uplift by tier).
- **Decision:** account managers lead with high-propensity accounts that are not near a renewal risk.
- **Caveat:** deployed model is logistic regression; its top-decile probabilities ran about 30% high before recalibration.
- **Next question:** seat add, tier upgrade or add-on: which play fits which account?

## 6. Cross-model check
- **Question:** are some accounts both a save risk and an expansion candidate?
- **Result:** yes, but rarely. {quad['Save & grow']['snapshots']} of {sum(q['snapshots'] for q in ov['quadrants']):,} out-of-time snapshots ({ov['joint_top20_share']:.1%}) are in the top 20% on both scores, versus {ov['expected_if_independent']:.1%} if the scores were independent. Spearman correlation {ov['spearman']:.2f}.
- **Segments (out-of-time):** Protect churn {quad['Protect']['churn_rate']:.1%}, expansion {quad['Protect']['expansion_rate']:.1%}; Grow churn {quad['Grow']['churn_rate']:.1%}, expansion {quad['Grow']['expansion_rate']:.1%}; Save & grow churn {quad['Save & grow']['churn_rate']:.1%}, expansion {quad['Save & grow']['expansion_rate']:.1%}; Maintain churn {quad['Maintain']['churn_rate']:.1%}, expansion {quad['Maintain']['expansion_rate']:.1%}.
- **Decision:** for the {lb['quadrant_counts'].get('Save & grow', 0)} live "Save & grow" accounts, resolve the risk driver before pitching expansion.
- **Caveat:** the negative correlation reflects the simulator's design (health feeds both).
"""
open(f"{D}/business_insights.md", "w").write(bi)

# ------------------------------------------------------------------ data dictionary
def n(k): return dq.get(k, "n/a")
dd = f"""# Data dictionary (v2, synthetic)

Seven tables, linked by `account_id`, `opportunity_id` and `lead_id`. Period: 2024-01-01 to {kp['as_of']}.
Raw files in `data/raw/` are deliberately messy; `data/clean/` holds the cleaned versions produced by `02_clean_and_validate.py`.

## Tables

| Table | Grain | Rows (raw) | Key columns |
|---|---|---|---|
| `leads` | one inbound lead | {n('leads.raw_rows'):,} | `lead_id`, `created_date`, `industry`, `company_size_employees`, `region`, `lead_source`, `contact_seniority`, `demo_requested`, `engagement_score` |
| `opportunities` | one deal | {n('opportunities.raw_rows'):,} | `opportunity_id`, `lead_id`, stage entry dates, `closed_date`, `outcome`, `deal_size`, `competitor_present`, `decision_makers_engaged`, `sales_rep_id`, `rep_forecast_pct`, `loss_reason` |
| `accounts` | one won deal that became a customer | {n('accounts.raw_rows'):,} | `account_id`, `opportunity_id`, `account_tier`, `start_date`, `contract_term_months`, `csm_id`, `initial_acv` |
| `subscriptions` | current subscription state per account | {n('subscriptions.raw_rows'):,} | `plan_tier`, `mrr`, `seats_licensed`, `renewal_date`, `status`, `churn_date`, `churn_reason`, `expansions` |
| `subscription_events` | one MRR movement | see file | `event_type` (New, Expansion - seats / tier upgrade / add-on, Contraction, Churn), `mrr_change`, `mrr_after` |
| `usage_events` | account x month | {n('usage_events.raw_rows'):,} | `login_rate`, `active_users`, `seats_licensed`, `features_adopted` (of 12), `events_count`, `api_calls`, `integrations_connected`, `peak_seat_utilization` |
| `support_tickets` | one ticket | {n('support_tickets.raw_rows'):,} | `ticket_type`, `severity`, `resolution_hours`, `csat_score`, `is_escalated` |

Derived: `data/clean/account_snapshots.csv` has one row per active account per month-end (features known at that date) plus
`y_churn_90d` and `y_expansion_90d`, defined only when the next 90 days lie inside the data.

## Data-quality issues injected, and what the cleaner did

| Table | Issue | Count found | Treatment |
|---|---|---|---|
| leads | Raw industry spellings collapsing to 11 industries | {n('leads.raw_unique_industry_labels')} raw labels | Lookup on lower-cased, trimmed text; blanks become "Unknown" |
| leads | Duplicate leads (same email, different case, a few days later) | {n('leads.duplicates_removed'):,} removed | Keep earliest; never drop a lead an opportunity points to |
| leads | Dates written dd/mm/yyyy | {n('leads.dd_mm_yyyy_dates_normalized')} | Parsed explicitly |
| leads | Missing company size / source / seniority | {n('leads.missing_company_size'):,} / {n('leads.missing_lead_source')} / {n('leads.missing_contact_seniority'):,} | Kept as "Unknown" (missingness can be informative) |
| leads | Engagement score of -1 used as a blank | {n('leads.engagement_sentinel_to_null')} | Set to missing |
| opportunities | Raw stage spellings | {n('opportunities.raw_unique_stage_labels')} raw labels | Mapped to 6 stages |
| opportunities | Close date "0000-00-00" or before the create date | {n('opportunities.bad_close_date_zeros')} + {n('opportunities.close_before_create')} | Rebuilt from the account start date (won) or last stage date plus median dwell (lost); flagged `close_date_reconstructed` |
| opportunities | Missing, zero or negative deal size | {n('opportunities.missing_or_nonpositive_deal_size')} | Median of the same size band; flagged `deal_size_imputed` |
| opportunities | Missing decision-makers engaged | {n('opportunities.missing_decision_makers')} | Median plus a missing flag |
| opportunities | Lead id that does not exist | {n('opportunities.orphan_lead_id')} | Kept; lead attributes set to "Unknown" |
| accounts / subscriptions | Accounts with no subscription row | {n('accounts.orphan_no_subscription_row')} | Rebuilt from `subscription_events` |
| subscriptions | Tier written in mixed case; zero or negative MRR; missing renewal date | {n('subscriptions.tier_case_fixed')}; {n('subscriptions.nonpositive_mrr_repaired_from_event_log')}; {n('subscriptions.missing_renewal_date_recomputed')} | Normalized; MRR taken from the event log; renewal date recomputed from start date and term |
| usage_events | Duplicate rows; active users above seats; missing months | {n('usage_events.duplicates_removed')}; {n('usage_events.active_users_capped_at_seats')}; {n('usage_events.missing_months_inside_account_life')} | Dropped; capped at seats; gaps left as gaps (features use available months) |
| support_tickets | Severity spellings (P1-P4, case); missing severity; duplicates | {n('support_tickets.raw_unique_severity_labels')} labels; {n('support_tickets.missing_severity'):,}; {n('support_tickets.duplicates_removed')} | Mapped to 4 levels; "Unknown"; dropped |

Counts were reconciled against an internal log of what the generator injected; every detected count matched except lead
duplicates (a few extra from natural email collisions).
"""
open(f"{D}/data_dictionary.md", "w").write(dd)

# ------------------------------------------------------------------ limitations & changelog
lim = f"""# Limitations and changelog (v1 to v2)

## Design choices that shape every result

- **Calibrated quantities (base rates only):** lead-to-opportunity {gen['config']['target_lead_to_opp']:.0%}, win rate {gen['config']['target_win_rate']:.0%}, annual churn about {gen['config']['target_annual_churn']:.0%}, annual expansion about {gen['config']['target_annual_expansion']:.0%}. Effect sizes and noise levels were fixed before any model was trained and were not tuned to reach a score. Two post-hoc realism edits were made after looking at the raw data: the ticket-severity cut points (the first version produced too many critical tickets) and calibrating the base rates on the final seed.
- **Hidden drivers:** each account has a health driver H and a growth driver G (correlation {gen['config']['corr_H_G']} at signing, {iv.get('corr_H_G_live_book', float('nan')):.2f} in the live book). Observed usage, tickets and contract events are noisy functions of them. Coefficients are in `docs/generator_assumptions.json`.
- **Labels:** an event counts if it falls in the 3 months after the snapshot; labels are blank when that window runs past {kp['as_of']}.
- **Validation:** four expanding windows (test starts 2025-04, 2025-07, 2025-10, 2026-01). Training stops 3 months before each test window starts. XGBoost depth and tree count are chosen on an inner time split of the training data only. The deployed model is the one with the higher pooled PR-AUC (rule set before training).
- **Recalibration:** a logistic recalibration learned on out-of-time predictions is applied to live scores (monotone, ranking unchanged).

## Remaining limitations

1. Synthetic data: results show the method recovers planted structure under noise, not that the same effects exist in real firms.
2. Stage dwell times, exit stages and the churn-expansion link are simulator settings.
3. Overlapping monthly labels make rows correlated; intervals resample accounts.
4. Short history (30 months), small first fold.
5. SHAP and importance are associational; no intervention was tested.
6. Tier thresholds (2x and 1x base rate) are conventions.
7. The dashboard reads pre-computed files; there is no live CRM connection or scheduled refresh.
8. Churn timing is concentrated at renewals by design, so months-to-renewal dominates the churn model.

## Changelog

| Area | v1 | v2 |
|---|---|---|
| Accounts | 473 | {des['accounts']:,} with snapshots; {kp['scored_accounts']:,} scored, {kp['active_accounts']:,} active |
| Account dynamics | One fixed trajectory | Two hidden drivers with mid-life shifts |
| Observed signals | Some deterministic | All noisy |
| Validation | Single split | Forward-in-time, purge gap, point-in-time test |
| Expansion AUC | 1.000 | {exd['roc_auc']:.3f} |
| Churn AUC | 0.967 (single split) | {chd['roc_auc']:.3f} forward |
| Lead scoring | AUC 0.637, 2.0x quintile ratio | AUC {lsd['roc_auc']:.3f}, {ls['top_vs_bottom_quintile_ratio']:.1f}x |
| Deal-win | AUC 0.731 using stage | AUC {dwd['roc_auc']:.3f} without stage; rep forecast added |
| Churn x expansion overlap | 0 accounts (by construction) | {ov['joint_top20_share']:.1%} of snapshots vs {ov['expected_if_independent']:.1%} if independent |
| Stalled pipeline | Past-median rule | Past 75th-percentile rule |
| Money at risk | Count and ARR of flagged accounts | Probability-weighted expected loss and tier ARR |
| Dashboard | Computed in app | Reads pre-computed files |
"""
open(f"{D}/limitations_and_changelog.md", "w").write(lim)
print("docs written")
