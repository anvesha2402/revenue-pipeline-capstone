"""Writes powerquery/*.m (one file per table) and powerquery/ALL_QUERIES.txt from pbi_schema.SCHEMA."""
import os
import pandas as pd
from pbi_schema import SCHEMA

OUT = "powerquery"
os.makedirs(OUT, exist_ok=True)
T = {"text": "type text", "int": "Int64.Type", "num": "type number", "date": "type date"}
blocks = []
for tbl, cols in SCHEMA.items():
    head = pd.read_csv(f"data/{tbl}.csv", nrows=1).columns.tolist()
    assert head == [c[0] for c in cols], (tbl, head, [c[0] for c in cols])
    types = ", ".join(f'{{"{c[0]}", {T[c[2]]}}}' for c in cols)
    ren = ", ".join(f'{{"{c[0]}", "{c[1]}"}}' for c in cols if c[0] != c[1])
    m = f'''let
    Folder = if Text.EndsWith(FolderPath, "\\") then FolderPath else FolderPath & "\\",
    Source = Csv.Document(File.Contents(Folder & "{tbl}.csv"), [Delimiter = ",", Columns = {len(cols)}, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {{{types}}}, "en-US"),
    Renamed = Table.RenameColumns(Typed, {{{ren}}})
in
    Renamed'''
    open(f"{OUT}/{tbl}.m", "w").write(m + "\n")
    blocks.append(f"//////// QUERY NAME: {tbl}\n{m}\n")
open(f"{OUT}/ALL_QUERIES.txt", "w").write("\n".join(blocks))
print(len(SCHEMA), "queries written")
