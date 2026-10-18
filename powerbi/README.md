# Power BI kit

Start with `POWER_BI_BUILD_GUIDE.md` (or open `guide_page.html` in a browser). Everything the guide mentions is in this folder:
`data/` (star schema CSVs), `powerquery/` (loading scripts), `measures.tmdl` (83 DAX measures), `design/` (theme, backgrounds, previews, layout maps),
`validation/` (correct answers to check your model against). The Python scripts regenerate everything from the project's clean data (`../run_all.sh`).

## Ready-made project (.pbip)

`python3 check_pbip.py` builds `pbip_out/Revenue_Pipeline_Power_BI/` (a Power BI Project: `Revenue_Pipeline.pbip`, the semantic model in TMDL, the report in PBIR, the CSVs and a README) and then runs four checks on it:
`validate_schemas.py` (every JSON file against Microsoft's published schemas, kept in `pbip_assets/`), `validate_objects.py` (every visual's formatting properties against Microsoft's property lists),
`validate_model.py` (tables, columns, relationships, sort-by pairs, every DAX reference, CSV contents) and `validate_report.py` (every field a visual uses exists; layout, interactions, resources).
The generators are `pbip_model.py` (model) and `pbip_report.py` (pages and visuals); both read the same schema, measures and layout files as the manual build guide, so the project and the guide cannot drift apart.
Power BI Desktop itself was not available when this was written, so the project is verified against the file formats, not by opening it; `README_FIRST.md` inside the project lists what to confirm in Desktop.
