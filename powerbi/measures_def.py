"""All DAX measures: (name, display_folder, format_string, plain-language meaning, DAX)."""
LASTD = "LASTNONBLANK(dim_date[Date], CALCULATE(COUNTROWS(fact_arr_monthly)))"
M = []
def add(name, folder, fmt, meaning, dax):
    M.append(dict(name=name, folder=folder, fmt=fmt, meaning=meaning, dax=dax.strip("\n")))

USD, USDK, PCT, INT, DEC1 = r"\$#,0", r"\$#,0,\K", "0.0%", "#,0", "#,0.0"
F0, F1, F2, F3, F4, F5, F6 = ("0 Helpers", "1 Pipeline", "2 Funnel", "3 Revenue and retention", "4 Risk and growth",
                              "5 Model reliability", "6 Labels and colours")

# ---------------------------------------------------------------- helpers
add("As Of Date", F0, "dd mmm yyyy", "The reporting date: the latest date in the date table (30 Jun 2026). Every 'last 12 months' measure counts back from it.",
    "CALCULATE(MAX(dim_date[Date]), REMOVEFILTERS(dim_date))")

# ---------------------------------------------------------------- pipeline
add("Open Pipeline", F1, USD, "Total value of deals that are still open (not yet won or lost).",
    'CALCULATE(SUM(fact_opportunity[Deal Size]), fact_opportunity[Outcome] = "Open")')
add("Open Deals", F1, INT, "Number of deals that are still open.",
    'CALCULATE(COUNTROWS(fact_opportunity), fact_opportunity[Outcome] = "Open")')
add("Avg Open Deal Size", F1, USD, "Average value of an open deal.", "DIVIDE([Open Pipeline], [Open Deals])")
add("Won Deals 12M", F1, INT, "Deals won in the 12 months up to the reporting date.", """
VAR AsOf = [As Of Date]
VAR StartDate = EDATE(AsOf, -12)
RETURN
CALCULATE(
    COUNTROWS(fact_opportunity),
    fact_opportunity[Outcome] = "Won",
    fact_opportunity[Closed Date] > StartDate,
    fact_opportunity[Closed Date] <= AsOf
)""")
add("Closed Deals 12M", F1, INT, "Deals won or lost in the 12 months up to the reporting date.", """
VAR AsOf = [As Of Date]
VAR StartDate = EDATE(AsOf, -12)
RETURN
CALCULATE(
    COUNTROWS(fact_opportunity),
    fact_opportunity[Outcome] IN {"Won", "Lost"},
    fact_opportunity[Closed Date] > StartDate,
    fact_opportunity[Closed Date] <= AsOf
)""")
add("Win Rate 12M", F1, PCT, "Of the deals that closed in the last 12 months, the share that were won.",
    "DIVIDE([Won Deals 12M], [Closed Deals 12M])")
add("Avg Sales Cycle Days", F1, "#,0", "Average number of days from deal creation to close, for deals won in the last 12 months.", """
VAR AsOf = [As Of Date]
VAR StartDate = EDATE(AsOf, -12)
RETURN
CALCULATE(
    AVERAGE(fact_opportunity[Sales Cycle Days]),
    fact_opportunity[Outcome] = "Won",
    fact_opportunity[Closed Date] > StartDate,
    fact_opportunity[Closed Date] <= AsOf
)""")
add("Pipeline Velocity per Day", F1, USD, "Dollars of new business the pipeline is expected to produce per day: open deals x average deal size x win rate / sales cycle days.",
    "DIVIDE([Open Deals] * [Avg Open Deal Size] * [Win Rate 12M], [Avg Sales Cycle Days])")
add("Weighted Pipeline Flat", F1, USD, "Open pipeline multiplied by the overall 12-month win rate (every deal gets the same probability).",
    "[Open Pipeline] * [Win Rate 12M]")
