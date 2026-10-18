"""Validate every JSON file in the project against Microsoft's published schemas (local copies)."""
import json, os, sys
from jsonschema import Draft7Validator, Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7, DRAFT202012

SCHEMA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pbip_assets", "schemas")   # Microsoft schemas, copied from github.com/microsoft/json-schemas
BASE = "https://developer.microsoft.com/json-schemas/"

def local(uri):
    if uri.startswith(BASE): return os.path.join(SCHEMA_ROOT, uri[len(BASE):])
    raise KeyError(uri)

def retrieve(uri):
    uri = uri.split("#")[0]
    with open(local(uri), encoding="utf-8") as f: data = json.load(f)
    return Resource.from_contents(data, default_specification=DRAFT7)

REG = Registry(retrieve=retrieve)

def validate_file(path):
    with open(path, encoding="utf-8") as f: doc = json.load(f)
    uri = doc.get("$schema")
    if not uri: return [("no $schema", "")]
    try:
        with open(local(uri), encoding="utf-8") as f: schema = json.load(f)
    except Exception as e:
        return [(f"schema not available locally: {uri}", str(e))]
    cls = Draft202012Validator if "2020-12" in schema.get("$schema", "") else Draft7Validator
    v = cls(schema, registry=REG)
    errs = []
    for e in sorted(v.iter_errors(doc), key=lambda e: list(map(str, e.absolute_path))):
        loc = "/".join(map(str, e.absolute_path))
        msg = e.message if len(e.message) < 300 else e.message[:300] + "..."
        # add the best-matching sub-error for oneOf/anyOf failures
        if e.context:
            best = sorted(e.context, key=lambda c: len(list(c.absolute_path)), reverse=True)[0]
            msg += f"  [deepest: /{'/'.join(map(str, best.absolute_path))}: {best.message[:200]}]"
        errs.append((loc, msg))
    return errs

def run(root, quiet=False):
    bad, n = 0, 0
    for dp, dn, fn in os.walk(root):
        rel = os.path.relpath(dp, root).split(os.sep)[0]
        if "StaticResources" in dp or rel in ("data", "validation"): continue
        for f in fn:
            if f.endswith((".json", ".pbir", ".pbip", ".pbism", ".platform")):
                p = os.path.join(dp, f)
                n += 1
                errs = validate_file(p)
                if errs:
                    bad += 1
                    if not quiet:
                        print("FAIL", os.path.relpath(p, root))
                        for loc, m in errs[:8]: print("    ", loc, "->", m)
    print(f"schema validation: {n} files checked, {bad} with errors")
    return bad

if __name__ == "__main__":
    sys.exit(1 if run(sys.argv[1]) else 0)
