#!/usr/bin/env python3
"""Baut aus dem KI-Laufbogen (assets/raw/walk.png) den Spielbogen des Dachses.

    .venv/bin/python styles/bleistift-skizze/scripts/build_badger.py

Je Figur (Lage aus assets/sheet_cells.json, Messwerte aus assets/walk_advance.json):
  1. Ausschnitt fester Größe (249x415 px), linke Kante = Hüllrechteck - PAD, Sohle auf gemeinsamer Zeile.
  2. walk_5 … walk_7: Beine ab Zeile 230 um 10 px strecken (das Bildmodell hat sie in der zweiten Reihe kürzer
     gezeichnet; der Kopf würde sonst in 3 von 8 Bildern absacken).
  3. Oberkörper gegen die Beine scheren, damit der Kopf je Bildwechsel gleich weit vorrückt (Füße unverändert).
  4. Farbe: Grafit wie der Hintergrund, nur der rote Schal bleibt Buntstift. Papier in der Figur bleibt deckend.
  5. Verkleinern um F = 49/83 (Figur etwa 196 px), Blinzelbild aus der Dreiviertelansicht.
Ergebnis: assets/badger.png + demo/art/badger.png (Bogen, eine Reihe) und demo/art/badger.json
"""
import json, pathlib, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]
CW, CH = 249, 415          # Ausschnitt im KI-Bogen
F = 49 / 83                # -> 147 x 245
OW, OH = 147, 245
PAD = 15                   # Rand links vom Hüllrechteck
SOLE_ROW = 398             # Sohlenzeile im Ausschnitt
G_DARK = np.array([0x33, 0x34, 0x3C], np.float32) / 255.0
ORDER = [f"walk_{i}" for i in range(8)] + ["stand", "turn", "blink"]


def shift_rows(arr, shifts):
    """Verschiebt jede Zeile um shifts[r] Pixel (linear interpoliert); arr vormultipliziert, HxWxC."""
    h, w, c = arr.shape
    xs = np.arange(w, dtype=np.float32)
    out = np.zeros_like(arr)
    for r in range(h):
        s = shifts[r]
        if abs(s) < 1e-3:
            out[r] = arr[r]
            continue
        for k in range(c):
            out[r, :, k] = np.interp(xs - s, xs, arr[r, :, k], left=0.0, right=0.0)
    return out


def stretch_below(arr, y0, extra):
    """Streckt die Zeilen ab y0 bis zur Sohle (SOLE_ROW) um extra Zeilen; darüber wird nach oben geschoben."""
    h, w, c = arr.shape
    out = np.zeros_like(arr)
    # Ziel: Zeile y_t (y_t <= SOLE_ROW) holt sich Quelle y_s
    for yt in range(h):
        if yt > SOLE_ROW:
            ys = yt
        elif yt >= y0 - extra:
            ys = y0 + (yt - (y0 - extra)) * (SOLE_ROW - y0) / (SOLE_ROW - (y0 - extra))
        else:
            ys = yt + extra
        y_lo = int(np.floor(ys))
        t = ys - y_lo
        if 0 <= y_lo < h - 1:
            out[yt] = arr[y_lo] * (1 - t) + arr[y_lo + 1] * t
        elif 0 <= y_lo < h:
            out[yt] = arr[y_lo]
    return out


def colorize(rgb):
    """Grafit + roter Schal (Buntstift)."""
    gray = (rgb * np.array([0.30, 0.59, 0.11], np.float32)).sum(2, keepdims=True)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    red = np.clip(((r - np.maximum(g, b)) - 0.12) / 0.15, 0, 1)[..., None]
    out = gray + (rgb - gray) * red
    return 1.0 - (1.0 - out) * (1.0 - G_DARK)


