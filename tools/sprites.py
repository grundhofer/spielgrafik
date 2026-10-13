#!/usr/bin/env python3
"""Werkzeuge für KI-erzeugte Sprites: freistellen, zerlegen, ausrichten, verpixeln.

  key      Hintergrundfarbe transparent machen (falls das Bild keinen Alphakanal hat)
           sprites.py key in.png out.png --color ff00ff --tol 60
  slice    Sprite-Sheet in gleich große, am Boden ausgerichtete Einzelbilder zerlegen
           sprites.py slice sheet.png walk.png --frames 6 [--rows 1] [--height 96] [--nearest]
           -> walk.png (Streifen, Einzelbilder nebeneinander) + walk.json (frame_w, frame_h, count)
  pixelize Auf ein grobes Raster verkleinern und auf eine Palette reduzieren
           sprites.py pixelize in.png out.png --width 320 --palette nes [--dither bayer]
           sprites.py pixelize in.png out.png --height 64 --colors 16 [--alpha-cut 128]
           sprites.py pixelize ki_pixelart.png out.png --width 256 --colors 24 --resample mode
           Paletten: gb, nes, pico8, c64, ega, cga, zx, 1bit, oder --palette-hex "112233,445566"
  palette  Palette eines Bildes als PNG-Streifen ausgeben (für Referenzen in Prompts)
           sprites.py palette in.png pal.png --colors 16

Ausgabe von pixelize ist in Rasterauflösung; in Godot mit Filter "Nearest" ganzzahlig skalieren.
"""
import argparse, json, pathlib, sys

import numpy as np
from PIL import Image

PALETTES = {
    "gb": "0f380f 306230 8bac0f 9bbc0f",
    "1bit": "000000 ffffff",
    "cga": "000000 55ffff ff55ff ffffff",
    "pico8": "000000 1d2b53 7e2553 008751 ab5236 5f574f c2c3c7 fff1e8 ff004d ffa300 ffec27 00e436 29adff 83769c ff77a8 ffccaa",
    "ega": "000000 0000aa 00aa00 00aaaa aa0000 aa00aa aa5500 aaaaaa 555555 5555ff 55ff55 55ffff ff5555 ff55ff ffff55 ffffff",
    "c64": "000000 ffffff 68372b 70a4b2 6f3d86 588d43 352879 b8c76f 6f4f25 433900 9a6759 444444 6c6c6c 9ad284 6c5eb5 959595",
    "zx": "000000 0000d7 d70000 d700d7 00d700 00d7d7 d7d700 d7d7d7 0000ff ff0000 ff00ff 00ff00 00ffff ffff00 ffffff",
    "nes": ("7c7c7c 0000fc 0000bc 4428bc 940084 a80020 a81000 881400 503000 007800 006800 005800 004058 000000 "
            "bcbcbc 0078f8 0058f8 6844fc d800cc e40058 f83800 e45c10 ac7c00 00b800 00a800 00a844 008888 "
            "f8f8f8 3cbcfc 6888fc 9878f8 f878f8 f85898 f87858 fca044 f8b800 b8f818 58d854 58f898 00e8d8 787878 "
            "fcfcfc a4e4fc b8b8f8 d8b8f8 f8b8f8 f8a4c0 f0d0b0 fce0a8 f8d878 d8f878 b8f8b8 b8f8d8 00fcfc f8d8f8"),
}
BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16 - 0.5


def hexpal(s):
    vals = [v.strip().lstrip("#") for v in s.replace(",", " ").split() if v.strip()]
    return np.array([[int(v[i:i + 2], 16) for i in (0, 2, 4)] for v in vals], dtype=np.float32)


def rgba(path):
    return Image.open(path).convert("RGBA")


