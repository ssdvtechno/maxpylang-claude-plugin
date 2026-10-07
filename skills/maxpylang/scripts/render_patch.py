#!/usr/bin/env python3
"""
render_patch.py - draw a .maxpat / .amxd as an image, so layout can be checked without Max.

Usage:
  render_patch.py patch.maxpat                 -> patch.png (matplotlib, else qlmanage/rsvg-convert, else .svg)
  render_patch.py device.amxd --presentation   -> device face as Live shows it (169 px strip)
  render_patch.py patch.maxpat -o out.svg      SVG output needs only the standard library

Boxes are drawn at their patching_rect (or presentation_rect) with their text; cords run from
outlet to inlet, signal cords thick and yellow-grey like in Max. Look at the PNG with an image
viewer (or Claude's Read tool) to spot crossings, overlaps and cramped sections.
"""
import argparse
import json
import os
import struct
import sys

DEVICE_HEIGHT = 169
XLET_W = 7.0
FILL = {"newobj": "#e8e8e8", "message": "#d8dde6", "comment": None}
UI_FILL = "#cfe3d6"


def load(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] == b"ampf":
        off = 0
        while off + 8 <= len(data):
            tag, size = data[off:off + 4], struct.unpack("<I", data[off + 4:off + 8])[0]
            if tag == b"ptch":
                return json.loads(data[off + 8:off + 8 + size].rstrip(b"\x00"))
            off += 8 + size
        raise ValueError("no ptch chunk")
    return json.loads(data)


def label(b):
    if b.get("maxclass") in ("newobj", "message", "comment"):
        return b.get("text", "")
    name = ((b.get("saved_attribute_attributes") or {}).get("valueof") or {}).get("parameter_longname") \
        or b.get("varname")
    return f"{b.get('maxclass')}: {name}" if name else f"[{b.get('maxclass')}]"


def xlet_x(rect, i, n):
    x, _, w, _ = rect
    if n <= 1:
        return x + XLET_W / 2
    return x + XLET_W / 2 + i * (w - XLET_W) / (n - 1)


def primitives(d, presentation):
    boxes = [b["box"] for b in d["patcher"].get("boxes", [])]
    key = "presentation_rect" if presentation else "patching_rect"
    if presentation:
        boxes = [b for b in boxes if b.get("presentation")]
    rects = {}
    for b in boxes:
        r = list(b.get(key) or b.get("patching_rect") or [0, 0, 40, 22])
        while len(r) < 4:
            r.append(22.0)
        rects[b["id"]] = r
    shapes = []  # ("rect", x, y, w, h, fill, edge) | ("text", x, y, s, size) | ("line", x1, y1, x2, y2, sig)
    if not presentation:
        by_id = {b["id"]: b for b in boxes}
        for ln in d["patcher"].get("lines", []):
            (s, so), (t, ti) = ln["patchline"]["source"], ln["patchline"]["destination"]
            if s not in rects or t not in rects:
                continue
            sb, tb = by_id[s], by_id[t]
            ot = sb.get("outlettype") or []
            sig = so < len(ot) and ot[so] in ("signal", "multichannelsignal")
            x1 = xlet_x(rects[s], so, sb.get("numoutlets", 1))
            y1 = rects[s][1] + rects[s][3]
            x2 = xlet_x(rects[t], ti, tb.get("numinlets", 1))
            y2 = rects[t][1]
            shapes.append(("line", x1, y1, x2, y2, sig))
    for b in boxes:
        x, y, w, h = rects[b["id"]]
        cls = b.get("maxclass")
        fill = FILL.get(cls, UI_FILL) if cls in FILL else UI_FILL
        if cls != "comment":
            shapes.append(("rect", x, y, w, h, fill, "#555555"))
        text = label(b)
        if presentation and cls not in FILL and ": " in text:
            text = text.split(": ", 1)[1]
        if cls != "comment":
            fit = max(3, int((w - 4) / 5.6))
            text = text if len(text) <= fit else text[:fit - 1] + "…"
        if text:
            light = presentation and cls == "comment"
            shapes.append(("text", x + 3, y + min(h, 22) / 2 + 4, text, 9, light))
    xs = [r[0] + r[2] for r in rects.values()] or [100]
    ys = [r[1] + r[3] for r in rects.values()] or [100]
    width = max(xs) + 20
    height = max(max(ys) + 20, DEVICE_HEIGHT + 10 if presentation else 0)
    return shapes, width, height


