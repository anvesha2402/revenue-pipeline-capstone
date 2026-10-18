# Business insights (v2, synthetic data)

Each section: question, metric, insight, decision, caveat, next question.

## 1. Lead scoring
- **Question:** which inbound leads should reps call first?
- **Metric:** forward ROC-AUC 0.668 (0.658-0.677); conversion by score band 51% (top) to 15% (bottom).
- **Insight:** the top band converts 3.3x the bottom band. Source, seniority, engagement and demo requests carry the signal. A simple model matches XGBoost.
- **Decision:** order the call list by score; route low-score leads to nurture instead of rep time.
- **Caveat:** a score ranks leads; it does not say why a lead converts. Unobserved factors cap the AUC.
- **Next question:** does working leads in score order raise closed revenue per rep-hour? Needs an experiment.

## 2. Deal-win probability
- **Question:** which open deals are likely to close?
- **Metric:** forward ROC-AUC 0.652 (0.635-0.674); reps' forecast alone 0.643; combined 0.677.
- **Insight:** competitor presence is the strongest signal (25% win rate with one vs 41% without). Deal stage is excluded because it leaks the outcome on closed deals.
- **Decision:** managers review competitive deals early and compare the model with the rep's forecast; disagreements are the review list.
- **Caveat:** rep skill and forecasts are simulated from the same hidden win logit, so the model-versus-rep comparison is illustrative.
- **Next question:** which competitor and which loss reason drive the gap?

## 3. Pipeline velocity
- **Question:** where do deals stall and how much revenue sits there?
- **Metric:** median stage days (Qualified 19, Discovery 16, Proposal 19, Negotiation 12); stalled = longer in stage than 75% of comparable deals.
- **Insight:** $6.4M of $32.2M open pipeline is stalled. Qualified has the most stalled dollars ($2.4M); Negotiation has the highest stalled share (29%). Early speed does not change the win rate once a deal reaches Proposal.
- **Velocity:** 748 open deals x $43K average x 35% win rate / 78-day cycle = $144K of new ARR per day.
- **Decision:** target coaching at stalled deals in Qualified first (most dollars), and review Negotiation deals for pricing or legal blockers (highest share).
- **Caveat:** stage durations are simulator inputs.
- **Next question:** which stalled deals are also low on win probability?

## 4. Churn (next 90 days)
- **Question:** which active accounts will cancel, and how much ARR is exposed?
- **Metric:** forward ROC-AUC 0.827 (0.805-0.852); PR-AUC 0.267 vs 4.9% base rate; top 10% of scores holds 49% of churners.
- **Insight:** renewal timing dominates; within a renewal window, falling logins, low seat utilization and low feature adoption separate accounts that leave from those that stay.
- **Exposure:** 279 high-risk accounts hold $7.5M ARR; probability-weighted loss over 90 days is $3.0M. Comparable historical snapshots churned at 4.9% per 90 days.
- **Decision:** start save plays 90 days before renewal for high-risk accounts, ordered by expected ARR loss.
- **Caveat:** correlational. A save play's effect is not measured.
- **Next question:** which intervention, at which lead time, changes the outcome?

## 5. Expansion (next 90 days)
- **Question:** which accounts are ready to buy more?
- **Metric:** forward ROC-AUC 0.800 (0.775-0.825); PR-AUC 0.246 vs 5.6% base rate; top 10% of scores holds 41% of expanders.
- **Insight:** depth of use (activity per user, features adopted, integrations) predicts expansion better than seat-limit hits alone.
- **Exposure:** 263 high-propensity accounts hold $9.4M ARR; expected expansion over 90 days is $1.1M (propensity x historical uplift by tier).
- **Decision:** account managers lead with high-propensity accounts that are not near a renewal risk.
- **Caveat:** deployed model is logistic regression; its top-decile probabilities ran about 30% high before recalibration.
- **Next question:** seat add, tier upgrade or add-on: which play fits which account?

## 6. Cross-model check
- **Question:** are some accounts both a save risk and an expansion candidate?
- **Result:** yes, but rarely. 155 of 11,872 out-of-time snapshots (1.3%) are in the top 20% on both scores, versus 4.0% if the scores were independent. Spearman correlation -0.52.
- **Segments (out-of-time):** Protect churn 16.4%, expansion 1.0%; Grow churn 1.3%, expansion 16.9%; Save & grow churn 12.3%, expansion 11.0%; Maintain churn 2.3%, expansion 3.5%.
- **Decision:** for the 9 live "Save & grow" accounts, resolve the risk driver before pitching expansion.
- **Caveat:** the negative correlation reflects the simulator's design (health feeds both).