def cmd_key(a):
    im = np.asarray(rgba(a.inp)).astype(np.float32)
    key = hexpal(a.color)[0]
    dist = np.sqrt(((im[..., :3] - key) ** 2).sum(-1))
    alpha = np.clip((dist - a.tol) / max(1, a.soft), 0, 1)
    out = im.copy()
    out[..., 3] = np.minimum(out[..., 3], alpha * 255)
    # Farbsaum entfernen: halbtransparente Pixel von der Schlüsselfarbe wegschieben
    semi = (alpha > 0) & (alpha < 1)
    a3 = alpha[semi][:, None]
    out[..., :3][semi] = np.clip((im[..., :3][semi] - key * (1 - a3)) / np.maximum(a3, 0.05), 0, 255)
    if a.despill > 0:
        # Farbstich der Schlüsselfarbe im Randstreifen (a.despill Pixel neben Transparenz) entfernen:
        # Schlüsselkanäle (z. B. R und B bei Magenta) nicht heller als der hellste Nicht-Schlüsselkanal.
        near = alpha < 1
        for _ in range(int(a.despill)):
            grow = near.copy()
            grow[1:] |= near[:-1]; grow[:-1] |= near[1:]; grow[:, 1:] |= near[:, :-1]; grow[:, :-1] |= near[:, 1:]
            near = grow
        band = near & (alpha > 0)
        kc = key > 127
        if kc.any() and (~kc).any():
            rgb = out[..., :3]
            m = rgb[..., kc].min(-1)
            n = rgb[..., ~kc].max(-1)
            excess = np.where(band, np.clip(m - n, 0, None), 0)
            rgb[..., kc] -= excess[..., None]
    Image.fromarray(out.astype(np.uint8)).save(a.out)
    print(f"{a.out}: {(alpha == 0).mean():.0%} transparent")


def runs(mask1d, min_gap):
    """Zusammenhängende Bereiche mit Inhalt; Lücken kürzer als min_gap werden überbrückt."""
    idx = np.flatnonzero(mask1d)
    if idx.size == 0:
        return []
    out, start, prev = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - prev > min_gap:
            out.append((start, prev + 1))
            start = i
        prev = i
    out.append((start, prev + 1))
    return out


