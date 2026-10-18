"""Builds the report half of the .pbip project (PBIR format): 2 pages, ~35 visuals, theme, page backgrounds.

Geometry comes from layout_spec.PAGES (the same table used for the background images and the manual guide),
so the project, the background art and the guide can never drift apart.
"""
import hashlib, json, os, shutil
from layout_spec import PAGES, NAVY, BLUE, ORANGE, AQUA, GRAY

SCHEMA_BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
# Schema versions. "low" = oldest versions that support everything used (any current Desktop opens them);
# "high" = newest published. Chosen with env PBIP_VERSIONS (default low).
_VERS = {"low": ("2.4.0", "2.0.0", "3.0.0", "1.0.0"), "high": ("2.7.0", "2.1.0", "3.2.0", "1.1.0")}
V_VISUAL, V_PAGE, V_REPORT, V_PAGES = _VERS[os.environ.get("PBIP_VERSIONS", "low")]
MODEL = "Revenue_Pipeline"
INK, SEC, MUTED, BORDER, WHITE, PALEBLUE = "#0b0b0b", "#52514e", "#898781", "#dcdbd3", "#ffffff", "#B7D3F6"
FONT = "'Segoe UI', wf_segoe-ui_normal, helvetica, arial, sans-serif"
FONT_SEMI = "'Segoe UI Semibold', wf_segoe-ui_semibold, helvetica, arial, sans-serif"

# ------------------------------------------------------------------ expression helpers
def lit(v): return {"expr": {"Literal": {"Value": v}}}
def s(x): return lit("'" + x.replace("'", "''") + "'")
def dbl(x): return lit(f"{x}D")
def lng(x): return lit(f"{x}L")
def b(x): return lit("true" if x else "false")
def clr(h): return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{h}'"}}}}}
def fam(f): return s(f)
def name_id(*parts): return hashlib.md5("|".join(parts).encode()).hexdigest()[:20]

def col(t, c): return {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}}
def mea(m, t="_Measures"): return {"Measure": {"Expression": {"SourceRef": {"Entity": t}}, "Property": m}}
def ref(field):
    k = next(iter(field)); return field[k]["Expression"]["SourceRef"]["Entity"] + "." + field[k]["Property"]
def prop(field):
    k = next(iter(field)); return field[k]["Property"]
def proj(field, display=None, active=None):
    p = {"field": field, "queryRef": ref(field), "nativeQueryRef": prop(field)}
    if display: p["displayName"] = display
    if active: p["active"] = True
    return p
def role(*projs): return {"projections": list(projs)}

# ------------------------------------------------------------------ container ("frame") formatting
def title_block(text, size=12, color=INK, sub=None, sub_measure=None, sub_size=9, sub_color=SEC, pad_left=None):
    vc = {"title": [{"properties": {"show": b(True), "text": s(text), "fontColor": clr(color), "fontSize": dbl(size),
                                    "fontFamily": fam(FONT_SEMI), "alignment": s("left"), "titleWrap": b(False)}}]}
    if sub or sub_measure:
        sp = {"show": b(True), "fontColor": clr(sub_color), "fontSize": dbl(sub_size), "fontFamily": fam(FONT), "alignment": s("left"), "titleWrap": b(False)}
        sp["text"] = {"expr": mea(sub_measure)} if sub_measure else s(sub)
        vc["subTitle"] = [{"properties": sp}]
    if pad_left is not None:
        vc["padding"] = [{"properties": {"left": dbl(pad_left), "right": dbl(6), "top": dbl(4), "bottom": dbl(4)}}]
    return vc

def bare(extra=None):
    """Container with no title / background / border (header texts, plain cards)."""
    vc = {"title": [{"properties": {"show": b(False)}}], "background": [{"properties": {"show": b(False)}}],
          "border": [{"properties": {"show": b(False)}}]}
    if extra: vc.update(extra)
    return vc

def alt(vc, text):
    vc["general"] = [{"properties": {"altText": s(text)}}]
    return vc

# ------------------------------------------------------------------ filters (visual level)
def _from(alias, entity): return {"Name": alias, "Entity": entity, "Type": 0}
def _scol(alias, c): return {"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": c}}
def f_in(entity, column, values, seed):
    vals = [[{"Literal": {"Value": v}}] for v in values]
    return {"name": name_id("flt", seed, entity, column), "field": col(entity, column), "type": "Categorical",
            "filter": {"Version": 2, "From": [_from("t", entity)],
                       "Where": [{"Condition": {"In": {"Expressions": [_scol("t", column)], "Values": vals}}}]}}
