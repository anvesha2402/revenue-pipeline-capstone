# Revenue Pipeline Capstone

*A full-funnel B2B SaaS revenue pipeline system — five connected models, one dashboard, acquisition through retention and expansion.*

> Headline business insight: **TBD — fill in once all five models are built (Stage 2).**

## The Five Business Questions (project north star)

Every table in `/data`, every model in `/notebooks`, and every chart in the
dashboard should trace back to one of these:

1. **Lead Scoring:** With limited SDR hours, which leads should get worked first?
2. **Deal-Win Probability:** Which open deals will actually close, and can the sales forecast be trusted?
3. **Pipeline Velocity:** Where exactly do deals stall, and how much revenue is sitting stuck right now?
4. **Retention/Churn:** Which active accounts are about to churn, and how much ARR is genuinely at risk?
5. **Expansion/Upsell:** Which healthy accounts are ready to buy more, and what specifically should they be offered?

The cross-model question that ties them together: **does expansion propensity
ever overlap with churn risk on the same account** — and if so, what's the
right single play (not "upsell" or "retain" in isolation)?

## Status
- [x] Data architecture + synthetic dataset (6 tables, `account_id`-linked, deliberately messy)
- [ ] Model layer (5 models + business insights)
- [ ] Dashboard
- [ ] Portfolio packaging (video, LinkedIn post, CV line)
