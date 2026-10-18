"""Builds the whole Power BI Project:  python build_pbip.py <output_folder>
   <output_folder>/Revenue_Pipeline_Power_BI/
        Revenue_Pipeline.pbip, Revenue_Pipeline.SemanticModel/, Revenue_Pipeline.Report/, data/*.csv, .gitignore
"""
import json, os, shutil, sys
import pbip_model, pbip_report, pbip_readme

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
BASE_THEME = os.path.join(HERE, "pbip_assets", "CY24SU10.json")      # Microsoft's standard base theme (the report needs it as a fallback)

def main(out_parent, name="Revenue_Pipeline"):
    root = os.path.join(out_parent, f"{name}_Power_BI")
    if os.path.exists(root): shutil.rmtree(root)
    os.makedirs(root)
    pbip_model.build(root, name)
    rep, pages = pbip_report.build(root, os.path.join(HERE, "design"), BASE_THEME)
    with open(os.path.join(root, f"{name}.pbip"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
                   "version": "1.0", "artifacts": [{"report": {"path": f"{name}.Report"}}], "settings": {"enableAutoRecovery": True}}, f, indent=2)
        f.write("\n")
    with open(os.path.join(root, ".gitignore"), "w", newline="\n") as f:
        f.write("# Power BI local-only files\n**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    shutil.copytree(os.path.join(HERE, "data"), os.path.join(root, "data"))
    shutil.copytree(os.path.join(HERE, "validation"), os.path.join(root, "validation"))
    with open(os.path.join(root, "README_FIRST.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(pbip_readme.text(HERE))
    n = sum(len(p.visuals) for p in pages)
    print(f"built {root}\n  pages: {[p.display for p in pages]}  visuals: {n}")
    return root

if __name__ == "__main__":
    main(sys.argv[1])
