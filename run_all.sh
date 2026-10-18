#!/usr/bin/env bash
# Rebuilds everything from scratch (about 3 minutes). Run from the repo root.
set -euo pipefail
pip install -q -r requirements-pipeline.txt
python generate_synthetic_data_v2.py --out data/raw --docs docs      # 1. messy synthetic CRM data
python 02_clean_and_validate.py                                       # 2. cleaning + data-quality report
python 03a_build_snapshots.py                                         # 3. point-in-time features + no-leakage test
python 03b_lead_deal_velocity.py                                      # 4. lead scoring, deal-win, pipeline velocity
python 03c_churn_expansion.py                                         # 5. churn + expansion, overlap check, SHAP
python 04_export_and_figures.py                                       # 6. dashboard files + figures
python3 06_export_powerbi.py                                          # 7. Power BI star schema (CSV)
(cd powerbi && python3 gen_m_queries.py && python3 build_measures.py && python3 expected_values.py && python3 make_backgrounds.py && python3 make_preview.py && python3 make_layout_maps.py && python3 build_guide.py && python3 check_pbip.py)   # 8. Power BI kit + .pbip project (built and checked)
python3 05_write_docs.py                                              # 7. README + docs from results
echo "done. launch the dashboard with:  streamlit run dashboard/app.py"
