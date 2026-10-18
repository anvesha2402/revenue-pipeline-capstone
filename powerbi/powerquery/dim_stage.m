let
    Folder = if Text.EndsWith(FolderPath, "\") then FolderPath else FolderPath & "\",
    Source = Csv.Document(File.Contents(Folder & "dim_stage.csv"), [Delimiter = ",", Columns = 4, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {{"stage_key", Int64.Type}, {"stage", type text}, {"stage_order", Int64.Type}, {"stage_group", type text}}, "en-US"),
    Renamed = Table.RenameColumns(Typed, {{"stage_key", "Stage Key"}, {"stage", "Stage"}, {"stage_order", "Stage Order"}, {"stage_group", "Stage Group"}})
in
    Renamed
