## Retention / Churn Model

**Business question:** Which active accounts are about to churn, and how much ARR is genuinely at risk?

**Metric:** XGBoost ROC-AUC 0.967 (vs. 0.966 for a Logistic Regression baseline — 
nearly identical performance, suggesting the churn signal here is strong and 
largely linear rather than needing complex feature interactions).

**Insight:** Two features dominate the churn signal by a wide margin — 
declining feature adoption and declining active-user counts — far ahead of 
support-ticket volume, resolution time, or deal size. Scored across all 389 
currently active accounts, only 11 fall into Medium or High risk tiers, 
together representing $106,013 in annualized ARR exposure.

**Decision it enables:** CS gets a specific, ranked worklist (risk × ARR) 
instead of a flat renewal-rate assumption or ARR-only prioritization. Ranking 
by ARR alone would miss several of the highest-probability churners — e.g. 
A000045 and A000391 are SMB accounts with below-average MRR but rank in the 
top of the High-risk tier by predicted probability.

**Follow-on question (open, needs real data):** of accounts "saved" in a 
prior outreach cycle, which specific intervention worked? This synthetic 
dataset has no history of past CS actions to test against — flagged here as 
the natural next study once real usage data is available.

## Lead Scoring Model

**Business question:** With limited SDR hours, which leads should get worked first?

**Metric:** Logistic Regression baseline ROC-AUC 0.637, XGBoost 0.617 — the
baseline edges out XGBoost here (unlike the churn model, where they tied).
This signals the conversion relationship is mostly linear; the extra model
complexity doesn't add lift. XGBoost is still used for SHAP explainability,
to keep one consistent interpretability tool across all five models.

**Insight:** Top-quintile-scored leads convert at 2.0x the rate of
bottom-quintile leads (53.8% vs 27.1%) — a real but more modest gap than a
"4x" figure might suggest; engagement and firmographic signals help, but
conversion in this dataset carries substantial unexplained variance.

**Decision it enables:** SDR routing weighted toward top-quintile leads is
justified, but a 2x (not 4x) gap means lead-quality targeting alone won't
fix a volume problem — reallocating marketing spend toward high-scoring
channels should be evaluated alongside, not instead of, generating more
volume from those channels.

**Follow-on question:** Is the bottleneck lead quality or lead quantity —
are there enough high-scoring leads being generated at all? (Worth a
follow-up cut: volume of top-quintile leads per channel per month.)

## Deal-Win Probability Model

**Business question:** Which open deals will actually close, and can the sales forecast be trusted?

**Scope note:** the original hypothesis compares model output to reps' 
self-reported forecast category — our synthetic schema has no such field, 
so we substitute deal stage as a naive "assumed confidence" proxy and flag 
where the model disagrees with it. Documented here as an honest scope 
limitation, not a hidden substitution.

**Metric:** ROC-AUC 0.731 (baseline and XGBoost tied).

**Insight:** `stage_number` has essentially zero SHAP importance — deal 
stage alone carries almost no information about win probability in this 
dataset. What actually predicts a win is competitor presence (biggest driver), 
deal size, and stakeholder count. This means a forecast roll-up based on 
"what stage is this deal in" is close to uninformative; the deals flagged as 
biggest stage-vs-model mismatches are disproportionately ones with an active 
competitor mentioned, regardless of how advanced the stage looks.

**Decision it enables:** Management attention redirected to deals the 
model flags as at-risk despite being in a late stage (biggest overconfidence 
list) — these are the surprise-loss candidates a forecast roll-up based on 
stage alone would miss.

## Pipeline Velocity (non-ML analysis)

**Business question:** Where exactly do deals stall, and how much revenue is sitting stuck right now?

**Method:** No model needed here — median days-in-stage per stage, computed 
directly from stage-entry timestamps, is the whole analysis. Not every 
funnel question needs ML.

**Insight:** Qualified is the clear bottleneck stage (36-day median dwell, 
vs. 15/15/8 days for Prospecting/Proposal/Negotiation) — deals spend more 
than twice as long moving through qualification as any other stage. 
$7,338,816 across 338 open deals is currently sitting past that 36-day 
median in Qualified alone.

**Decision it enables:** A process fix targeted specifically at qualification 
— not a generic "move faster" directive, and not proposal or legal/procurement, 
which the plan's illustrative hypothesis guessed at but the data doesn't 
support.

**Follow-on question, answered:** does the slow stage also correlate with a 
lower eventual win rate? No — closed deals that spent above-median time in 
Qualified won at 50.7%, versus 49.9% for those at or below median. 
Essentially identical. **Slow is costing time, not deals** — a real and 
useful distinction: this justifies a process/SLA fix (speed for its own 
sake, cash-flow and forecast-timing reasons) rather than a quality-scare 
narrative ("slow deals are dying"), which the data doesn't support.

## Expansion / Upsell Model

**Business question:** Which healthy accounts are ready to buy more, and what specifically should they be offered?

**Scope note:** no product catalog exists in this synthetic schema, so 
"recommended next product" is derived from each account's dominant growth 
signal (seat growth vs. feature-adoption growth) rather than a named SKU.

**Metric:** XGBoost ROC-AUC 1.000 — and this number should NOT be taken at 
face value. Investigation (SHAP) showed `avg_features_adopted` alone carries 
~10x the weight of any other feature, traced back to a data-generation gap: 
the growing/declining trajectory formulas for `features_adopted` were fully 
deterministic with no random noise (unlike usage, which had ±15% noise). 
This makes the synthetic classes near-perfectly separable — an artifact of 
how the data was built, not a claim that real-world expansion prediction 
would perform this well. Flagged explicitly rather than reported at face value.

**Insight:** Among currently active accounts, the model separates growth-track 
accounts cleanly by feature-adoption trajectory, and further splits them into 
seat-growth vs. feature-adoption-growth patterns — giving each flagged account 
a specific pitch rather than a blanket "upsell" flag.

**Decision it enables:** Account managers get a ranked list with a reason, 
not a binary flag.

## Cross-Model Insight: Churn × Expansion Overlap

**The question:** Does expansion propensity ever overlap with churn risk on the same account?

**Finding: zero overlap** — no account scores Medium/High on churn risk AND 
above 0.5 on expansion propensity simultaneously.

**Why, honestly:** this is a limitation of the synthetic data design, not 
evidence the real-world phenomenon doesn't exist. Each account was generated 
with exactly one lifetime trajectory (stable / declining / growing), making 
churn risk and expansion propensity mutually exclusive by construction — no 
account can be both "declining" and "growing" at once in this dataset. Real 
accounts can absolutely show mixed signals (e.g., usage growing while 
unrelated scaling-pain tickets rise), which this generator doesn't simulate.

**What this means for the project:** stated plainly in the README as a 
named limitation and a concrete "what I'd do differently with real data" 
line — build trajectories that can shift or blend mid-lifecycle rather than 
one label for an account's whole history. The dashboard's cross-flag logic 
is still built and functional (Stage 3) — it will simply show zero flagged 
accounts on this dataset, which is itself an honest, explainable result to 
walk through in the demo video rather than something to hide.
