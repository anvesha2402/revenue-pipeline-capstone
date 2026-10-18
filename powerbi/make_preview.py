"""Target-look previews (matplotlib). They show what the finished Power BI pages should look like, using the real numbers."""
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from layout_spec import *

D = "data"
rd = lambda n, **k: pd.read_csv(f"{D}/{n}.csv", **k)
opp, arr, acc, hl, drv = rd("fact_opportunity", parse_dates=["closed_date"]), rd("fact_arr_monthly", parse_dates=["month_end_date"]), rd("dim_account"), rd("fact_account_health"), rd("fact_driver")
lead, rep, stg, lb = rd("fact_lead"), rd("dim_rep"), rd("dim_stage"), rd("ref_lead_bands")
INK, INK2, MUT, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#c3c2b7",
                     "xtick.color": MUT, "ytick.color": MUT, "axes.labelcolor": INK2})

def usd(x, d=1):
    return f"${x/1e6:,.{d}f}M" if abs(x) >= 1e6 else f"${x/1e3:,.0f}K"

def canvas(page):
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    bg = fig.add_axes([0, 0, 1, 1]); bg.set_xlim(0, W); bg.set_ylim(H, 0); bg.axis("off")
    bg.imshow(plt.imread(f"design/background_{page}_{PAGES[page]['name'].lower()}.png"), extent=[0, W, H, 0], aspect="auto", zorder=0)
    P = PAGES[page]
    bg.text(24, 24, P["title"], color="white", fontsize=17, fontweight="bold", va="center")
    bg.text(24, 44, P["subtitle"], color="#b7d3f6", fontsize=8.5, va="center")
    for i, (nm, on) in enumerate([("Pipeline", page == "P1"), ("Customers", page == "P2")]):
        x = 560 + i * 150
        bg.add_patch(FancyBboxPatch((x, 14), 140, 30, boxstyle="round,pad=0,rounding_size=15", fc="white" if on else "#1c4a85", ec="none"))
        bg.text(x + 70, 29, nm, color=NAVY if on else "white", fontsize=9.5, fontweight="bold", ha="center", va="center")
    bg.text(1154, 29, "As of 30 Jun 2026  |  synthetic data", color="#b7d3f6", fontsize=8, ha="right", va="center")
    bg.add_patch(FancyBboxPatch((1162, 14), 98, 32, boxstyle="round,pad=0,rounding_size=6", fc="none", ec="#b7d3f6", lw=1))
    bg.text(1211, 30, "Reset filters", color="white", fontsize=8, ha="center", va="center")
    return fig, bg

def slicers(bg, page):
    for (vid, typ, nm, (x, y, w, h)) in PAGES[page]["visuals"]:
        if typ.startswith("Slicer"):
            bg.text(x + 2, y + 8, nm, fontsize=7.5, color=INK2, va="center")
            bg.add_patch(FancyBboxPatch((x, y + 17), w, 24, boxstyle="round,pad=0,rounding_size=4", fc="white", ec="#c3c2b7", lw=0.8))
            bg.text(x + 8, y + 29, "All", fontsize=8.5, color=INK, va="center"); bg.text(x + w - 14, y + 29, "v", fontsize=8, color=MUT, va="center")

def note(bg, page, txt):
    for (vid, typ, nm, (x, y, w, h)) in PAGES[page]["visuals"]:
        if vid == "T1":
            bg.text(x + w, y + 30, txt, fontsize=8, color=INK2, ha="right", va="center")

def kpis(bg, page, items):
    ks = [v for v in PAGES[page]["visuals"] if v[0].startswith("K")]
    for (vid, typ, nm, (x, y, w, h)), (val, sub) in zip(ks, items):
        bg.text(x + 16, y + 15, nm, fontsize=8.2, color=INK, fontweight="bold", va="center")
        bg.text(x + 16, y + 32, sub, fontsize=6.8, color=MUT, va="center")
        bg.text(x + 16, y + 58, val, fontsize=19, color=INK, fontweight="bold", va="center")

def panel_title(bg, page, vid, sub=None):
    v = [v for v in PAGES[page]["visuals"] if v[0] == vid][0]; x, y, w, h = v[3]
    bg.text(x + 14, y + 17, v[2], fontsize=9, color=INK, fontweight="bold", va="center")
    if sub: bg.text(x + 14, y + 31, sub, fontsize=7, color=MUT, va="center")
    return x, y, w, h