def cmd_slice(a):
    im = rgba(a.inp)
    arr = np.asarray(im)
    opaque = arr[..., 3] > a.alpha
    rows = runs(opaque.any(1), a.gap) if a.rows > 1 else [(0, arr.shape[0])]
    if a.rows > 1 and len(rows) != a.rows:
        rows = sorted(rows, key=lambda r: r[1] - r[0], reverse=True)[:a.rows]
        rows.sort()
    cells = []
    for y0, y1 in rows:
        band = opaque[y0:y1]
        cols = runs(band.any(0), a.gap)
        # Kleine Splitter (Krümel) verwerfen, dann bei Bedarf die größten N behalten
        cols = [c for c in cols if (c[1] - c[0]) > 6 and band[:, c[0]:c[1]].sum() > 200]
        cells += [(y0, y1, x0, x1) for x0, x1 in cols]
    want = a.frames * (a.rows if a.rows > 1 else 1) if a.frames else len(cells)
    # Berühren sich zwei Figuren (Schal, Fuß), den breitesten Bereich an der dünnsten Spalte teilen
    while len(cells) < want:
        i = max(range(len(cells)), key=lambda j: cells[j][3] - cells[j][2])
        y0, y1, x0, x1 = cells[i]
        prof = opaque[y0:y1, x0:x1].sum(0).astype(float)
        lo, hi = int(len(prof) * 0.2), int(len(prof) * 0.8)
        if hi - lo < 4:
            break
        cut = x0 + lo + int(np.argmin(prof[lo:hi]))
        cells[i:i + 1] = [(y0, y1, x0, cut), (y0, y1, cut, x1)]
        print(f"geteilt bei x={cut} (Deckung {int(prof[cut - x0])} px)")
    if len(cells) != want:
        print(f"WARNUNG: {len(cells)} Bereiche gefunden, {want} erwartet. "
              f"--gap ändern oder Sheet prüfen. Breiten: {[c[3] - c[2] for c in cells]}")
        if len(cells) > want:
            cells = sorted(cells, key=lambda c: -(opaque[c[0]:c[1], c[2]:c[3]].sum()))[:want]
            cells.sort(key=lambda c: (c[0], c[2]))
    frames = []
    for y0, y1, x0, x1 in cells:
        sub = opaque[y0:y1, x0:x1]
        ys = np.flatnonzero(sub.any(1))
        crop = im.crop((x0, y0 + ys[0], x1, y0 + ys[-1] + 1))
        frames.append(crop)
    fw = max(f.width for f in frames) + 2 * a.pad
    fh = max(f.height for f in frames) + 2 * a.pad
    scale = (a.height / fh) if a.height else 1.0
    resample = Image.NEAREST if a.nearest else Image.LANCZOS
    tw, th = max(1, round(fw * scale)), max(1, round(fh * scale))
    strip = Image.new("RGBA", (tw * len(frames), th), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        cell = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
        fa = np.asarray(f)[..., 3] > a.alpha
        # horizontal am Schwerpunkt ausrichten (verhindert Zittern), vertikal am Boden
        cx = int(np.flatnonzero(fa.any(0)).mean()) if a.align == "center" else f.width // 2
        x = fw // 2 - cx if a.align == "center" else (fw - f.width) // 2
        x = max(0, min(fw - f.width, x))
        cell.paste(f, (x, fh - a.pad - f.height), f)
        if scale != 1.0:
            cell = cell.resize((tw, th), resample)
        strip.paste(cell, (i * tw, 0))
    strip.save(a.out)
    meta = {"source": str(a.inp), "count": len(frames), "frame_w": tw, "frame_h": th,
            "hframes": len(frames), "baseline": "bottom", "nearest": bool(a.nearest)}
    pathlib.Path(a.out).with_suffix(".json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta))


def quantize(rgb, pal, dither):
    h, w, _ = rgb.shape
    x = rgb.astype(np.float32)
    if dither == "bayer":
        spread = 255 / max(2, len(pal) ** 0.5)
        t = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w]
        x = x + t[..., None] * spread
    if dither == "fs":
        img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
        p = Image.new("P", (1, 1))
        flat = pal.astype(np.uint8).flatten().tolist()
        p.putpalette(flat + flat[:3] * (256 - len(pal)))
        return np.asarray(img.quantize(palette=p, dither=Image.FLOYDSTEINBERG).convert("RGB"))
    # Abstand im Oklab-Raum: wahrnehmungsnah, sonst wird z. B. Dunkelgrau zu Braun
    d = ((oklab(x)[:, :, None, :] - oklab(pal)[None, None]) ** 2).sum(-1)
    return pal[d.argmin(-1)].astype(np.uint8)


def oklab(rgb):
    c = np.clip(rgb, 0, 255) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return np.cbrt(c @ m1.T) @ m2.T


def cmd_pixelize(a):
    im = rgba(a.inp)
    if a.width:
        size = (a.width, max(1, round(im.height * a.width / im.width)))
    elif a.height:
        size = (max(1, round(im.width * a.height / im.height)), a.height)
    else:
        size = (im.width // a.factor, im.height // a.factor)
    # BOX mittelt jede Zelle; das entspricht einem sauberen Raster ohne Kantenglättung zwischen Zellen
    small = im.resize(size, Image.BOX)
    arr = np.asarray(small).astype(np.float32)
    if a.contrast != 1.0:
        arr[..., :3] = np.clip((arr[..., :3] - 128) * a.contrast + 128, 0, 255)
    if a.palette_hex:
        pal = hexpal(a.palette_hex)
    elif a.palette:
        pal = hexpal(PALETTES[a.palette])
    else:
        q = Image.fromarray(arr[..., :3].astype(np.uint8)).quantize(colors=a.colors, method=Image.MEDIANCUT)
        pal = np.array(q.getpalette()[:3 * a.colors], dtype=np.float32).reshape(-1, 3)
    if a.resample == "mode":
        # Für Bilder, die schon als Pixel-Art erzeugt wurden: jede Zelle bekommt ihre häufigste
        # Palettenfarbe statt des Mittelwerts. Kanten bleiben hart, Mischfarben entstehen nicht.
        c = max(1, round(im.width / size[0]))
        big = np.asarray(im.convert("RGB").resize((size[0] * c, size[1] * c), Image.NEAREST)).astype(np.float32)
        lab, plab = oklab(big), oklab(pal)
        idx = np.zeros(big.shape[:2], dtype=np.int32)
        best = np.full(big.shape[:2], np.inf)
        for k in range(len(pal)):
            dk = ((lab - plab[k]) ** 2).sum(-1)
            idx = np.where(dk < best, k, idx)
            best = np.minimum(dk, best)
        cells = idx.reshape(size[1], c, size[0], c).transpose(0, 2, 1, 3).reshape(size[1], size[0], c * c)
        counts = np.stack([(cells == k).sum(-1) for k in range(len(pal))], -1)
        rgb = pal[counts.argmax(-1)].astype(np.uint8)
    else:
        rgb = quantize(arr[..., :3], pal, a.dither)
    alpha = np.where(arr[..., 3] >= a.alpha_cut, 255, 0).astype(np.uint8)
    out = np.dstack([rgb, alpha])
    Image.fromarray(out, "RGBA").save(a.out)
    used = len(np.unique(rgb[alpha > 0].reshape(-1, 3), axis=0)) if alpha.any() else 0
    print(f"{a.out}: {size[0]}x{size[1]}, {used} Farben aus Palette mit {len(pal)}")


def cmd_palette(a):
    q = rgba(a.inp).convert("RGB").quantize(colors=a.colors, method=Image.MEDIANCUT)
    pal = np.array(q.getpalette()[:3 * a.colors], dtype=np.uint8).reshape(-1, 3)
    Image.fromarray(np.repeat(np.repeat(pal[None], 32, 0), 32, 1)).save(a.out)
    print(" ".join("%02x%02x%02x" % tuple(c) for c in pal))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    k = sp.add_parser("key"); k.add_argument("inp"); k.add_argument("out")
    k.add_argument("--color", default="ff00ff"); k.add_argument("--tol", type=float, default=60)
    k.add_argument("--soft", type=float, default=40)
    k.add_argument("--despill", type=int, default=2, help="Randstreifen in Pixeln, in dem der Farbstich entfernt wird (0 = aus)")
    s = sp.add_parser("slice"); s.add_argument("inp"); s.add_argument("out")
    s.add_argument("--frames", type=int, default=0); s.add_argument("--rows", type=int, default=1)
    s.add_argument("--gap", type=int, default=4); s.add_argument("--alpha", type=int, default=24)
    s.add_argument("--pad", type=int, default=4); s.add_argument("--height", type=int, default=0)
    s.add_argument("--nearest", action="store_true")
    s.add_argument("--align", choices=["center", "box"], default="center")
    p = sp.add_parser("pixelize"); p.add_argument("inp"); p.add_argument("out")
    p.add_argument("--width", type=int); p.add_argument("--height", type=int)
    p.add_argument("--factor", type=int, default=8)
    p.add_argument("--palette", choices=sorted(PALETTES)); p.add_argument("--palette-hex")
    p.add_argument("--colors", type=int, default=16)
    p.add_argument("--dither", choices=["none", "bayer", "fs"], default="none")
    p.add_argument("--alpha-cut", type=int, default=128); p.add_argument("--contrast", type=float, default=1.0)
    p.add_argument("--resample", choices=["box", "mode"], default="box",
                   help="box: Zellmittel (Gemälde verkleinern); mode: häufigste Farbe (KI-Pixel-Art einrasten)")
    q = sp.add_parser("palette"); q.add_argument("inp"); q.add_argument("out")
    q.add_argument("--colors", type=int, default=16)
    a = ap.parse_args()
    {"key": cmd_key, "slice": cmd_slice, "pixelize": cmd_pixelize, "palette": cmd_palette}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
