"""
generate_synthetic_data.py
============================
Generates a single, internally-consistent synthetic B2B SaaS revenue-pipeline
dataset for the Revenue Pipeline Capstone project.

WHY SYNTHETIC: no real CRM export is available. Every table here is generated
together, from one random seed, so a single `account_id` traces cleanly from
first lead touch -> opportunity -> won deal -> subscription -> monthly usage
-> support tickets -> churn or expansion. This is disclosed openly in the
README; nothing here is claimed to be real company data.

WHY THE NUMBERS AREN'T RANDOM NOISE: every stage-to-stage transition (lead
conversion, deal win, monthly churn hazard, expansion trigger) is driven by a
logistic function of a handful of "business" features (engagement, adoption,
support experience, contract type, competitor presence, tenure) plus noise.
That's what makes the five downstream models in notebooks/ have something
real to learn, instead of fitting pure randomness.

Output (written to ./data/):
    leads.csv
    opportunities.csv
    opportunity_stage_history.csv
    accounts.csv
    subscriptions.csv
    usage_monthly.csv
    support_tickets.csv

Run:
    python generate_synthetic_data.py
"""

import numpy as np
import pandas as pd
from datetime import date
from faker import Faker

# --------------------------------------------------------------------------
# CONFIG — change these to resize the dataset. Defaults produce a dataset in
# the "few thousand accounts" range, sized to run fast on a laptop while
# still being big enough for the five models to find real signal.
# --------------------------------------------------------------------------
SEED = 42
N_LEADS = 15_000
START_DATE = pd.Timestamp("2023-01-01")
END_DATE = pd.Timestamp("2026-09-01")  # "today" for this synthetic world

INDUSTRIES = [
    "SaaS/Software", "FinTech", "E-commerce/Retail", "Healthcare IT",
    "Manufacturing", "Media/Entertainment", "EdTech", "Logistics",
    "Professional Services", "Telecom",
]
REGIONS = ["North America", "Europe", "APAC", "India", "LATAM", "MEA"]
LEAD_SOURCES = ["Organic Search", "Paid Ads", "Referral", "Outbound SDR", "Event/Webinar", "Partner"]
PLAN_TIERS = ["Starter", "Growth", "Business", "Enterprise"]
STAGES = ["Prospecting", "Qualification", "Proposal", "Negotiation", "Closed"]

rng = np.random.default_rng(SEED)
fake = Faker()
Faker.seed(SEED)


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def random_dates(start, end, n):
    """Vectorized random dates between two Timestamps."""
    start_u = start.value // 10**9
    end_u = end.value // 10**9
    ints = rng.integers(start_u, end_u, n)
    return pd.to_datetime(ints, unit="s")


