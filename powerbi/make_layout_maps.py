"""Numbered layout maps: each visual's box with its number, matching the coordinate tables in the guide."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from layout_spec import *
for page, P in PAGES.items():
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.axis("off")
    ax.imshow(plt.imread(f"design/background_{page}_{P['name'].lower()}.png"), extent=[0, W, H, 0], aspect="auto", alpha=0.55)
    for hid, nm, (x, y, w, h) in HEADER:
        ax.add_patch(Rectangle((x, y), w, h, fc="none", ec="#d03b3b", lw=1.5, ls="--"))
        ax.text(x + 5, y + h / 2, f"{hid}  {nm}  x{x} y{y} w{w} h{h}", color="#d03b3b", fontsize=6.8, va="center", fontweight="bold")
    for vid, typ, nm, (x, y, w, h) in P["visuals"]:
        ax.add_patch(Rectangle((x, y), w, h, fc="#2a78d6", alpha=0.10, ec="#2a78d6", lw=1.4))
        if h < 60 and not vid.startswith("K"):
            ax.text(x + 6, y + h / 2, f"{vid}  {nm}  x{x} y{y} w{w} h{h}", fontsize=6.8, color="#0d366b", va="center", fontweight="bold")
        else:
            ax.text(x + 6, y + 12, vid, fontsize=10, fontweight="bold", color="#0d366b", va="center")
            ax.text(x + 6, y + 27, nm, fontsize=7, color="#0b0b0b", va="top", wrap=True)
            ax.text(x + 6, y + h - 8, f"{typ}\nx{x} y{y} w{w} h{h}", fontsize=6.3, color="#52514e", va="bottom")
    fig.savefig(f"design/layout_map_{page}_{P['name'].lower()}.png", dpi=110); plt.close(fig)
print("ok")
