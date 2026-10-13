#!/usr/bin/env python3
"""Zerlegt den KI-Laufbogen in Spielbilder für die Noir-Demo.

    .venv/bin/python styles/noir/scripts/build_badger.py [--src walk|walk3]

Quelle (Standard walk3): assets/raw/walk3.png, Übermalung von raw/walk.png durch agy (Gemini-Bildmodell) in flachen
Gouache-Flächen; JPEG, von genimg.py über Magenta freigestellt, 1264×848 statt 1536×1024. Sie wird gleichmäßig auf
1024 px Höhe skaliert (vormultipliziert, Lanczos) und waagerecht mittig auf 1536 px gesetzt (je 5 px Rand); dann
decken sich die Silhouetten mit raw/walk.png je Zelle zu 98,1–98,5 % ohne Verschiebung, Sohlen 1 px tiefer, Enden
der Bodenkontakte in der Quelle 0–6 px versetzt (im Spiel höchstens 2 px, gemessen). Magenta-Reste am Rand werden entfernt (Rot und Blau um ihren
gemeinsamen Überschuss über Grün gesenkt). --src walk baut die frühere Fassung aus raw/walk.png (Codex, echter
Alphakanal).

Der Bogen liegt im Raster des Blender-Layouts (assets/ref/layouts.json: 2×5 Zellen à 307×512, 409,6 px/m); das
Bildmodell hat Posen und Lage gehalten (raw/walk.png: Silhouetten-IoU 0,91–0,95 gegen die Blender-Posen, Sohlen
2–3 px tiefer). Deshalb wird jede Zelle mit demselben festen Ausschnitt verarbeitet, ohne Einzelverschiebung:
  1. Ausschnitt x 14…294, y 56…490 jeder Zelle (Vielfache von 7), damit die Verkleinerung um 3/7 ganzzahlig aufgeht.
  2. Tonwerte: alles außer dem roten Schal entsättigen (Gewicht aus Sättigung und Farbton), leichte S-Kurve.
  3. Kissen-Normalen: Alpha binarisiert (> 0,5), Höhe = weichgezeichnete Maske (σ 22 px in Quellgröße) mal Maske,
     die Kante mit σ 1,5 px geglättet (alles in Gleitkomma), daraus der Gradient. Innenformen bekommen kein Relief.
     Damit kann der Figuren-Shader in Godot hartes Licht aus beliebiger Richtung setzen (Laterne, Fenster,
     Gegenlicht), obwohl die Figur ein flaches Bild ist.
  4. Vormultipliziert mit Lanczos um 3/7 verkleinern: 120×186 je Bild, Figur etwa 179 px hoch (177 px/m).
Ergebnis:
  assets/badger.png     Bogen 11×1 (walk_0 … walk_7, stand, turn, turn_blink), RGBA
  assets/badger_n.png   Normalen im selben Raster (RGB = N·0,5+0,5, Bildschirm-y nach unten), A = Alpha
  assets/badger.json    Bildgröße, Fußpunkt (Ursprung des Rigs), Vorschub je Laufbild, Sohlenzeilen
"""
import argparse, json, pathlib

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCES = {   # Rohbild, Sohlenzeile im Bogen (Zellkoordinaten), Augen der Zelle "turn" (Mitte x, y, Radius)
    "walk3": (ROOT / "assets/raw/walk3.png", 486.0, [(179.5, 132.5, 6.0), (220.5, 129.5, 5.0)]),
    "walk": (ROOT / "assets/raw/walk.png", 485.5, [(178.5, 136.5, 7.5), (219.5, 128.5, 5.5)]),
}
LAYOUT = ROOT / "assets/ref/layouts.json"
OUT = ROOT / "assets"
X0, Y0, X1, Y1 = 14, 56, 294, 490      # Ausschnitt je Zelle (Quellpixel)
F = 3 / 7                               # Verkleinerung
FW, FH = round((X1 - X0) * F), round((Y1 - Y0) * F)
STEP_SRC = 21.0                         # gemessener Vorschub je Laufbild im KI-Bogen (Standfuß, Bilder 1→3, 5→7)
NORMAL_SIGMA = 22                       # Kissenbreite in Quellpixeln
NORMAL_GAIN = 9.0                       # Steilheit der Kissennormalen
EDGE_SIGMA = 1.5                        # Glättung der binarisierten Silhouette (Quellpixel)


