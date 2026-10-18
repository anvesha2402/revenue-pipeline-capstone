# All DAX measures (plain copy version)

Use this only if the TMDL paste method does not work. For each measure: select the `_Measures` table, then **Home > New measure**, paste the line(s) below as is, press Enter. Then, with the measure selected, set the Format on the **Measure tools** ribbon as shown.


## 0 Helpers

### As Of Date
The reporting date: the latest date in the date table (30 Jun 2026). Every 'last 12 months' measure counts back from it.

Format: `dd mmm yyyy`

```dax
As Of Date =
CALCULATE(MAX(dim_date[Date]), REMOVEFILTERS(dim_date))
```


## 1 Pipeline

### Open Pipeline
Total value of deals that are still open (not yet won or lost).

Format: `\$#,0`

```dax
Open Pipeline =
CALCULATE(SUM(fact_opportunity[Deal Size]), fact_opportunity[Outcome] = "Open")
```

### Open Deals
Number of deals that are still open.

Format: `#,0`

```dax
Open Deals =
CALCULATE(COUNTROWS(fact_opportunity), fact_opportunity[Outcome] = "Open")
```

### Avg Open Deal Size
Average value of an open deal.

Format: `\$#,0`

```dax
Avg Open Deal Size =
DIVIDE([Open Pipeline], [Open Deals])
```

### Won Deals 12M
Deals won in the 12 months up to the reporting date.

Format: `#,0`

```dax
Won Deals 12M =
VAR AsOf = [As Of Date]
VAR StartDate = EDATE(AsOf, -12)
RETURN
CALCULATE(
    COUNTROWS(fact_opportunity),
    fact_opportunity[Outcome] = "Won",
    fact_opportunity[Closed Date] > StartDate,
    fact_opportunity[Closed Date] <= AsOf
)
```

### Closed Deals 12M
Deals won or lost in the 12 months up to the reporting date.

Format: `#,0`

```dax
Closed Deals 12M =
VAR AsOf = [As Of Date]
VAR StartDate = EDATE(AsOf, -12)
RETURN
CALCULATE(
    COUNTROWS(fact_opportunity),
    fact_opportunity[Outcome] IN {"Won", "Lost"},
    fact_opportunity[Closed Date] > StartDate,
    fact_opportunity[Closed Date] <= AsOf
)
```

### Win Rate 12M
Of the deals that closed in the last 12 months, the share that were won.

Format: `0.0%`

```dax
Win Rate 12M =
DIVIDE([Won Deals 12M], [Closed Deals 12M])
```

### Avg Sales Cycle Days
Average number of days from deal creation to close, for deals won in the last 12 months.

Format: `#,0`

```dax
Avg Sales Cycle Days =
VAR AsOf = [As Of Date]
VAR StartDate = EDATE(AsOf, -12)
RETURN
CALCULATE(
    AVERAGE(fact_opportunity[Sales Cycle Days]),
    fact_opportunity[Outcome] = "Won",
    fact_opportunity[Closed Date] > StartDate,
    fact_opportunity[Closed Date] <= AsOf
)
```

### Pipeline Velocity per Day
Dollars of new business the pipeline is expected to produce per day: open deals x average deal size x win rate / sales cycle days.

Format: `\$#,0`

```dax
Pipeline Velocity per Day =
DIVIDE([Open Deals] * [Avg Open Deal Size] * [Win Rate 12M], [Avg Sales Cycle Days])
```

### Weighted Pipeline Flat
Open pipeline multiplied by the overall 12-month win rate (every deal gets the same probability).

Format: `\$#,0`

```dax
Weighted Pipeline Flat =
[Open Pipeline] * [Win Rate 12M]
```

### Weighted Pipeline Model
Open pipeline where each deal is multiplied by the deal-win model's own probability for that deal.

Format: `\$#,0`

