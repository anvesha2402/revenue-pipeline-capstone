"""Report-side checks: every field a visual uses exists in the model, sort/format selectors point at projected fields,
page order / interactions / sync groups are consistent, and nothing overlaps or leaves the 1280x720 canvas."""
import json, os, re, sys
from pbi_schema import SCHEMA
from measures_def import M as MEASURES
from layout_spec import PAGES, W, H

COLS = {t: {n for _, n, _ in cols} for t, cols in SCHEMA.items()}
MEAS = {m["name"] for m in MEASURES}
ERR = []
def err(m): ERR.append(m)

def field_ok(entity, prop, kind, where):
    if kind == "Measure":
        if entity != "_Measures" or prop not in MEAS: err(f"{where}: measure {entity}.{prop} does not exist")
    else:
        if entity not in COLS or prop not in COLS[entity]: err(f"{where}: column {entity}.{prop} does not exist")

def walk_fields(node, froms, where, found):
    """collect (kind, entity, prop) from any Column/Measure expression; resolve Source aliases through `froms`."""
    if isinstance(node, dict):
        if "From" in node and isinstance(node["From"], list):
            froms = dict(froms)
            for f in node["From"]:
                if "Entity" in f: froms[f["Name"]] = f["Entity"]
        for kind in ("Column", "Measure"):
            if kind in node and isinstance(node[kind], dict) and "Expression" in node[kind] and "Property" in node[kind]:
                sr = node[kind]["Expression"].get("SourceRef", {})
                ent = sr.get("Entity") or froms.get(sr.get("Source"))
                if ent is None: err(f"{where}: unresolved source alias {sr}")
                else: found.append((kind, ent, node[kind]["Property"]))
        for v in node.values(): walk_fields(v, froms, where, found)
    elif isinstance(node, list):
        for v in node: walk_fields(v, froms, where, found)

def projections(v):
    out = []
    for rname, r in v.get("query", {}).get("queryState", {}).items():
        for p in r["projections"]:
            k = next(iter(p["field"])); f = p["field"][k]
            out.append((rname, p, f["Expression"]["SourceRef"]["Entity"] + "." + f["Property"]))
    return out