def f_topn(entity, column, n, m_name, seed):
    """Top-N filter in the form Power BI itself writes: a sub-query in From + an In against it."""
    inner = {"Version": 2,
             "From": [_from("d", entity), _from("m", "_Measures")],
             "Select": [dict(_scol("d", column), Name="field")],
             "OrderBy": [{"Direction": 2, "Expression": {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": m_name}}}],
             "Top": n}
    return {"name": name_id("flt", seed, entity, column, "topn"), "field": col(entity, column), "type": "TopN",
            "filter": {"Version": 2,
                       "From": [{"Name": "subquery", "Expression": {"Subquery": {"Query": inner}}, "Type": 2}, _from("t", entity)],
                       "Where": [{"Condition": {"In": {"Expressions": [_scol("t", column)], "Table": {"SourceRef": {"Source": "subquery"}}}}}]}}

def sort_def(field, direction):
    return {"sort": [{"field": field, "direction": direction}], "isDefaultSort": False}

# ------------------------------------------------------------------ visual wrapper
class Page:
    def __init__(self, key, name, display):
        self.key, self.name, self.display = key, name, display
        self.visuals = []   # (folder, json)
        self.z = 1000
        self.interactions = []
    def add(self, vid, vtype, geom, query=None, objects=None, container=None, filters=None, sort=None, extra=None, tab=None):
        x, y, w, h = geom
        name = f"{self.key}_{vid}"
        visual = {"visualType": vtype}
        if query is not None or sort is not None:
            q = {"queryState": query or {}}
            if sort: q["sortDefinition"] = sort
            visual["query"] = q
        if objects: visual["objects"] = objects
        if container: visual["visualContainerObjects"] = container
        if extra: visual.update(extra)
        visual["drillFilterOtherVisuals"] = True
        j = {"$schema": f"{SCHEMA_BASE}/visualContainer/{V_VISUAL}/schema.json", "name": name,
             "position": {"x": x, "y": y, "z": self.z, "height": h, "width": w, "tabOrder": tab if tab is not None else self.z},
             "visual": visual}
        if filters: j["filterConfig"] = {"filters": filters}
        self.visuals.append((name, j)); self.z += 100
        return name

def geo(page_id, vid):
    return next(v for v in PAGES[page_id]["visuals"] if v[0] == vid)[3]

# ------------------------------------------------------------------ visual recipes
def kpi(page, page_id, vid, measure, title, sub_measure, units, decimals, alt_text):
    g = geo(page_id, vid)
    labels = {"color": clr(INK), "fontSize": dbl(22), "fontFamily": fam(FONT_SEMI), "labelDisplayUnits": dbl(units), "labelPrecision": lng(decimals)}
    objects = {"labels": [{"properties": labels}], "categoryLabels": [{"properties": {"show": b(False)}}]}
    vc = alt(title_block(title, 10, INK, sub_measure=sub_measure, sub_size=8, sub_color=MUTED, pad_left=12), alt_text)
    return page.add(vid, "card", g, {"Values": role(proj(mea(measure)))}, objects, vc)

def header(page, page_id, title, subtitle, on_page):
    def textbox(vid, text, size, color, semibold, geom):
        run = {"value": text, "textStyle": {"fontFamily": FONT_SEMI if semibold else FONT, "fontSize": f"{size}pt", "color": color}}
        return page.add(vid, "textbox", geom, None, {"general": [{"properties": {"paragraphs": [{"textRuns": [run]}]}}]}, bare())
    textbox("title", title, 20, WHITE, True, (24, 4, 520, 30))
    textbox("subtitle", subtitle, 10, PALEBLUE, False, (24, 34, 520, 20))
    # page navigator (auto-lists the report's pages, highlights the current one)
    nav_obj = {
        "fill": [{"properties": {"show": b(True), "fillColor": clr("#1C4A85")}, "selector": {"id": "default"}},
                 {"properties": {"fillColor": clr(WHITE)}, "selector": {"id": "selection:selected"}}],
        "text": [{"properties": {"fontColor": clr(WHITE), "fontSize": dbl(11), "fontFamily": fam(FONT), "bold": b(False)}, "selector": {"id": "default"}},
                 {"properties": {"fontColor": clr(NAVY), "bold": b(True)}, "selector": {"id": "selection:selected"}}],
        "outline": [{"properties": {"show": b(False)}}],
        "shape": [{"properties": {"tileShape": s("rectangleRounded"), "roundEdge": lng(16)}}],
        "layout": [{"properties": {"cellPadding": lng(6)}}]}
    page.add("page_navigator", "pageNavigator", (560, 14, 290, 32), None, nav_obj, alt(bare(), "Page navigation: Pipeline and Customers"))
    # as-of label
    page.add("asof_label", "card", (858, 14, 296, 32), {"Values": role(proj(mea("As Of Label")))},
             {"labels": [{"properties": {"color": clr(PALEBLUE), "fontSize": dbl(10), "fontFamily": fam(FONT)}}],
              "categoryLabels": [{"properties": {"show": b(False)}}]}, bare())
    # reset button
    btn_obj = {"icon": [{"properties": {"shapeType": s("blank")}, "selector": {"id": "default"}}, {"properties": {"show": b(False)}}],
               "outline": [{"properties": {"show": b(True), "lineColor": clr(PALEBLUE), "weight": dbl(1)}}],
               "fill": [{"properties": {"show": b(False)}}],
               "shape": [{"properties": {"tileShape": s("rectangleRounded"), "roundEdge": lng(16)}}],
               "text": [{"properties": {"show": b(True), "text": s("Reset filters"), "fontColor": clr(WHITE), "fontSize": dbl(10),
                                        "fontFamily": fam(FONT), "horizontalAlignment": s("center")}, "selector": {"id": "default"}}]}
    vc = bare({"visualLink": [{"properties": {"show": b(True), "type": s("ClearAllSlicers")}}]})
    page.add("reset_button", "actionButton", (1162, 14, 98, 32), None, btn_obj, alt(vc, "Reset all filters"))

def slicer(page, page_id, vid, table, column, header_text, sync_name):
    g = geo(page_id, vid)
    obj = {"data": [{"properties": {"mode": s("Dropdown")}}],
           "selection": [{"properties": {"singleSelect": b(False), "selectAllCheckboxEnabled": b(True)}}],
           "header": [{"properties": {"show": b(True), "text": s(header_text), "textSize": dbl(9), "fontColor": clr(SEC), "fontFamily": fam(FONT)}}],
           "items": [{"properties": {"textSize": dbl(10), "fontColor": clr(INK), "fontFamily": fam(FONT)}}]}
    vc = {"title": [{"properties": {"show": b(False)}}],
          "background": [{"properties": {"show": b(True), "color": clr(WHITE), "transparency": dbl(0)}}],
          "border": [{"properties": {"show": b(True), "color": clr(BORDER), "radius": dbl(6)}}]}
    alt(vc, f"{header_text} filter")
    extra = {"syncGroup": {"groupName": sync_name, "fieldChanges": True, "filterChanges": True}} if sync_name else None
    return page.add(vid, "slicer", g, {"Values": role(proj(col(table, column), active=True))}, obj, vc, extra=extra)

def note_card(page, page_id, vid, measure):
    g = geo(page_id, vid)
    return page.add(vid, "card", g, {"Values": role(proj(mea(measure)))},
                    {"labels": [{"properties": {"color": clr(SEC), "fontSize": dbl(10), "fontFamily": fam(FONT)}}],
                     "categoryLabels": [{"properties": {"show": b(False)}}]},
                    alt(bare(), "How far to trust the model scores"))

# chart object builders
def axis_cat(size=9, extra=None):
    p = {"fontSize": dbl(size), "fontFamily": fam(FONT), "labelColor": clr(SEC), "showAxisTitle": b(False)}
    if extra: p.update(extra)
    return [{"properties": p}]
def axis_val(show=False, units=None, start=None, end=None, grid=False):
    p = {"show": b(show), "showAxisTitle": b(False), "fontSize": dbl(9), "fontFamily": fam(FONT), "labelColor": clr(SEC), "gridlineShow": b(grid)}
    if grid: p["gridlineColor"] = clr("#e8e7e1")
    if units: p["labelDisplayUnits"] = dbl(units)
    if start is not None: p["start"] = dbl(start)
    if end is not None: p["end"] = dbl(end)
    return [{"properties": p}]
def labels(show=True, units=None, precision=None, size=9, color=INK):
    p = {"show": b(show), "fontSize": dbl(size), "fontFamily": fam(FONT), "color": clr(color)}
    if units is not None: p["labelDisplayUnits"] = dbl(units)
    if precision is not None: p["labelPrecision"] = lng(precision)
    return [{"properties": p}]
def legend(show, pos="Top"):
    p = {"show": b(show)}
    if show: p.update({"position": s(pos), "fontSize": dbl(9), "labelColor": clr(SEC), "showTitle": b(False)})
    return [{"properties": p}]
def fill_default(hexcolor): return {"properties": {"fill": clr(hexcolor)}}
def fill_for(measure_ref, hexcolor): return {"properties": {"fill": clr(hexcolor)}, "selector": {"metadata": measure_ref}}
def fill_value(table, column, value, hexcolor):
    sel = {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": col(table, column), "Right": {"Literal": {"Value": "'" + value + "'"}}}}}]}
    return {"properties": {"fill": clr(hexcolor)}, "selector": sel}

def chart_container(title, subtitle, alt_text, sub_measure=None):
    return alt(title_block(title, 12, INK, sub=subtitle, sub_measure=sub_measure, sub_size=9, pad_left=12), alt_text)

# ------------------------------------------------------------------ table helpers
def col_width(metadata_ref, w): return {"properties": {"value": dbl(w)}, "selector": {"metadata": metadata_ref}}
TABLE_BASE = {
    "grid": [{"properties": {"rowPadding": dbl(3), "gridHorizontal": b(True), "gridHorizontalColor": clr("#e8e7e1"), "gridVertical": b(False),
                              "outlineStyle": dbl(0), "textSize": dbl(9)}}],
    "columnHeaders": [{"properties": {"bold": b(True), "fontSize": dbl(9), "fontColor": clr(SEC), "fontFamily": fam(FONT_SEMI), "backColor": clr(WHITE),
                                       "outlineStyle": dbl(1), "outlineColor": clr(BORDER)}}],
    "values": [{"properties": {"fontSize": dbl(9), "fontFamily": fam(FONT), "fontColor": clr(INK), "backColor": clr(WHITE),
                                "backColorPrimary": clr(WHITE), "backColorSecondary": clr("#fafaf8")}}],
    "total": [{"properties": {"totals": b(False)}}],
}

# ------------------------------------------------------------------ the two pages
def page_pipeline():
    P, pid = Page("p1", "pipeline", "Pipeline"), "P1"
    header(P, pid, "Revenue Pipeline", "Sales pipeline, deal health and conversion", True)
    slicer(P, pid, "S1", "dim_region", "Region", "Region", "Region")
    slicer(P, pid, "S2", "dim_industry", "Industry", "Industry", "Industry")
    note_card(P, pid, "T1", "Reliability Pipeline")
    k = {}
    for vid, m, t, sm, u, dec, al in [
        ("K1", "Open Pipeline", "Open pipeline", "Label Open Pipeline", 1000000, 1, "Open pipeline value"),
        ("K2", "Weighted Pipeline Model", "Weighted pipeline", "Label Weighted Pipeline", 1000000, 1, "Open pipeline weighted by the deal-win model"),
        ("K3", "Win Rate 12M", "Win rate (12 months)", "Label Win Rate", 1, 1, "Win rate over the last 12 months"),
        ("K4", "Avg Sales Cycle Days", "Sales cycle (days)", "Label Cycle", 1, 0, "Average sales cycle in days"),
        ("K5", "Pipeline Velocity per Day", "Velocity ($ per day)", "Label Velocity", 1000, 0, "Pipeline velocity in dollars per day"),
        ("K6", "Stalled Pipeline", "Stalled pipeline", "Label Stalled", 1000000, 1, "Value of stalled open deals")]:
        k[vid] = kpi(P, pid, vid, m, t, sm, u, dec, al)

    # V1 funnel
    P.add("V1", "funnel", geo(pid, "V1"),
          {"Category": role(proj(col("ref_funnel", "Step"), active=True)), "Y": role(proj(mea("Funnel Value")))},
          {"labels": [{"properties": {"show": b(True), "fontSize": dbl(9), "fontFamily": fam(FONT), "funnelLabelStyle": s("Data, percent of first")}}],
           "categoryAxis": [{"properties": {"show": b(True), "fontSize": dbl(9), "fontFamily": fam(FONT), "color": clr(SEC)}}]},
          chart_container("Lead-to-win funnel", "leads created to deals won", "Funnel from leads created to deals won"))
    # V2 open pipeline by stage (stacked bar, on-track vs stalled)
    P.add("V2", "barChart", geo(pid, "V2"),
          {"Category": role(proj(col("dim_stage", "Stage"), active=True)),
           "Y": role(proj(mea("On Track Pipeline")), proj(mea("Stalled Pipeline")))},
          {"dataPoint": [fill_for("_Measures.On Track Pipeline", BLUE), fill_for("_Measures.Stalled Pipeline", ORANGE)],
           "labels": labels(True, 1000000, 1, 8), "legend": legend(True, "Top"),
           "categoryAxis": axis_cat(9), "valueAxis": axis_val(False)},
          chart_container("Open pipeline by stage", "stalled = longer in stage than 75% of comparable deals", "Open pipeline by stage, split into on-track and stalled"),
          filters=[f_in("dim_stage", "Stage Group", ["'Open'"], "p1v2")],
          sort=sort_def(col("dim_stage", "Stage"), "Ascending"))
    # V3 lead score vs conversion
    P.add("V3", "clusteredColumnChart", geo(pid, "V3"),
          {"Category": role(proj(col("ref_lead_bands", "Score Band"), active=True)), "Y": role(proj(mea("Conversion by Score Band")))},
          {"dataPoint": [fill_default(BLUE)], "labels": labels(True, 1, 0, 9), "legend": legend(False),
           "categoryAxis": axis_cat(8), "valueAxis": axis_val(False, start=0)},
          chart_container("Lead score vs conversion", "out-of-time test, fixed numbers", "Conversion rate by lead score band"))
    # V4 win rate by competitor presence
    comp = ("fact_opportunity", "Competitor")
    P.add("V4", "clusteredBarChart", geo(pid, "V4"),
          {"Category": role(proj(col(*comp), active=True)), "Y": role(proj(mea("Win Rate All Closed")))},
          {"dataPoint": [fill_value(*comp, "No competitor", BLUE), fill_value(*comp, "Competitor present", ORANGE)],
           "labels": labels(True, 1, 0, 10), "legend": legend(False), "categoryAxis": axis_cat(9), "valueAxis": axis_val(False, start=0, end=0.6)},
          chart_container("Win rate: competitor in the deal", "all closed deals", "Win rate with and without a competitor in the deal"))
    # V5 new ARR by month
    P.add("V5", "clusteredColumnChart", geo(pid, "V5"),
          {"Category": role(proj(col("dim_date", "Month Label"), active=True)), "Y": role(proj(mea("New ARR Booked")))},
          {"dataPoint": [fill_default(BLUE)], "labels": labels(False), "legend": legend(False),
           "categoryAxis": axis_cat(8, {"axisType": s("Categorical")}), "valueAxis": axis_val(True, 1000000, grid=True)},
          chart_container("New ARR booked by month", "new customers' annual recurring revenue", "New ARR booked each month"))
    # V6 win rate by rep
    P.add("V6", "clusteredBarChart", geo(pid, "V6"),
          {"Category": role(proj(col("dim_rep", "Sales Rep"), active=True)), "Y": role(proj(mea("Win Rate All Closed")))},
          {"dataPoint": [fill_default(BLUE)], "labels": labels(True, 1, 0, 9), "legend": legend(False),
           "categoryAxis": axis_cat(9), "valueAxis": axis_val(False, start=0, end=0.5)},
          chart_container("Win rate by sales rep", "all closed deals", "Win rate for each sales rep"),
          sort=sort_def(mea("Win Rate All Closed"), "Descending"))
    # V7 stalled deals table
    cols = [(col("fact_opportunity", "Opportunity ID"), "Deal"), (col("dim_stage", "Stage"), "Stage"), (col("dim_rep", "Sales Rep"), "Rep"),
            (mea("Deal Value"), "Value"), (mea("Deal Days in Stage"), "Days in stage"), (mea("Deal Model Probability"), "Model win %"),
            (mea("Deal Rep Forecast"), "Rep forecast %")]
    tobj = json.loads(json.dumps(TABLE_BASE))
    tobj["columnWidth"] = [col_width(ref(f), w) for (f, _), w in zip(cols, [66, 78, 40, 76, 76, 70, 64])]
    P.add("V7", "tableEx", geo(pid, "V7"), {"Values": role(*[proj(f, display=n) for f, n in cols])}, tobj,
          chart_container("Stalled deals to review", "open deals past the 75th-percentile time in stage, top 10 by value", "Table of the ten largest stalled open deals"),
          filters=[f_in("fact_opportunity", "Outcome", ["'Open'"], "p1v7a"), f_in("fact_opportunity", "Is Stalled", ["1L"], "p1v7b"),
                   f_topn("fact_opportunity", "Opportunity ID", 10, "Stalled Pipeline", "p1v7c")],
          sort=sort_def(mea("Deal Value"), "Descending"))
    # interactions: choosing a rep must not move the KPI cards
    P.interactions = [{"source": P.key + "_V6", "target": k[v], "type": "NoFilter"} for v in k]
    return P

def page_customers():
    P, pid = Page("p2", "customers", "Customers"), "P2"
    header(P, pid, "Customer Health and Retention", "Revenue, retention and the accounts that need attention", False)
    slicer(P, pid, "S1", "dim_region", "Region", "Region", "Region")
    slicer(P, pid, "S2", "dim_industry", "Industry", "Industry", "Industry")
    slicer(P, pid, "S3", "dim_account", "Plan Tier", "Plan tier", None)
    slicer(P, pid, "S4", "dim_account", "Segment", "Segment", None)
    note_card(P, pid, "T1", "Reliability Customers")
    k = {}
    for vid, m, t, sm, u, dec, al in [
        ("K1", "ARR", "Active ARR", "Label ARR", 1000000, 1, "Active annual recurring revenue"),
        ("K2", "Net Revenue Retention 12M", "Net revenue retention", "Label NRR", 1, 1, "Net revenue retention over 12 months"),
        ("K3", "Gross Revenue Retention 12M", "Gross revenue retention", "Label GRR", 1, 1, "Gross revenue retention over 12 months"),
        ("K4", "Logo Retention 12M", "Customer (logo) retention", "Label Logo", 1, 1, "Share of customers kept over 12 months"),
        ("K5", "Expected ARR Loss 90D", "Expected ARR loss (90 days)", "Label Expected Loss", 1000000, 1, "Revenue the churn model expects to lose in 90 days"),
        ("K6", "Expected Expansion 90D", "Expected expansion (90 days)", "Label Expected Expansion", 1000000, 1, "Extra revenue the expansion model expects in 90 days")]:
        k[vid] = kpi(P, pid, vid, m, t, sm, u, dec, al)

    # V1 ARR bridge
    P.add("V1", "waterfallChart", geo(pid, "V1"),
          {"Category": role(proj(col("ref_bridge", "Step"), active=True)), "Y": role(proj(mea("Bridge Value")))},
          {"sentimentColors": [{"properties": {"increaseFill": clr(AQUA), "decreaseFill": clr(ORANGE), "totalFill": clr(NAVY)}}],
           "labels": labels(True, 1000000, 1, 9), "legend": legend(False), "categoryAxis": axis_cat(8), "valueAxis": axis_val(False)},
          chart_container("ARR bridge, last 12 months", "start, movements, end", "Waterfall of ARR from 12 months ago to today"))
    # V2 ARR over time
    P.add("V2", "areaChart", geo(pid, "V2"),
          {"Category": role(proj(col("dim_date", "Month Label"), active=True)), "Y": role(proj(mea("ARR")))},
          {"dataPoint": [fill_default(BLUE)], "lineStyles": [{"properties": {"strokeWidth": dbl(2), "areaShow": b(True)}}],
           "legend": legend(False), "categoryAxis": axis_cat(8), "valueAxis": axis_val(True, 1000000, grid=True)},
          chart_container("ARR over time", "month-end ARR", "Month-end ARR over time"))
    # V3 scatter churn vs expansion
    SEG = [("Maintain", GRAY), ("Protect", ORANGE), ("Grow", AQUA), ("Save & grow", BLUE)]
    sc_cat = {"fontSize": dbl(9), "fontFamily": fam(FONT), "labelColor": clr(SEC), "showAxisTitle": b(True), "titleText": s("Churn probability, next 90 days"),
              "titleFontSize": dbl(9), "titleColor": clr(SEC), "start": dbl(0), "gridlineShow": b(True), "gridlineColor": clr("#e8e7e1")}
    sc_val = {"show": b(True), "fontSize": dbl(9), "fontFamily": fam(FONT), "labelColor": clr(SEC), "showAxisTitle": b(True), "titleText": s("Expansion probability"),
              "titleFontSize": dbl(9), "titleColor": clr(SEC), "start": dbl(0), "gridlineShow": b(True), "gridlineColor": clr("#e8e7e1")}
    P.add("V3", "scatterChart", geo(pid, "V3"),
          {"Category": role(proj(col("dim_account", "Account ID"), active=True)), "X": role(proj(mea("Avg Churn Probability"))),
           "Y": role(proj(mea("Avg Expansion Probability"))), "Size": role(proj(mea("Account ARR Now"))),
           "Series": role(proj(col("dim_account", "Segment"))),
           "Tooltips": role(proj(col("dim_account", "Customer")), proj(mea("Account ARR Now")))},
          {"dataPoint": [fill_value("dim_account", "Segment", n, c) for n, c in SEG], "markers": [{"properties": {"transparency": dbl(30)}}],
           "legend": legend(True, "Top"), "categoryAxis": [{"properties": sc_cat}], "valueAxis": [{"properties": sc_val}]},
          chart_container("Churn risk vs expansion potential", "each dot is a scored customer; dot size = ARR", "Scatter of churn probability against expansion probability"))
    # V4 customers to act on first
    cols = [(col("dim_account", "Customer"), "Customer"), (col("dim_account", "Plan Tier"), "Plan"), (mea("Account ARR Now"), "ARR"),
            (mea("Avg Churn Probability"), "Churn prob."), (mea("Expected ARR Loss 90D"), "Expected loss"),
            (mea("Avg Months to Renewal"), "Renews in (months)"), (col("dim_account", "Churn Risk"), "Churn risk")]
    tobj = json.loads(json.dumps(TABLE_BASE))
    tobj["columnWidth"] = [col_width(ref(f), w) for (f, _), w in zip(cols, [210, 70, 80, 80, 100, 90, 60])]
    wild = [{"dataViewWildcard": {"matchingOption": 1}}]
    grad = {"FillRule": {"Input": mea("Avg Churn Probability"), "FillRule": {"linearGradient2": {
        "min": {"color": {"Literal": {"Value": "'#FFFFFF'"}}}, "max": {"color": {"Literal": {"Value": "'#F4B49B'"}}},
        "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}}}}}}
    tobj["values"] += [
        {"properties": {"backColor": {"solid": {"color": {"expr": grad}}}}, "selector": {"data": wild, "metadata": "_Measures.Avg Churn Probability"}},
        {"properties": {"fontColor": {"solid": {"color": {"expr": mea("Churn Risk Color")}}}}, "selector": {"data": wild, "metadata": "dim_account.Churn Risk"}}]
    tobj["columnFormatting"] = [{"properties": {"dataBars": {"positiveColor": clr(ORANGE), "negativeColor": clr(ORANGE), "axisColor": clr(BORDER),
                                                              "reverseDirection": b(False), "hideText": b(False)}},
                                 "selector": {"metadata": "_Measures.Expected ARR Loss 90D"}}]
    P.add("V4", "tableEx", geo(pid, "V4"), {"Values": role(*[proj(f, display=n) for f, n in cols])}, tobj,
          chart_container("Customers to act on first", None, "Ten customers with the largest expected revenue loss", sub_measure="Label Coverage"),
          filters=[f_topn("dim_account", "Customer", 10, "Expected ARR Loss 90D", "p2v4")],
          sort=sort_def(mea("Expected ARR Loss 90D"), "Descending"))
    # V5 / V6 driver charts
    for vid, model, title, alt_t in [("V5", "Churn", "Why this churn score", "Factors behind the selected customer's churn score"),
                                     ("V6", "Expansion", "Why this expansion score", "Factors behind the selected customer's expansion score")]:
        P.add(vid, "barChart", geo(pid, vid),
              {"Category": role(proj(col("fact_driver", "Driver"), active=True)), "Y": role(proj(mea("Driver Impact"))),
               "Series": role(proj(col("fact_driver", "Direction")))},
              {"dataPoint": [fill_value("fact_driver", "Direction", "Raises the score", ORANGE), fill_value("fact_driver", "Direction", "Lowers the score", BLUE)],
               "labels": labels(False), "legend": legend(False), "categoryAxis": axis_cat(8), "valueAxis": axis_val(False)},
              chart_container(title, None, alt_t, sub_measure="Driver Hint"),
              filters=[f_in("fact_driver", "Model", [f"'{model}'"], "p2" + vid)],
              sort=sort_def(mea("Driver Impact"), "Descending"))
    P.interactions = ([{"source": P.key + "_V4", "target": k[v], "type": "NoFilter"} for v in k] +
                      [{"source": P.key + "_V4", "target": P.key + "_" + v, "type": "NoFilter"} for v in ("V1", "V2", "V3")])
    return P

# ------------------------------------------------------------------ write
def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f: json.dump(obj, f, indent=2, ensure_ascii=False); f.write("\n")

def build(root, design_dir, base_theme_path):
    rep = os.path.join(root, f"{MODEL}.Report")
    write_json(os.path.join(rep, "definition.pbir"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{MODEL}.SemanticModel"}}})
    write_json(os.path.join(rep, ".platform"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": MODEL}, "config": {"version": "2.0", "logicalId": "7c1e5b94-3a0f-5f6e-8d2b-0a4c9e61d3f7"}})
    d = os.path.join(rep, "definition")
    write_json(os.path.join(d, "version.json"), {"$schema": f"{SCHEMA_BASE}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})

    pages = [page_pipeline(), page_customers()]
    bg = {"P1": "background_P1_pipeline.png", "P2": "background_P2_customers.png"}
    reg_dir = os.path.join(rep, "StaticResources", "RegisteredResources")
    os.makedirs(reg_dir, exist_ok=True)
    images, items = {}, []
    for pid, fn in bg.items():
        reg_name = fn.replace(".png", "") + "8160249301.png"
        shutil.copy(os.path.join(design_dir, fn), os.path.join(reg_dir, reg_name))
        images[pid] = reg_name; items.append({"name": reg_name, "path": reg_name, "type": "Image"})
    theme_file = "Revenue_Pipeline_Theme.json"
    shutil.copy(os.path.join(design_dir, "theme_revenue_pipeline.json"), os.path.join(reg_dir, theme_file))
    items.insert(0, {"name": theme_file, "path": theme_file, "type": "CustomTheme"})
    base_dir = os.path.join(rep, "StaticResources", "SharedResources", "BaseThemes")
    os.makedirs(base_dir, exist_ok=True)
    shutil.copy(base_theme_path, os.path.join(base_dir, "CY24SU10.json"))

    write_json(os.path.join(d, "report.json"), {
        "$schema": f"{SCHEMA_BASE}/report/{V_REPORT}/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": {"visual": "2.1.0", "report": "3.0.0", "page": "2.0.0"}, "type": "SharedResources"},
            "customTheme": {"name": theme_file, "reportVersionAtImport": {"visual": "2.1.0", "report": "3.0.0", "page": "2.0.0"}, "type": "RegisteredResources"}},
        "objects": {"section": [{"properties": {"verticalAlignment": s("Top")}}],
                    "outspacePane": [{"properties": {"visible": b(False), "expanded": b(False)}}]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources", "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources", "items": items}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}})

    write_json(os.path.join(d, "pages", "pages.json"), {"$schema": f"{SCHEMA_BASE}/pagesMetadata/{V_PAGES}/schema.json",
                                                          "pageOrder": [p.name for p in pages], "activePageName": pages[0].name})
    for p, pid in zip(pages, ["P1", "P2"]):
        page_json = {
            "$schema": f"{SCHEMA_BASE}/page/{V_PAGE}/schema.json", "name": p.name, "displayName": p.display,
            "displayOption": "FitToPage", "height": 720, "width": 1280,
            "objects": {
                "background": [{"properties": {"transparency": dbl(0), "image": {"image": {
                    "name": s(images[pid]),
                    "url": {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources", "PackageType": 1, "ItemName": images[pid]}}},
                    "scaling": s("Fit")}}}}],
                "outspace": [{"properties": {"color": clr("#F1F1EE"), "transparency": dbl(0)}}]},
            "visualInteractions": p.interactions}
        write_json(os.path.join(d, "pages", p.name, "page.json"), page_json)
        for vname, vjson in p.visuals:
            write_json(os.path.join(d, "pages", p.name, "visuals", vname, "visual.json"), vjson)
    return rep, pages

if __name__ == "__main__":
    import sys
    build(sys.argv[1], "design", sys.argv[2])