add("Weighted Pipeline Model", F1, USD, "Open pipeline where each deal is multiplied by the deal-win model's own probability for that deal.", """
SUMX(
    FILTER(fact_opportunity, fact_opportunity[Outcome] = "Open"),
    fact_opportunity[Deal Size] * fact_opportunity[Model Win Probability]
)""")
add("Stalled Pipeline", F1, USD, "Value of open deals that have sat in their current stage longer than 75% of comparable deals did.",
    'CALCULATE(SUM(fact_opportunity[Deal Size]), fact_opportunity[Outcome] = "Open", fact_opportunity[Is Stalled] = 1)')
add("Stalled Deals", F1, INT, "Number of stalled open deals.",
    'CALCULATE(COUNTROWS(fact_opportunity), fact_opportunity[Outcome] = "Open", fact_opportunity[Is Stalled] = 1)')
add("On Track Pipeline", F1, USD, "Open pipeline that is not stalled.", "[Open Pipeline] - COALESCE([Stalled Pipeline], 0)")
add("Stalled Share", F1, PCT, "Stalled pipeline as a share of open pipeline.", "DIVIDE(COALESCE([Stalled Pipeline], 0), [Open Pipeline])")
add("Win Rate All Closed", F1, PCT, "Win rate across all deals ever closed in the current filter (used for rep and competitor comparisons).", """
DIVIDE(
    CALCULATE(COUNTROWS(fact_opportunity), fact_opportunity[Outcome] = "Won"),
    CALCULATE(COUNTROWS(fact_opportunity), fact_opportunity[Outcome] IN {"Won", "Lost"})
)""")
add("Closed Deals All", F1, INT, "Number of deals ever closed (won or lost) in the current filter.",
    'CALCULATE(COUNTROWS(fact_opportunity), fact_opportunity[Outcome] IN {"Won", "Lost"})')
add("Avg Won Deal Size", F1, USD, "Average value of won deals.", 'CALCULATE(AVERAGE(fact_opportunity[Deal Size]), fact_opportunity[Outcome] = "Won")')
add("New ARR Booked", F1, USD, "New annual recurring revenue from customers who signed in the period.", "SUM(fact_arr_monthly[New ARR])")
add("Deal Model Probability", F1, PCT, "The model's win probability for the deal(s) in the current row.", "AVERAGE(fact_opportunity[Model Win Probability])")
add("Deal Rep Forecast", F1, "0\\%", "The sales rep's own win-probability forecast for the deal(s) in the current row.", "AVERAGE(fact_opportunity[Rep Forecast Pct])")
add("Deal Days in Stage", F1, "#,0", "Days the deal has been in its current stage.", "AVERAGE(fact_opportunity[Days in Stage])")
add("Deal Value", F1, USD, "Value of the deal(s) in the current row.", "SUM(fact_opportunity[Deal Size])")

# ---------------------------------------------------------------- funnel
add("Leads", F2, INT, "Number of leads created.", "COUNTROWS(fact_lead)")
add("Opportunities", F2, INT, "Leads that became a sales opportunity.", "SUM(fact_lead[Became Opportunity])")
add("Reached Discovery", F2, INT, "Leads whose deal reached the Discovery stage or later.", "SUM(fact_lead[Reached Discovery])")
add("Reached Proposal", F2, INT, "Leads whose deal reached the Proposal stage or later.", "SUM(fact_lead[Reached Proposal])")
add("Reached Negotiation", F2, INT, "Leads whose deal reached the Negotiation stage or later.", "SUM(fact_lead[Reached Negotiation])")
add("Closed Won Leads", F2, INT, "Leads whose deal was won.", "SUM(fact_lead[Closed Won])")
add("Funnel Value", F2, INT, "Picks the right count for each funnel step (the funnel chart uses the ref_funnel table as its categories).", """
SWITCH(
    SELECTEDVALUE(ref_funnel[Step]),
    "Leads", [Leads],
    "Became an opportunity", [Opportunities],
    "Reached Discovery", [Reached Discovery],
    "Reached Proposal", [Reached Proposal],
    "Reached Negotiation", [Reached Negotiation],
    "Closed won", [Closed Won Leads]
)""")
add("Lead to Opportunity Rate", F2, PCT, "Share of leads that became an opportunity.", "DIVIDE([Opportunities], [Leads])")
add("Lead to Won Rate", F2, "0.0%", "Share of leads that ended as a won deal.", "DIVIDE([Closed Won Leads], [Leads])")
add("Conversion by Score Band", F2, PCT, "Share of leads in each lead-score band that became opportunities (out-of-time test, fixed numbers).",
    "AVERAGE(ref_lead_bands[Conversion Rate])")

