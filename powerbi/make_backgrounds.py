from PIL import Image, ImageDraw, ImageFilter
from layout_spec import *

S = 4   # supersample
def hexrgb(h): h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def render(page, path):
    img = Image.new("RGB", (W * S, H * S), hexrgb(PLANE))
    # soft shadows
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
    for (x, y, w, h, _a) in PAGES[page]["panels"]:
        sd.rounded_rectangle([x * S, (y + 2) * S, (x + w) * S, (y + h + 2) * S], radius=8 * S, fill=(20, 30, 50, 34))
    sh = sh.filter(ImageFilter.GaussianBlur(5 * S))
    img = Image.alpha_composite(img.convert("RGBA"), sh).convert("RGB")
    d = ImageDraw.Draw(img)
    # header band
    d.rectangle([0, 0, W * S, 58 * S], fill=hexrgb(NAVY))
    d.rectangle([0, 58 * S, W * S, 61 * S], fill=hexrgb(AQUA))
    for (x, y, w, h, accent) in PAGES[page]["panels"]:
        d.rounded_rectangle([x * S, y * S, (x + w) * S, (y + h) * S], radius=8 * S, fill=hexrgb(CARD), outline=hexrgb(BORDER), width=S)
        if accent:
            d.rounded_rectangle([x * S, y * S, (x + 6) * S, (y + h) * S], radius=3 * S, fill=hexrgb(accent))
            d.rectangle([(x + 3) * S, y * S, (x + 7) * S, (y + h) * S], fill=hexrgb(CARD))
            d.rounded_rectangle([x * S, y * S, (x + 5) * S, (y + h) * S], radius=2 * S, fill=hexrgb(accent))
    img = img.resize((W * 2, H * 2), Image.LANCZOS)
    img.save(path, optimize=True)

for p in PAGES:
    render(p, f"design/background_{p}_{PAGES[p]['name'].lower()}.png")
print("ok")