def to_svg(shapes, width, height, presentation):
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
           f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="Arial, sans-serif">',
           f'<rect width="100%" height="100%" fill="#ffffff"/>']
    if presentation:
        out.append(f'<rect x="0" y="0" width="{width:.0f}" height="{DEVICE_HEIGHT}" fill="#3a3a3a"/>')
    for s in shapes:
        if s[0] == "line":
            _, x1, y1, x2, y2, sig = s
            style = 'stroke="#b5a642" stroke-width="2.5" stroke-dasharray="4 2"' if sig else 'stroke="#333" stroke-width="1"'
            out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" {style}/>')
    for s in shapes:
        if s[0] == "rect":
            _, x, y, w, h, fill, edge = s
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" stroke="{edge}"/>')
        elif s[0] == "text":
            _, x, y, t, size, light = s
            color = "#eeeeee" if light else "#111111"
            out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size + 2}" fill="{color}">{esc(t)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def to_png(shapes, width, height, presentation, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    dpi = 100
    fig = plt.figure(figsize=(width / dpi * 1.5, height / dpi * 1.5), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)
    ax.axis("off")
    if presentation:
        ax.add_patch(Rectangle((0, 0), width, DEVICE_HEIGHT, color="#3a3a3a", zorder=0))
    for s in shapes:
        if s[0] == "line":
            _, x1, y1, x2, y2, sig = s
            ax.plot([x1, x2], [y1, y2], color="#b5a642" if sig else "#333333",
                    lw=2.2 if sig else 0.8, ls=(0, (4, 2)) if sig else "-", zorder=1)
    for s in shapes:
        if s[0] == "rect":
            _, x, y, w, h, fill, edge = s
            ax.add_patch(Rectangle((x, y), w, h, facecolor=fill, edgecolor=edge, lw=0.8, zorder=2))
        elif s[0] == "text":
            _, x, y, t, size, light = s
            ax.text(x, y, t, fontsize=size, color="#eeeeee" if light else "#111111",
                    va="baseline", zorder=3, clip_on=True)
    fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("-o", "--out", help="output .png or .svg (default: next to the patch)")
    ap.add_argument("--presentation", action="store_true", help="draw the presentation view / device face")
    a = ap.parse_args()
    d = load(a.path)
    shapes, width, height = primitives(d, a.presentation)
    if a.presentation and not any(s[0] == "rect" or s[0] == "text" for s in shapes):
        print("nothing is in the presentation view", file=sys.stderr)
    base = os.path.splitext(a.path)[0] + ("_face" if a.presentation else "")
    out = a.out or base + ".png"
    if out.endswith(".svg"):
        with open(out, "w", encoding="utf-8") as f:
            f.write(to_svg(shapes, width, height, a.presentation))
    else:
        try:
            to_png(shapes, width, height, a.presentation, out)
        except ImportError:  # no matplotlib: SVG, then the OS's converter if there is one
            svg = os.path.splitext(out)[0] + ".svg"
            with open(svg, "w", encoding="utf-8") as f:
                f.write(to_svg(shapes, width, height, a.presentation))
            out = svg_to_png(svg, out, max(width, height)) or svg
            if out == svg:
                print("(no PNG converter found: pip install matplotlib for PNG previews)", file=sys.stderr)
    print(out)
    return 0


def svg_to_png(svg, png, size):
    """Convert with whatever the OS has: qlmanage (macOS), rsvg-convert, ImageMagick. Returns png or None."""
    import shutil
    import subprocess
    import tempfile
    tries = []
    if shutil.which("rsvg-convert"):
        tries.append(["rsvg-convert", "-o", png, svg])
    for magick in ("magick", "convert"):
        if shutil.which(magick):
            tries.append([magick, svg, png])
    for cmd in tries:
        if subprocess.run(cmd, capture_output=True).returncode == 0 and os.path.exists(png):
            return png
    if shutil.which("qlmanage"):
        tmp = tempfile.mkdtemp()
        subprocess.run(["qlmanage", "-t", "-s", str(int(size * 1.5)), "-o", tmp, svg], capture_output=True)
        made = os.path.join(tmp, os.path.basename(svg) + ".png")
        if os.path.exists(made):
            shutil.move(made, png)
            return png
    return None


if __name__ == "__main__":
    sys.exit(main())