# ---------------------------------------------------------------- revenue and retention
add("ARR", F3, USD, "Annual recurring revenue at the end of the period shown (for a single month, that month's end; for a card, the latest month).",
    f"CALCULATE(SUM(fact_arr_monthly[ARR End]), {LASTD})")
add("Customers", F3, INT, "Number of customers with revenue at the end of the period shown.",
    f"CALCULATE(DISTINCTCOUNT(fact_arr_monthly[Account ID]), fact_arr_monthly[ARR End] > 0, {LASTD})")
add("ARR 12M Ago", F3, USD, "ARR at the same date one year before the reporting date.", """
VAR AsOf = [As Of Date]
VAR StartDate = EOMONTH(AsOf, -12)
RETURN
CALCULATE(SUM(fact_arr_monthly[ARR End]), REMOVEFILTERS(dim_date), dim_date[Date] = StartDate)""")
for nm, col, mean in [("New ARR 12M", "New ARR", "ARR added by new customers in the last 12 months."),
                      ("Expansion ARR 12M", "Expansion ARR", "ARR added by existing customers (extra seats, upgrades, add-ons) in the last 12 months."),
                      ("Contraction ARR 12M", "Contraction ARR", "ARR lost to existing customers downgrading in the last 12 months (shown as a negative number)."),
                      ("Churned ARR 12M", "Churn ARR", "ARR lost to customers who cancelled in the last 12 months (shown as a negative number).")]:
    add(nm, F3, USD, mean, f"""
VAR AsOf = [As Of Date]
VAR StartDate = EOMONTH(AsOf, -12)
RETURN
CALCULATE(SUM(fact_arr_monthly[{col}]), REMOVEFILTERS(dim_date), dim_date[Date] > StartDate, dim_date[Date] <= AsOf)""")
add("Bridge Value", F3, USD, "Feeds the ARR bridge (waterfall) chart: returns the right amount for each bridge step.", """
SWITCH(
    SELECTEDVALUE(ref_bridge[Step]),
    "Starting ARR (12 months ago)", [ARR 12M Ago],
    "New customers", [New ARR 12M],
    "Expansion", [Expansion ARR 12M],
    "Contraction", [Contraction ARR 12M],
    "Churn", [Churned ARR 12M]
)""")
_COH = """
VAR AsOf = [As Of Date]
VAR StartDate = EOMONTH(AsOf, -12)
VAR Tbl =
    ADDCOLUMNS(
        VALUES(dim_account[Account ID]),
        "@Start", CALCULATE(SUM(fact_arr_monthly[ARR End]), REMOVEFILTERS(dim_date), dim_date[Date] = StartDate),
        "@Now",   CALCULATE(SUM(fact_arr_monthly[ARR End]), REMOVEFILTERS(dim_date), dim_date[Date] = AsOf)
    )
VAR Cohort = FILTER(Tbl, [@Start] > 0)
RETURN
"""
add("Net Revenue Retention 12M", F3, PCT, "Of the revenue we had from customers 12 months ago, how much do those same customers pay now (includes upgrades, downgrades and cancellations)? Above 100% means growth from existing customers.",
    _COH + "DIVIDE(SUMX(Cohort, [@Now]), SUMX(Cohort, [@Start]))")
add("Gross Revenue Retention 12M", F3, PCT, "Same cohort, but upgrades are ignored: how much of the old revenue did we keep? Can never exceed 100%.",
    _COH + "DIVIDE(SUMX(Cohort, MIN([@Now], [@Start])), SUMX(Cohort, [@Start]))")
add("Logo Retention 12M", F3, PCT, "Of the customers we had 12 months ago, the share still customers today.",
    _COH + "DIVIDE(COUNTROWS(FILTER(Cohort, [@Now] > 0)), COUNTROWS(Cohort))")
