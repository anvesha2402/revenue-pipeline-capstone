"""Check each visual's `objects` against Microsoft's theme schema (which lists every formatting object / property per visual type).
The visualContainer JSON schema does not check these, so a typo in a property name would otherwise only show up in Desktop."""
import json, os, sys, re
S = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pbip_assets", "themeschema.json")))
VS = S["properties"]["visualStyles"]["properties"]; DEFS = S["definitions"]
CONTAINER = {"actionButtonSection","*","background","border","divider","dropShadow","general","lockAspect","padding","spacing","stylePreset","subTitle","title","visualHeader","visualHeaderTooltip","visualLink","visualTooltip"}

def resolve(n):
    while isinstance(n, dict) and "$ref" in n: n = DEFS[n["$ref"].split("/")[-1]]
    return n
def collect(node):
    out = {}
    node = resolve(node)
    for p in node.get("allOf", [node]):
        p = resolve(p)
        for oname, osch in p.get("properties", {}).items():
            osch = resolve(osch); items = resolve(osch.get("items", {}))
            props = items.get("properties", {}) if isinstance(items, dict) else {}
            out.setdefault(oname, {}).update(props)
    return out
_cache = {}
def objs_for(vtype):
    if vtype not in _cache:
        _cache[vtype] = collect(VS[vtype]["properties"]["*"]) if vtype in VS else None
    return _cache[vtype]

def literal_py(expr):
    """PBIR expression -> (kind, python value) for simple literals, else (kind, None)."""
    if not isinstance(expr, dict): return ("raw", expr)
    e = expr.get("expr", expr)
    if "Literal" in e:
        v = e["Literal"]["Value"]
        if v in ("true", "false"): return ("boolean", v == "true")
        if re.fullmatch(r"-?\d+(\.\d+)?D", v): return ("number", float(v[:-1]))
        if re.fullmatch(r"-?\d+L", v): return ("number", int(v[:-1]))
        if v.startswith("'") and v.endswith("'"): return ("string", v[1:-1].replace("''", "'"))
        return ("other", v)
    return ("expr", None)

def check_prop(sch, key, val, where, errs):
    sch = resolve(sch)
    if "solid" in val if isinstance(val, dict) else False:
        return                                    # colour: structure is fixed by container schema
    kind, v = literal_py(val)
    t = sch.get("type")
    if kind == "expr":
        return
    enum = None
    if "enum" in sch: enum = sch["enum"]
    elif "oneOf" in sch and all("const" in o for o in sch["oneOf"]): enum = [o["const"] for o in sch["oneOf"]]
    if enum and None not in enum and v not in enum:
        errs.append(f"{where}.{key}: value {v!r} not in {enum}")
    if t == "boolean" and kind != "boolean": errs.append(f"{where}.{key}: expected boolean, got {kind}")
    if t == "number" and kind != "number": errs.append(f"{where}.{key}: expected number (use 12D / 12L), got {kind} {v!r}")
    if t == "string" and kind not in ("string",) and not enum: errs.append(f"{where}.{key}: expected string, got {kind}")

def run(root):
    errs, nvis = [], 0
    for dp, _, fn in os.walk(os.path.join(root, "Revenue_Pipeline.Report", "definition", "pages")):
        for f in fn:
            if f != "visual.json": continue
            j = json.load(open(os.path.join(dp, f))); nvis += 1
            vt = j["visual"]["visualType"]; name = j["name"]
            objs = objs_for(vt)
            if objs is None: errs.append(f"{name}: visualType {vt} not in theme schema"); continue
            for oname, lst in j["visual"].get("objects", {}).items():
                if oname not in objs: errs.append(f"{name}: object '{oname}' not valid for {vt}"); continue
                for item in lst:
                    for pk, pv in item.get("properties", {}).items():
                        if pk not in objs[oname]:
                            errs.append(f"{name}: {oname}.{pk} not valid for {vt}  (valid: {', '.join(sorted(objs[oname]))[:300]})"); continue
                        check_prop(objs[oname][pk], pk, pv, f"{name}:{oname}", errs)
    print(f"object/property check: {nvis} visuals, {len(errs)} problems")
    for e in errs: print("  ", e)
    return len(errs)

if __name__ == "__main__":
    sys.exit(1 if run(sys.argv[1]) else 0)