```dax
Weighted Pipeline Model =
SUMX(
    FILTER(fact_opportunity, fact_opportunity[Outcome] = "Open"),
    fact_opportunity[Deal Size] * fact_opportunity[Model Win Probability]
)
```

### Stalled Pipeline
Value of open deals that have sat in their current stage longer than 75% of comparable deals did.

Format: `\$#,0`

```dax
Stalled Pipeline =
CALCULATE(SUM(fact_opportunity[Deal Size]), fact_opportunity[Outcome] = "Open", fact_opportunity[Is Stalled] = 1)
```

### Stalled Deals
Number of stalled open deals.

Format: `#,0`

```dax
Stalled Deals =
CALCULATE(COUNTROWS(fact_opportunity), fact_opportunity[Outcome] = "Open", fact_opportunity[Is Stalled] = 1)
```

### On Track Pipeline
Open pipeline that is not stalled.

Format: `\$#,0`

```dax
On Track Pipeline =
[Open Pipeline] - COALESCE([Stalled Pipeline], 0)
```

### Stalled Share
Stalled pipeline as a share of open pipeline.

Format: `0.0%`

```dax
Stalled Share =
DIVIDE(COALESCE([Stalled Pipeline], 0), [Open Pipeline])
```

### Win Rate All Closed
Win rate across all deals ever closed in the current filter (used for rep and competitor comparisons).

Format: `0.0%`

```dax
Win Rate All Closed =
DIVIDE(
    CALCULATE(COUNTROWS(fact_opportunity), fact_opportunity[Outcome] = "Won"),
    CALCULATE(COUNTROWS(fact_opportunity), fact_opportunity[Outcome] IN {"Won", "Lost"})
)
```

### Closed Deals All
Number of deals ever closed (won or lost) in the current filter.

Format: `#,0`

```dax
Closed Deals All =
CALCULATE(COUNTROWS(fact_opportunity), fact_opportunity[Outcome] IN {"Won", "Lost"})
```

### Avg Won Deal Size
Average value of won deals.

Format: `\$#,0`

```dax
Avg Won Deal Size =
CALCULATE(AVERAGE(fact_opportunity[Deal Size]), fact_opportunity[Outcome] = "Won")
```

### New ARR Booked
New annual recurring revenue from customers who signed in the period.

Format: `\$#,0`

```dax
New ARR Booked =
SUM(fact_arr_monthly[New ARR])
```

### Deal Model Probability
The model's win probability for the deal(s) in the current row.

Format: `0.0%`

```dax
Deal Model Probability =
AVERAGE(fact_opportunity[Model Win Probability])
```

### Deal Rep Forecast
The sales rep's own win-probability forecast for the deal(s) in the current row.

Format: `0\%`

```dax
Deal Rep Forecast =
AVERAGE(fact_opportunity[Rep Forecast Pct])
```

### Deal Days in Stage
Days the deal has been in its current stage.

Format: `#,0`

```dax
Deal Days in Stage =
AVERAGE(fact_opportunity[Days in Stage])
```

### Deal Value
Value of the deal(s) in the current row.

Format: `\$#,0`

```dax
Deal Value =
SUM(fact_opportunity[Deal Size])
```


## 2 Funnel

### Leads
Number of leads created.

Format: `#,0`

```dax
Leads =
COUNTROWS(fact_lead)
```

### Opportunities
Leads that became a sales opportunity.

Format: `#,0`

```dax
Opportunities =
SUM(fact_lead[Became Opportunity])
```

### Reached Discovery
Leads whose deal reached the Discovery stage or later.

Format: `#,0`

```dax
Reached Discovery =
SUM(fact_lead[Reached Discovery])
```

### Reached Proposal
Leads whose deal reached the Proposal stage or later.

Format: `#,0`

```dax
Reached Proposal =
SUM(fact_lead[Reached Proposal])
```

### Reached Negotiation
Leads whose deal reached the Negotiation stage or later.

Format: `#,0`

```dax
Reached Negotiation =
SUM(fact_lead[Reached Negotiation])
```

