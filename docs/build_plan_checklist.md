# Build Plan Checklist — Revenue Pipeline Capstone

Source: `Revenue Pipeline Capstone — Build Plan.pdf`. This file turns that plan into a
literal, checkable task list. Check items off as you go — this is the file to reopen
each session to see exactly where you left off.

## Stage 1 — Data Architecture & Verification ✅ DONE

- [x] Design the six-table schema (leads, opportunities, opportunity_stage_history,
      accounts, subscriptions, usage_monthly, support_tickets), keyed on `account_id`
      end to end.
- [x] Write `data/generate_synthetic_data.py` (faker + numpy + pandas, scripted
      business logic: engagement→conversion, SE-involvement/competitor→win,
      adoption/tenure/contract-type→churn, health→expansion).
- [x] Run it, verify the patterns are learnable (checked: annual contracts churn
      19.5% vs. monthly 27.4%; churned accounts average health 55.6 vs. active 68.3;
      competitor-present deals win 47.5% vs. 60.6% without).
- [x] `data/data_dictionary.md` + `data/sample/*.csv`.

**Open item — do this yourself before Stage 2:** the plan's first instruction is
"Rescue A0011 first" — your inventory record says the churn-model file on hand is
the default Colab tutorial page, not your real code. I checked your connected Drive
and didn't find a distinctly-named A0011 notebook, but two things there could serve
as your real base:
- `Phase9_Full_Draft.md` / `Phase15_Full_Draft.md` in your TECH folder (MERIDIAN churn
  model + deployment chapters — actual working XGBoost/Random Forest code against a
  churn target, written by you as part of the data-science curriculum).
- The IBM Telco churn coursework notebooks/transcripts in the same folder (KNN,
  logistic regression, bagging/random forest — all on a real churn target with
  metrics you already produced).
