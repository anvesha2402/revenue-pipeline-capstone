#!/usr/bin/env python3
"""
Revenue Pipeline Capstone - synthetic data generator v2
=======================================================

What changed from v1 (and why)
------------------------------
1. Two INDEPENDENT-ish latent drivers per account instead of one fixed "trajectory":
     H (customer health)  -> drives churn, login rate, tickets
     G (growth / need)    -> drives expansion, feature adoption, API usage
   corr(H, G) is mild (0.25), and both can shift mid-life. An account can therefore be
   growing AND unhappy at the same time (fixes the "zero churn x expansion overlap" artifact).
2. Every observed signal is a NOISY function of the latents. No deterministic formulas
   (fixes the "features_adopted = 1.000 AUC" artifact).
3. Everything is dated, so models can be validated forward in time. Monthly usage rows,
   dated tickets, dated MRR events (new / expansion / contraction / churn).
4. ~2,400 accounts instead of 473.
5. Added CRM fields a real RevOps team has: region, sales rep, rep forecast, discount.
6. Realistic contract mechanics: churn happens mostly at renewal dates.

Calibration rule
----------------
Only BASE RATES are calibrated (lead->opp ~30%, win ~35%, annual churn ~13%, annual
expansion ~20%). Effect sizes and noise levels are fixed a priori in CONFIG below and
are NOT tuned to hit any model score. Model AUCs are whatever falls out.

Usage:  python generate_synthetic_data_v2.py --out data/raw --docs docs
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
from faker import Faker
from scipy.special import expit

CONFIG = dict(
    seed=42,
    start="2024-01-01",
    cutoff="2026-06-30",
    # volumes
    leads_per_month_start=500,
    leads_per_month_end=1300,
    # base-rate targets (the ONLY calibrated quantities)
    target_lead_to_opp=0.30,
    target_win_rate=0.35,
    target_annual_churn=0.13,
    target_annual_expansion=0.20,
    # latent dynamics (a priori)
    corr_H_G=0.25,
    H_persistence=0.90,
    G_persistence=0.90,
    H_innov_sd=0.35,
    G_innov_sd=0.35,
    H_shock_neg_prob=0.035, H_shock_neg_mean=-1.3, H_shock_neg_sd=0.4,
    H_shock_pos_prob=0.010, H_shock_pos_mean=0.8,
    G_shock_pos_prob=0.040, G_shock_pos_mean=1.1, G_shock_pos_sd=0.4,
    G_shock_neg_prob=0.015, G_shock_neg_mean=-0.9,
    # observation noise (a priori; same order of magnitude for every signal)
    login_noise_sd=0.55,
    feature_noise_sd=0.50,
    events_noise_sd=0.35,
    api_noise_sd=0.70,
    # hazards (effect sizes a priori; intercepts calibrated to base rates)
    churn_coef_H=-1.0, churn_coef_G=-0.25, churn_frailty_sd=0.40,
    churn_midterm_offset=-4.0, churn_enterprise=-0.35, churn_early_tenure=0.40,
    churn_exogenous_monthly=0.001,
    exp_coef_G=0.90, exp_coef_H=0.30, exp_seat_limit=0.60, exp_renewal=0.80,
    exp_recent_expansion=-0.80,
)

CAN_INDUSTRIES = ["SaaS", "FinTech", "Healthcare", "Manufacturing", "Retail & E-commerce",
                  "Logistics", "Education", "Media", "Telecom", "Energy", "Professional Services"]
IND_WEIGHTS = [.18, .12, .10, .10, .11, .07, .06, .06, .06, .06, .08]
# 17+ raw spellings that collapse to the 11 canonical industries (injected as messiness)
IND_VARIANTS = {
    "SaaS": ["SaaS", "saas ", "Software (SaaS)"],
    "FinTech": ["FinTech", "Fin-Tech", "financial tech"],
    "Healthcare": ["Healthcare", "Health Care", "healthcare "],
    "Manufacturing": ["Manufacturing", "Mfg"],
    "Retail & E-commerce": ["Retail & E-commerce", "Retail/Ecom", "ecommerce"],
    "Logistics": ["Logistics", "Supply Chain"],
    "Education": ["Education", "EdTech"],
    "Media": ["Media", "Media & Ent."],
    "Telecom": ["Telecom", "Telecommunications"],
    "Energy": ["Energy", "Energy & Utilities"],
    "Professional Services": ["Professional Services", "Consulting"],
}
SOURCES = ["Webinar", "Paid Search", "Organic Search", "Referral", "Outbound SDR", "Event", "Partner"]
SRC_P = [.16, .22, .20, .10, .14, .10, .08]
SENIORITY = ["Individual Contributor", "Manager", "Director", "VP / C-level"]
SEN_P = [.34, .34, .20, .12]
REGIONS = ["North America", "EMEA", "APAC", "LATAM"]
REG_P = [.36, .30, .26, .08]
BANDS = ["1-50", "51-200", "201-1,000", "1,001-5,000", "5,000+"]
BAND_EDGES = [0, 50, 200, 1000, 5000, 10 ** 9]
DEAL_MEDIAN = {"1-50": 6000, "51-200": 15000, "201-1,000": 38000, "1,001-5,000": 85000, "5,000+": 160000}
STAGES = ["Qualified", "Discovery", "Proposal", "Negotiation"]
STAGE_MEDIAN_DAYS = [20, 17, 19, 12]
LOSS_REASONS = ["Price", "Chose competitor", "No decision", "Product fit", "Timing / budget"]
CSMS = [f"CSM{str(i).zfill(2)}" for i in range(1, 9)]
TICKET_TYPES = ["Bug", "How-to", "Integration", "Billing", "Feature Request", "Outage"]
SEVERITIES = ["Low", "Medium", "High", "Critical"]
TIER_PRICE_PER_SEAT_YEAR = {"Starter": 360, "Growth": 540, "Enterprise": 720}
TIER_ORDER = ["Starter", "Growth", "Enterprise"]


def month_index(ts, start):
    return (ts.year - start.year) * 12 + ts.month - start.month


def bisect(fn, lo, hi, target, iters=40):
    for _ in range(iters):
        mid = (lo + hi) / 2
        if fn(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ---------------------------------------------------------------- leads
def gen_leads(rng, fake, cfg, start, cutoff):
    ms = pd.date_range(start, cutoff, freq="MS")
    n_m = np.round(np.linspace(cfg["leads_per_month_start"], cfg["leads_per_month_end"], len(ms))
                   + rng.normal(0, 25, len(ms))).astype(int)
    mi = np.repeat(np.arange(len(ms)), n_m)
    dim = ms.days_in_month.to_numpy()
    days = (rng.random(len(mi)) * dim[mi]).astype(int)
    created = (pd.Series(ms[mi]) + pd.to_timedelta(days, unit="D")).clip(upper=cutoff)
    N = len(created)

    industry = rng.choice(CAN_INDUSTRIES, N, p=IND_WEIGHTS)
    emp = np.clip(np.exp(rng.normal(np.log(250), 1.5, N)), 5, 80000).astype(int)
    band = pd.cut(emp, BAND_EDGES, labels=BANDS).astype(str)
    region = rng.choice(REGIONS, N, p=REG_P)
    source = rng.choice(SOURCES, N, p=SRC_P)
    seniority = rng.choice(SENIORITY, N, p=SEN_P)
    demo_base = {"Webinar": .16, "Paid Search": .12, "Organic Search": .12, "Referral": .30,
                 "Outbound SDR": .08, "Event": .26, "Partner": .28}
    demo = (rng.random(N) < np.array([demo_base[s] for s in source])).astype(int)
    eng = np.clip(rng.normal(40 + 25 * demo, 18), 0, 100).round(0)

    src_eff = {"Webinar": 0.0, "Paid Search": -0.25, "Organic Search": 0.0, "Referral": 0.6,
               "Outbound SDR": -0.4, "Event": 0.1, "Partner": 0.35}
    sen_eff = {"Individual Contributor": -0.3, "Manager": 0.0, "Director": 0.25, "VP / C-level": 0.5}
    band_eff = {"1-50": -0.2, "51-200": 0.1, "201-1,000": 0.35, "1,001-5,000": 0.2, "5,000+": -0.1}
    ind_eff = dict(zip(CAN_INDUSTRIES, rng.normal(0, 0.15, len(CAN_INDUSTRIES))))
    lin = (0.9 * demo + np.array([src_eff[s] for s in source]) + np.array([sen_eff[s] for s in seniority])
           + np.array([band_eff[b] for b in band]) + 0.35 * (eng - 40) / 20
           + np.array([ind_eff[i] for i in industry]))
    eps = rng.normal(0, 1.1, N)
    a = bisect(lambda a_: expit(a_ + lin + eps).mean(), -5, 5, cfg["target_lead_to_opp"])
    converted = rng.random(N) < expit(a + lin + eps)

    leads = pd.DataFrame({
        "lead_id": [f"L{str(i + 1).zfill(6)}" for i in range(N)],
        "created_date": created.values,
        "company_name": [fake.company() for _ in range(N)],
        "industry": industry,
        "company_size_employees": emp,
        "size_band": band,
        "region": region,
        "lead_source": source,
        "contact_seniority": seniority,
        "demo_requested": demo,
        "engagement_score": eng,
        "_converted": converted,
    })
    leads["contact_email"] = [
        f"{fake.first_name().lower()}.{fake.last_name().lower()}@{c.split()[0].lower().strip(',.')}.com"
        for c in leads["company_name"]]
    return leads


# ---------------------------------------------------------------- opportunities
def gen_opps(rng, cfg, leads, cutoff):
    L = leads[leads["_converted"]].copy().reset_index(drop=True)
    n = len(L)
    lag = np.clip(np.exp(rng.normal(np.log(12), 0.7, n)), 1, 75).round().astype(int)
    created = pd.to_datetime(L["created_date"]) + pd.to_timedelta(lag, unit="D")
    keep = created <= cutoff
    L, created, n = L[keep].reset_index(drop=True), created[keep].reset_index(drop=True), int(keep.sum())

    deal = np.array([DEAL_MEDIAN[b] for b in L["size_band"]]) * np.exp(rng.normal(0, 0.45, n))
    deal = (np.round(deal / 50) * 50).astype(int)
    band_idx = np.array([BANDS.index(b) for b in L["size_band"]])
    competitor = rng.random(n) < np.clip(0.35 + 0.05 * band_idx, 0, 0.6)
    comp_name = np.where(competitor, rng.choice(["Competitor A", "Competitor B", "Competitor C", "Competitor D"], n), "")
    dm = np.minimum(1 + rng.poisson(1.1, n), 5)

    reps = [f"R{str(i + 1).zfill(2)}" for i in range(12)]
    rep_region = {r: REGIONS[i // 3] for i, r in enumerate(reps)}
    rep_skill = dict(zip(reps, rng.normal(0, 0.35, 12)))
    rep_optim = dict(zip(reps, rng.normal(0.4, 0.25, 12)))
    rep_id = np.array([rng.choice([r for r in reps if rep_region[r] == reg]) for reg in L["region"]])

    z_size = (np.log(deal) - np.log(deal).mean()) / np.log(deal).std()
    lin = (-0.85 * competitor + 0.30 * (dm - 2.3) - 0.30 * z_size
           + np.array([rep_skill[r] for r in rep_id]) + 0.20 * L["demo_requested"].to_numpy()
           + 0.20 * (L["engagement_score"].to_numpy() - 40) / 20
           + 0.35 * (L["lead_source"].to_numpy() == "Referral"))
    eps = rng.normal(0, 1.0, n)
    a = bisect(lambda a_: expit(a_ + lin + eps).mean(), -5, 5, cfg["target_win_rate"])
    win_logit = a + lin + eps
    will_win = rng.random(n) < expit(win_logit)

    # rep forecast: noisy, optimistic partial view of the same logit (taken at Proposal)
    fc = expit(0.5 * win_logit + np.array([rep_optim[r] for r in rep_id]) + rng.normal(0, 0.9, n))
    fc = (np.round(fc * 100 / 5) * 5).astype(float)
    fc[rng.random(n) < 0.12] = np.nan

    # stage dwell (days)
    size_factor = (deal / 30000.0) ** 0.12
    dwell = np.column_stack([np.exp(rng.normal(np.log(m), 0.55, n)) * size_factor for m in STAGE_MEDIAN_DAYS])
    dwell[:, 2] *= np.where(competitor, 1.15, 1.0)
    dwell = np.maximum(1, np.round(dwell)).astype(int)
    exit_stage = rng.choice(4, n, p=[.22, .30, .33, .15])
    last_idx = np.where(will_win, 3, exit_stage)
    cum = np.cumsum(dwell, axis=1)
    closed = created + pd.to_timedelta(cum[np.arange(n), last_idx], unit="D")

    entry = {}
    for k, s in enumerate(STAGES):
        offs = np.zeros(n, int) if k == 0 else cum[:, k - 1]
        ent = created + pd.to_timedelta(offs, unit="D")
        reached = k <= last_idx
        ent = ent.where(reached & (ent <= cutoff))
        entry[s] = ent
    is_closed = closed <= cutoff
    outcome = np.where(~is_closed, "Open", np.where(will_win, "Won", "Lost"))
    cur_stage = np.empty(n, dtype=object)
    for i in range(n):
        if outcome[i] == "Won":
            cur_stage[i] = "Closed Won"
        elif outcome[i] == "Lost":
            cur_stage[i] = "Closed Lost"
        else:
            ks = [k for k, s in enumerate(STAGES) if pd.notna(entry[s][i])]
            cur_stage[i] = STAGES[ks[-1]]
    loss_reason = np.where(outcome == "Lost", rng.choice(LOSS_REASONS, n, p=[.28, .30, .20, .12, .10]), "")
    disc = np.clip(rng.normal(8 + 6 * competitor, 5), 0, 35).round(1)

    opps = pd.DataFrame({
        "opportunity_id": [f"O{str(i + 1).zfill(6)}" for i in range(n)],
        "lead_id": L["lead_id"].to_numpy(),
        "created_date": created.values,
        "qualified_date": entry["Qualified"].values,
        "discovery_date": entry["Discovery"].values,
        "proposal_date": entry["Proposal"].values,
        "negotiation_date": entry["Negotiation"].values,
        "closed_date": closed.where(is_closed).values,
        "stage": cur_stage,
        "outcome": outcome,
        "deal_size": deal,
        "discount_pct": np.where(outcome == "Won", disc, np.where(outcome == "Lost", disc, np.nan)),
        "competitor_present": competitor.astype(int),
        "competitor_name": comp_name,
        "decision_makers_engaged": dm,
        "sales_rep_id": rep_id,
        "region": L["region"].to_numpy(),
        "rep_forecast_pct": fc,
        "loss_reason": loss_reason,
        "_true_win_prob": expit(win_logit).round(4),
    })
    return opps


# ---------------------------------------------------------------- account simulation
def build_accounts(rng, fake, opps, leads, cfg, start, cutoff):
    W = opps[opps["outcome"] == "Won"].sort_values("closed_date").reset_index(drop=True)
    L = leads.set_index("lead_id")
    n = len(W)
    tier = np.where(W["deal_size"] < 12000, "Starter", np.where(W["deal_size"] < 60000, "Growth", "Enterprise"))
    term = rng.choice([12, 24, 36], n, p=[.65, .20, .15])
    csm = rng.choice(CSMS, n)
    H0 = rng.normal(0.25, 1.0, n) + np.where(tier == "Enterprise", 0.15, 0.0)
    G0 = cfg["corr_H_G"] * (H0 - 0.25) + np.sqrt(1 - cfg["corr_H_G"] ** 2) * rng.normal(0, 1.0, n)
    drift_g = rng.normal(0.04, 0.06, n)
    frailty = rng.normal(0, cfg["churn_frailty_sd"], n)
    accounts = pd.DataFrame({
        "account_id": [f"A{str(i + 1).zfill(5)}" for i in range(n)],
        "opportunity_id": W["opportunity_id"].to_numpy(),
        "company_name": L.loc[W["lead_id"], "company_name"].to_numpy(),
        "industry": L.loc[W["lead_id"], "industry"].to_numpy(),
        "company_size_employees": L.loc[W["lead_id"], "company_size_employees"].to_numpy(),
        "size_band": L.loc[W["lead_id"], "size_band"].to_numpy(),
        "region": W["region"].to_numpy(),
        "account_tier": tier,
        "start_date": W["closed_date"].values,
        "contract_term_months": term,
        "csm_id": csm,
        "initial_acv": W["deal_size"].to_numpy(),
        "discount_pct": W["discount_pct"].to_numpy(),
        "lat_H0": H0, "lat_G0": G0, "lat_drift_g": drift_g, "lat_frailty": frailty,
    })
    return accounts


def simulate(accounts, cfg, c0, e0, seed, start, cutoff, collect=False):
    """Month-by-month simulation. Returns summary counters (and rows if collect)."""
    rng = np.random.default_rng(seed)
    n_months = month_index(cutoff, start) + 1
    month_starts = pd.date_range(start, cutoff, freq="MS")
    month_ends = month_starts + pd.offsets.MonthEnd(0)
    usage, tickets, events, latent_rows, acct_out = [], [], [], [], []
    churn_n = exp_n = acct_months = 0
    c = cfg
    sd_ix = np.sqrt(1 - c["corr_H_G"] ** 2)
    ticket_id = 0
    for a in accounts.itertuples(index=False):
        start_m = month_index(pd.Timestamp(a.start_date), start)
        tier, term = a.account_tier, a.contract_term_months
        price = TIER_PRICE_PER_SEAT_YEAR[tier]
        seats = max(3, int(round(a.initial_acv / price)))
        mrr = a.initial_acv * (1 - (0 if np.isnan(a.discount_pct) else a.discount_pct) / 100) / 12.0
        mrr0 = mrr
        H, G, muH, muG = a.lat_H0, a.lat_G0, a.lat_H0, a.lat_G0
        integ = 0
        last_exp_k = -99
        n_exp = 0
        churned = False
        churn_date = None
        churn_reason = ""
        recent_neg_shock_k = -99
        if collect:
            events.append((a.account_id, pd.Timestamp(a.start_date), "New", mrr, mrr))
        k = 0
        while True:
            m = start_m + k
            if m >= n_months:
                break
            if k > 0:
                zH, zG = rng.normal(), rng.normal()
                eH = c["H_innov_sd"] * zH
                eG = c["G_innov_sd"] * (c["corr_H_G"] * zH + sd_ix * zG)
                sH = 0.0
                u = rng.random()
                if u < c["H_shock_neg_prob"]:
                    sH = rng.normal(c["H_shock_neg_mean"], c["H_shock_neg_sd"]); recent_neg_shock_k = k
                elif u < c["H_shock_neg_prob"] + c["H_shock_pos_prob"]:
                    sH = rng.normal(c["H_shock_pos_mean"], 0.3)
                sG = 0.0
                u = rng.random()
                if u < c["G_shock_pos_prob"]:
                    sG = rng.normal(c["G_shock_pos_mean"], c["G_shock_pos_sd"])
                elif u < c["G_shock_pos_prob"] + c["G_shock_neg_prob"]:
                    sG = rng.normal(c["G_shock_neg_mean"], 0.3)
                muH += 0.5 * sH
                muG += a.lat_drift_g + 0.5 * sG
                H = c["H_persistence"] * H + (1 - c["H_persistence"]) * muH + eH + sH
                G = c["G_persistence"] * G + (1 - c["G_persistence"]) * muG + eG + sG
            ramp = np.exp(-k / 2.0)
            He = H - 0.9 * ramp
            # ---- observed signals (all noisy) ----
            login = expit(0.15 + 0.85 * He + 0.25 * G + rng.normal(0, c["login_noise_sd"]))
            active = int(rng.binomial(seats, login))
            util = active / seats
            peak_util = min(1.0, util * rng.uniform(1.0, 1.25))
            feat_p = expit(-0.5 + 0.40 * G + 0.50 * He + rng.normal(0, c["feature_noise_sd"]))
            feats = int(rng.binomial(12, feat_p))
            ev = int(active * np.exp(1.8 + 0.25 * G + 0.2 * He + rng.normal(0, c["events_noise_sd"])))
            api = int(seats * np.exp(2.0 + 0.45 * G + rng.normal(0, c["api_noise_sd"])))
            if rng.random() < expit(-2.6 + 0.7 * G):
                integ = min(8, integ + 1)
            if rng.random() < 0.04 and H < -0.5:
                integ = max(0, integ - 1)
            acct_months += 1
            if collect:
                usage.append((a.account_id, month_ends[m], seats, active, round(login, 4), feats, ev, api, integ,
                              round(peak_util, 4)))
                latent_rows.append((a.account_id, month_ends[m], H, G))
                lam = np.exp(-0.35 - 0.5 * He - 0.1 * G + 0.25 * np.log(seats / 10.0))
                nt = rng.poisson(min(lam, 12))
                for _ in range(nt):
                    ticket_id += 1
                    d = month_starts[m] + pd.Timedelta(days=int(rng.integers(0, month_ends[m].day)))
                    uu = -0.7 * He + rng.normal(0, 0.9)
                    sev = SEVERITIES[0] if uu < 0.3 else SEVERITIES[1] if uu < 1.2 else SEVERITIES[2] if uu < 2.0 else SEVERITIES[3]
                    tw = np.array([.30, .25, .12, .10, .13 + 0.04 * G, .10 + 0.03 * max(-He, 0)])
                    tw = np.clip(tw, 0.02, None); tw /= tw.sum()
                    tt = rng.choice(TICKET_TYPES, p=tw)
                    res_med = {"Low": 20, "Medium": 14, "High": 10, "Critical": 6}[sev]
                    res_h = float(np.exp(rng.normal(np.log(res_med), 0.7)))
                    csat = np.nan
                    if rng.random() > 0.45:
                        csat = float(np.clip(np.round(4.1 + 0.45 * He - 0.012 * res_h + rng.normal(0, 0.9)), 1, 5))
                    esc_p = 0.02 + (0.10 if sev in ("High", "Critical") else 0.0) + 0.04 * max(-He, 0)
                    tickets.append((f"T{str(ticket_id).zfill(7)}", a.account_id, d, tt, sev, round(res_h, 1), csat,
                                    int(rng.random() < min(esc_p, 0.5))))
            # ---- decide events for NEXT month (info set: month m and earlier) ----
            if m + 1 >= n_months:
                break
            nxt = m + 1
            is_renew = ((nxt - start_m) % term == 0) and nxt > start_m
            base = c0 if is_renew else c0 + c["churn_midterm_offset"]
            clog = (base + c["churn_coef_H"] * H + c["churn_coef_G"] * G + a.lat_frailty
                    + (c["churn_enterprise"] if tier == "Enterprise" else 0.0)
                    + (c["churn_early_tenure"] if k < 6 else 0.0))
            p_ch = 1 - (1 - expit(clog)) * (1 - c["churn_exogenous_monthly"])
            if rng.random() < p_ch:
                churned = True
                churn_n += 1
                if is_renew:
                    cd = pd.Timestamp(a.start_date) + pd.DateOffset(months=nxt - start_m)
                    cd = min(cd, month_ends[nxt])
                else:
                    cd = month_starts[nxt] + pd.Timedelta(days=int(rng.integers(0, month_ends[nxt].day)))
                churn_date = cd
                if k - recent_neg_shock_k <= 6:
                    churn_reason = "Champion left / reorg"
                elif util < 0.35:
                    churn_reason = "Low adoption"
                else:
                    churn_reason = str(rng.choice(["Price", "Chose competitor", "Budget cut", "Business closure / M&A"],
                                                  p=[.30, .30, .25, .15]))
                if collect:
                    events.append((a.account_id, cd, "Churn", -mrr, 0.0))
                break
            elog = (e0 + c["exp_coef_G"] * G + c["exp_coef_H"] * H
                    + (c["exp_seat_limit"] if peak_util >= 0.95 else 0.0)
                    + (c["exp_renewal"] if is_renew else 0.0)
                    + (c["exp_recent_expansion"] if (k - last_exp_k) <= 6 else 0.0)
                    + (0.25 if tier == "Growth" else 0.0))
            if rng.random() < expit(elog):
                exp_n += 1
                u = rng.random()
                if u < 0.60:
                    typ, up = "Expansion - seats", rng.uniform(0.10, 0.40)
                    seats = int(np.ceil(seats * (1 + up)))
                elif u < 0.85:
                    typ, up = "Expansion - tier upgrade", rng.uniform(0.25, 0.70)
                    if tier != "Enterprise":
                        tier = TIER_ORDER[TIER_ORDER.index(tier) + 1]
                    seats = int(np.ceil(seats * 1.1))
                else:
                    typ, up = "Expansion - add-on", rng.uniform(0.08, 0.25)
                old = mrr
                mrr = mrr * (1 + up)
                last_exp_k = k + 1
                n_exp += 1
                if collect:
                    d = month_starts[nxt] + pd.Timedelta(days=int(rng.integers(0, month_ends[nxt].day)))
                    events.append((a.account_id, d, typ, mrr - old, mrr))
            elif rng.random() < expit(-5.0 - 0.8 * H - 0.5 * G):
                dn = rng.uniform(0.10, 0.30)
                old = mrr
                mrr = mrr * (1 - dn)
                seats = max(3, int(np.floor(seats * (1 - dn))))
                if collect:
                    d = month_starts[nxt] + pd.Timedelta(days=int(rng.integers(0, month_ends[nxt].day)))
                    events.append((a.account_id, d, "Contraction", mrr - old, mrr))
            k += 1
        if collect:
            acct_out.append(dict(account_id=a.account_id, plan_tier=tier, seats_licensed=seats, mrr=round(mrr, 2),
                                 initial_mrr=round(mrr0, 2), status="Churned" if churned else "Active",
                                 churn_date=churn_date, churn_reason=churn_reason, expansions=n_exp))
    out = dict(churn_n=churn_n, exp_n=exp_n, acct_months=acct_months)
    if collect:
        out.update(usage=usage, tickets=tickets, events=events, latent=latent_rows, acct=acct_out)
    return out


def calibrate(accounts, cfg, start, cutoff):
    tgt_c = cfg["target_annual_churn"] / 12
    tgt_e = cfg["target_annual_expansion"] / 12
    c0, e0 = -2.4, -4.0
    for _ in range(3):
        lo, hi = -7.0, 1.0
        for _ in range(11):
            mid = (lo + hi) / 2
            r = simulate(accounts, cfg, mid, e0, cfg["seed"], start, cutoff)
            (lo, hi) = (mid, hi) if r["churn_n"] / r["acct_months"] < tgt_c else (lo, mid)
        c0 = (lo + hi) / 2
        lo, hi = -9.0, 0.0
        for _ in range(11):
            mid = (lo + hi) / 2
            r = simulate(accounts, cfg, c0, mid, cfg["seed"], start, cutoff)
            (lo, hi) = (mid, hi) if r["exp_n"] / r["acct_months"] < tgt_e else (lo, mid)
        e0 = (lo + hi) / 2
    r = simulate(accounts, cfg, c0, e0, cfg["seed"], start, cutoff)
    print(f"  calibrated c0={c0:.3f} e0={e0:.3f} | monthly churn {r['churn_n']/r['acct_months']:.4f} "
          f"(~{12*r['churn_n']/r['acct_months']:.1%}/yr) expansion {12*r['exp_n']/r['acct_months']:.1%}/yr")
    return c0, e0


# ---------------------------------------------------------------- messiness
def messify(tables, rng, log):
    leads, opps, accounts, subs, usage, tickets, events = (tables[k] for k in
        ["leads", "opportunities", "accounts", "subscriptions", "usage_events", "support_tickets", "subscription_events"])

    # LEADS ---------------------------------------------------------
    n = len(leads)
    for col, frac in [("company_size_employees", .11), ("industry", .08), ("lead_source", .03), ("contact_seniority", .06)]:
        idx = rng.random(n) < frac
        leads.loc[idx, col] = np.nan
        log[f"leads.missing_{col}"] = int(idx.sum())
    var_map = {k: v for k, v in IND_VARIANTS.items()}
    def messy_industry(x):
        if pd.isna(x): return x
        return rng.choice(var_map[x]) if rng.random() < 0.55 else x
    leads["industry"] = leads["industry"].map(messy_industry)
    n_dup = int(0.12 * n)
    dup = leads.sample(n_dup, random_state=int(rng.integers(1e9))).copy()
    dup["lead_id"] = [f"L{str(n + i + 1).zfill(6)}" for i in range(n_dup)]
    dup["contact_email"] = dup["contact_email"].str.upper()
    dup["company_name"] = dup["company_name"].str.upper()
    dup["created_date"] = pd.to_datetime(dup["created_date"]) + pd.to_timedelta(rng.integers(0, 6, n_dup), unit="D")
    dup["_converted"] = False
    leads = pd.concat([leads, dup], ignore_index=True)
    log["leads.duplicate_rows_added"] = n_dup
    leads["created_date"] = pd.to_datetime(leads["created_date"]).dt.strftime("%Y-%m-%d")
    bad = rng.random(len(leads)) < 0.03
    leads.loc[bad, "created_date"] = pd.to_datetime(leads.loc[bad, "created_date"]).dt.strftime("%d/%m/%Y")
    log["leads.dd_mm_yyyy_dates"] = int(bad.sum())
    neg = rng.random(len(leads)) < 0.004
    leads.loc[neg, "engagement_score"] = -1
    log["leads.engagement_minus1_sentinel"] = int(neg.sum())

    # OPPORTUNITIES -------------------------------------------------
    n = len(opps)
    stage_var = {"Qualified": ["Qualified", "qualified", "Qualifed"], "Discovery": ["Discovery", "Disco", "discovery"],
                 "Proposal": ["Proposal", "Proposal Sent", "proposal"], "Negotiation": ["Negotiation", "Neg.", "negotiation"],
                 "Closed Won": ["Closed Won", "closed-won", "Won"], "Closed Lost": ["Closed Lost", "closed-lost", "Lost"]}
    opps["stage"] = [rng.choice(stage_var[s]) if rng.random() < 0.30 else s for s in opps["stage"]]
    idx = rng.random(n) < 0.06
    opps.loc[idx, "deal_size"] = np.nan; log["opportunities.missing_deal_size"] = int(idx.sum())
    idx = rng.random(n) < 0.003
    opps.loc[idx, "deal_size"] = [0 if r < .5 else -abs(v) for r, v in zip(rng.random(idx.sum()), opps.loc[idx, "deal_size"].fillna(100))]
    log["opportunities.zero_or_negative_deal_size"] = int(idx.sum())
    idx = rng.random(n) < 0.01
    opps.loc[idx, "lead_id"] = [f"L9{str(i).zfill(5)}" for i in range(idx.sum())]
    log["opportunities.orphan_lead_id"] = int(idx.sum())
    for col in ["created_date", "qualified_date", "discovery_date", "proposal_date", "negotiation_date", "closed_date"]:
        opps[col] = pd.to_datetime(opps[col]).dt.strftime("%Y-%m-%d")
    closed_mask = opps["closed_date"].notna()
    idx = closed_mask & (rng.random(n) < 0.012)
    opps.loc[idx, "closed_date"] = "0000-00-00"
    log["opportunities.bad_close_date_zeros"] = int(idx.sum())
    idx = closed_mask & ~idx & (rng.random(n) < 0.008)
    opps.loc[idx, "closed_date"] = (pd.to_datetime(opps.loc[idx, "created_date"]) - pd.Timedelta(days=5)).dt.strftime("%Y-%m-%d")
    log["opportunities.close_before_create"] = int(idx.sum())
    idx = rng.random(n) < 0.08
    opps.loc[idx, "decision_makers_engaged"] = np.nan; log["opportunities.missing_decision_makers"] = int(idx.sum())

    # ACCOUNTS / SUBSCRIPTIONS -------------------------------------
    accounts["start_date"] = pd.to_datetime(accounts["start_date"]).dt.strftime("%Y-%m-%d")
    idx = rng.random(len(accounts)) < 0.05
    accounts.loc[idx, "industry"] = np.nan; log["accounts.missing_industry"] = int(idx.sum())
    orphan = accounts.sample(frac=0.02, random_state=int(rng.integers(1e9))).index
    subs = subs[~subs["account_id"].isin(accounts.loc[orphan, "account_id"])].copy()
    log["accounts.orphan_no_subscription"] = int(len(orphan))
    idx = rng.random(len(subs)) < 0.005
    subs.loc[idx, "mrr"] = [0 if r < .5 else -abs(v) for r, v in zip(rng.random(idx.sum()), subs.loc[idx, "mrr"])]
    log["subscriptions.zero_or_negative_mrr"] = int(idx.sum())
    idx = rng.random(len(subs)) < 0.04
    subs.loc[idx, "renewal_date"] = np.nan; log["subscriptions.missing_renewal_date"] = int(idx.sum())
    subs["plan_tier"] = [t.lower() if rng.random() < 0.05 else t for t in subs["plan_tier"]]
    for c in ["start_date", "renewal_date", "churn_date"]:
        subs[c] = pd.to_datetime(subs[c]).dt.strftime("%Y-%m-%d")

    # USAGE ---------------------------------------------------------
    drop = rng.random(len(usage)) < 0.03
    log["usage_events.missing_months"] = int(drop.sum())
    usage = usage[~drop].copy()
    idx = rng.random(len(usage)) < 0.005
    usage.loc[idx, "active_users"] = (usage.loc[idx, "seats_licensed"] * rng.uniform(1.2, 2.0, idx.sum())).astype(int)
    log["usage_events.active_users_exceeds_seats"] = int(idx.sum())
    dups = usage.sample(frac=0.01, random_state=int(rng.integers(1e9)))
    usage = pd.concat([usage, dups], ignore_index=True)
    log["usage_events.duplicate_rows"] = int(len(dups))
    usage["month_end"] = pd.to_datetime(usage["month_end"]).dt.strftime("%Y-%m-%d")

    # TICKETS -------------------------------------------------------
    sev_var = {"Low": ["Low", "low", "P4"], "Medium": ["Medium", "med", "P3"], "High": ["High", "high", "P2"], "Critical": ["Critical", "CRITICAL", "P1"]}
    tickets["severity"] = [rng.choice(sev_var[s]) if rng.random() < 0.25 else s for s in tickets["severity"]]
    idx = rng.random(len(tickets)) < 0.05
    tickets.loc[idx, "severity"] = np.nan; log["support_tickets.missing_severity"] = int(idx.sum())
    dups = tickets.sample(frac=0.01, random_state=int(rng.integers(1e9)))
    tickets = pd.concat([tickets, dups], ignore_index=True)
    log["support_tickets.duplicate_rows"] = int(len(dups))
    tickets["created_date"] = pd.to_datetime(tickets["created_date"]).dt.strftime("%Y-%m-%d")

    events["event_date"] = pd.to_datetime(events["event_date"]).dt.strftime("%Y-%m-%d")
    return dict(leads=leads.drop(columns=["_converted"]), opportunities=opps.drop(columns=["_true_win_prob"]),
                accounts=accounts.drop(columns=[c for c in accounts.columns if c.startswith("lat_")]),
                subscriptions=subs, usage_events=usage, support_tickets=tickets, subscription_events=events)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--docs", default="docs")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True); os.makedirs(args.docs, exist_ok=True)
    cfg = CONFIG
    start, cutoff = pd.Timestamp(cfg["start"]), pd.Timestamp(cfg["cutoff"])
    rng = np.random.default_rng(cfg["seed"]); fake = Faker(); Faker.seed(cfg["seed"])

    print("[1/6] leads"); leads = gen_leads(rng, fake, cfg, start, cutoff)
    print("[2/6] opportunities"); opps = gen_opps(rng, cfg, leads, cutoff)
    print("[3/6] accounts"); accounts = build_accounts(rng, fake, opps, leads, cfg, start, cutoff)
    print(f"   leads={len(leads):,} opps={len(opps):,} won+closed accounts={len(accounts):,}")
    print("[4/6] calibrating churn/expansion base rates")
    c0, e0 = calibrate(accounts, cfg, start, cutoff)
    print("[5/6] full simulation")
    r = simulate(accounts, cfg, c0, e0, cfg["seed"], start, cutoff, collect=True)

    usage = pd.DataFrame(r["usage"], columns=["account_id", "month_end", "seats_licensed", "active_users", "login_rate",
                                              "features_adopted", "events_count", "api_calls", "integrations_connected",
                                              "peak_seat_utilization"])
    tickets = pd.DataFrame(r["tickets"], columns=["ticket_id", "account_id", "created_date", "ticket_type", "severity",
                                                  "resolution_hours", "csat_score", "is_escalated"])
    events = pd.DataFrame(r["events"], columns=["account_id", "event_date", "event_type", "mrr_change", "mrr_after"])
    events["mrr_change"] = events["mrr_change"].round(2); events["mrr_after"] = events["mrr_after"].round(2)
    latent = pd.DataFrame(r["latent"], columns=["account_id", "month_end", "H_health", "G_growth"])
    acct_state = pd.DataFrame(r["acct"])
    subs = accounts[["account_id", "start_date", "contract_term_months"]].merge(acct_state, on="account_id")
    subs.insert(0, "subscription_id", [f"S{str(i + 1).zfill(5)}" for i in range(len(subs))])
    def next_renewal(row):
        s, t = pd.Timestamp(row.start_date), row.contract_term_months
        ref = pd.Timestamp(row.churn_date) if pd.notna(row.churn_date) else cutoff
        j = 1
        while s + pd.DateOffset(months=t * j) <= ref:
            j += 1
        return s + pd.DateOffset(months=t * j)
    subs["renewal_date"] = [next_renewal(x) for x in subs.itertuples()]
    subs = subs[["subscription_id", "account_id", "plan_tier", "mrr", "initial_mrr", "seats_licensed", "contract_term_months",
                 "start_date", "renewal_date", "status", "churn_date", "churn_reason", "expansions"]]

    print("[6/6] messiness + write")
    tables = dict(leads=leads, opportunities=opps, accounts=accounts.copy(), subscriptions=subs, usage_events=usage,
                  support_tickets=tickets, subscription_events=events)
    # internal ground truth (never published)
    gt = latent.merge(accounts[["account_id", "lat_H0", "lat_G0"]], on="account_id")
    gt.to_csv(os.path.join(args.docs, "_ground_truth_latents_monthly.csv"), index=False)
    log = {}
    out = messify(tables, np.random.default_rng(cfg["seed"] + 1), log)
    for k, df in out.items():
        df.to_csv(os.path.join(args.out, f"{k}.csv"), index=False)
        print(f"   {k:22s} {len(df):>8,} rows")
    json.dump(log, open(os.path.join(args.docs, "_injected_issues_log.json"), "w"), indent=2)
    json.dump(dict(config=cfg, calibrated=dict(churn_intercept=c0, expansion_intercept=e0)),
              open(os.path.join(args.docs, "generator_assumptions.json"), "w"), indent=2, default=str)
    print("done.")


if __name__ == "__main__":
    main()