### Closed Won Leads
Leads whose deal was won.

Format: `#,0`

```dax
Closed Won Leads =
SUM(fact_lead[Closed Won])
```

### Funnel Value
Picks the right count for each funnel step (the funnel chart uses the ref_funnel table as its categories).

Format: `#,0`

```dax
Funnel Value =
SWITCH(
    SELECTEDVALUE(ref_funnel[Step]),
    "Leads", [Leads],
    "Became an opportunity", [Opportunities],
    "Reached Discovery", [Reached Discovery],
    "Reached Proposal", [Reached Proposal],
    "Reached Negotiation", [Reached Negotiation],
    "Closed won", [Closed Won Leads]
)
```

### Lead to Opportunity Rate
Share of leads that became an opportunity.

Format: `0.0%`

```dax
Lead to Opportunity Rate =
DIVIDE([Opportunities], [Leads])
```

### Lead to Won Rate
Share of leads that ended as a won deal.

Format: `0.0%`

```dax
Lead to Won Rate =
DIVIDE([Closed Won Leads], [Leads])
```

### Conversion by Score Band
Share of leads in each lead-score band that became opportunities (out-of-time test, fixed numbers).

Format: `0.0%`

```dax
Conversion by Score Band =
AVERAGE(ref_lead_bands[Conversion Rate])
```


## 3 Revenue and retention

