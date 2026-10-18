let
    Folder = if Text.EndsWith(FolderPath, "\") then FolderPath else FolderPath & "\",
    Source = Csv.Document(File.Contents(Folder & "dim_date.csv"), [Delimiter = ",", Columns = 11, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {{"date", type date}, {"year", Int64.Type}, {"quarter", type text}, {"year_quarter", type text}, {"month_number", Int64.Type}, {"month_name", type text}, {"month_label", type text}, {"year_month_sort", Int64.Type}, {"month_start", type date}, {"month_end", type date}, {"is_month_end", Int64.Type}}, "en-US"),
    Renamed = Table.RenameColumns(Typed, {{"date", "Date"}, {"year", "Year"}, {"quarter", "Quarter"}, {"year_quarter", "Year Quarter"}, {"month_number", "Month Number"}, {"month_name", "Month"}, {"month_label", "Month Label"}, {"year_month_sort", "Month Sort"}, {"month_start", "Month Start"}, {"month_end", "Month End"}, {"is_month_end", "Is Month End"}})
in
    Renamed
