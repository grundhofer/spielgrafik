#!/usr/bin/env python3
"""Ornamentrahmen (gpt-image, assets/raw/frame.png) für den 1280x720-Bildschirm aufbereiten.

    .venv/bin/python styles/jugendstil/scripts/build_frame.py

Das Bildmodell hat die Layout-Skizze nur ungefähr befolgt: Der Rahmen füllt die Zeilen 0..966 (statt 80..944),
darunter ist das Bild durchsichtig. Damit nichts verzerrt wird, wird der Rahmen gleichmäßig auf 720 Zeilen
verkleinert (Faktor 720/967) und links und rechts mit dem Grund des Rahmens (Petrol) auf 1280 Breite ergänzt;
am Außenrand läuft eine Gold- und eine Konturlinie wie am Fensterrand.
Gemessen und in frame.json geschrieben: Fenster (durchsichtige Fläche um die Bildmitte) als Rahmen in
Bildschirmkoordinaten samt Bogenkante je Spalte, Textfeld (cremefarbene Fläche unten).
Goldmaske für den Schimmer-Shader: Pixel im Goldton (Farbton 30..50°, Sättigung > 0,45, Helligkeit > 0,55).

Ausgang (assets/ und demo/art/): frame.png (1280x720 RGBA), frame_gold.png (L), frame.json
"""
import json, pathlib
from collections import deque
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTS = [ROOT / "assets", ROOT / "demo/art"]
SW, SH = 1280, 720


def flood(trans, seed):
    h, w = trans.shape
    out = np.zeros_like(trans)
    q = deque([seed])
    out[seed] = True
    while q:
        y, x = q.popleft()
        for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= yy < h and 0 <= xx < w and trans[yy, xx] and not out[yy, xx]:
                out[yy, xx] = True
                q.append((yy, xx))
    return out


def downscale_rgba(arr, size):
    f = arr.astype(np.float32) / 255.0
    a = f[..., 3:4]
    pm = np.concatenate([f[..., :3] * a, a], -1)
    ch = [np.asarray(Image.fromarray(pm[..., k], "F").resize(size, Image.LANCZOS)) for k in range(4)]
    al = np.clip(ch[3], 0, 1)
    col = np.stack(ch[:3], -1) / np.maximum(al[..., None], 1e-4)
    col[al < 1e-3] = 0
    return (np.concatenate([np.clip(col, 0, 1), al[..., None]], -1) * 255 + 0.5).astype(np.uint8)