Locate the actual A0011 file (check your laptop, other Drive accounts, or Colab's
"Recent" list directly — Colab file search isn't exposed to me), or decide to rebuild
it from one of the above as your verified base. Don't proceed to Stage 2's churn
notebook until this is resolved — everything downstream cites its ROC-AUC.

## Stage 2 — Model Layer (aim: 2 weeks)

Shared pattern for every notebook: load data → engineer features in `src/features.py`
→ train/test split → fit baseline (sklearn LogisticRegression) → fit XGBoost → compare
→ SHAP → one-paragraph business interpretation. Build `src/data_pipeline.py` once,
reuse it in all five notebooks.

- [ ] `src/data_pipeline.py` — shared loaders for all seven CSVs, with the leakage
      note from the data dictionary applied (don't hand `health_score` to the churn
      model without engineering around it).
- [ ] `src/features.py` — reusable feature builders (e.g. rolling adoption trend,
      ticket trend, RFM-style recency/frequency from usage_monthly).
- [ ] `notebooks/04_churn_retention.ipynb` — resolve the A0011 item above first, then
      rebuild on this dataset: XGBoost classifier, target = `account_status`,
      features engineered from `usage_monthly` + `support_tickets` + `accounts`
      (contract_type, tenure, adoption trend, ticket trend — not raw `health_score`).
      Add SHAP on top. Report ROC-AUC + precision/recall + top SHAP drivers.
- [ ] `notebooks/01_lead_scoring.ipynb` — same pipeline pattern, target =
      `converted_to_opportunity` on `leads.csv`. Report ROC-AUC + a lead-score
      (0–100) calibration.
- [ ] `notebooks/02_deal_win_probability.ipynb` — target = `outcome` (Won/Lost,
      excluding Open) on `opportunities.csv`. Report win-probability calibration +
      SHAP on competitor_present / SE-involvement / engagement.
- [ ] `notebooks/03_pipeline_velocity.ipynb` — **no ML.** Use
      `opportunity_stage_history.csv`: median/mean days-in-stage per stage, stage-to-
      stage conversion rate, flag the stage with the biggest drop-off as the
      bottleneck. Cross-cut by `competitor_present` to show the stall pattern.
- [ ] `notebooks/05_expansion_propensity.ipynb` — target = "expanded at least once"
      on `accounts.csv` joined to `usage_monthly` (use pre-expansion-month features
      only, to avoid leaking the future). Report ROC-AUC + SHAP + a ranked shortlist
      of currently-healthy non-expanded accounts.
- [ ] `src/models/` — one module per model with a shared `train()`/`evaluate()`
      interface (this is the "engineering discipline, not five one-off scripts"
      signal the plan calls out).
- [ ] `src/explain.py` — shared SHAP wrapper used by all four classifiers.
- [ ] **Checkpoint:** five notebooks, each ending in a metrics summary + one
      business-interpretation paragraph. Copy the five headline metrics into
      `docs/metrics_summary.md`.

## Stage 3 — Product Layer: the Dashboard (aim: 1 week)

- [ ] Read the `dataviz` skill's guidance once before writing any chart code in
      `dashboard/app.py`, so the KPI tiles / funnel chart / SHAP visuals read as one
      visual system.
- [ ] `dashboard/app.py` (Streamlit), four sections top to bottom:
  1. KPI row: Total Pipeline Value · Win Rate · Avg. Deal Cycle Time · Churn-Risk $
     Exposure · Expansion Revenue Potential.
  2. Funnel chart: Leads → MQL/SQL (converted) → Opportunity → Closed-Won →
     Renewal/Expansion, with conversion % on each arrow.
  3. Account Health table: every active account — lead score (if available),
     win probability (if still open), churn-risk tier, expansion-propensity score;
     filterable and sortable.
  4. Drill-down panel: click an account → SHAP waterfall + one-line recommended
     action ("Flag for CSM outreach" / "Route to expansion play").
- [ ] Deploy on Streamlit Community Cloud (free) — get a working public URL.
- [ ] *(Optional)* Power BI companion view — same data, exec-summary layout, for a
      business-facing screenshot.
- [ ] **Checkpoint:** a live URL you can put on your CV, LinkedIn, or drop into an
      interview chat mid-conversation.

## Stage 4 — Portfolio Packaging (aim: 1–2 weeks)

- [ ] Fill in the README skeleton already in this repo, in order: impact number →
      architecture image → live demo link → tech badges → five model summaries →
      results table → local setup → synthetic-data disclosure → "what I'd do with
      real CRM data" paragraph (item 9 — this is the one hiring managers weight most,
      per the plan: it shows you know the portfolio-vs-production gap).
- [ ] Export the Mermaid diagram above as `docs/architecture_diagram.png`.
- [ ] Record the 2–2:30 min demo video per the beat sheet in the original build plan
      (hook with a dollar figure → architecture in 25s → live dashboard walkthrough
      with one SHAP drill-down → quick cuts of the other four models → why it matters
      → CTA with both links). Script it and read it twice before recording.
- [ ] Build the LinkedIn carousel (problem → architecture → one screenshot per model
      → metrics slide → CTA slide with both links), then use the
      `linkedin-post-writer` skill to draft the actual post once the project and
      screenshots exist.
- [ ] Add the finished project as your capstone line on the CV, linking both the repo
      and the live dashboard.
- [ ] **Final checkpoint:** one link — the GitHub repo — that is simultaneously a
      working product (dashboard), a documented codebase, and (via the README) a
      case study.

## Notes on scope

- Total original estimate: 5–6 weeks part-time. Stage 1 is done; realistic remaining
  effort is ~4–5 weeks of evenings/weekends for Stages 2–4, with Stage 2 (five
  models) the long pole.
- Keep the stack narrow on purpose: pandas → scikit-learn → XGBoost → SHAP →
  Streamlit, end to end. Reaching for a different library per model would undercut
  the "I can standardize a workflow" signal this project is built to send.
