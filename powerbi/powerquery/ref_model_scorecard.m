let
    Folder = if Text.EndsWith(FolderPath, "\") then FolderPath else FolderPath & "\",
    Source = Csv.Document(File.Contents(Folder & "ref_model_scorecard.csv"), [Delimiter = ",", Columns = 10, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {{"model_name", type text}, {"predicts", type text}, {"validation", type text}, {"algorithm", type text}, {"roc_auc", type number}, {"roc_auc_low", type number}, {"roc_auc_high", type number}, {"base_rate", type number}, {"top10_lift", type number}, {"n_scored", Int64.Type}}, "en-US"),
    Renamed = Table.RenameColumns(Typed, {{"model_name", "Model Name"}, {"predicts", "Predicts"}, {"validation", "Validation"}, {"algorithm", "Algorithm"}, {"roc_auc", "ROC AUC"}, {"roc_auc_low", "ROC AUC Low"}, {"roc_auc_high", "ROC AUC High"}, {"base_rate", "Base Rate"}, {"top10_lift", "Top 10 Lift"}, {"n_scored", "Rows Scored"}})
in
    Renamed