def ax_in(fig, rect, top=42, l=14, r=12, b=10):
    x, y, w, h = rect
    a = fig.add_axes([(x + l) / W, 1 - (y + h - b) / H, (w - l - r) / W, (h - top - b) / H]); a.set_facecolor("none")
    a.grid(axis="y", color=GRID, lw=0.7); a.set_axisbelow(True); a.tick_params(labelsize=7, length=0); return a

def table(bg, rect, headers, rows, colx, top=44, rh=18.5, aligns=None):
    x, y, w, h = rect
    for hx, hd, al in zip(colx, headers, aligns):
        bg.text(x + hx, y + top, hd, fontsize=7, color=INK, fontweight="bold", va="center", ha=al)
    bg.plot([x + 10, x + w - 10], [y + top + 9, y + top + 9], color="#c3c2b7", lw=0.8)
    for i, r in enumerate(rows):
        yy = y + top + 20 + i * rh
        if i % 2: bg.add_patch(plt.Rectangle((x + 10, yy - rh / 2), w - 20, rh, fc="#f7f7f5", ec="none", zorder=1))
        for hx, c, al in zip(colx, r, aligns):
            col, txt = (c if isinstance(c, tuple) else (INK, c))
            bg.text(x + hx, yy, txt, fontsize=7, color=col, va="center", ha=al, zorder=3)

# =============================================================== PAGE 1
fig, bg = canvas("P1"); slicers(bg, "P1")
note(bg, "P1", "Model check (tested on future data): deal-win AUC 0.65  |  top lead band converts 3.3x the bottom band")
op = opp[opp.outcome == "Open"].merge(stg, on="stage_key")
kpis(bg, "P1", [("$32.2M", "748 open deals"), ("$9.7M", "flat win rate: $11.2M"), ("34.7%", "1,366 won of 3,932 closed"),
                ("78", "won deals, last 12 months"), ("$144K", "new ARR the pipeline should produce"), ("$6.4M", "20% of open pipeline, 97 deals")])
# funnel
x, y, w, h = panel_title(bg, "P1", "V1", "leads created to deals won (lead cohort)")
steps = [("Leads", 27009), ("Became an opportunity", 7812), ("Reached Discovery", 6404), ("Reached Proposal", 4804), ("Reached Negotiation", 3108), ("Closed won", 2399)]
mx = steps[0][1]; fx0, fw = x + 118, w - 180
for i, (n, v) in enumerate(steps):
    yy = y + 46 + i * 29; bw = max(fw * (v / mx), 4)
    bg.add_patch(FancyBboxPatch((fx0, yy), bw, 22, boxstyle="round,pad=0,rounding_size=3", fc=plt.matplotlib.colors.to_rgb(BLUE) + (1 - 0.12 * i,), ec="none"))
    bg.text(x + 14, yy + 11, n, fontsize=7.2, color=INK2, va="center")
    bg.text(fx0 + bw + 6, yy + 11, f"{v:,}", fontsize=7.5, color=INK, va="center", fontweight="bold")