add("ARR Growth 12M", F3, PCT, "Change in ARR compared with 12 months ago.", "DIVIDE([ARR] - [ARR 12M Ago], [ARR 12M Ago])")

# ---------------------------------------------------------------- risk and growth
add("Expected ARR Loss 90D", F4, USD, "Sum over customers of (probability of cancelling in the next 90 days x that customer's ARR). The model's estimate of revenue likely to leave.",
    "SUM(fact_account_health[Expected ARR Loss])")
add("Expected Expansion 90D", F4, USD, "Sum over customers of (probability of buying more in the next 90 days x expected extra ARR).",
    "SUM(fact_account_health[Expected Expansion ARR])")
add("Scored ARR", F4, USD, "ARR of customers the models have scored (customers need at least 3 months of history).", "SUM(fact_account_health[Scored ARR])")
add("Scored Share of ARR", F4, "0%", "Share of today's ARR that the models cover.", "DIVIDE([Scored ARR], [ARR])")
add("Scored Accounts", F4, INT, "Number of active customers the models have scored.",
    "CALCULATE(COUNTROWS(fact_account_health), fact_account_health[Is Scored] = 1)")
add("High Churn Risk Accounts", F4, INT, "Number of customers in the High churn-risk tier (at least 2x the average churn rate).",
    'CALCULATE(COUNTROWS(fact_account_health), dim_account[Churn Risk] = "High")')
add("High Churn Risk ARR", F4, USD, "ARR sitting in High churn-risk customers.",
    'CALCULATE(SUM(fact_account_health[ARR Now]), dim_account[Churn Risk] = "High")')
add("High Expansion Accounts", F4, INT, "Number of customers in the High expansion-potential tier.",
    'CALCULATE(COUNTROWS(fact_account_health), dim_account[Expansion Potential] = "High")')
add("High Expansion ARR", F4, USD, "ARR sitting in High expansion-potential customers.",
    'CALCULATE(SUM(fact_account_health[ARR Now]), dim_account[Expansion Potential] = "High")')
add("ARR Renewing Next 90D", F4, USD, "ARR on contracts that come up for renewal within the next 90 days.",
    "CALCULATE(SUM(fact_account_health[ARR Now]), fact_account_health[Renews Within 90D] = 1)")
add("Expected Loss Share of Scored ARR", F4, PCT, "Expected 90-day loss as a share of scored ARR.", "DIVIDE([Expected ARR Loss 90D], [Scored ARR])")
add("Avg Churn Probability", F4, PCT, "Average probability of cancelling in the next 90 days (for one customer: that customer's probability).",
    "AVERAGE(fact_account_health[Churn Probability])")
add("Avg Expansion Probability", F4, PCT, "Average probability of buying more in the next 90 days.", "AVERAGE(fact_account_health[Expansion Probability])")
add("Avg Months to Renewal", F4, "0.0", "Average months until the contract renews.", "AVERAGE(fact_account_health[Months to Renewal])")
add("Account ARR Now", F4, USD, "Current ARR of the customer(s) in the row.", "SUM(fact_account_health[ARR Now])")
add("Driver Impact", F4, "0.00", "How strongly one factor pushes the selected customer's score up (positive) or down (negative). Blank unless exactly one customer is selected.",
    "IF(HASONEVALUE(dim_account[Account ID]), SUM(fact_driver[Impact]), BLANK())")

# ---------------------------------------------------------------- model reliability
add("Churn Model AUC", F5, "0.00", "How well the churn model separates customers who cancel from those who stay in a forward-in-time test (0.5 = coin toss, 1.0 = perfect).",
    'CALCULATE(MAX(ref_model_scorecard[ROC AUC]), ref_model_scorecard[Model Name] = "Churn (90-day)")')
add("Expansion Model AUC", F5, "0.00", "Same measure for the expansion model.",
    'CALCULATE(MAX(ref_model_scorecard[ROC AUC]), ref_model_scorecard[Model Name] = "Expansion (90-day)")')
add("Deal Win Model AUC", F5, "0.00", "Same measure for the deal-win model.",
    'CALCULATE(MAX(ref_model_scorecard[ROC AUC]), ref_model_scorecard[Model Name] = "Deal-win")')
