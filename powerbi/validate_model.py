"""Structural checks of the semantic model that a JSON schema cannot do (there is no public TMDL parser outside Desktop/Tabular Editor):
  1. TMDL layout lint (tabs, known keywords, nesting, name quoting)
  2. every table's Power Query output == the columns declared in TMDL (names, order, types) == the CSV header
  3. relationships: columns exist, types match, 'one' side unique, every 'many' key present in the 'one' side
  4. sort-by pairs: the sort column exists and maps 1:1 to the label column in the data
  5. every DAX reference ([Measure], Table[Column]) resolves; parentheses/quotes balanced
"""
import os, re, sys
import pandas as pd
from pbi_schema import SCHEMA
from measures_def import M as MEASURES
import pbip_model as pm

HERE = os.path.dirname(os.path.abspath(__file__))
ERR = []
def err(msg): ERR.append(msg)

def parse_name(tok):
    tok = tok.strip()
    if tok.startswith("'"):
        end = tok.rindex("'"); return tok[1:end].replace("''", "'")
    return tok

TOP = {"table", "ref", "relationship", "model", "database", "expression", "annotation"}
TABLE_L1 = {"column", "measure", "partition", "annotation", "hierarchy", "lineageTag", "dataCategory", "isHidden", "description"}
COL_PROPS = {"dataType", "formatString", "isKey", "isHidden", "lineageTag", "summarizeBy", "sourceColumn", "sortByColumn", "displayFolder", "dataCategory", "annotation"}
MEA_PROPS = {"formatString", "displayFolder", "lineageTag", "isHidden", "description"}
PART_PROPS = {"mode", "source"}

def lint_tmdl(root):
    d = os.path.join(root, "Revenue_Pipeline.SemanticModel", "definition")
    files = []
    for dp, _, fn in os.walk(d):
        files += [os.path.join(dp, f) for f in fn if f.endswith(".tmdl")]
    tables = {}
    for p in files:
        rel = os.path.relpath(p, d)
        txt = open(p, encoding="utf-8").read()
        if "\r" in txt: err(f"{rel}: contains CR characters")
        if not txt.endswith("\n"): err(f"{rel}: missing final newline")
        in_multi = None  # indent level of a multi-line body
        cur = None
        for i, raw in enumerate(txt.split("\n"), 1):
            if not raw.strip(): continue
            if raw.startswith(" "): err(f"{rel}:{i}: line starts with spaces (TMDL needs tabs)"); continue
            lvl = len(raw) - len(raw.lstrip("\t")); line = raw.lstrip("\t")
            if line.startswith("///"): continue
            if in_multi is not None:
                if lvl >= in_multi: continue          # body of an expression / M source
                in_multi = None
            if lvl == 0:
                kw = line.split()[0].rstrip(":")
                if kw not in TOP: err(f"{rel}:{i}: unknown top-level keyword '{kw}'")
                if kw == "table":
                    cur = parse_name(line[len("table"):]); tables[cur] = {"cols": [], "measures": [], "file": rel, "parts": 0}
                continue
            if rel.startswith("tables") and lvl == 1:
                kw = line.split()[0].rstrip(":")
                if kw not in TABLE_L1: err(f"{rel}:{i}: unknown table-level keyword '{kw}'")
                if kw == "column": tables[cur]["cols"].append({"name": parse_name(line[len("column"):]), "props": {}})
                elif kw == "measure":
                    nm = line[len("measure"):].split(" =")[0]
                    tables[cur]["measures"].append(parse_name(nm))
                    if line.rstrip().endswith("="): in_multi = 3
                elif kw == "partition": tables[cur]["parts"] += 1
                continue
            if rel.startswith("tables") and lvl == 2:
                kw = line.split()[0].rstrip(":")
                last_is_col = tables[cur]["cols"] and True
                # figure out the owning level-1 object by scanning backwards is overkill: check keyword is known anywhere
                if kw not in COL_PROPS | MEA_PROPS | PART_PROPS: err(f"{rel}:{i}: unknown property '{kw}'")
                if kw == "source" and line.rstrip().endswith("="): in_multi = 3
                if kw in COL_PROPS and tables[cur]["cols"] and ":" in line:
                    # attach to the most recent column (measures have separate prop set, but share names formatString/displayFolder)
                    tables[cur]["cols"][-1]["props"].setdefault(kw, line.split(":", 1)[1].strip())
                continue
    return tables

def load_csv(table):
    return pd.read_csv(os.path.join(HERE, "data", f"{table}.csv"), dtype=str, keep_default_na=False)

