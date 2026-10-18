let
    Folder = if Text.EndsWith(FolderPath, "\") then FolderPath else FolderPath & "\",
    Source = Csv.Document(File.Contents(Folder & "ref_funnel.csv"), [Delimiter = ",", Columns = 2, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {{"step_order", Int64.Type}, {"step", type text}}, "en-US"),
    Renamed = Table.RenameColumns(Typed, {{"step_order", "Step Order"}, {"step", "Step"}})
in
    Renamed