# stages
x, y, w, h = panel_title(bg, "P1", "V2", "stalled = longer in stage than 75% of comparable deals")
g = op.groupby("stage_order").agg(stage=("stage", "first"), tot=("deal_size", "sum")).join(op[op.is_stalled == 1].groupby("stage_order").deal_size.sum().rename("st")).fillna(0)
a = ax_in(fig, (x, y, w, h), l=66); a.grid(axis="y", visible=False); a.grid(axis="x", color=GRID, lw=0.7)
yy = np.arange(len(g))[::-1]
a.barh(yy, (g.tot - g.st) / 1e6, color=BLUE, height=0.55, label="On track"); a.barh(yy, g.st / 1e6, left=(g.tot - g.st) / 1e6 + 0.05, color=ORANGE, height=0.55, label="Stalled")
a.set_yticks(yy); a.set_yticklabels(g.stage, fontsize=7.5, color=INK2); a.legend(frameon=False, fontsize=7, loc="lower right")
# lead bands
x, y, w, h = panel_title(bg, "P1", "V3", "out-of-time test, fixed numbers")
a = ax_in(fig, (x, y, w, h)); a.bar(range(5), lb.conversion_rate * 100, color=[BLUE] * 5, width=0.6)
for i, v in enumerate(lb.conversion_rate * 100): a.text(i, v + 1, f"{v:.0f}%", ha="center", fontsize=7, color=INK)
a.set_xticks(range(5)); a.set_xticklabels(["Q1\nhighest", "Q2", "Q3", "Q4", "Q5\nlowest"], fontsize=6.5); a.set_ylim(0, 60); a.set_yticks([])
# competitor
x, y, w, h = panel_title(bg, "P1", "V4", "all closed deals")
cc = opp[opp.outcome.isin(["Won", "Lost"])].groupby("competitor").outcome.apply(lambda s: (s == "Won").mean()).sort_values()
a = ax_in(fig, (x, y, w, h), l=108); a.grid(axis="y", visible=False); a.grid(axis="x", color=GRID, lw=0.7)
a.barh(cc.index, cc.values * 100, color=[ORANGE, BLUE], height=0.5)
for i, v in enumerate(cc.values * 100): a.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=8, color=INK)
a.set_xlim(0, 55); a.tick_params(axis="y", labelsize=7.5, labelcolor=INK2)
# new ARR
x, y, w, h = panel_title(bg, "P1", "V5", "new customers' annual recurring revenue")
m = arr.groupby("month_end_date").new_arr.sum(); m = m[m.index >= "2024-02-01"]
a = ax_in(fig, (x, y, w, h)); a.bar(range(len(m)), m.values / 1e6, color=BLUE, width=0.7)
a.set_xticks(range(0, len(m), 4)); a.set_xticklabels([d.strftime("%b %y") for d in m.index[::4]], fontsize=7); a.set_ylabel("$M", fontsize=7)
# rep
x, y, w, h = panel_title(bg, "P1", "V6", "all closed deals; sorted high to low")
rr = opp[opp.outcome.isin(["Won", "Lost"])].merge(rep, on="rep_key").groupby("sales_rep").outcome.apply(lambda s: (s == "Won").mean()).sort_values()
a = ax_in(fig, (x, y, w, h), l=24); a.grid(axis="y", visible=False); a.grid(axis="x", color=GRID, lw=0.7)
a.barh(rr.index, rr.values * 100, color=BLUE, height=0.62); a.tick_params(axis="y", labelsize=7, labelcolor=INK2); a.set_xlim(0, 50)
for i, v in enumerate(rr.values * 100): a.text(v + 0.8, i, f"{v:.0f}%", va="center", fontsize=6.5, color=INK)
# stalled deals table
x, y, w, h = panel_title(bg, "P1", "V7", "open deals past the 75th-percentile time in stage, top 10 by value")
t = op[op.is_stalled == 1].sort_values("deal_size", ascending=False).head(10)
t = t.merge(rep, on="rep_key")
rows = [[r.opportunity_id, r.stage, r.sales_rep, f"${r.deal_size:,.0f}", f"{r.days_in_stage:.0f}", f"{r.model_win_prob:.0%}", f"{r.rep_forecast_pct:.0f}%" if r.rep_forecast_pct == r.rep_forecast_pct else "-"] for r in t.itertuples()]
table(bg, (x, y, w, h), ["Deal", "Stage", "Rep", "Value", "Days in stage", "Model win", "Rep forecast"], rows, [14, 84, 160, 235, 300, 370, 462], rh=18.5, aligns=["left", "left", "left", "right", "right", "right", "right"])
fig.savefig("design/preview_page1_pipeline.png", dpi=150); plt.close(fig)

# =============================================================== PAGE 2
fig, bg = canvas("P2"); slicers(bg, "P2")
note(bg, "P2", "Model check (tested on future data): churn AUC 0.83  |  expansion AUC 0.80")
kpis(bg, "P2", [("$69.6M", "2,106 customers"), ("86.6%", "existing customers, 12 months"), ("80.2%", "before upgrades, 12 months"),
                ("80.6%", "customers kept, 12 months"), ("$3.0M", "279 high-risk accounts, $7.5M ARR"), ("$1.1M", "263 high-potential accounts")])
