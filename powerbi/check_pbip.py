"""Builds the Power BI Project and runs every check on it.     python3 check_pbip.py [output_parent_folder]
Needs only: pandas, jsonschema, referencing (pip install pandas jsonschema)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, HERE)
import build_pbip, validate_schemas, validate_objects, validate_model, validate_report

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "pbip_out")
root = build_pbip.main(out)
bad = 0
bad += validate_schemas.run(root)      # every JSON file against Microsoft's published schemas
bad += validate_objects.run(root)      # every visual's formatting properties against Microsoft's property lists
bad += validate_model.run(root)        # tables, columns, relationships, sort-by pairs, DAX references, CSV contents
bad += validate_report.run(root)       # every field a visual uses exists; interactions, layout, resources
print("\nALL CHECKS PASSED" if not bad else f"\n{bad} PROBLEM(S) - see above")
sys.exit(1 if bad else 0)
