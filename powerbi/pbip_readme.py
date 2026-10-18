"""Writes README_FIRST.md inside the project folder. Numbers are read from validation/expected_values.csv (computed independently in pandas)."""
import csv, os

def expected(here):
    rows = list(csv.reader(open(os.path.join(here, "validation", "expected_values.csv"), encoding="utf-8")))
    hdr = rows[0]
    return {r[0]: dict(zip(hdr[1:], map(float, r[1:]))) for r in rows[1:]}

def usd_m(x): return f"${x/1e6:,.1f}M"
def pct(x): return f"{x*100:,.1f}%"

def text(here):
    E = expected(here)
    n = lambda m, c="No filters": E[m][c]
    P1 = [("Open pipeline", usd_m(n("Open Pipeline"))), ("Weighted pipeline", usd_m(n("Weighted Pipeline Model"))), ("Win rate (12 months)", pct(n("Win Rate 12M"))),
          ("Sales cycle (days)", f"{n('Avg Sales Cycle Days'):,.0f}"), ("Velocity ($ per day)", f"${n('Pipeline Velocity per Day')/1e3:,.0f}K"),
          ("Stalled pipeline", usd_m(n("Stalled Pipeline")))]
    P2 = [("Active ARR", usd_m(n("ARR"))), ("Net revenue retention", pct(n("Net Revenue Retention 12M"))), ("Gross revenue retention", pct(n("Gross Revenue Retention 12M"))),
          ("Customer (logo) retention", pct(n("Logo Retention 12M"))), ("Expected ARR loss (90 days)", usd_m(n("Expected ARR Loss 90D"))),
          ("Expected expansion (90 days)", usd_m(n("Expected Expansion 90D")))]
    tbl = lambda rows: "\n".join(f"| {a} | {b} |" for a, b in rows)
    emea = usd_m(E["Open Pipeline"]["Region = EMEA"])
    return f"""# Revenue Pipeline: Power BI Project

This folder is a complete Power BI Project: the data model, the relationships, all 83 measures, two report pages and every visual on them. It opens in **Power BI Desktop for Windows** (free). All data is synthetic.

## Open it

1. **Unzip so the folder is `C:\\Revenue_Pipeline_Power_BI\\`.** The data path inside the project points to `C:\\Revenue_Pipeline_Power_BI\\data\\`. If you unzip somewhere else, do step 4.
2. **Double-click `Revenue_Pipeline.pbip`.** Power BI Desktop opens the report. If it says a preview feature is needed: *File > Options and settings > Options > Preview features*, tick **Power BI Project (.pbip) save option**, **Store semantic model using TMDL format** and **Store reports using enhanced metadata format (PBIR)**, click OK, close Power BI, and open the file again.
3. **Click Home > Refresh.** A project stores the design, not the data, so every visual is empty until the first refresh. It loads 15 tables and takes about a minute.
4. **If Refresh says it cannot find a file:** *Home > Transform data > Edit parameters*, type the path of the `data` folder into `FolderPath` (it must end with a backslash, for example `D:\\Projects\\Revenue_Pipeline_Power_BI\\data\\`), click OK, then Refresh.
5. **Save a copy as a normal report file** if you want one: *File > Save as*, and choose `.pbix`.

## What you should see after Refresh (no slicer selected)

Page 1, Pipeline

| Card | Value |
|---|---|
{tbl(P1)}

Page 2, Customers

| Card | Value |
|---|---|
{tbl(P2)}

More checks: table of stalled deals starts with O007235 (Discovery, R01, $371,200); table of customers starts with Love, King and Anderson (A01270), expected loss $36,699. Choose Region = EMEA in the slicer: open pipeline becomes {emea}. The full list of expected values for every measure, with four filter settings, is in `validation/expected_values.csv`. A query that prints the same measures from inside your model is in `validation/check_measures.dax`.

## Please check these in the first 30 minutes

I generated these files from Microsoft's published file formats and checked all of them against the official schemas, and I cross-checked every field and measure reference by script. I could not open Power BI Desktop, so these are the things only Desktop can confirm. For each one that is wrong, tell me what you see and I will fix the generator.

1. **Any visual showing an error icon.** Hover over it to read the message; it names the field or measure that failed.
2. **Page navigator** (top centre): the current page should be white with dark text, the other page blue. If both look the same, select the navigator, *Format > Visual > Pages*, and set the selected colour by hand.
3. **Reset filters button** (top right): select Region = EMEA, then click it. The slicer should clear. In Desktop, hold Ctrl while you click a button to run it.
4. **Slicers Region and Industry** are linked across the two pages. Pick a region on page 1, switch to page 2: it should still be selected.
5. **Two tables show ten rows each** (stalled deals; customers to act on first). If one shows fewer, the Top N filter is not working: select the table, open the Filters pane, and re-apply Top 10 by the same measure.
6. **Customers table:** orange data bars on Expected loss, pink shading on Churn prob., coloured Churn risk text. Click a customer row: the two charts on the right fill with reasons, and the KPI cards stay the same. Click the row again to clear it.
7. **ARR bridge** (waterfall): five movement bars and a final Total bar. Start bar may show in the green "increase" colour; that is how the waterfall works.
8. **Backgrounds:** the white card panels in the background image should line up with the visuals. If they are a few pixels off, the image is stretched: *Format page > Canvas background > Image fit* should be **Fit**.
9. **Fonts:** the report uses Segoe UI, which comes with Windows. Another system will substitute a similar font.

## If it does not open

Power BI names the file it could not read. Send me the exact message. You are not stuck: `POWER_BI_BUILD_GUIDE.md` (in the main download) builds the same report by hand from the same CSV files, step by step.

## What is in this folder

| Item | What it is |
|---|---|
| `Revenue_Pipeline.pbip` | The file you open |
| `Revenue_Pipeline.SemanticModel/` | The data model in TMDL text format: 16 tables, 14 relationships, 83 measures, the loading queries |
| `Revenue_Pipeline.Report/` | The report in PBIR text format: 2 pages, 43 items, theme, backgrounds |
| `data/` | The 15 CSV files the model loads |
| `validation/` | Correct answers and a check query |

Everything is plain text, so it works with Git. The `.gitignore` excludes the two local files Power BI creates (`.pbi/localSettings.json`, `.pbi/cache.abf`).
"""

if __name__ == "__main__":
    print(text(os.path.dirname(os.path.abspath(__file__))))