def main():
    cells = {c["name"]: c for c in json.loads((ROOT / "assets/sheet_cells.json").read_text())}
    wa = json.loads((ROOT / "assets/walk_advance.json").read_text())
    sheet = np.asarray(Image.open(ROOT / "assets/raw/walk.png").convert("RGBA"), np.float32) / 255.0
    sheet = np.pad(sheet, ((CH, CH), (CW, CW), (0, 0)))

    # Vorschub und Scherung
    adv = wa["advance"]
    head = wa["head_x"]
    X = [0.0]
    for a in adv:
        X.append(X[-1] + a)
    step = X[-1] / 8.0
    B = [X[i] + head[f"walk_{i}"] for i in range(8)]
    shear = {f"walk_{i}": (i * step) - (B[i] - B[0]) for i in range(8)}
    shear["stand"] = 0.0
    shear["turn"] = 0.0
    band0, band1 = wa["shear_band"]

    frames = {}
    for name in ORDER[:-1]:
        c = cells[name]
        x0, y0b = c["box"][0], c["box"][1]
        sole = c["sole_y"]
        sx = x0 - PAD + CW
        sy = sole - SOLE_ROW + CH
        crop = sheet[sy:sy + CH, sx:sx + CW].copy()
        crop[..., :3] *= crop[..., 3:]
        top = y0b - (sole - SOLE_ROW)                 # Zeile der Kappe im Ausschnitt
        if name in wa["leg_stretch"]:
            ly, extra = wa["leg_stretch"][name]
            crop = stretch_below(crop, top + ly, extra)
            top -= extra
        d = shear[name]
        shifts = np.zeros(CH, np.float32)
        r0, r1 = top + band0, top + band1
        for r in range(CH):
            if r < r0:
                shifts[r] = d
            elif r < r1:
                shifts[r] = d * (r1 - r) / (r1 - r0)
        crop = shift_rows(crop, shifts)
        a = crop[..., 3:]
        rgb = np.where(a > 1e-4, crop[..., :3] / np.maximum(a, 1e-4), 1.0)
        rgb = colorize(np.clip(rgb, 0, 1))
        frames[name] = np.concatenate([rgb * a, a], 2)   # vormultipliziert

    # Blinzeln: Augen der Dreiviertelansicht mit Fell der Augenbinde daneben überdecken, Lidstrich darüber
    f = frames["turn"].copy()
    lid = Image.new("L", (CW * 4, CH * 4), 0)
    dl = ImageDraw.Draw(lid)
    for ex, ey, r, sdx, sdy in wa["turn_eyes"]:
        src = f[ey - r + sdy:ey + r + 1 + sdy, ex - r + sdx:ex + r + 1 + sdx].copy()
        yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
        m = np.clip(1.5 - np.sqrt(xx ** 2 + yy ** 2) / r, 0, 1)[..., None]
        patch = f[ey - r:ey + r + 1, ex - r:ex + r + 1]
        f[ey - r:ey + r + 1, ex - r:ex + r + 1] = patch * (1 - m) + src * m
        # geschlossenes Lid: flacher Bogen nach unten
        pts = [((ex + t * r) * 4, (ey + 0.35 * r * (1 - t * t)) * 4) for t in np.linspace(-1, 1, 9)]
        dl.line(pts, fill=255, width=int(max(6, r * 1.3)), joint="curve")
    la = np.asarray(lid.filter(ImageFilter.GaussianBlur(2)).resize((CW, CH), Image.LANCZOS), np.float32)[..., None] / 255.0
    la *= 0.9
    ink = np.concatenate([G_DARK * 0.8, [1.0]]).astype(np.float32)
    f = f * (1 - la) + ink * la
    frames["blink"] = f

    out = Image.new("RGBA", (OW * len(ORDER), OH), (0, 0, 0, 0))
    meta = {"frame_w": OW, "frame_h": OH, "scale": F, "sole_y": (SOLE_ROW + 1) * F, "order": ORDER,
            "pad": PAD, "frames": {}}
    for i, name in enumerate(ORDER):
        pm = frames[name]
        im = Image.fromarray((np.clip(pm, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
        # vormultipliziert verkleinern, dann zurückrechnen
        im = im.resize((OW, OH), Image.LANCZOS)
        arr = np.asarray(im, np.float32) / 255.0
        a = arr[..., 3:]
        rgb = np.where(a > 1e-3, arr[..., :3] / np.maximum(a, 1e-3), 1.0)
        arr = np.concatenate([np.clip(rgb, 0, 1), a], 2)
        out.paste(Image.fromarray((arr * 255 + 0.5).astype(np.uint8), "RGBA"), (i * OW, 0))
        meta["frames"][name] = {"index": i, "shear_src": round(float(shear.get(name, 0.0)), 2)}
    meta["advance"] = [a * F for a in adv]
    meta["advance_to_stand"] = {k: v * F for k, v in wa["advance_to_stand"].items()}
    meta["stand_to_turn"] = (head["stand"] - head["turn"]) * F
    meta["head_x"] = {k: (v + PAD) * F for k, v in head.items()}
    out.save(ROOT / "assets/badger.png")
    shutil.copy(ROOT / "assets/badger.png", ROOT / "demo/art/badger.png")
    (ROOT / "demo/art/badger.json").write_text(json.dumps(meta, indent=1))
    print("ok", ROOT / "assets/badger.png", out.size)
    print("shear (Quellpixel):", {k: round(v, 1) for k, v in shear.items()})


if __name__ == "__main__":
    main()
