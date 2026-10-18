let
    Folder = if Text.EndsWith(FolderPath, "\") then FolderPath else FolderPath & "\",
    Source = Csv.Document(File.Contents(Folder & "dim_industry.csv"), [Delimiter = ",", Columns = 2, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {{"industry_key", Int64.Type}, {"industry", type text}}, "en-US"),
    Renamed = Table.RenameColumns(Typed, {{"industry_key", "Industry Key"}, {"industry", "Industry"}})
in
    Renamed
