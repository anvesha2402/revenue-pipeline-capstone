let
    Folder = if Text.EndsWith(FolderPath, "\") then FolderPath else FolderPath & "\",
    Source = Csv.Document(File.Contents(Folder & "fact_lead.csv"), [Delimiter = ",", Columns = 13, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, {{"lead_id", type text}, {"created_date", type date}, {"region_key", Int64.Type}, {"industry_key", Int64.Type}, {"lead_source", type text}, {"contact_seniority", type text}, {"demo_requested", Int64.Type}, {"engagement_score", type number}, {"became_opportunity", Int64.Type}, {"reached_discovery", Int64.Type}, {"reached_proposal", Int64.Type}, {"reached_negotiation", Int64.Type}, {"closed_won", Int64.Type}}, "en-US"),
    Renamed = Table.RenameColumns(Typed, {{"lead_id", "Lead ID"}, {"created_date", "Created Date"}, {"region_key", "Region Key"}, {"industry_key", "Industry Key"}, {"lead_source", "Lead Source"}, {"contact_seniority", "Contact Seniority"}, {"demo_requested", "Demo Requested"}, {"engagement_score", "Engagement Score"}, {"became_opportunity", "Became Opportunity"}, {"reached_discovery", "Reached Discovery"}, {"reached_proposal", "Reached Proposal"}, {"reached_negotiation", "Reached Negotiation"}, {"closed_won", "Closed Won"}})
in
    Renamed
