#!/usr/bin/env python3
"""
02_clean_and_validate.py
Reads data/raw/*.csv (deliberately messy), writes data/clean/*.csv and docs/data_quality_report.json.

Every rule is detect -> fix -> count. Counts are written to the report so the cleaning is auditable.
(Internal check: detected counts are compared with docs/_injected_issues_log.json when present.)
"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

RAW = sys.argv[1] if len(sys.argv) > 1 else "data/raw"
CLEAN = sys.argv[2] if len(sys.argv) > 2 else "data/clean"
DOCS = sys.argv[3] if len(sys.argv) > 3 else "docs"
os.makedirs(CLEAN, exist_ok=True)
rep = {}

IND_MAP = {
    "saas": "SaaS", "software (saas)": "SaaS",
    "fintech": "FinTech", "fin-tech": "FinTech", "financial tech": "FinTech",
    "healthcare": "Healthcare", "health care": "Healthcare",
    "manufacturing": "Manufacturing", "mfg": "Manufacturing",
    "retail & e-commerce": "Retail & E-commerce", "retail/ecom": "Retail & E-commerce", "ecommerce": "Retail & E-commerce",
    "logistics": "Logistics", "supply chain": "Logistics",
    "education": "Education", "edtech": "Education",
    "media": "Media", "media & ent.": "Media",
    "telecom": "Telecom", "telecommunications": "Telecom",
    "energy": "Energy", "energy & utilities": "Energy",
    "professional services": "Professional Services", "consulting": "Professional Services",
}
STAGE_MAP = {
    "qualified": "Qualified", "qualifed": "Qualified", "discovery": "Discovery", "disco": "Discovery",
    "proposal": "Proposal", "proposal sent": "Proposal", "negotiation": "Negotiation", "neg.": "Negotiation",
    "closed won": "Closed Won", "closed-won": "Closed Won", "won": "Closed Won",
    "closed lost": "Closed Lost", "closed-lost": "Closed Lost", "lost": "Closed Lost",
}
SEV_MAP = {"low": "Low", "p4": "Low", "medium": "Medium", "med": "Medium", "p3": "Medium",
           "high": "High", "p2": "High", "critical": "Critical", "p1": "Critical"}
STAGES = ["Qualified", "Discovery", "Proposal", "Negotiation"]
CUTOFF = pd.Timestamp("2026-06-30")


def canon_ind(x):
    if pd.isna(x):
        return "Unknown"
    return IND_MAP.get(str(x).strip().lower(), "Unknown")


def parse_mixed(s):
    """ISO yyyy-mm-dd or dd/mm/yyyy -> Timestamp; anything else -> NaT."""
    s = s.astype("string")
    out = pd.to_datetime(s.where(s.str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)), format="%Y-%m-%d", errors="coerce")
    sl = s.where(s.str.match(r"^\d{2}/\d{2}/\d{4}$", na=False))
    out2 = pd.to_datetime(sl, format="%d/%m/%Y", errors="coerce")
    return out.fillna(out2), int(sl.notna().sum())


# ---------------------------------------------------------------- opportunities first (leads need converted flag)
O = pd.read_csv(f"{RAW}/opportunities.csv")
rep["opportunities.raw_rows"] = len(O)
rep["opportunities.raw_unique_stage_labels"] = int(O["stage"].nunique())
O["stage"] = O["stage"].astype(str).str.strip().str.lower().map(STAGE_MAP)
rep["opportunities.unmapped_stage_labels"] = int(O["stage"].isna().sum())
O["outcome"] = np.where(O["stage"] == "Closed Won", "Won", np.where(O["stage"] == "Closed Lost", "Lost", "Open"))
date_cols = ["created_date", "qualified_date", "discovery_date", "proposal_date", "negotiation_date", "closed_date"]
bad_close = O["closed_date"].astype("string").str.startswith("0000", na=False)
rep["opportunities.bad_close_date_zeros"] = int(bad_close.sum())
for c in date_cols:
    O[c] = pd.to_datetime(O[c].where(~O[c].astype("string").str.startswith("0000", na=False)), errors="coerce")
neg_cycle = O["closed_date"].notna() & (O["closed_date"] < O["created_date"])
rep["opportunities.close_before_create"] = int(neg_cycle.sum())
O.loc[neg_cycle, "closed_date"] = pd.NaT
O["close_date_reconstructed"] = False
# reconstruct missing close dates for closed deals: Won -> account start_date; Lost -> last stage entry + median dwell
A_raw = pd.read_csv(f"{RAW}/accounts.csv", parse_dates=["start_date"])
won_start = A_raw.set_index("opportunity_id")["start_date"]
need = O["outcome"].isin(["Won", "Lost"]) & O["closed_date"].isna()
w = need & (O["outcome"] == "Won")
O.loc[w, "closed_date"] = O.loc[w, "opportunity_id"].map(won_start)
need2 = O["outcome"].isin(["Won", "Lost"]) & O["closed_date"].isna()
med_dwell = {}
stage_cols = ["qualified_date", "discovery_date", "proposal_date", "negotiation_date", "closed_date"]
ok = O["outcome"].eq("Won") & O["closed_date"].notna()
for i, s in enumerate(STAGES):
    nxt = stage_cols[i + 1]
    m = O[stage_cols[i]].notna() & O[nxt].notna()
    med_dwell[s] = float((O.loc[m, nxt] - O.loc[m, stage_cols[i]]).dt.days.median()) if m.any() else 15.0
for idx in O.index[need2]:
    last = None
    for s, c in zip(STAGES, stage_cols[:4]):
        if pd.notna(O.at[idx, c]):
            last = (s, O.at[idx, c])
    base = last[1] if last else O.at[idx, "created_date"]
    O.at[idx, "closed_date"] = base + pd.Timedelta(days=med_dwell.get(last[0], 15) if last else 15)
O.loc[need, "close_date_reconstructed"] = True
rep["opportunities.close_date_reconstructed"] = int(need.sum())
O["closed_date"] = O["closed_date"].where(O["closed_date"] <= CUTOFF)
bad_size = O["deal_size"].isna() | (O["deal_size"] <= 0)
rep["opportunities.missing_or_nonpositive_deal_size"] = int(bad_size.sum())

# ---------------------------------------------------------------- leads
L = pd.read_csv(f"{RAW}/leads.csv")
rep["leads.raw_rows"] = len(L)
rep["leads.raw_unique_industry_labels"] = int(L["industry"].nunique())
L["created_date"], n_ddmm = parse_mixed(L["created_date"])
rep["leads.dd_mm_yyyy_dates_normalized"] = n_ddmm
rep["leads.unparseable_dates"] = int(L["created_date"].isna().sum())
L["industry"] = L["industry"].map(canon_ind)
rep["leads.clean_unique_industry_labels"] = int(L["industry"].nunique())
L["email_key"] = L["contact_email"].str.lower().str.strip()
L = L.sort_values(["created_date", "lead_id"]).reset_index(drop=True)
dup = L.duplicated("email_key", keep="first") & ~L["lead_id"].isin(set(O["lead_id"]))  # never drop a lead an opportunity points to
rep["leads.duplicates_removed"] = int(dup.sum())
L = L[~dup].drop(columns="email_key").reset_index(drop=True)
sent = L["engagement_score"] < 0
rep["leads.engagement_sentinel_to_null"] = int(sent.sum())
L.loc[sent, "engagement_score"] = np.nan
rep["leads.missing_company_size"] = int(L["company_size_employees"].isna().sum())
L["size_band"] = L["size_band"].where(L["company_size_employees"].notna(), "Unknown")
for c in ["lead_source", "contact_seniority"]:
    rep[f"leads.missing_{c}"] = int(L[c].isna().sum())
    L[c] = L[c].fillna("Unknown")
rep["leads.missing_industry_after_canon"] = int((L["industry"] == "Unknown").sum())

# ---------------------------------------------------------------- opportunities (continued)
lead_ids = set(L["lead_id"])
rep["opportunities.orphan_lead_id"] = int((~O["lead_id"].isin(lead_ids)).sum())
size_by_band = L.set_index("lead_id")["size_band"]
O["size_band"] = O["lead_id"].map(size_by_band).fillna("Unknown")
O["deal_size_imputed"] = bad_size
med_by_band = O.loc[~bad_size].groupby("size_band")["deal_size"].median()
O.loc[bad_size, "deal_size"] = O.loc[bad_size, "size_band"].map(med_by_band).fillna(O.loc[~bad_size, "deal_size"].median())
rep["opportunities.missing_decision_makers"] = int(O["decision_makers_engaged"].isna().sum())
O["decision_makers_missing"] = O["decision_makers_engaged"].isna().astype(int)
O["decision_makers_engaged"] = O["decision_makers_engaged"].fillna(O["decision_makers_engaged"].median())
O["competitor_name"] = O["competitor_name"].fillna("")
O["loss_reason"] = O["loss_reason"].fillna("")
O["rep_forecast_missing"] = O["rep_forecast_pct"].isna().astype(int)
conv_ids = set(O["lead_id"])
L["converted"] = L["lead_id"].isin(conv_ids).astype(int)
rep["opportunities.clean_rows"] = len(O)

# ---------------------------------------------------------------- subscription events = source of truth for subscription state
E = pd.read_csv(f"{RAW}/subscription_events.csv", parse_dates=["event_date"])
S_raw = pd.read_csv(f"{RAW}/subscriptions.csv")
rep["subscriptions.raw_rows"] = len(S_raw)
A = A_raw.copy()
rep["accounts.raw_rows"] = len(A)
orph = ~A["account_id"].isin(S_raw["account_id"])
rep["accounts.orphan_no_subscription_row"] = int(orph.sum())
E = E.sort_values(["account_id", "event_date"])
last = E.groupby("account_id").tail(1).set_index("account_id")
churn_ev = E[E["event_type"] == "Churn"].set_index("account_id")["event_date"]
tier_map = {"starter": "Starter", "growth": "Growth", "enterprise": "Enterprise"}
S = S_raw.copy()
S["plan_tier"] = S["plan_tier"].str.strip().str.lower().map(tier_map)
rep["subscriptions.tier_case_fixed"] = int((S_raw["plan_tier"] != S["plan_tier"]).sum())
bad_mrr = S["mrr"] <= 0
rep["subscriptions.nonpositive_mrr_repaired_from_event_log"] = int(bad_mrr.sum())
# rebuild missing subscription rows from the event log
miss = A.loc[orph, ["account_id", "start_date", "contract_term_months"]].copy()
miss["status"] = np.where(miss["account_id"].isin(churn_ev.index), "Churned", "Active")
miss["plan_tier"] = A.set_index("account_id").loc[miss["account_id"], "account_tier"].to_numpy()
miss["subscription_id"] = [f"SR{i:05d}" for i in range(len(miss))]
miss["churn_date"] = miss["account_id"].map(churn_ev)
miss["initial_mrr"] = E[E["event_type"] == "New"].set_index("account_id").loc[miss["account_id"], "mrr_after"].to_numpy()
S["start_date"] = pd.to_datetime(S["start_date"])
S["churn_date"] = pd.to_datetime(S["churn_date"])
S["renewal_date"] = pd.to_datetime(S["renewal_date"])
S = pd.concat([S, miss], ignore_index=True)
S["mrr"] = S["account_id"].map(last["mrr_after"]).where(S["status"] == "Active", S["account_id"].map(
    E[E["event_type"] != "Churn"].groupby("account_id")["mrr_after"].last()))
S["subscription_rebuilt_from_events"] = S["subscription_id"].str.startswith("SR")
miss_renew = S["renewal_date"].isna()
rep["subscriptions.missing_renewal_date_recomputed"] = int(miss_renew.sum())
term = S["contract_term_months"]
def recompute_renewal(row):
    ref = row["churn_date"] if pd.notna(row["churn_date"]) else CUTOFF
    j = 1
    while row["start_date"] + pd.DateOffset(months=int(row["contract_term_months"]) * j) <= ref:
        j += 1
    return row["start_date"] + pd.DateOffset(months=int(row["contract_term_months"]) * j)
S.loc[miss_renew, "renewal_date"] = S[miss_renew].apply(recompute_renewal, axis=1)
S["churn_reason"] = S["churn_reason"].fillna("")
S["expansions"] = S["expansions"].fillna(0).astype(int)
S["seats_licensed"] = S["seats_licensed"].fillna(S["seats_licensed"].median())
rep["subscriptions.clean_rows"] = len(S)

# accounts
ind_from_lead = L.set_index("lead_id")["industry"]
opp_lead = O.set_index("opportunity_id")["lead_id"]
A["industry"] = A["industry"].map(canon_ind)
fix = A["industry"].eq("Unknown")
A.loc[fix, "industry"] = A.loc[fix, "opportunity_id"].map(opp_lead).map(ind_from_lead).fillna("Unknown")
rep["accounts.industry_filled_from_lead"] = int((fix & ~A["industry"].eq("Unknown")).sum())
rep["accounts.industry_still_unknown"] = int(A["industry"].eq("Unknown").sum())

# usage
U = pd.read_csv(f"{RAW}/usage_events.csv", parse_dates=["month_end"])
rep["usage_events.raw_rows"] = len(U)
dups = U.duplicated(["account_id", "month_end"], keep="first")
rep["usage_events.duplicates_removed"] = int(dups.sum())
U = U[~dups].copy()
over = U["active_users"] > U["seats_licensed"]
rep["usage_events.active_users_capped_at_seats"] = int(over.sum())
U.loc[over, "active_users"] = U.loc[over, "seats_licensed"]
U["seat_utilization"] = U["active_users"] / U["seats_licensed"]
# recompute login_rate consistently with capped users
U["login_rate"] = np.where(over, U["seat_utilization"], U["login_rate"])
U = U.sort_values(["account_id", "month_end"]).reset_index(drop=True)
exp_rows = 0
for aid, g in U.groupby("account_id"):
    full = pd.date_range(g["month_end"].min(), g["month_end"].max(), freq="ME")
    exp_rows += len(full) - len(g)
rep["usage_events.missing_months_inside_account_life"] = int(exp_rows)

# tickets
T = pd.read_csv(f"{RAW}/support_tickets.csv", parse_dates=["created_date"])
rep["support_tickets.raw_rows"] = len(T)
rep["support_tickets.raw_unique_severity_labels"] = int(T["severity"].nunique())
d = T.duplicated("ticket_id", keep="first")
rep["support_tickets.duplicates_removed"] = int(d.sum())
T = T[~d].copy()
T["severity"] = T["severity"].astype("string").str.strip().str.lower().map(SEV_MAP)
rep["support_tickets.missing_severity"] = int(T["severity"].isna().sum())
rep["support_tickets.clean_unique_severity_labels"] = int(T["severity"].nunique())
T["severity"] = T["severity"].fillna("Unknown")

# write
L.to_csv(f"{CLEAN}/leads.csv", index=False)
O.to_csv(f"{CLEAN}/opportunities.csv", index=False)
A.to_csv(f"{CLEAN}/accounts.csv", index=False)
S.to_csv(f"{CLEAN}/subscriptions.csv", index=False)
E.to_csv(f"{CLEAN}/subscription_events.csv", index=False)
U.to_csv(f"{CLEAN}/usage_events.csv", index=False)
T.to_csv(f"{CLEAN}/support_tickets.csv", index=False)

# internal reconciliation against the injected-issue log (not part of the public report)
inj = f"{DOCS}/_injected_issues_log.json"
if os.path.exists(inj):
    log = json.load(open(inj))
    chk = {
        "leads.duplicates (injected vs removed)": (log["leads.duplicate_rows_added"], rep["leads.duplicates_removed"]),
        "leads.dd/mm dates": (log["leads.dd_mm_yyyy_dates"], rep["leads.dd_mm_yyyy_dates_normalized"]),
        "opps.zero date": (log["opportunities.bad_close_date_zeros"], rep["opportunities.bad_close_date_zeros"]),
        "opps.close<create": (log["opportunities.close_before_create"], rep["opportunities.close_before_create"]),
        "accounts.orphans": (log["accounts.orphan_no_subscription"], rep["accounts.orphan_no_subscription_row"]),
        "usage.dups": (log["usage_events.duplicate_rows"], rep["usage_events.duplicates_removed"]),
        "tickets.dups": (log["support_tickets.duplicate_rows"], rep["support_tickets.duplicates_removed"]),
        "tickets.missing_sev": (log["support_tickets.missing_severity"], rep["support_tickets.missing_severity"]),
    }
    for k, (i, d_) in chk.items():
        print(f"  {k:42s} injected={i:>6} detected={d_:>6} {'OK' if i == d_ else 'DIFF'}")
json.dump(rep, open(f"{DOCS}/data_quality_report.json", "w"), indent=2)
print(json.dumps(rep, indent=1))
