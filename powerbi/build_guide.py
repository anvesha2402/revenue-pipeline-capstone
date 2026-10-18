import base64, re, io
import markdown, pandas as pd
from layout_spec import PAGES, HEADER

t = open("GUIDE.template.md").read()
def pos(m):
    page, vid = m.group(1), m.group(2)
    x, y, w, h = [v for v in PAGES[page]["visuals"] if v[0] == vid][0][3]
    return f"Horizontal {x}, Vertical {y}, Width {w}, Height {h}"
t = re.sub(r"@@(P\d):(\w+)@@", pos, t)

ev = pd.read_csv("validation/expected_values.csv", index_col=0)
def money(x): return f"${x/1e6:,.1f}M"
rows = []
for sc, lab, p1 in [("Region = EMEA", "Region = EMEA", True), ("Region = APAC, Industry = SaaS", "Region = APAC and Industry = SaaS", True),
                    ("Plan Tier = Enterprise", "Plan tier = Enterprise (Page 2 only)", False), ("Segment = Protect", "Segment = Protect (Page 2 only)", False)]:
    c = ev[sc]
    rows.append(f"| {lab} | {money(c['Open Pipeline']) if p1 else 'n/a'} | {c['Win Rate 12M']:.1%} {'' if p1 else ''}".replace(" ", " ") + f" | {money(c['Stalled Pipeline']) if p1 else 'n/a'} | {money(c['ARR'])} | {c['Net Revenue Retention 12M']:.1%} | {money(c['Expected ARR Loss 90D'])} |")
# page-1 metrics do not respond to tier/segment: show n/a for win rate too
rows = [r if i < 2 else r.replace(f"{ev[['Plan Tier = Enterprise','Segment = Protect'][i-2]]['Win Rate 12M']:.1%}", "n/a") for i, r in enumerate(rows)]
t = t.replace("@@TESTROWS@@", "\n".join(rows))

coords = ["| Page | ID | Visual type | Content | Horizontal | Vertical | Width | Height |", "|---|---|---|---|---|---|---|---|"]
for pg, P in PAGES.items():
    for hid, nm, (x, y, w, h) in HEADER:
        coords.append(f"| {P['name']} | {hid} | header | {nm} | {x} | {y} | {w} | {h} |")
    for vid, typ, nm, (x, y, w, h) in P["visuals"]:
        coords.append(f"| {P['name']} | {vid} | {typ} | {nm} | {x} | {y} | {w} | {h} |")
t = t.replace("@@COORDS@@", "\n".join(coords) + "\n\n![Layout map page 1](design/layout_map_P1_pipeline.png)\n\n![Layout map page 2](design/layout_map_P2_customers.png)\n")
# make sure lists are preceded by a blank line (needed by most markdown renderers)
out, prev = [], ""
for ln in t.split("\n"):
    is_item = bool(re.match(r"\s*(- |\d+\. )", ln))
    prev_item = bool(re.match(r"\s*(- |\d+\. )", prev)) or prev.startswith("   ")
    if is_item and prev.strip() and not prev_item and not prev.startswith("|"):
        out.append("")
    if (not is_item) and ln.strip() and prev_item and not ln.startswith(" ") and not ln.startswith("|") and prev.strip():
        out.append("")
    out.append(ln); prev = ln
t = "\n".join(out)
assert "@@" not in t
open("POWER_BI_BUILD_GUIDE.md", "w").write(t)
print(len(t.split()), "words")
print("\n".join(rows))
