"""Builds the semantic-model half of the .pbip project (TMDL format).

Reads the single sources of truth already used by the manual guide:
  pbi_schema.SCHEMA      tables, columns, types, friendly names
  powerquery/*.m         Power Query (M) for every table
  measures_def.M         the 83 DAX measures
and writes   <root>/Revenue_Pipeline.SemanticModel/...
"""
import json, os, re, uuid
from pbi_schema import SCHEMA
from measures_def import M as MEASURES

NS = uuid.UUID("6f1d0c52-0f0e-4b53-9a53-3c9d5d1a7b11")      # fixed namespace -> repeatable GUIDs
def guid(*parts): return str(uuid.uuid5(NS, "|".join(parts)))

DEFAULT_FOLDER = "C:\\Revenue_Pipeline_Power_BI\\data\\"

TABLE_ORDER = ["dim_date", "dim_region", "dim_industry", "dim_rep", "dim_stage", "dim_account",
               "fact_arr_monthly", "fact_account_health", "fact_driver", "fact_opportunity", "fact_lead",
               "ref_model_scorecard", "ref_lead_bands", "ref_funnel", "ref_bridge", "_Measures"]
assert set(TABLE_ORDER) == set(SCHEMA) | {"_Measures"}

# ---- sort-by-column pairs (guide step 3.5)
SORT_BY = {("dim_date", "Month Label"): "Month Sort", ("dim_date", "Month"): "Month Number",
           ("dim_stage", "Stage"): "Stage Order", ("dim_account", "Plan Tier"): "Plan Tier Order",
           ("dim_account", "Segment"): "Segment Order", ("ref_funnel", "Step"): "Step Order",
           ("ref_bridge", "Step"): "Step Order", ("ref_lead_bands", "Score Band"): "Band Order"}

# ---- columns hidden from the field list (guide step 3.6). "ALL" hides every column.
HIDE = {
    "dim_date": ["Month Number", "Month Sort", "Month Start", "Month End", "Is Month End"],
    "dim_region": ["Region Key"], "dim_industry": ["Industry Key"], "dim_rep": ["Rep Key"],
    "dim_stage": ["Stage Key", "Stage Order"],
    "dim_account": ["Plan Tier Order", "Segment Order", "Region Key", "Industry Key"],
    "fact_arr_monthly": "ALL", "fact_account_health": "ALL",
    "fact_driver": ["Account ID", "Rank", "Impact"],
    "fact_opportunity": ["Region Key", "Industry Key", "Rep Key", "Stage Key", "Deal Size", "Discount Pct", "Decision Makers Engaged",
                         "Rep Forecast Pct", "Days in Stage", "Stage 75th Pctl Days", "Sales Cycle Days", "Model Win Probability", "Deal Label"],
    "fact_lead": ["Region Key", "Industry Key", "Became Opportunity", "Reached Discovery", "Reached Proposal", "Reached Negotiation", "Closed Won"],
    "ref_model_scorecard": ["ROC AUC", "ROC AUC Low", "ROC AUC High", "Base Rate", "Top 10 Lift", "Rows Scored"],
    "ref_lead_bands": ["Leads", "Conversion Rate", "Band Order"],
    "ref_funnel": ["Step Order"], "ref_bridge": ["Step Order"],
}

DTYPE = {"text": "string", "int": "int64", "num": "double", "date": "dateTime"}
MONEY_COLS = {"ARR End", "New ARR", "Expansion ARR", "Contraction ARR", "Churn ARR", "ARR Now", "Expected ARR Loss", "Expected Expansion ARR",
              "Scored ARR", "Deal Size"}
PCT_COLS = {"Churn Probability", "Expansion Probability", "Model Win Probability", "Seat Utilization 3M", "Login Rate 3M", "Base Rate",
            "Conversion Rate", "ROC AUC Low", "ROC AUC High"}

def q(name):
    """TMDL object-name quoting: single quotes unless it is a plain identifier."""
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else "'" + name.replace("'", "''") + "'"

def col_format(table, name, typ):
    if typ == "date": return "dd mmm yyyy"
    if name in MONEY_COLS: return "\\$#,0"
    if name in PCT_COLS: return "0.0%"
    if typ == "int": return "0"
    if typ == "num": return "#,0.00"
    return None

