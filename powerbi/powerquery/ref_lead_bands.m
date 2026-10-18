let
    Folder = if Text.EndsWith(FolderPath, "\") then FolderPath else FolderPath & "\",
    Source = Csv.Document(File.Contents(Folder & "ref_lead_bands.csv"), [Delimiter = ",", Columns = 4, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {{"score_band", type text}, {"leads", Int64.Type}, {"conversion_rate", type number}, {"band_order", Int64.Type}}, "en-US"),
    Renamed = Table.RenameColumns(Typed, {{"score_band", "Score Band"}, {"leads", "Leads"}, {"conversion_rate", "Conversion Rate"}, {"band_order", "Band Order"}})
in
    Renamed
