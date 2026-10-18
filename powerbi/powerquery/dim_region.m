let
    Folder = if Text.EndsWith(FolderPath, "\") then FolderPath else FolderPath & "\",
    Source = Csv.Document(File.Contents(Folder & "dim_region.csv"), [Delimiter = ",", Columns = 2, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {{"region_key", Int64.Type}, {"region", type text}}, "en-US"),
    Renamed = Table.RenameColumns(Typed, {{"region_key", "Region Key"}, {"region", "Region"}})
in
    Renamed
