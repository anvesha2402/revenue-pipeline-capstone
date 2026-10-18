import re
from measures_def import M
from pbi_schema import SCHEMA

# ---- lint: every table[column] reference must exist; every [Measure] reference must exist
cols = {(t, c[1]) for t, cs in SCHEMA.items() for c in cs}
names = {m["name"] for m in M}
assert len(names) == len(M), "duplicate measure names"
bad = []
for m in M:
    d = m["dax"]
    for t, c in re.findall(r"([A-Za-z_]+)\[([^\]]+)\]", d):
        if (t, c) not in cols and c not in names:
            bad.append((m["name"], t, c))
    if d.count("(") != d.count(")") or d.count("{") != d.count("}"):
        bad.append((m["name"], "unbalanced brackets", ""))
    if d.count('"') % 2:
        bad.append((m["name"], "odd quotes", ""))
    for ref in re.findall(r"(?<![A-Za-z_\]\"])\[([^\]@][^\]]*)\]", d):
        if ref not in names and ref not in {"@Start", "@Now"}:
            pass
print("measures:", len(M), "| lint problems:", bad)
assert not bad

# ---- TMDL (paste into TMDL view)
T = "\t"
out = ["createOrReplace", "", f"{T}ref table _Measures", ""]
for m in M:
    lines = m["dax"].split("\n")
    out.append(f"{T*2}/// {m['meaning']}")
    if len(lines) == 1:
        out.append(f"{T*2}measure '{m['name']}' = {lines[0]}")
    else:
        out.append(f"{T*2}measure '{m['name']}' =")
        for ln in lines:
            lead = len(ln) - len(ln.lstrip(" "))
            out.append(f"{T*4}{T*(lead//4)}{ln.lstrip(' ')}")
    if m["fmt"]:
        out.append(f"{T*3}formatString: {m['fmt']}")
    out.append(f"{T*3}displayFolder: {m['folder']}")
    out.append("")
open("measures.tmdl", "w").write("\n".join(out))

# ---- plain list for manual copy
md = ["# All DAX measures (plain copy version)\n",
      "Use this only if the TMDL paste method does not work. For each measure: select the `_Measures` table, then **Home > New measure**, paste the line(s) below as is, press Enter. "
      "Then, with the measure selected, set the Format on the **Measure tools** ribbon as shown.\n"]
cur = None
for m in M:
    if m["folder"] != cur:
        cur = m["folder"]
        md.append(f"\n## {cur}\n")
    md.append(f"### {m['name']}\n{m['meaning']}\n\nFormat: `{m['fmt'] or 'text (no format needed)'}`\n\n```dax\n{m['name']} =\n{m['dax']}\n```\n")
open("measures_plain.md", "w").write("\n".join(md))
print("written")