def check_columns(root, tables):
    dtype_m = {"text": "type text", "int": "Int64.Type", "num": "type number", "date": "type date"}
    for t in pm.TABLE_ORDER:
        if t not in tables: err(f"table {t} missing in TMDL"); continue
        if t == "_Measures": continue
        want = [n for _, n, _ in SCHEMA[t]]
        got = [c["name"] for c in tables[t]["cols"]]
        if want != got: err(f"{t}: TMDL columns {got} != schema {want}")
        if len(set(got)) != len(got): err(f"{t}: duplicate column names")
        # TMDL sourceColumn/dataType vs schema
        for c, (src, name, typ) in zip(tables[t]["cols"], SCHEMA[t]):
            if c["props"].get("sourceColumn") != name: err(f"{t}.{name}: sourceColumn {c['props'].get('sourceColumn')!r}")
            if c["props"].get("dataType") != pm.DTYPE[typ]: err(f"{t}.{name}: dataType {c['props'].get('dataType')} != {pm.DTYPE[typ]}")
        # M text: last Table.RenameColumns -> output names; CSV header -> src names
        m = open(os.path.join(HERE, "powerquery", f"{t}.m"), encoding="utf-8").read()
        pairs = re.findall(r'\{"([^"]+)",\s*"([^"]+)"\}', m.split("Table.RenameColumns")[-1])
        if [b for _, b in pairs] != want: err(f"{t}: Power Query output names {[b for _, b in pairs]} != schema {want}")
        if [a for a, _ in pairs] != [s for s, _, _ in SCHEMA[t]]: err(f"{t}: Power Query source names differ from schema source names")
        hdr = list(load_csv(t).columns)
        if hdr != [s for s, _, _ in SCHEMA[t]]: err(f"{t}: CSV header {hdr} != schema source names")
        # types in M
        tt = re.findall(r'\{"([^"]+)",\s*([A-Za-z0-9_.\s]+?)\}', m.split("Table.TransformColumnTypes")[1].split(")")[0])
        for (a, mt), (src, name, typ) in zip(tt, SCHEMA[t]):
            if a != src or mt.strip() != dtype_m[typ]: err(f"{t}.{src}: M type {mt!r} expected {dtype_m[typ]}")
        # CSV content parses to the declared type
        df = load_csv(t)
        for src, name, typ in SCHEMA[t]:
            s = df[src]
            if typ in ("int", "num"):
                bad = pd.to_numeric(s.replace("", pd.NA).dropna(), errors="coerce").isna().sum()
                if bad: err(f"{t}.{src}: {bad} non-numeric values")
                if typ == "int":
                    nn = pd.to_numeric(s.replace("", pd.NA).dropna(), errors="coerce")
                    if (nn != nn.round()).any(): err(f"{t}.{src}: int column holds decimals")
            if typ == "date":
                bad = pd.to_datetime(s.replace("", pd.NA).dropna(), format="%Y-%m-%d", errors="coerce").isna().sum()
                if bad: err(f"{t}.{src}: {bad} values not in YYYY-MM-DD")

def check_relationships(root):
    seen = set()
    for mt, mc, ot, oc in pm.RELATIONSHIPS:
        sm = {n: (s, ty) for s, n, ty in SCHEMA[mt]}; so = {n: (s, ty) for s, n, ty in SCHEMA[ot]}
        if mc not in sm or oc not in so: err(f"relationship {mt}.{mc}->{ot}.{oc}: column missing"); continue
        if sm[mc][1] != so[oc][1]: err(f"relationship {mt}.{mc}->{ot}.{oc}: type mismatch {sm[mc][1]} vs {so[oc][1]}")
        one = load_csv(ot)[so[oc][0]]; many = load_csv(mt)[sm[mc][0]]
        if one.duplicated().any(): err(f"relationship {ot}.{oc} is not unique ({one.duplicated().sum()} duplicates)")
        if (one == "").any(): err(f"relationship {ot}.{oc} has blanks")
        missing = set(many[many != ""].unique()) - set(one.unique())
        if missing: err(f"relationship {mt}.{mc}: {len(missing)} keys not in {ot}.{oc}, e.g. {list(missing)[:3]}")
        if (many == "").any(): err(f"relationship {mt}.{mc}: {(many == '').sum()} blank keys")
        key = (mt, mc, ot, oc)
        if key in seen: err(f"duplicate relationship {key}")
        seen.add(key)
    # no table pair connected twice (ambiguity) and no cycles
    pairs = {}
    for mt, mc, ot, oc in pm.RELATIONSHIPS:
        pairs.setdefault(frozenset((mt, ot)), []).append((mc, oc))
    for k, v in pairs.items():
        if len(v) > 1: err(f"{set(k)} connected by {len(v)} relationships (only 1 can be active)")
    # ambiguity check: filters travel one -> many only, so every (dimension, table) pair must have at most ONE directed path
    out = {}
    for mt, _, ot, _ in pm.RELATIONSHIPS: out.setdefault(ot, []).append(mt)
    def count_paths(src, dst):
        if src == dst: return 1
        return sum(count_paths(n, dst) for n in out.get(src, []))
    nodes = set(out) | {m for ms in out.values() for m in ms}
    for a in nodes:
        for b in nodes:
            if a != b and count_paths(a, b) > 1: err(f"ambiguous filter path: {count_paths(a, b)} routes from {a} to {b}")