def run(root):
    rep = os.path.join(root, "Revenue_Pipeline.Report", "definition")
    pages_meta = json.load(open(os.path.join(rep, "pages", "pages.json")))
    folders = sorted(d for d in os.listdir(os.path.join(rep, "pages")) if os.path.isdir(os.path.join(rep, "pages", d)))
    if sorted(pages_meta["pageOrder"]) != folders: err(f"pageOrder {pages_meta['pageOrder']} != page folders {folders}")
    if pages_meta["activePageName"] not in folders: err("activePageName is not a page")
    sync = {}
    nvis = 0
    for pf in folders:
        pj = json.load(open(os.path.join(rep, "pages", pf, "page.json")))
        if pj["name"] != pf: err(f"page {pf}: name {pj['name']} != folder")
        vdir = os.path.join(rep, "pages", pf, "visuals")
        vis = {}
        for vf in sorted(os.listdir(vdir)):
            vj = json.load(open(os.path.join(vdir, vf, "visual.json"))); nvis += 1
            if vj["name"] != vf: err(f"{vf}: name {vj['name']} != folder")
            vis[vf] = vj
        # --- fields
        for vf, vj in vis.items():
            v = vj["visual"]; where = f"{pf}/{vf}"
            found = []
            walk_fields(v.get("query", {}), {}, where, found)
            walk_fields(vj.get("filterConfig", {}), {}, where, found)
            walk_fields(v.get("objects", {}), {}, where, found)
            walk_fields(v.get("visualContainerObjects", {}), {}, where, found)
            for kind, ent, prop in set(found): field_ok(ent, prop, kind, where)
            projs = projections(v); refs = {r for _, _, r in projs}
            for rname, p, r in projs:
                ent, prop = r.split(".", 1)
                if p["queryRef"] != r or p["nativeQueryRef"] != prop: err(f"{where}: queryRef/nativeQueryRef mismatch for {r}")
            # selectors that name a field must name a projected one
            def sels(n):
                if isinstance(n, dict):
                    if "metadata" in n and isinstance(n["metadata"], str): yield n["metadata"]
                    for x in n.values(): yield from sels(x)
                elif isinstance(n, list):
                    for x in n: yield from sels(x)
            for m_ in set(sels(v.get("objects", {}))):
                if m_ not in refs: err(f"{where}: selector metadata {m_} is not a projected field")
            for s_ in v.get("query", {}).get("sortDefinition", {}).get("sort", []):
                k = next(iter(s_["field"])); f = s_["field"][k]; r = f["Expression"]["SourceRef"]["Entity"] + "." + f["Property"]
                if r not in refs: err(f"{where}: sorted by {r}, which is not in the visual")
            # data roles required per type
            need = {"card": ["Values"], "slicer": ["Values"], "funnel": ["Category", "Y"], "barChart": ["Category", "Y"],
                    "clusteredBarChart": ["Category", "Y"], "clusteredColumnChart": ["Category", "Y"], "waterfallChart": ["Category", "Y"],
                    "areaChart": ["Category", "Y"], "scatterChart": ["Category", "X", "Y"], "tableEx": ["Values"]}.get(v["visualType"], [])
            for r in need:
                if r not in v.get("query", {}).get("queryState", {}): err(f"{where}: {v['visualType']} lacks data role {r}")
            # sync groups
            if "syncGroup" in v:
                f = [r for _, _, r in projs][0]
                sync.setdefault(v["syncGroup"]["groupName"], set()).add((f, pf))
        # --- interactions
        for it in pj.get("visualInteractions", []):
            for k in ("source", "target"):
                if it[k] not in vis: err(f"{pf}: visualInteractions {k} '{it[k]}' is not a visual on this page")
        # --- layout
        names = list(vis)
        boxes = {n: (vis[n]["position"]["x"], vis[n]["position"]["y"], vis[n]["position"]["width"], vis[n]["position"]["height"]) for n in names}
        for n, (x, y, w, h) in boxes.items():
            if x < 0 or y < 0 or x + w > W or y + h > H: err(f"{pf}/{n}: outside the {W}x{H} canvas {boxes[n]}")
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                ax, ay, aw, ah = boxes[a]; bx, by, bw, bh = boxes[b]
                if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah: err(f"{pf}: {a} overlaps {b}  {boxes[a]} / {boxes[b]}")
        zs = [vis[n]["position"]["z"] for n in names]; tabs = [vis[n]["position"]["tabOrder"] for n in names]
        if len(set(zs)) != len(zs): err(f"{pf}: duplicate z-order")
        if len(set(tabs)) != len(tabs): err(f"{pf}: duplicate tabOrder")
        # --- matches the pixel layout used for the background art
        pid = "P1" if pf == "pipeline" else "P2"
        for vid, _, _, geom in PAGES[pid]["visuals"]:
            key = f"{'p1' if pid=='P1' else 'p2'}_{vid}"
            if key not in boxes: err(f"{pf}: layout item {vid} missing"); continue
            if boxes[key] != tuple(geom): err(f"{pf}/{key}: {boxes[key]} differs from layout spec {geom}")
    for g, members in sync.items():
        fields = {f for f, _ in members}; pgs = {p for _, p in members}
        if len(fields) != 1: err(f"sync group {g} mixes fields {fields}")
        if len(pgs) < 2: err(f"sync group {g} only on {pgs}")
    # report.json resources exist
    rj = json.load(open(os.path.join(rep, "report.json")))
    for pkg in rj["resourcePackages"]:
        sub = "SharedResources/BaseThemes" if pkg["type"] == "SharedResources" else "RegisteredResources"
        for it in pkg["items"]:
            fn = os.path.basename(it["path"])
            if not os.path.exists(os.path.join(root, "Revenue_Pipeline.Report", "StaticResources", sub, fn)): err(f"resource missing: {sub}/{fn}")
    for pf in folders:
        pj = json.load(open(os.path.join(rep, "pages", pf, "page.json")))
        img = pj["objects"]["background"][0]["properties"]["image"]["image"]["name"]["expr"]["Literal"]["Value"].strip("'")
        if not os.path.exists(os.path.join(root, "Revenue_Pipeline.Report", "StaticResources", "RegisteredResources", img)): err(f"{pf}: background image {img} missing")
        if not any(it["name"] == img for pkg in rj["resourcePackages"] for it in pkg["items"]): err(f"{pf}: background image {img} not registered in report.json")
    print(f"report checks: {len(folders)} pages, {nvis} visuals, {len(ERR)} problems")
    for e in ERR: print("  ", e)
    return len(ERR)

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.exit(1 if run(sys.argv[1]) else 0)