def main():
    raw = np.asarray(Image.open(ROOT / "assets/raw/frame.png").convert("RGBA")).copy()
    a = raw[..., 3]
    raw[..., 3] = np.where(a >= 250, 255, a)          # Codex liefert höchstens 254
    rows = np.flatnonzero((raw[..., 3] > 128).any(1))
    top, bot = int(rows.min()), int(rows.max())       # 0 .. 966
    frame = raw[top:bot + 1]
    h, w = frame.shape[:2]
    f = SH / h
    fw = round(w * f)
    small = downscale_rgba(frame, (fw, SH))
    ox = (SW - fw) // 2

    # Grund des Rahmens: häufigste dunkle Petrolfarbe in den Seitenleisten
    side = frame[300:700, 5:60].reshape(-1, 4)
    side = side[side[:, 3] == 255][:, :3]
    q = (side // 8).astype(np.int32)
    keys, cnt = np.unique(q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2], return_counts=True)
    k = keys[cnt.argmax()]
    sel = side[(q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2]) == k]
    ground = tuple(int(v) for v in np.median(sel, 0))
    # Konturfarbe (dunkelste häufige Farbe) und Gold aus dem Rahmen
    fl = frame.reshape(-1, 4)
    fl = fl[fl[:, 3] == 255][:, :3].astype(np.int32)
    lum = fl.sum(1)
    key = tuple(int(v) for v in np.median(fl[lum < np.percentile(lum, 3)], 0))
    hsv = np.asarray(Image.fromarray(frame[..., :3]).convert("HSV")).astype(np.float32) / 255.0
    gold_m = ((hsv[..., 0] > 30 / 360) & (hsv[..., 0] < 50 / 360) & (hsv[..., 1] > 0.45) & (hsv[..., 2] > 0.55)
              & (frame[..., 3] > 200))
    gold = tuple(int(v) for v in np.median(frame[..., :3][gold_m], 0))

    canvas = np.zeros((SH, SW, 4), np.uint8)
    canvas[...] = ground + (255,)
    # Außenlinie: 2 px Kontur ganz außen, 2 px Gold, dann Grund
    canvas[:, :2, :3] = key
    canvas[:, -2:, :3] = key
    canvas[:, 4:6, :3] = gold
    canvas[:, -6:-4, :3] = gold
    # Rahmenbild einsetzen (über den Grund geblendet, damit der Fensterbereich durchsichtig bleibt)
    # Fensterfläche = durchsichtige Fläche, die mit der Bildmitte zusammenhängt, um 2 px erweitert, damit der
    # weiche Alpharand des Rahmenbilds dazugehört. Dort bleibt das Alpha des Rahmenbilds (Szene scheint durch),
    # überall sonst wird über den Grund geblendet und deckend gemacht (z. B. die durchsichtigen Zeilen unten).
    body = canvas[:, ox:ox + fw].astype(np.float32)
    sm = small.astype(np.float32)
    al = sm[..., 3:4] / 255.0
    core = flood(small[..., 3] < 128, (SH // 2, fw // 2))
    win = core.copy()
    for _ in range(2):
        g = win.copy()
        g[1:] |= win[:-1]; g[:-1] |= win[1:]; g[:, 1:] |= win[:, :-1]; g[:, :-1] |= win[:, 1:]
        win = g
    rgb = np.where(win[..., None], sm[..., :3], sm[..., :3] * al + body[..., :3] * (1 - al))
    canvas[:, ox:ox + fw, :3] = np.clip(rgb + 0.5, 0, 255).astype(np.uint8)
    canvas[:, ox:ox + fw, 3] = np.where(win, small[..., 3], 255).astype(np.uint8)
    win = core

    # Fenster messen (Bildschirmkoordinaten)
    wy, wx = np.nonzero(win)
    wx = wx + ox
    x0, x1, y0, y1 = int(wx.min()), int(wx.max()), int(wy.min()), int(wy.max())
    arch = []
    for x in range(x0, x1 + 1):
        col = np.flatnonzero(win[:, x - ox])
        arch.append(int(col.min()) if len(col) else y1)
    # Textfeld: cremefarbene Fläche unten
    c = canvas[..., :3].astype(np.int32)
    cream = (c[..., 0] > 225) & (c[..., 1] > 205) & (c[..., 2] > 165) & (canvas[..., 3] == 255)
    cream[: y1 + 5] = False
    py, px = np.nonzero(cream)
    rows_full = [y for y in range(int(py.min()), int(py.max()) + 1) if cream[y].sum() > 0.8 * (px.max() - px.min())]
    panel = {"x0": int(np.percentile(px, 1)), "x1": int(np.percentile(px, 99)),
             "y0": int(min(rows_full)), "y1": int(max(rows_full))}
    panel_col = tuple(int(v) for v in np.median(c[cream], 0))

    gm = np.zeros((SH, SW), np.uint8)
    hsv_s = np.asarray(Image.fromarray(canvas[..., :3]).convert("HSV")).astype(np.float32) / 255.0
    g = ((hsv_s[..., 0] > 30 / 360) & (hsv_s[..., 0] < 50 / 360) & (hsv_s[..., 1] > 0.45) & (hsv_s[..., 2] > 0.55)
         & (canvas[..., 3] > 200))
    gm[g] = 255

    info = {"scale": f, "offset_x": ox, "src_rows": [top, bot], "window": {"x0": x0, "x1": x1, "y0": y0, "y1": y1},
            "arch_top": arch, "panel": panel, "panel_colour": panel_col, "ground": ground, "key": key, "gold": gold,
            "gold_share": round(float(g.mean()), 4)}
    for d in OUTS:
        d.mkdir(parents=True, exist_ok=True)
        Image.fromarray(canvas, "RGBA").save(d / "frame.png")
        Image.fromarray(gm, "L").save(d / "frame_gold.png")
        (d / "frame.json").write_text(json.dumps(info, indent=1))
    print("Faktor", round(f, 4), "Breite", fw, "Versatz", ox)
    print("Fenster", info["window"], "Textfeld", panel, "Creme", panel_col)
    print("Grund", ground, "Kontur", key, "Gold", gold, "Goldanteil", info["gold_share"])


if __name__ == "__main__":
    main()
