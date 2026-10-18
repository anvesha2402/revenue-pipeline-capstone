import json, os, re, sys, urllib.request, ssl
OUT = sys.argv[1]
RAW = "https://raw.githubusercontent.com/microsoft/json-schemas/main/"
BASE = "https://developer.microsoft.com/json-schemas/"
seen = {}
def fetch(url):
    if url in seen: return
    rel = url.replace(BASE, "")
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        data = urllib.request.urlopen(RAW + rel, timeout=60).read()
        open(path, "wb").write(data)
    seen[url] = path
    txt = open(path, encoding="utf-8").read()
    for ref in set(re.findall(r'"\$ref"\s*:\s*"([^"]+)"', txt)):
        ref = ref.split("#")[0]
        if not ref: continue
        if ref.startswith("http"):
            if ref.startswith(BASE): fetch(ref)
        else:
            # relative ref
            base_dir = url.rsplit("/", 1)[0] + "/"
            from urllib.parse import urljoin
            fetch(urljoin(url, ref))
for u in sys.argv[2:]:
    fetch(u)
print(len(seen), "files")
for u in seen: print(u)
