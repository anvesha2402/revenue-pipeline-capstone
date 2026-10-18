let
    Folder = if Text.EndsWith(FolderPath, "\") then FolderPath else FolderPath & "\",
    Source = Csv.Document(File.Contents(Folder & "fact_arr_monthly.csv"), [Delimiter = ",", Columns = 7, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {{"account_id", type text}, {"month_end_date", type date}, {"arr_end", type number}, {"new_arr", type number}, {"expansion_arr", type number}, {"contraction_arr", type number}, {"churn_arr", type number}}, "en-US"),
    Renamed = Table.RenameColumns(Typed, {{"account_id", "Account ID"}, {"month_end_date", "Month End Date"}, {"arr_end", "ARR End"}, {"new_arr", "New ARR"}, {"expansion_arr", "Expansion ARR"}, {"contraction_arr", "Contraction ARR"}, {"churn_arr", "Churn ARR"}})
in
    Renamed
