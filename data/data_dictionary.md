# Data Dictionary — Revenue Pipeline Capstone

All tables key off `account_id`, which traces a customer from first lead touch
through to churn or expansion. Not every table links cleanly to every other —
see "Known data quality issues" per table; that's intentional (see README).

## leads.csv
| Column | Meaning |
|---|---|
| lead_id | Unique lead identifier |
| company_name | Company name |
| industry | Company industry |
| company_size | Employee count |
| lead_source | Acquisition channel |
| created_date | Date lead entered the system |
| pricing_page_visits | Pricing page visits — engagement signal |
| demo_requested | Requested a product demo — engagement signal |
| content_downloads | Gated content downloads — engagement signal |
| email_opens | Marketing emails opened — engagement signal |
| converted | Became a sales opportunity — **target for Lead Scoring model** |
| converted_date | Date of conversion (null if not converted) |

**Known data quality issues:** ~12% missing `company_size`, ~8% missing
`industry`, `industry` has 10+ inconsistent label variants (casing/naming),
~4% duplicate leads (re-submitted forms), `lead_source` has typo variants.

## opportunities.csv
| Column | Meaning |
|---|---|
| opp_id | Unique opportunity identifier |
| lead_id | FK to leads |
| company_name | Company name |
| deal_size | Deal value ($) |
| num_stakeholders | Distinct stakeholders engaged in the deal |
| competitor_present | Whether a competitor was actively mentioned |
| current_stage | Furthest funnel stage reached |
| date_entered_prospecting/qualified/proposal/negotiation | Stage-timestamp history — feeds **Pipeline Velocity** |
| close_date | Date deal closed (null if still open) |
| won | True/False if closed, null if open — **target for Deal-Win Probability model** |

**Known data quality issues:** ~1.5% duplicate records, ~2% `close_date`
entered before the deal started (entry error), ~7% missing `deal_size`,
`current_stage` has 8 label variants instead of the real 4.

## accounts.csv
| Column | Meaning |
|---|---|
| account_id | Unique account identifier — the central join key |
| opp_id | FK to opportunities (**null for ~3% "orphan" accounts** created manually, bypassing the funnel) |
| company_name | Company name |
| account_tier | SMB / Mid-Market / Enterprise, derived from deal size |
| initial_deal_size | Deal size at signup ($) |
| signup_date | Date account was created |

## subscriptions.csv
| Column | Meaning |
|---|---|
| subscription_id | Unique subscription identifier |
| account_id | FK to accounts |
| plan | Starter / Growth / Enterprise |
| mrr | Monthly recurring revenue ($) — a few rows are $0/negative (mislabeled trial/comped accounts) |
| billing_frequency | Monthly / Annual |
| contract_start_date | Start of contract |
| contract_end_date | End of contract (null for month-to-month) |
| status | Active / Churned — **target label source for Retention/Churn model** |
| churn_date | Date of churn (null if still active) |

## usage_events.csv
| Column | Meaning |
|---|---|
| account_id | FK to accounts |
| month | Month of the usage snapshot |
| active_users | Active seats that month |
| features_adopted | Count of product features actively used |
| logins | Total logins that month (a few outlier accounts inflated by a tracking/dedup bug) |

**Known data quality issues:** ~4% of account-months missing entirely
(tracking gaps — not a real usage drop, don't confuse with churn signal).

## support_tickets.csv
| Column | Meaning |
|---|---|
| ticket_id | Unique ticket identifier |
| account_id | FK to accounts |
| opened_date | Date ticket was opened |
| severity | Low / Medium / High (missing for ~10% of tickets) |
| resolved | Whether the ticket was resolved |
| resolution_time_days | Days to resolve (null if unresolved) |

## Internal only — not part of the published dataset
`docs/_ground_truth_trajectory.csv` — per-account lifecycle label
(stable/declining/growing) used only to validate model results against the
data-generation logic. A real company would never have this column; it's
excluded from the "public" data tables on purpose.
