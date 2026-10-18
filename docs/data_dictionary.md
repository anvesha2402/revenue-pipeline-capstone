# Data dictionary (v2, synthetic)

Seven tables, linked by `account_id`, `opportunity_id` and `lead_id`. Period: 2024-01-01 to 2026-06-30.
Raw files in `data/raw/` are deliberately messy; `data/clean/` holds the cleaned versions produced by `02_clean_and_validate.py`.

## Tables

| Table | Grain | Rows (raw) | Key columns |
|---|---|---|---|
| `leads` | one inbound lead | 30,256 | `lead_id`, `created_date`, `industry`, `company_size_employees`, `region`, `lead_source`, `contact_seniority`, `demo_requested`, `engagement_score` |
| `opportunities` | one deal | 7,886 | `opportunity_id`, `lead_id`, stage entry dates, `closed_date`, `outcome`, `deal_size`, `competitor_present`, `decision_makers_engaged`, `sales_rep_id`, `rep_forecast_pct`, `loss_reason` |
| `accounts` | one won deal that became a customer | 2,420 | `account_id`, `opportunity_id`, `account_tier`, `start_date`, `contract_term_months`, `csm_id`, `initial_acv` |
| `subscriptions` | current subscription state per account | 2,372 | `plan_tier`, `mrr`, `seats_licensed`, `renewal_date`, `status`, `churn_date`, `churn_reason`, `expansions` |
| `subscription_events` | one MRR movement | see file | `event_type` (New, Expansion - seats / tier upgrade / add-on, Contraction, Churn), `mrr_change`, `mrr_after` |
| `usage_events` | account x month | 25,346 | `login_rate`, `active_users`, `seats_licensed`, `features_adopted` (of 12), `events_count`, `api_calls`, `integrations_connected`, `peak_seat_utilization` |
| `support_tickets` | one ticket | 33,923 | `ticket_type`, `severity`, `resolution_hours`, `csat_score`, `is_escalated` |

Derived: `data/clean/account_snapshots.csv` has one row per active account per month-end (features known at that date) plus
`y_churn_90d` and `y_expansion_90d`, defined only when the next 90 days lie inside the data.

## Data-quality issues injected, and what the cleaner did

| Table | Issue | Count found | Treatment |
|---|---|---|---|
| leads | Raw industry spellings collapsing to 11 industries | 26 raw labels | Lookup on lower-cased, trimmed text; blanks become "Unknown" |
| leads | Duplicate leads (same email, different case, a few days later) | 3,247 removed | Keep earliest; never drop a lead an opportunity points to |
| leads | Dates written dd/mm/yyyy | 937 | Parsed explicitly |
| leads | Missing company size / source / seniority | 2,947 / 819 / 1,586 | Kept as "Unknown" (missingness can be informative) |
| leads | Engagement score of -1 used as a blank | 114 | Set to missing |
| opportunities | Raw stage spellings | 18 raw labels | Mapped to 6 stages |
| opportunities | Close date "0000-00-00" or before the create date | 90 + 49 | Rebuilt from the account start date (won) or last stage date plus median dwell (lost); flagged `close_date_reconstructed` |
| opportunities | Missing, zero or negative deal size | 486 | Median of the same size band; flagged `deal_size_imputed` |
| opportunities | Missing decision-makers engaged | 612 | Median plus a missing flag |
| opportunities | Lead id that does not exist | 74 | Kept; lead attributes set to "Unknown" |
| accounts / subscriptions | Accounts with no subscription row | 48 | Rebuilt from `subscription_events` |
| subscriptions | Tier written in mixed case; zero or negative MRR; missing renewal date | 121; 13; 158 | Normalized; MRR taken from the event log; renewal date recomputed from start date and term |
| usage_events | Duplicate rows; active users above seats; missing months | 251; 119; 615 | Dropped; capped at seats; gaps left as gaps (features use available months) |
| support_tickets | Severity spellings (P1-P4, case); missing severity; duplicates | 12 labels; 1,661; 336 | Mapped to 4 levels; "Unknown"; dropped |

Counts were reconciled against an internal log of what the generator injected; every detected count matched except lead
duplicates (a few extra from natural email collisions).
