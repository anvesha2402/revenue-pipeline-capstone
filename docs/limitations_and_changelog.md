# Limitations and changelog (v1 to v2)

## Design choices that shape every result

- **Calibrated quantities (base rates only):** lead-to-opportunity 30%, win rate 35%, annual churn about 13%, annual expansion about 20%. Effect sizes and noise levels were fixed before any model was trained and were not tuned to reach a score. Two post-hoc realism edits were made after looking at the raw data: the ticket-severity cut points (the first version produced too many critical tickets) and calibrating the base rates on the final seed.
- **Hidden drivers:** each account has a health driver H and a growth driver G (correlation 0.25 at signing, 0.10 in the live book). Observed usage, tickets and contract events are noisy functions of them. Coefficients are in `docs/generator_assumptions.json`.
- **Labels:** an event counts if it falls in the 3 months after the snapshot; labels are blank when that window runs past 2026-06-30.
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
| Accounts | 473 | 1,980 with snapshots; 1,715 scored, 2,106 active |
| Account dynamics | One fixed trajectory | Two hidden drivers with mid-life shifts |
| Observed signals | Some deterministic | All noisy |
| Validation | Single split | Forward-in-time, purge gap, point-in-time test |
| Expansion AUC | 1.000 | 0.800 |
| Churn AUC | 0.967 (single split) | 0.827 forward |
| Lead scoring | AUC 0.637, 2.0x quintile ratio | AUC 0.668, 3.3x |
| Deal-win | AUC 0.731 using stage | AUC 0.652 without stage; rep forecast added |
| Churn x expansion overlap | 0 accounts (by construction) | 1.3% of snapshots vs 4.0% if independent |
| Stalled pipeline | Past-median rule | Past 75th-percentile rule |
| Money at risk | Count and ARR of flagged accounts | Probability-weighted expected loss and tier ARR |
| Dashboard | Computed in app | Reads pre-computed files |