# --------------------------------------------------------------------------
# 1. LEADS
# --------------------------------------------------------------------------
def generate_leads(n=N_LEADS):
    lead_ids = [f"L{100000 + i}" for i in range(n)]
    account_ids = [f"A{100000 + i}" for i in range(n)]  # pre-assigned; only used if converted

    created_at = random_dates(START_DATE, END_DATE - pd.Timedelta(days=120), n)
    source = rng.choice(LEAD_SOURCES, n, p=[0.28, 0.18, 0.14, 0.22, 0.12, 0.06])
    industry = rng.choice(INDUSTRIES, n)
    region = rng.choice(REGIONS, n, p=[0.30, 0.22, 0.18, 0.15, 0.10, 0.05])
    company_size = rng.choice(
        ["1-50", "51-200", "201-1000", "1000+"], n, p=[0.35, 0.30, 0.22, 0.13]
    )
    size_rank = pd.Series(company_size).map({"1-50": 0, "51-200": 1, "201-1000": 2, "1000+": 3}).to_numpy()

    web_sessions_30d = rng.poisson(4, n) + (size_rank * rng.poisson(1, n))
    content_downloads = rng.poisson(1.2, n)
    demo_requested = rng.binomial(1, 0.22 + 0.05 * size_rank)
    email_open_rate = np.clip(rng.normal(0.35, 0.15, n), 0, 1)
    pricing_page_views = rng.poisson(1.5, n)

    source_boost = pd.Series(source).map(
        {"Referral": 0.9, "Partner": 0.6, "Outbound SDR": 0.2, "Event/Webinar": 0.3,
         "Paid Ads": -0.1, "Organic Search": 0.0}
    ).to_numpy()

    engagement_score = (
        0.10 * web_sessions_30d
        + 0.35 * content_downloads
        + 1.10 * demo_requested
        + 1.40 * email_open_rate
        + 0.20 * pricing_page_views
    )

    logit = (
        -2.6
        + 0.28 * size_rank
        + 0.35 * engagement_score
        + source_boost
        + rng.normal(0, 0.6, n)  # noise so it's learnable, not deterministic
    )
    conv_prob = sigmoid(logit)
    converted = rng.binomial(1, conv_prob)

    conversion_delay_days = rng.integers(2, 45, n)
    conversion_date = created_at + pd.to_timedelta(conversion_delay_days, unit="D")
    conversion_date = np.where(converted == 1, conversion_date, pd.NaT)

    lead_status = np.select(
        [converted == 1, (converted == 0) & (engagement_score > engagement_score.mean())],
        ["Converted", "Working"],
        default="Disqualified",
    )

    leads = pd.DataFrame({
        "lead_id": lead_ids,
        "account_id": account_ids,
        "created_at": created_at,
        "source": source,
        "industry": industry,
        "region": region,
        "company_size": company_size,
        "web_sessions_30d": web_sessions_30d,
        "content_downloads": content_downloads,
        "demo_requested": demo_requested,
        "email_open_rate": np.round(email_open_rate, 3),
        "pricing_page_views": pricing_page_views,
        "engagement_score": np.round(engagement_score, 2),
        "lead_status": lead_status,
        "converted_to_opportunity": converted.astype(bool),
        "conversion_date": pd.to_datetime(conversion_date),
        # ground-truth probability kept for QA/debugging only — drop before modeling
        "_true_conversion_prob": np.round(conv_prob, 4),
    })
    return leads


# --------------------------------------------------------------------------
# 2. OPPORTUNITIES + STAGE HISTORY  (new-business, sourced from converted leads)
# --------------------------------------------------------------------------
def generate_opportunities(leads):
    conv = leads[leads["converted_to_opportunity"]].reset_index(drop=True)
    n = len(conv)
    opp_ids = [f"O{200000 + i}" for i in range(n)]

    size_rank = conv["company_size"].map({"1-50": 0, "51-200": 1, "201-1000": 2, "1000+": 3}).to_numpy()
    plan_tier = np.select(
        [size_rank == 0, size_rank == 1, size_rank == 2, size_rank == 3],
        PLAN_TIERS,
        default=PLAN_TIERS[0],
    )
    base_deal_size = {"Starter": 3000, "Growth": 9000, "Business": 24000, "Enterprise": 65000}
    deal_size_usd = np.array([base_deal_size[t] for t in plan_tier]) * rng.lognormal(0, 0.28, n)
    deal_size_usd = np.round(deal_size_usd, -2)

    competitor_present = rng.binomial(1, 0.35, n)
    num_stakeholders = rng.integers(1, 7, n)
    se_involved = rng.binomial(1, 0.30 + 0.10 * size_rank)
    engagement_score = conv["engagement_score"].to_numpy()

    win_logit = (
        -0.4
        + 0.45 * se_involved
        - 0.55 * competitor_present
        + 0.10 * np.minimum(num_stakeholders, 4)
        - 0.03 * np.maximum(num_stakeholders - 4, 0)  # too many stakeholders slows things down
        + 0.22 * engagement_score
        + rng.normal(0, 0.7, n)
    )
    win_prob = sigmoid(win_logit)
    outcome_roll = rng.random(n)
    still_open_mask = rng.random(n) < 0.06  # a slice of recent opps are still open (unresolved)
    outcome = np.where(outcome_roll < win_prob, "Won", "Lost")
    outcome = np.where(still_open_mask, "Open", outcome)

    created_date = conv["conversion_date"]
    total_cycle_days = rng.integers(14, 150, n).astype(float)
    total_cycle_days += competitor_present * rng.integers(0, 30, n)
    total_cycle_days -= se_involved * rng.integers(0, 15, n)
    total_cycle_days = np.clip(total_cycle_days, 7, None)
    close_date = created_date + pd.to_timedelta(total_cycle_days, unit="D")
    close_date = np.where(outcome == "Open", pd.NaT, close_date)

    opps = pd.DataFrame({
        "opportunity_id": opp_ids,
        "account_id": conv["account_id"].to_numpy(),
        "lead_id": conv["lead_id"].to_numpy(),
        "opp_type": "New Business",
        "created_date": created_date.to_numpy(),
        "close_date": pd.to_datetime(close_date),
        "product_tier": plan_tier,
        "deal_size_usd": deal_size_usd,
        "competitor_present": competitor_present.astype(bool),
        "num_stakeholders": num_stakeholders,
        "sales_engineering_involved": se_involved.astype(bool),
        "engagement_score": engagement_score,
        "total_cycle_days": total_cycle_days.round(0),
        "outcome": outcome,
        "_true_win_prob": np.round(win_prob, 4),
    })
    return opps


