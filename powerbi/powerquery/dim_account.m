let
    Folder = if Text.EndsWith(FolderPath, "\") then FolderPath else FolderPath & "\",
    Source = Csv.Document(File.Contents(Folder & "dim_account.csv"), [Delimiter = ",", Columns = 17, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {{"account_id", type text}, {"company_name", type text}, {"customer_label", type text}, {"account_tier", type text}, {"tier_order", Int64.Type}, {"size_band", type text}, {"csm_id", type text}, {"customer_since", type date}, {"customer_status", type text}, {"churn_date", type date}, {"churn_reason", type text}, {"segment", type text}, {"segment_order", Int64.Type}, {"churn_risk", type text}, {"expansion_potential", type text}, {"region_key", Int64.Type}, {"industry_key", Int64.Type}}, "en-US"),
    Renamed = Table.RenameColumns(Typed, {{"account_id", "Account ID"}, {"company_name", "Company"}, {"customer_label", "Customer"}, {"account_tier", "Plan Tier"}, {"tier_order", "Plan Tier Order"}, {"size_band", "Company Size"}, {"csm_id", "CSM"}, {"customer_since", "Customer Since"}, {"customer_status", "Customer Status"}, {"churn_date", "Churn Date"}, {"churn_reason", "Churn Reason"}, {"segment", "Segment"}, {"segment_order", "Segment Order"}, {"churn_risk", "Churn Risk"}, {"expansion_potential", "Expansion Potential"}, {"region_key", "Region Key"}, {"industry_key", "Industry Key"}})
in
    Renamed
