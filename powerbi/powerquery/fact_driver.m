let
    Folder = if Text.EndsWith(FolderPath, "\") then FolderPath else FolderPath & "\",
    Source = Csv.Document(File.Contents(Folder & "fact_driver.csv"), [Delimiter = ",", Columns = 6, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {{"account_id", type text}, {"model", type text}, {"rank", Int64.Type}, {"driver", type text}, {"impact", type number}, {"direction", type text}}, "en-US"),
    Renamed = Table.RenameColumns(Typed, {{"account_id", "Account ID"}, {"model", "Model"}, {"rank", "Rank"}, {"driver", "Driver"}, {"impact", "Impact"}, {"direction", "Direction"}})
in
    Renamed