def generate_stage_history(opps):
    """Per-opportunity stage timestamps, for the pipeline-velocity notebook."""
    rows = []
    for opp in opps.itertuples():
        n_stages = len(STAGES) if opp.outcome != "Open" else rng.integers(1, len(STAGES))
        cycle = opp.total_cycle_days
        # split total cycle time into stage chunks; deals with a competitor present or
        # no SE involvement stall longer in Proposal/Negotiation
        weights = rng.dirichlet(np.ones(n_stages)) if n_stages > 1 else np.array([1.0])
        if opp.competitor_present and n_stages >= 4:
            weights[2:4] *= 1.6
            weights /= weights.sum()
        durations = np.maximum((weights * cycle).round(0), 1)

        entered = opp.created_date
        for i in range(n_stages):
            exited = entered + pd.to_timedelta(durations[i], unit="D")
            rows.append({
                "opportunity_id": opp.opportunity_id,
                "stage": STAGES[i],
                "entered_at": entered,
                "exited_at": exited if (i < n_stages - 1 or opp.outcome != "Open") else pd.NaT,
                "days_in_stage": durations[i],
            })
            entered = exited
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 3. ACCOUNTS  (created from Won new-business opportunities)
# --------------------------------------------------------------------------
def generate_accounts(leads, won_opps):
    lead_lookup = leads.set_index("lead_id")[["industry", "region", "company_size"]]
    accts = won_opps.join(lead_lookup, on="lead_id")

    n = len(accts)
    account_ids = accts["account_id"].to_numpy()
    signup_date = accts["close_date"].to_numpy()
    plan_tier = accts["product_tier"].to_numpy()
    mrr = (accts["deal_size_usd"].to_numpy() / 12).round(2)
    contract_type = rng.choice(["Monthly", "Annual"], n, p=[0.30, 0.70])
    csm_owner = [fake.first_name() + " " + fake.last_name()[0] + "." for _ in range(n)]

    accounts = pd.DataFrame({
        "account_id": account_ids,
        "account_name": [fake.company() for _ in range(n)],
        "industry": accts["industry"].to_numpy(),
        "region": accts["region"].to_numpy(),
        "company_size": accts["company_size"].to_numpy(),
        "plan_tier": plan_tier,
        "contract_type": contract_type,
        "signup_date": signup_date,
        "initial_mrr": mrr,
        "csm_owner": csm_owner,
        # filled in later by the usage/churn simulation:
        "account_status": "Active",
        "churn_date": pd.NaT,
        "current_mrr": mrr,
        "current_plan_tier": plan_tier,
    })
    return accounts