add("Lead Score Lift", F5, "0.0\\x", "How many times more likely the top-scored fifth of leads is to convert than the bottom-scored fifth.", """
DIVIDE(
    CALCULATE(MAX(ref_lead_bands[Conversion Rate]), ref_lead_bands[Band Order] = 1),
    CALCULATE(MAX(ref_lead_bands[Conversion Rate]), ref_lead_bands[Band Order] = 5)
)""")

# ---------------------------------------------------------------- labels and colours (text measures)
add("As Of Label", F6, "", "Text for the header: 'As of 30 Jun 2026'.", '"As of " & FORMAT([As Of Date], "dd mmm yyyy") & "  |  synthetic data"')
add("Label Open Pipeline", F6, "", "Sub-title under the Open Pipeline card.", 'FORMAT([Open Deals], "#,0") & " open deals"')
add("Label Weighted Pipeline", F6, "", "Sub-title under the Weighted Pipeline card.", '"flat win rate: " & FORMAT([Weighted Pipeline Flat] / 1000000, "$0.0") & "M"')
add("Label Win Rate", F6, "", "Sub-title under the Win Rate card.", 'FORMAT([Won Deals 12M], "#,0") & " won of " & FORMAT([Closed Deals 12M], "#,0") & " closed"')
add("Label Cycle", F6, "", "Sub-title under the Sales Cycle card.", '"won deals, last 12 months"')
add("Label Velocity", F6, "", "Sub-title under the Velocity card.", '"new ARR the pipeline should produce"')
add("Label Stalled", F6, "", "Sub-title under the Stalled card.", 'FORMAT([Stalled Share], "0%") & " of open pipeline, " & FORMAT([Stalled Deals], "#,0") & " deals"')
add("Label ARR", F6, "", "Sub-title under the ARR card.", 'FORMAT([Customers], "#,0") & " customers"')
add("Label NRR", F6, "", "Sub-title under the NRR card.", '"existing customers, 12 months"')
add("Label GRR", F6, "", "Sub-title under the GRR card.", '"before upgrades, 12 months"')
add("Label Logo", F6, "", "Sub-title under the logo retention card.", '"customers kept, 12 months"')
add("Label Expected Loss", F6, "", "Sub-title under the Expected ARR Loss card.", 'FORMAT([High Churn Risk Accounts], "#,0") & " high-risk accounts, " & FORMAT([High Churn Risk ARR] / 1000000, "$0.0") & "M ARR"')
add("Label Expected Expansion", F6, "", "Sub-title under the Expected Expansion card.", 'FORMAT([High Expansion Accounts], "#,0") & " high-potential accounts"')
add("Label Coverage", F6, "", "Footnote on how much ARR the models cover.", 'FORMAT([Scored Share of ARR], "0%") & " of ARR is scored (customers under 3 months old are not)"')
add("Reliability Pipeline", F6, "", "Header note on page 1: how much to trust the model scores.",
    '"Model check (tested on future data): deal-win AUC " & FORMAT([Deal Win Model AUC], "0.00") & "  |  top lead band converts " & FORMAT([Lead Score Lift], "0.0") & "x the bottom band"')
add("Reliability Customers", F6, "", "Header note on page 2: how much to trust the model scores.",
    '"Model check (tested on future data): churn AUC " & FORMAT([Churn Model AUC], "0.00") & "  |  expansion AUC " & FORMAT([Expansion Model AUC], "0.00")')
add("Driver Hint", F6, "", "Sub-title for the driver charts: tells the viewer to select a customer, or names the selected one.",
    'IF(HASONEVALUE(dim_account[Account ID]), "Drivers for " & SELECTEDVALUE(dim_account[Customer]), "Click a customer in the table")')
add("Churn Risk Color", F6, "", "Hex colour for the churn-risk text in the table (red / amber / green).", """
SWITCH(
    SELECTEDVALUE(dim_account[Churn Risk]),
    "High", "#D03B3B",
    "Medium", "#C98500",
    "Low", "#0A8A0A",
    "#898781"
)""")