def m_block(table, tab_level):
    """M code from powerquery/<table>.m, re-indented with tabs for TMDL."""
    m = open(f"powerquery/{table}.m", encoding="utf-8").read().rstrip("\n")
    out = []
    for ln in m.split("\n"):
        lead = len(ln) - len(ln.lstrip(" "))
        out.append("\t" * (tab_level + lead // 4) + ln.lstrip(" "))
    return out

def table_tmdl(table):
    T = "\t"
    L = []
    cols = SCHEMA.get(table)
    if table == "dim_date": L.append("/// Calendar table. Marked as the date table; every 'last 12 months' measure counts back from its latest date.")
    elif table == "_Measures": L.append("/// Holds every DAX measure, grouped into display folders. It has no data of its own.")
    elif table.startswith("ref_"): L.append("/// Fixed reference numbers exported from the Python models. Not connected to other tables on purpose.")
    L.append(f"table {q(table)}")
    L.append(f"{T}lineageTag: {guid('table', table)}")
    if table == "dim_date": L.append(f"{T}dataCategory: Time")
    L.append("")
    if table == "_Measures":
        for m in MEASURES:
            lines = m["dax"].split("\n")
            L.append(f"{T}/// {m['meaning']}")
            if len(lines) == 1:
                L.append(f"{T}measure {q(m['name'])} = {lines[0]}")
            else:
                L.append(f"{T}measure {q(m['name'])} =")
                for ln in lines:
                    lead = len(ln) - len(ln.lstrip(" "))
                    L.append(f"{T*3}{T*(lead // 4)}{ln.lstrip(' ')}")
            if m["fmt"]: L.append(f"{T*2}formatString: {m['fmt']}")
            L.append(f"{T*2}displayFolder: {m['folder']}")
            L.append(f"{T*2}lineageTag: {guid('measure', m['name'])}")
            L.append("")
        L.append(f"{T}column Column1")
        L.append(f"{T*2}dataType: string")
        L.append(f"{T*2}isHidden")
        L.append(f"{T*2}lineageTag: {guid('column', '_Measures', 'Column1')}")
        L.append(f"{T*2}summarizeBy: none")
        L.append(f"{T*2}sourceColumn: Column1")
        L.append("")
        L.append(f"{T}partition _Measures = m")
        L.append(f"{T*2}mode: import")
        L.append(f"{T*2}source =")
        L += [f"{T*3}let", f"{T*4}Source = #table(type table [Column1 = text], {{}})", f"{T*3}in", f"{T*4}Source"]
        L.append("")
        return "\n".join(L) + "\n"
    hide = HIDE.get(table, [])
    for src, name, typ in cols:
        L.append(f"{T}column {q(name)}")
        L.append(f"{T*2}dataType: {DTYPE[typ]}")
        fmt = col_format(table, name, typ)
        if fmt: L.append(f"{T*2}formatString: {fmt}")
        if table == "dim_date" and name == "Date": L.append(f"{T*2}isKey")
        if hide == "ALL" or name in hide: L.append(f"{T*2}isHidden")
        L.append(f"{T*2}lineageTag: {guid('column', table, name)}")
        L.append(f"{T*2}summarizeBy: none")
        L.append(f"{T*2}sourceColumn: {name}")
        sb = SORT_BY.get((table, name))
        if sb: L.append(f"{T*2}sortByColumn: {q(sb)}")
        L.append("")
    L.append(f"{T}partition {q(table)} = m")
    L.append(f"{T*2}mode: import")
    L.append(f"{T*2}source =")
    L += m_block(table, 3)
    L.append("")
    return "\n".join(L) + "\n"

RELATIONSHIPS = [  # (many table, many col, one table, one col)  - the 14 relationships of guide step 3.3
    ("dim_account", "Region Key", "dim_region", "Region Key"),
    ("fact_opportunity", "Region Key", "dim_region", "Region Key"),
    ("fact_lead", "Region Key", "dim_region", "Region Key"),
    ("dim_account", "Industry Key", "dim_industry", "Industry Key"),
    ("fact_opportunity", "Industry Key", "dim_industry", "Industry Key"),
    ("fact_lead", "Industry Key", "dim_industry", "Industry Key"),
    ("fact_arr_monthly", "Account ID", "dim_account", "Account ID"),
    ("fact_account_health", "Account ID", "dim_account", "Account ID"),
    ("fact_driver", "Account ID", "dim_account", "Account ID"),
    ("fact_arr_monthly", "Month End Date", "dim_date", "Date"),
    ("fact_lead", "Created Date", "dim_date", "Date"),
    ("fact_opportunity", "Created Date", "dim_date", "Date"),
    ("fact_opportunity", "Rep Key", "dim_rep", "Rep Key"),
    ("fact_opportunity", "Stage Key", "dim_stage", "Stage Key"),
]

def relationships_tmdl():
    T = "\t"; L = []
    for mt, mc, ot, oc in RELATIONSHIPS:
        L.append(f"relationship {guid('rel', mt, mc, ot, oc)}")
        L.append(f"{T}fromColumn: {q(mt)}.{q(mc)}")
        L.append(f"{T}toColumn: {q(ot)}.{q(oc)}")
        L.append("")
    return "\n".join(L)

def model_tmdl():
    order = ["FolderPath"] + TABLE_ORDER
    L = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3", "\tdiscourageImplicitMeasures",
         "\tsourceQueryCulture: en-US", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
         f"annotation PBI_QueryOrder = {json.dumps(order, separators=(',', ':'))}", ""]
    L += [f"ref table {q(t)}" for t in TABLE_ORDER]
    L += [""]
    return "\n".join(L)

def expressions_tmdl():
    return ("/// Folder that holds the 15 CSV files. If you unzipped somewhere else, change it with Home > Transform data > Edit parameters. It must end with a backslash.\n"
            f'expression FolderPath = "{DEFAULT_FOLDER}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
            f"\tlineageTag: {guid('expr', 'FolderPath')}\n\n\tannotation PBI_ResultType = Text\n")

def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f: f.write(text)

def build(root, model_name="Revenue_Pipeline"):
    sm = os.path.join(root, f"{model_name}.SemanticModel")
    write(os.path.join(sm, "definition.pbism"), json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "settings": {}}, indent=2) + "\n")
    write(os.path.join(sm, ".platform"), json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": model_name},
        "config": {"version": "2.0", "logicalId": guid("platform", "model")}}, indent=2) + "\n")
    d = os.path.join(sm, "definition")
    write(os.path.join(d, "database.tmdl"), "database\n\tcompatibilityLevel: 1567\n")
    write(os.path.join(d, "model.tmdl"), model_tmdl())
    write(os.path.join(d, "relationships.tmdl"), relationships_tmdl())
    write(os.path.join(d, "expressions.tmdl"), expressions_tmdl())
    for t in TABLE_ORDER:
        write(os.path.join(d, "tables", f"{t}.tmdl"), table_tmdl(t))
    return sm

if __name__ == "__main__":
    import sys
    print(build(sys.argv[1]))