# --------------------------------------------------------------------------
# 4. MONTHLY USAGE + SUPPORT TICKETS + CHURN/EXPANSION SIMULATION
#    (this is the engine that drives the retention & expansion models)
# --------------------------------------------------------------------------
def simulate_lifecycle(accounts):
    usage_rows = []
    ticket_rows = []
    sub_rows = []
    expansion_opp_rows = []
    account_update_rows = []

    plan_rank = {"Starter": 0, "Growth": 1, "Business": 2, "Enterprise": 3}

    for acct in accounts.itertuples():
        signup = pd.Timestamp(acct.signup_date)
        if pd.isna(signup) or signup >= END_DATE:
            continue

        months = pd.date_range(signup.replace(day=1), END_DATE, freq="MS")
        tenure_months = 0
        health = rng.normal(65, 12)          # 0-100 "adoption health" baseline
        health = np.clip(health, 20, 95)
        plan = acct.plan_tier
        mrr = acct.initial_mrr
        churned = False
        churn_month = pd.NaT
        expanded_once = False

        sub_id = f"S{300000 + acct.Index}"
        sub_rows.append({
            "subscription_id": sub_id, "account_id": acct.account_id,
            "plan_tier": plan, "mrr": mrr, "start_date": signup,
            "end_date": pd.NaT, "status": "Active", "billing_cycle": acct.contract_type,
        })

        for m in months:
            tenure_months += 1

            # health drifts: random walk, nudged by ramp-up period and support pain
            ramp_bonus = 3 if tenure_months <= 3 else 0
            health += rng.normal(ramp_bonus - 0.4, 4)
            health = np.clip(health, 5, 100)

            active_users = max(1, int(rng.poisson(5 + plan_rank[plan] * 6) * (health / 65)))
            feature_adoption_pct = np.clip(health / 100 + rng.normal(0, 0.05), 0.05, 1.0)
            logins_per_user = np.clip(rng.normal(8 + health / 12, 3), 0.5, None)
            api_calls = int(max(0, rng.normal(200 + plan_rank[plan] * 400, 80) * (health / 65)))

            # support tickets: worse health -> more tickets, lower csat
            n_tickets = rng.poisson(max(0.15, (100 - health) / 45))
            for _ in range(n_tickets):
                created = m + pd.to_timedelta(rng.integers(0, 27), unit="D")
                priority = rng.choice(["Low", "Medium", "High", "Critical"], p=[0.45, 0.32, 0.18, 0.05])
                resolve_days = rng.integers(1, 10)
                csat = np.clip(rng.normal(health / 20, 1.0), 1, 5)
                ticket_rows.append({
                    "ticket_id": f"T{400000 + len(ticket_rows)}",
                    "account_id": acct.account_id,
                    "created_date": created,
                    "priority": priority,
                    "resolved_date": created + pd.to_timedelta(resolve_days, unit="D"),
                    "csat_score": round(float(csat), 1),
                })

            price_increase_flag = tenure_months in (12, 24, 36) and rng.random() < 0.4

            usage_rows.append({
                "account_id": acct.account_id,
                "month": m,
                "tenure_months": tenure_months,
                "active_users": active_users,
                "feature_adoption_pct": round(float(feature_adoption_pct), 3),
                "logins_per_user": round(float(logins_per_user), 1),
                "api_calls": api_calls,
                "support_tickets_this_month": n_tickets,
                "health_score": round(float(health), 1),
                "mrr": round(float(mrr), 2),
                "plan_tier": plan,
                "price_increase_flag": price_increase_flag,
            })

            # ---- churn hazard (monthly) ----
            churn_logit = (
                -4.3
                + 0.045 * (60 - health)
                + 0.35 * (acct.contract_type == "Monthly")
                - 0.02 * min(tenure_months, 24)          # tenure protects, up to a point
                + 0.5 * price_increase_flag
                + 0.30 * (n_tickets >= 3)
                + rng.normal(0, 0.4)
            )
            churn_hazard = sigmoid(churn_logit)
            if tenure_months >= 2 and rng.random() < churn_hazard:
                churned = True
                churn_month = m
                break

            # ---- expansion trigger (can happen once per account) ----
            if (not expanded_once and tenure_months >= 6 and health > 75
                    and plan_rank[plan] < 3 and rng.random() < 0.02):
                expanded_once = True
                new_plan = PLAN_TIERS[plan_rank[plan] + 1]
                new_mrr = round(mrr * rng.uniform(1.4, 2.2), 2)
                expansion_opp_rows.append({
                    "opportunity_id": f"O{500000 + len(expansion_opp_rows)}",
                    "account_id": acct.account_id,
                    "lead_id": np.nan,
                    "opp_type": "Expansion",
                    "created_date": m,
                    "close_date": m + pd.to_timedelta(rng.integers(10, 40), unit="D"),
                    "product_tier": new_plan,
                    "deal_size_usd": round((new_mrr - mrr) * 12, 2),
                    "competitor_present": False,
                    "num_stakeholders": rng.integers(1, 3),
                    "sales_engineering_involved": bool(rng.binomial(1, 0.5)),
                    "engagement_score": round(float(health / 10), 2),
                    "total_cycle_days": rng.integers(10, 40),
                    "outcome": "Won",
                    "_true_win_prob": np.nan,
                })
                plan = new_plan
                mrr = new_mrr

        account_update_rows.append({
            "account_id": acct.account_id,
            "account_status": "Churned" if churned else "Active",
            "churn_date": churn_month,
            "current_mrr": mrr,
            "current_plan_tier": plan,
        })

    return (pd.DataFrame(usage_rows), pd.DataFrame(ticket_rows), pd.DataFrame(sub_rows),
            pd.DataFrame(expansion_opp_rows), pd.DataFrame(account_update_rows))