# bridge
x, y, w, h = panel_title(bg, "P2", "V1", "start, movements, end")
vals = [("Starting ARR\n(12M ago)", 31.96385, BLUE), ("New\ncustomers", 43.44977, AQUA), ("Expansion", 2.91033, AQUA), ("Contraction", -1.17492, ORANGE), ("Churn", -7.53043, ORANGE)]
a = ax_in(fig, (x, y, w, h)); cum = 0
for i, (n, v, c) in enumerate(vals):
    if i == 0: a.bar(i, v, color=c, width=0.6); cum = v
    else: a.bar(i, v, bottom=cum, color=c, width=0.6); cum += v
    a.text(i, (cum if v > 0 else cum - v) + 1.2 if i else v + 1.2, f"{v:+.1f}" if i else f"{v:.1f}", ha="center", fontsize=7, color=INK)
a.bar(5, cum, color="#0d366b", width=0.6); a.text(5, cum + 1.2, f"{cum:.1f}", ha="center", fontsize=7, color=INK)
a.set_xticks(range(6)); a.set_xticklabels([v[0] for v in vals] + ["Total"], fontsize=6); a.set_ylim(0, 90); a.set_ylabel("$M", fontsize=7)
# arr trend
x, y, w, h = panel_title(bg, "P2", "V2", "month-end ARR")
m = arr.groupby("month_end_date").arr_end.sum() / 1e6
a = ax_in(fig, (x, y, w, h)); a.fill_between(range(len(m)), m.values, color=BLUE, alpha=0.18); a.plot(range(len(m)), m.values, color=BLUE, lw=2)
a.set_xticks(range(0, len(m), 4)); a.set_xticklabels([d.strftime("%b %y") for d in m.index[::4]], fontsize=7); a.set_ylabel("$M", fontsize=7)
a.text(len(m) - 1, m.values[-1] + 2, f"${m.values[-1]:.1f}M", ha="right", fontsize=7.5, fontweight="bold")
# scatter
x, y, w, h = panel_title(bg, "P2", "V3", "each dot is a scored customer; dot size = ARR")
s = hl[hl.is_scored == 1].merge(acc[["account_id", "segment"]], on="account_id")
a = ax_in(fig, (x, y, w, h), l=18, b=22)
for seg, c in [("Maintain", GRAY), ("Protect", ORANGE), ("Grow", AQUA), ("Save & grow", BLUE)]:
    q = s[s.segment == seg]; a.scatter(q.churn_prob_90d * 100, q.expansion_prob_90d * 100, s=np.clip(q.arr / 4000, 2, 40), c=c, alpha=0.75 if seg != "Maintain" else 0.5, lw=0, label=seg)
a.set_xlabel("Churn probability, next 90 days (%)", fontsize=6.5); a.set_ylabel("Expansion probability (%)", fontsize=6.5); a.legend(frameon=False, fontsize=6.5, loc="upper right", markerscale=1.2)
# table
x, y, w, h = panel_title(bg, "P2", "V4", "81% of ARR is scored (customers under 3 months old are not)")
t = hl[hl.is_scored == 1].merge(acc, on="account_id").sort_values("expected_loss_90d", ascending=False).head(10)
rc = {"High": "#D03B3B", "Medium": "#C98500", "Low": "#0A8A0A"}
rows = [[r.company_name[:26], r.account_tier, f"${r.arr:,.0f}", f"{r.churn_prob_90d:.1%}", f"${r.expected_loss_90d:,.0f}", f"{r.months_to_renewal:.1f}", (rc[r.churn_risk], r.churn_risk)] for r in t.itertuples()]
table(bg, (x, y, w, h), ["Customer", "Plan", "ARR", "Churn prob.", "Expected loss", "Renews in (mo.)", "Churn risk"], rows, [14, 200, 325, 400, 490, 580, 625], rh=18.5, aligns=["left", "left", "right", "right", "right", "right", "left"])
# drivers
top = t.iloc[0]
for vid, model in [("V5", "Churn"), ("V6", "Expansion")]:
    x, y, w, h = panel_title(bg, "P2", vid, f"Drivers for {top.company_name[:22]}")
    d = drv[(drv.account_id == top.account_id) & (drv.model == model)].sort_values("rank")
    a = ax_in(fig, (x, y, w, h), l=90); a.grid(axis="y", visible=False); a.grid(axis="x", color=GRID, lw=0.7)
    a.barh(d.driver[::-1], d.impact[::-1], color=[ORANGE if v > 0 else BLUE for v in d.impact[::-1]], height=0.55)
    a.axvline(0, color=MUT, lw=0.8); a.tick_params(axis="y", labelsize=6.3, labelcolor=INK2)
fig.savefig("design/preview_page2_customers.png", dpi=150); plt.close(fig)
print("ok")