### ARR
Annual recurring revenue at the end of the period shown (for a single month, that month's end; for a card, the latest month).

Format: `\$#,0`

```dax
ARR =
CALCULATE(SUM(fact_arr_monthly[ARR End]), LASTNONBLANK(dim_date[Date], CALCULATE(COUNTROWS(fact_arr_monthly))))
```

### Customers
Number of customers with revenue at the end of the period shown.

Format: `#,0`

```dax
Customers =
CALCULATE(DISTINCTCOUNT(fact_arr_monthly[Account ID]), fact_arr_monthly[ARR End] > 0, LASTNONBLANK(dim_date[Date], CALCULATE(COUNTROWS(fact_arr_monthly))))
```

### ARR 12M Ago
ARR at the same date one year before the reporting date.

Format: `\$#,0`

```dax
ARR 12M Ago =
VAR AsOf = [As Of Date]
VAR StartDate = EOMONTH(AsOf, -12)
RETURN
CALCULATE(SUM(fact_arr_monthly[ARR End]), REMOVEFILTERS(dim_date), dim_date[Date] = StartDate)
```

### New ARR 12M
ARR added by new customers in the last 12 months.

Format: `\$#,0`

```dax
New ARR 12M =
VAR AsOf = [As Of Date]
VAR StartDate = EOMONTH(AsOf, -12)
RETURN
CALCULATE(SUM(fact_arr_monthly[New ARR]), REMOVEFILTERS(dim_date), dim_date[Date] > StartDate, dim_date[Date] <= AsOf)
```

### Expansion ARR 12M
ARR added by existing customers (extra seats, upgrades, add-ons) in the last 12 months.

Format: `\$#,0`

```dax
Expansion ARR 12M =
VAR AsOf = [As Of Date]
VAR StartDate = EOMONTH(AsOf, -12)
RETURN
CALCULATE(SUM(fact_arr_monthly[Expansion ARR]), REMOVEFILTERS(dim_date), dim_date[Date] > StartDate, dim_date[Date] <= AsOf)
```

### Contraction ARR 12M
ARR lost to existing customers downgrading in the last 12 months (shown as a negative number).

Format: `\$#,0`

```dax
Contraction ARR 12M =
VAR AsOf = [As Of Date]
VAR StartDate = EOMONTH(AsOf, -12)
RETURN
CALCULATE(SUM(fact_arr_monthly[Contraction ARR]), REMOVEFILTERS(dim_date), dim_date[Date] > StartDate, dim_date[Date] <= AsOf)
```

### Churned ARR 12M
ARR lost to customers who cancelled in the last 12 months (shown as a negative number).

Format: `\$#,0`

```dax
Churned ARR 12M =
VAR AsOf = [As Of Date]
VAR StartDate = EOMONTH(AsOf, -12)
RETURN
CALCULATE(SUM(fact_arr_monthly[Churn ARR]), REMOVEFILTERS(dim_date), dim_date[Date] > StartDate, dim_date[Date] <= AsOf)
```

### Bridge Value
Feeds the ARR bridge (waterfall) chart: returns the right amount for each bridge step.

Format: `\$#,0`

```dax
Bridge Value =
SWITCH(
    SELECTEDVALUE(ref_bridge[Step]),
    "Starting ARR (12 months ago)", [ARR 12M Ago],
    "New customers", [New ARR 12M],
    "Expansion", [Expansion ARR 12M],
    "Contraction", [Contraction ARR 12M],
    "Churn", [Churned ARR 12M]
)
```

### Net Revenue Retention 12M
Of the revenue we had from customers 12 months ago, how much do those same customers pay now (includes upgrades, downgrades and cancellations)? Above 100% means growth from existing customers.

Format: `0.0%`

```dax
Net Revenue Retention 12M =
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
DIVIDE(SUMX(Cohort, [@Now]), SUMX(Cohort, [@Start]))
```

### Gross Revenue Retention 12M
Same cohort, but upgrades are ignored: how much of the old revenue did we keep? Can never exceed 100%.

Format: `0.0%`

```dax
Gross Revenue Retention 12M =
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
DIVIDE(SUMX(Cohort, MIN([@Now], [@Start])), SUMX(Cohort, [@Start]))
```

### Logo Retention 12M
Of the customers we had 12 months ago, the share still customers today.

Format: `0.0%`

```dax
Logo Retention 12M =
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
DIVIDE(COUNTROWS(FILTER(Cohort, [@Now] > 0)), COUNTROWS(Cohort))
```

### ARR Growth 12M
Change in ARR compared with 12 months ago.

Format: `0.0%`

```dax
ARR Growth 12M =
DIVIDE([ARR] - [ARR 12M Ago], [ARR 12M Ago])
```


## 4 Risk and growth

### Expected ARR Loss 90D
Sum over customers of (probability of cancelling in the next 90 days x that customer's ARR). The model's estimate of revenue likely to leave.

Format: `\$#,0`

```dax
Expected ARR Loss 90D =
SUM(fact_account_health[Expected ARR Loss])
```

### Expected Expansion 90D
Sum over customers of (probability of buying more in the next 90 days x expected extra ARR).

Format: `\$#,0`

```dax
Expected Expansion 90D =
SUM(fact_account_health[Expected Expansion ARR])
```

### Scored ARR
ARR of customers the models have scored (customers need at least 3 months of history).

Format: `\$#,0`

```dax
Scored ARR =
SUM(fact_account_health[Scored ARR])
```

### Scored Share of ARR
Share of today's ARR that the models cover.

Format: `0%`

```dax
Scored Share of ARR =
DIVIDE([Scored ARR], [ARR])
```

### Scored Accounts
Number of active customers the models have scored.

Format: `#,0`

```dax
Scored Accounts =
CALCULATE(COUNTROWS(fact_account_health), fact_account_health[Is Scored] = 1)
```

### High Churn Risk Accounts
Number of customers in the High churn-risk tier (at least 2x the average churn rate).

Format: `#,0`

```dax
High Churn Risk Accounts =
CALCULATE(COUNTROWS(fact_account_health), dim_account[Churn Risk] = "High")
```

### High Churn Risk ARR
ARR sitting in High churn-risk customers.

Format: `\$#,0`

```dax
High Churn Risk ARR =
CALCULATE(SUM(fact_account_health[ARR Now]), dim_account[Churn Risk] = "High")
```

### High Expansion Accounts
Number of customers in the High expansion-potential tier.

Format: `#,0`

```dax
High Expansion Accounts =
CALCULATE(COUNTROWS(fact_account_health), dim_account[Expansion Potential] = "High")
```

### High Expansion ARR
ARR sitting in High expansion-potential customers.

Format: `\$#,0`

```dax
High Expansion ARR =
CALCULATE(SUM(fact_account_health[ARR Now]), dim_account[Expansion Potential] = "High")
```

### ARR Renewing Next 90D
ARR on contracts that come up for renewal within the next 90 days.

Format: `\$#,0`

```dax
ARR Renewing Next 90D =
CALCULATE(SUM(fact_account_health[ARR Now]), fact_account_health[Renews Within 90D] = 1)
```

### Expected Loss Share of Scored ARR
Expected 90-day loss as a share of scored ARR.

Format: `0.0%`

```dax
Expected Loss Share of Scored ARR =
DIVIDE([Expected ARR Loss 90D], [Scored ARR])
```

### Avg Churn Probability
Average probability of cancelling in the next 90 days (for one customer: that customer's probability).

Format: `0.0%`

```dax
Avg Churn Probability =
AVERAGE(fact_account_health[Churn Probability])
```

### Avg Expansion Probability
Average probability of buying more in the next 90 days.

Format: `0.0%`

```dax
Avg Expansion Probability =
AVERAGE(fact_account_health[Expansion Probability])
```

### Avg Months to Renewal
Average months until the contract renews.

Format: `0.0`

```dax
Avg Months to Renewal =
AVERAGE(fact_account_health[Months to Renewal])
```

### Account ARR Now
Current ARR of the customer(s) in the row.

Format: `\$#,0`

```dax
Account ARR Now =
SUM(fact_account_health[ARR Now])
```

### Driver Impact
How strongly one factor pushes the selected customer's score up (positive) or down (negative). Blank unless exactly one customer is selected.

Format: `0.00`

```dax
Driver Impact =
IF(HASONEVALUE(dim_account[Account ID]), SUM(fact_driver[Impact]), BLANK())
```


## 5 Model reliability

### Churn Model AUC
How well the churn model separates customers who cancel from those who stay in a forward-in-time test (0.5 = coin toss, 1.0 = perfect).

Format: `0.00`

```dax
Churn Model AUC =
CALCULATE(MAX(ref_model_scorecard[ROC AUC]), ref_model_scorecard[Model Name] = "Churn (90-day)")
```

### Expansion Model AUC
Same measure for the expansion model.

Format: `0.00`

```dax
Expansion Model AUC =
CALCULATE(MAX(ref_model_scorecard[ROC AUC]), ref_model_scorecard[Model Name] = "Expansion (90-day)")
```

### Deal Win Model AUC
Same measure for the deal-win model.

Format: `0.00`

```dax
Deal Win Model AUC =
CALCULATE(MAX(ref_model_scorecard[ROC AUC]), ref_model_scorecard[Model Name] = "Deal-win")
```

### Lead Score Lift
How many times more likely the top-scored fifth of leads is to convert than the bottom-scored fifth.

Format: `0.0\x`

```dax
Lead Score Lift =
DIVIDE(
    CALCULATE(MAX(ref_lead_bands[Conversion Rate]), ref_lead_bands[Band Order] = 1),
    CALCULATE(MAX(ref_lead_bands[Conversion Rate]), ref_lead_bands[Band Order] = 5)
)
```


## 6 Labels and colours

### As Of Label
Text for the header: 'As of 30 Jun 2026'.

Format: `text (no format needed)`

```dax
As Of Label =
"As of " & FORMAT([As Of Date], "dd mmm yyyy") & "  |  synthetic data"
```

### Label Open Pipeline
Sub-title under the Open Pipeline card.

Format: `text (no format needed)`

```dax
Label Open Pipeline =
FORMAT([Open Deals], "#,0") & " open deals"
```

### Label Weighted Pipeline
Sub-title under the Weighted Pipeline card.

Format: `text (no format needed)`

```dax
Label Weighted Pipeline =
"flat win rate: " & FORMAT([Weighted Pipeline Flat] / 1000000, "$0.0") & "M"
```

### Label Win Rate
Sub-title under the Win Rate card.

Format: `text (no format needed)`

```dax
Label Win Rate =
FORMAT([Won Deals 12M], "#,0") & " won of " & FORMAT([Closed Deals 12M], "#,0") & " closed"
```

### Label Cycle
Sub-title under the Sales Cycle card.

Format: `text (no format needed)`

```dax
Label Cycle =
"won deals, last 12 months"
```

### Label Velocity
Sub-title under the Velocity card.

Format: `text (no format needed)`

```dax
Label Velocity =
"new ARR the pipeline should produce"
```

### Label Stalled
Sub-title under the Stalled card.

Format: `text (no format needed)`

```dax
Label Stalled =
FORMAT([Stalled Share], "0%") & " of open pipeline, " & FORMAT([Stalled Deals], "#,0") & " deals"
```

### Label ARR
Sub-title under the ARR card.

Format: `text (no format needed)`

```dax
Label ARR =
FORMAT([Customers], "#,0") & " customers"
```

### Label NRR
Sub-title under the NRR card.

Format: `text (no format needed)`

```dax
Label NRR =
"existing customers, 12 months"
```

### Label GRR
Sub-title under the GRR card.

Format: `text (no format needed)`

```dax
Label GRR =
"before upgrades, 12 months"
```

### Label Logo
Sub-title under the logo retention card.

Format: `text (no format needed)`

```dax
Label Logo =
"customers kept, 12 months"
```

### Label Expected Loss
Sub-title under the Expected ARR Loss card.

Format: `text (no format needed)`

```dax
Label Expected Loss =
FORMAT([High Churn Risk Accounts], "#,0") & " high-risk accounts, " & FORMAT([High Churn Risk ARR] / 1000000, "$0.0") & "M ARR"
```

### Label Expected Expansion
Sub-title under the Expected Expansion card.

Format: `text (no format needed)`

```dax
Label Expected Expansion =
FORMAT([High Expansion Accounts], "#,0") & " high-potential accounts"
```

### Label Coverage
Footnote on how much ARR the models cover.

Format: `text (no format needed)`

```dax
Label Coverage =
FORMAT([Scored Share of ARR], "0%") & " of ARR is scored (customers under 3 months old are not)"
```

### Reliability Pipeline
Header note on page 1: how much to trust the model scores.

Format: `text (no format needed)`

```dax
Reliability Pipeline =
"Model check (tested on future data): deal-win AUC " & FORMAT([Deal Win Model AUC], "0.00") & "  |  top lead band converts " & FORMAT([Lead Score Lift], "0.0") & "x the bottom band"
```

### Reliability Customers
Header note on page 2: how much to trust the model scores.

Format: `text (no format needed)`

```dax
Reliability Customers =
"Model check (tested on future data): churn AUC " & FORMAT([Churn Model AUC], "0.00") & "  |  expansion AUC " & FORMAT([Expansion Model AUC], "0.00")
```

### Driver Hint
Sub-title for the driver charts: tells the viewer to select a customer, or names the selected one.

Format: `text (no format needed)`

```dax
Driver Hint =
IF(HASONEVALUE(dim_account[Account ID]), "Drivers for " & SELECTEDVALUE(dim_account[Customer]), "Click a customer in the table")
```

### Churn Risk Color
Hex colour for the churn-risk text in the table (red / amber / green).

Format: `text (no format needed)`

```dax
Churn Risk Color =
SWITCH(
    SELECTEDVALUE(dim_account[Churn Risk]),
    "High", "#D03B3B",
    "Medium", "#C98500",
    "Low", "#0A8A0A",
    "#898781"
)
```