def main():
    print("Generating leads...")
    leads = generate_leads()

    print("Generating new-business opportunities...")
    opps = generate_opportunities(leads)

    print("Generating opportunity stage history...")
    stage_history = generate_stage_history(opps)

    won_opps = opps[opps["outcome"] == "Won"].copy()
    print(f"  {len(leads):,} leads -> {len(opps):,} opportunities -> {len(won_opps):,} won (new accounts)")

    print("Generating accounts...")
    accounts = generate_accounts(leads, won_opps)

    print("Simulating monthly usage, support tickets, churn & expansion "
          f"for {len(accounts):,} accounts (this is the slow step)...")
    usage, tickets, subs, expansion_opps, updates = simulate_lifecycle(accounts)

    updates = updates.set_index("account_id")
    accounts = accounts.set_index("account_id")
    accounts.update(updates)
    accounts = accounts.reset_index()

    all_opps = pd.concat([opps.drop(columns=["_true_win_prob"]),
                           expansion_opps.drop(columns=["_true_win_prob"])],
                          ignore_index=True)

    # drop ground-truth debug columns from the "public" leads table
    leads_public = leads.drop(columns=["_true_conversion_prob"])

    print("Writing CSVs to ./data/ ...")
    leads_public.to_csv("leads.csv", index=False)
    all_opps.to_csv("opportunities.csv", index=False)
    stage_history.to_csv("opportunity_stage_history.csv", index=False)
    accounts.to_csv("accounts.csv", index=False)
    subs.to_csv("subscriptions.csv", index=False)
    usage.to_csv("usage_monthly.csv", index=False)
    tickets.to_csv("support_tickets.csv", index=False)

    print("\nDone. Row counts:")
    for name, df in [("leads", leads_public), ("opportunities", all_opps),
                      ("opportunity_stage_history", stage_history), ("accounts", accounts),
                      ("subscriptions", subs), ("usage_monthly", usage),
                      ("support_tickets", tickets)]:
        print(f"  {name:28s} {len(df):>8,} rows")

    churn_rate = (accounts["account_status"] == "Churned").mean()
    print(f"\n  Overall churn rate across accounts: {churn_rate:.1%}")
    print(f"  Total active MRR: ${accounts.loc[accounts.account_status=='Active','current_mrr'].sum():,.0f}")


if __name__ == "__main__":
    main()
