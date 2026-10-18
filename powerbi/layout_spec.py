"""Pixel layout for both report pages (canvas 1280 x 720). Single source for backgrounds, layout maps and the guide tables."""
W, H = 1280, 720
NAVY, PLANE, CARD, BORDER = "#0d366b", "#f1f1ee", "#ffffff", "#dcdbd3"
BLUE, ORANGE, AQUA, VIOLET, GRAY = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#b7b6ac"

def kpi(i, y=116, w=199, h=80): return (18 + 209 * i, y, w, h)

PAGES = {
 "P1": dict(name="Pipeline", title="Revenue Pipeline", subtitle="Sales pipeline, deal health and conversion",
   panels=[(*kpi(i), c) for i, c in enumerate([BLUE, BLUE, BLUE, BLUE, BLUE, ORANGE])] + [
     (18, 206, 330, 232, None), (358, 206, 330, 232, None), (698, 206, 272, 232, None), (980, 206, 282, 232, None),
     (18, 448, 410, 256, None), (438, 448, 330, 256, None), (778, 448, 484, 256, None)],
   visuals=[
     ("S1", "Slicer (dropdown)", "Region", (18, 64, 200, 44)), ("S2", "Slicer (dropdown)", "Industry", (228, 64, 230, 44)),
     ("T1", "Card (text measure)", "Model note", (470, 64, 792, 44)),
     ("K1", "Card", "Open pipeline", kpi(0)), ("K2", "Card", "Weighted pipeline", kpi(1)), ("K3", "Card", "Win rate (12 months)", kpi(2)),
     ("K4", "Card", "Sales cycle (days)", kpi(3)), ("K5", "Card", "Velocity ($ per day)", kpi(4)), ("K6", "Card", "Stalled pipeline", kpi(5)),
     ("V1", "Funnel", "Lead-to-win funnel", (18, 206, 330, 232)), ("V2", "Stacked bar", "Open pipeline by stage", (358, 206, 330, 232)),
     ("V3", "Clustered column", "Lead score vs conversion", (698, 206, 272, 232)), ("V4", "Clustered bar", "Win rate: competitor in the deal", (980, 206, 282, 232)),
     ("V5", "Column chart", "New ARR booked by month", (18, 448, 410, 256)), ("V6", "Clustered bar", "Win rate by sales rep", (438, 448, 330, 256)),
     ("V7", "Table", "Stalled deals to review", (778, 448, 484, 256))]),
 "P2": dict(name="Customers", title="Customer Health and Retention", subtitle="Revenue, retention and the accounts that need attention",
   panels=[(*kpi(i), c) for i, c in enumerate([BLUE, BLUE, BLUE, BLUE, ORANGE, AQUA])] + [
     (18, 206, 400, 232, None), (428, 206, 400, 232, None), (838, 206, 424, 232, None),
     (18, 448, 700, 256, None), (728, 448, 260, 256, None), (998, 448, 264, 256, None)],
   visuals=[
     ("S1", "Slicer (dropdown)", "Region", (18, 64, 170, 44)), ("S2", "Slicer (dropdown)", "Industry", (196, 64, 200, 44)),
     ("S3", "Slicer (dropdown)", "Plan tier", (404, 64, 150, 44)), ("S4", "Slicer (dropdown)", "Segment", (562, 64, 190, 44)),
     ("T1", "Card (text measure)", "Model note", (764, 64, 498, 44)),
     ("K1", "Card", "Active ARR", kpi(0)), ("K2", "Card", "Net revenue retention", kpi(1)), ("K3", "Card", "Gross revenue retention", kpi(2)),
     ("K4", "Card", "Customer (logo) retention", kpi(3)), ("K5", "Card", "Expected ARR loss (90 days)", kpi(4)),
     ("K6", "Card", "Expected expansion (90 days)", kpi(5)),
     ("V1", "Waterfall", "ARR bridge, last 12 months", (18, 206, 400, 232)), ("V2", "Area chart", "ARR over time", (428, 206, 400, 232)),
     ("V3", "Scatter", "Churn risk vs expansion potential", (838, 206, 424, 232)),
     ("V4", "Table", "Customers to act on first", (18, 448, 700, 256)), ("V5", "Clustered bar", "Why this churn score", (728, 448, 260, 256)),
     ("V6", "Clustered bar", "Why this expansion score", (998, 448, 264, 256))]),
}

HEADER = [("H", "Text boxes: title and subtitle", (24, 8, 420, 44)), ("NAV", "Page navigator", (560, 14, 290, 32)),
          ("A", "Card: as-of label", (858, 14, 296, 32)), ("R", "Button: Clear all slicers", (1162, 14, 98, 32))]