def to_f(im):
    return np.asarray(im).astype(np.float32) / 255.0


def noir_tone(rgb):
    """Graustufen außer Rot (Schal); Rotgewicht weich aus Sättigung und Farbton."""
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1e-4)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    hue_red = np.clip(1 - np.abs(g - b) / np.maximum(r - mn, 1e-4) * 1.5, 0, 1) * (r >= mx - 1e-6)
    w = np.clip((sat - 0.30) / 0.25, 0, 1) * hue_red * np.clip((mx - 0.06) / 0.08, 0, 1)
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    # S-Kurve nur auf die Graustufen
    s = lum * lum * (3 - 2 * lum)
    gray = np.clip(0.6 * lum + 0.4 * s, 0, 1)
    out = np.repeat(gray[..., None], 3, -1) * (1 - w[..., None]) + rgb * w[..., None]
    return out, w


def gauss_blur(x, sigma):
    """Gaussche Weichzeichnung in Gleitkomma (getrennt nach Zeilen und Spalten, außen 0), ohne 8-bit-Stufen."""
    r = int(3 * sigma + 0.5)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2).astype(np.float32)
    k /= k.sum()
    x = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 0, x)
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 1, x)


def pillow_normals(alpha):
    # Nur die Silhouette zählt: Alpha erst binarisieren. Das Roh-Alpha schwankt im Innern des KI-Bogens
    # (0,957–1,0) und hat 8-bit-Stufen; mit der Steilheit 9 × 22 wurde daraus ein Relief aus Paket, Knöpfen und
    # Arm, das die harte Lichtschwelle im Shader als Sprenkel zeigte.
    m = (alpha > 0.5).astype(np.float32)
    h = gauss_blur(m, NORMAL_SIGMA) * m
    h = gauss_blur(h, EDGE_SIGMA)                         # Silhouettenkante glätten
    gy, gx = np.gradient(h)
    n = np.stack([-gx * NORMAL_GAIN * NORMAL_SIGMA, -gy * NORMAL_GAIN * NORMAL_SIGMA, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n


def premul_resize(rgba, size):
    a = rgba[..., 3:4]
    pm = np.concatenate([rgba[..., :3] * a, a], -1)
    chans = [to_f(Image.fromarray((np.clip(pm[..., i], 0, 1) * 255 + 0.5).astype(np.uint8)).resize(size, Image.LANCZOS))
             for i in range(4)]
    out = np.stack(chans, -1)
    a2 = out[..., 3:4]
    rgb = np.where(a2 > 1e-3, out[..., :3] / np.maximum(a2, 1e-3), 0)
    return np.concatenate([np.clip(rgb, 0, 1), a2], -1)


def resize_float(arr, size):
    """Lanczos für eine Gleitkommaebene über 16 bit."""
    im = Image.fromarray(((np.clip(arr, -1, 1) * 0.5 + 0.5) * 65535).astype(np.uint16))
    return np.asarray(im.resize(size, Image.LANCZOS)).astype(np.float32) / 65535.0 * 2 - 1


def close_eyes(cell):
    """Blinzeln für die Dreiviertelansicht: Auge (dunkler Fleck samt Glanzpunkt) mit dem Fell des dunklen
    Augenstreifens übermalen und ein Lid als dunklen Strich setzen. Zellkoordinaten, Quellauflösung."""
    out = cell.copy()
    lum = out[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    yy, xx = np.mgrid[0:out.shape[0], 0:out.shape[1]].astype(np.float32)
    for (cx, cy, r) in EYES:
        d = np.hypot(xx - cx, yy - cy)
        ring = (d > r + 1.5) & (d < r + 5) & (lum < 0.40) & (out[..., 3] > 0.9)
        fur = np.median(out[ring][:, :3], axis=0)
        disk = np.clip((r + 0.8 - d) / 1.6, 0, 1)[..., None]
        out[..., :3] = out[..., :3] * (1 - disk) + fur * disk
        lid = np.clip(1.4 - np.abs(yy - (cy + 0.6 + 0.04 * (xx - cx) ** 2 / r)) , 0, 1) * (np.abs(xx - cx) < r)
        out[..., :3] = out[..., :3] * (1 - 0.65 * lid[..., None])
    return out


EYES = []   # Mitte und Radius der Augen in der Zelle "turn" (aus SOURCES)


def load_sheet(path, size=(1536, 1024)):
    """Rohbild ins Layoutraster bringen: gleichmäßig auf die Layouthöhe skalieren (vormultipliziert) und mittig
    setzen; Magenta-Reste vom Freistellen entfernen."""
    im = Image.open(path).convert("RGBA")
    if im.size != size:
        w = round(im.width * size[1] / im.height)
        scaled = im.convert("RGBa").resize((w, size[1]), Image.LANCZOS)
        canvas = Image.new("RGBa", size)
        canvas.paste(scaled, ((size[0] - w) // 2, 0))
        im = canvas.convert("RGBA")
    a = to_f(im)
    rgb = a[..., :3]
    spill = np.clip(np.minimum(rgb[..., 0], rgb[..., 2]) - rgb[..., 1], 0, 1)
    rgb[..., 0] -= spill
    rgb[..., 2] -= spill
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", choices=sorted(SOURCES), default="walk3")
    raw, ground_src, eyes = SOURCES[ap.parse_args().src]
    EYES[:] = eyes
    lay = json.loads(LAYOUT.read_text())["walk"]
    src = load_sheet(raw)
    cells = []
    for c in lay["cells"]:
        cells.append((c["name"], src[c["y"]:c["y"] + c["h"], c["x"]:c["x"] + c["w"]]))
        if c["name"] == "turn":
            cells.append(("turn_blink", close_eyes(cells[-1][1])))
    names = [n for n, _ in cells]
    sheet = np.zeros((FH, FW * len(names), 4), np.float32)
    nsheet = np.zeros((FH, FW * len(names), 4), np.float32)
    soles = {}
    for i, (name, cell) in enumerate(cells):
        cut = cell[Y0:Y1, X0:X1].copy()
        alpha = cut[..., 3]
        alpha = np.where(alpha < 0.04, 0, alpha)
        rgb, _ = noir_tone(cut[..., :3])
        n = pillow_normals(alpha)
        small = premul_resize(np.concatenate([rgb, alpha[..., None]], -1), (FW, FH))
        nsm = np.stack([resize_float(n[..., k], (FW, FH)) for k in range(3)], -1)
        nsm /= np.maximum(np.linalg.norm(nsm, axis=-1, keepdims=True), 1e-4)
        sheet[:, i * FW:(i + 1) * FW] = small
        nsheet[:, i * FW:(i + 1) * FW, :3] = nsm * 0.5 + 0.5
        nsheet[:, i * FW:(i + 1) * FW, 3] = small[..., 3]
        rows = np.where((small[..., 3] > 0.5).any(1))[0]
        soles[name] = int(rows.max())

    Image.fromarray((np.clip(sheet, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(OUT / "badger.png")
    Image.fromarray((np.clip(nsheet, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(OUT / "badger_n.png")

    root_src = 307 / 2 + 0.012 * lay["px_per_m"]             # Ursprung des Rigs (pose_layout.py: CX = -0,012)
    info = {
        "frames": names, "frame_w": FW, "frame_h": FH, "scale": F,
        "anchor": [round((root_src - X0) * F, 2), round((ground_src - Y0) * F, 2)],
        "step_px": round(STEP_SRC * F, 3),
        "px_per_m": round(lay["px_per_m"] * F * 1.0, 2),
        "sole_rows": soles,
        "source": str(raw.relative_to(ROOT)),
    }
    (OUT / "badger.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info))


if __name__ == "__main__":
    main()