def check_sortby():
    for (t, label), sortcol in pm.SORT_BY.items():
        sm = {n: s for s, n, _ in SCHEMA[t]}
        if label not in sm or sortcol not in sm: err(f"sortBy {t}.{label}->{sortcol}: column missing"); continue
        df = load_csv(t)[[sm[label], sm[sortcol]]].drop_duplicates()
        if df[sm[label]].duplicated().any(): err(f"sortBy {t}.{label}: a label has more than one {sortcol} value")
        if df[sm[sortcol]].duplicated().any(): err(f"sortBy {t}.{label}: two labels share one {sortcol} value (Desktop rejects this)")

DAX_FUNCS_SKIP = set()
def strip_dax(s):
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S); s = re.sub(r"//[^\n]*", "", s)
    s = re.sub(r'"(?:[^"]|"")*"', '""', s)      # string literals
    return s

def check_dax():
    cols = {t: {n for _, n, _ in SCHEMA[t]} for t in SCHEMA}
    mnames = {m["name"] for m in MEASURES}
    if len(mnames) != len(MEASURES): err("duplicate measure names")
    for m in MEASURES:
        raw = m["dax"]
        s = strip_dax(raw)
        for a, b in ("()", "{}", "[]"):
            if s.count(a) != s.count(b): err(f"{m['name']}: unbalanced {a}{b}")
        if raw.count("'") % 2: err(f"{m['name']}: odd number of single quotes")
        local = set(re.findall(r"\bVAR\s+([A-Za-z_]\w*)", s))
        aliases = set(re.findall(r'""\s*,', s))      # placeholder
        alias_names = set(re.findall(r'"(@?[A-Za-z_][\w ]*)"\s*,', raw))
        # Table[Col]
        for tm in re.finditer(r"(?:'([^']+)'|\b([A-Za-z_]\w*))\[([^\]]+)\]", s):
            t = tm.group(1) or tm.group(2); c = tm.group(3)
            if t in local: continue
            if t not in cols: err(f"{m['name']}: unknown table '{t}' in {t}[{c}]"); continue
            if c not in cols[t]: err(f"{m['name']}: unknown column {t}[{c}]")
        # bare [Name]
        s2 = re.sub(r"(?:'[^']+'|\b[A-Za-z_]\w*)\[[^\]]+\]", "", s)
        for bm in re.finditer(r"\[([^\]]+)\]", s2):
            n = bm.group(1)
            if n in mnames or n in alias_names or n.startswith("@"): continue
            err(f"{m['name']}: bare reference [{n}] is neither a measure nor a local column")
        for v in re.findall(r"\bVAR\s+([A-Za-z_]\w*)\s*=", s):
            if len(re.findall(r"\b" + v + r"\b", s)) < 2: err(f"{m['name']}: variable {v} is never used")
        if not re.search(r"\bRETURN\b", s) and re.search(r"\bVAR\b", s): err(f"{m['name']}: VAR without RETURN")

def run(root):
    tables = lint_tmdl(root)
    check_columns(root, tables); check_relationships(root); check_sortby(); check_dax()
    # measure counts
    n = len(tables.get("_Measures", {}).get("measures", []))
    if n != len(MEASURES): err(f"_Measures has {n} measures in TMDL, {len(MEASURES)} defined")
    for t in tables:
        if tables[t]["parts"] != 1: err(f"{t}: {tables[t]['parts']} partitions (need exactly 1)")
    print(f"model checks: {len(tables)} tables, {n} measures, {len(pm.RELATIONSHIPS)} relationships, {len(ERR)} problems")
    for e in ERR: print("  ", e)
    return len(ERR)

if __name__ == "__main__":
    os.chdir(HERE)
    sys.exit(1 if run(sys.argv[1]) else 0)
