let
    Folder = if Text.EndsWith(FolderPath, "\") then FolderPath else FolderPath & "\",
    Source = Csv.Document(File.Contents(Folder & "dim_rep.csv"), [Delimiter = ",", Columns = 2, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {{"rep_key", Int64.Type}, {"sales_rep", type text}}, "en-US"),
    Renamed = Table.RenameColumns(Typed, {{"rep_key", "Rep Key"}, {"sales_rep", "Sales Rep"}})
in
    Renamed
