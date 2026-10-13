#!/usr/bin/env python3
"""Misst das lebende Porträt in den gerenderten Bildern (Godot, Messmodus: nur Figur vor Magenta).

    .venv/bin/python styles/lebendes-portraet/tools/measure.py [--frames DIR]

Prüft je Bild (180 Bilder, 30 fps):
  - Umriss: Mützenoberkante und Kopfmitte, Taillenränder unten; größter Sprung je Bild (soll ≤ 1,5 px sein,
    alles darüber wäre ein Zucken, kein Bewegen)
  - Löcher: Hintergrund-Pixel innerhalb des Umrisses (Lücken zwischen Ebenen bei Verformung)
  - Augen und Mund: Abweichung vom Ruhebild in den Bereichen aus assets/rig.json (Blinzeln, Sprechen)
  - Ruhe außerhalb: Pixel außerhalb Kopf/Schal, die sich mehr als 24 Stufen ändern (Körper soll nur atmen)
Schreibt assets/measure.json und gibt eine Zusammenfassung aus.
"""
import argparse, json, pathlib, re, subprocess, sys, tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import imgops as ops  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent.parent
DEMO = HERE / "demo"


def render(out, n=180, extra=()):
    # neue oder geänderte PNGs erst importieren (ohne Editor nutzt Godot sonst den alten Import)
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(n), "--", "--measure", *extra]
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
    if errs:
        sys.exit("Godot-Fehler: " + errs[0])
    return sorted(out.glob("f*.png"))


def figure_mask(im):
    a = np.asarray(im.convert("RGB"), np.int16)
    d = np.abs(a[..., 0] - 255) + a[..., 1] + np.abs(a[..., 2] - 255)
    return d > 60, a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames")
    a = ap.parse_args()
    rig = json.loads((HERE / "assets" / "rig.json").read_text())
    k = rig["scale"]
    m = re.search(r'\[node name="Portrait".*?\nposition = Vector2\(([-\d.]+), ([-\d.]+)\)', (DEMO / "main.tscn").read_text(), re.S)
    pos = np.array([float(m.group(1)), float(m.group(2))]) if m else np.zeros(2)

    def rect(r, pad=0):
        x0, y0, x1, y1 = r
        return [int(x0 * k + pos[0]) - pad, int(y0 * k + pos[1]) - pad, int(x1 * k + pos[0]) + pad, int(y1 * k + pos[1]) + pad]

    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        for sub in ("main", "noblink", "nomouth"):
            (td / sub).mkdir()
        frames = render(td / "main")
        imgs = [figure_mask(Image.open(p)) for p in frames]
        ref_eye = [figure_mask(Image.open(p))[1] for p in render(td / "noblink", extra=("--noblink",))]
        ref_mouth = [figure_mask(Image.open(p))[1] for p in render(td / "nomouth", extra=("--nomouth",))]
    masks = [mm for mm, _ in imgs]
    rgbs = [c for _, c in imgs]
    H, W = masks[0].shape
    eyes = [rect(rig["face"][e]["rect"], 6) for e in ("eye_l", "eye_r")]
    mouth = rect(rig["face"]["mouth"]["rect"], 6)
    head_top, head_cx, waist_l, waist_r, holes = [], [], [], [], []
    y_w = H - 30
    for mm in masks:
        ys, xs = np.nonzero(mm)
        top = ys.min()
        head_top.append(int(top))
        band = mm[top:top + 60]
        bx = np.nonzero(band.any(0))[0]
        head_cx.append(float((bx.min() + bx.max()) / 2))
        row = np.nonzero(mm[y_w])[0]
        waist_l.append(int(row.min()) if len(row) else -1)
        waist_r.append(int(row.max()) if len(row) else -1)
        filled = ops.fill_holes(mm)
        holes.append(int((filled & ~mm).sum()))

    def jumps(v):
        v = np.asarray(v, float)
        return float(np.abs(np.diff(v)).max()) if len(v) > 1 else 0.0

    def region_dev(r, refs):
        x0, y0, x1, y1 = r
        return [float(np.abs(c[y0:y1, x0:x1].astype(np.float32) - rf[y0:y1, x0:x1]).mean()) for c, rf in zip(rgbs, refs)]

    def outside_dev(refs, rects):
        out = []
        for c, rf in zip(rgbs, refs):
            d = np.abs(c.astype(np.int16) - rf).max(-1) > 24
            for x0, y0, x1, y1 in rects:
                d[y0:y1, x0:x1] = False
            out.append(int(d.sum()))
        return out

    # Vergleichsschalter: gleiche Bewegung ohne Blinzeln bzw. ohne Mund – Unterschied = nur Lid bzw. Mund
    eye_dev = [max(a, b) for a, b in zip(region_dev(eyes[0], ref_eye), region_dev(eyes[1], ref_eye))]
    mouth_dev = region_dev(mouth, ref_mouth)
    big = lambda r: [r[0] - 20, r[1] - 30, r[2] + 20, r[3] + 30]
    eye_leak = outside_dev(ref_eye, [big(e) for e in eyes])
    mouth_leak = outside_dev(ref_mouth, [big(mouth)])
    # Flimmern: Pixel, die sich von Bild zu Bild um mehr als 40 Stufen ändern und im Bild danach zurückspringen
    flicker = []
    for i in range(1, len(rgbs) - 1):
        d1 = np.abs(rgbs[i].astype(np.int16) - rgbs[i - 1]).max(-1)
        d2 = np.abs(rgbs[i + 1].astype(np.int16) - rgbs[i]).max(-1)
        back = np.abs(rgbs[i + 1].astype(np.int16) - rgbs[i - 1]).max(-1)
        flicker.append(float(((d1 > 40) & (d2 > 40) & (back < 12) & masks[i]).mean()))
    res = {
        "frames": len(frames),
        "portrait_position": pos.tolist(),
        "head_top_range": [min(head_top), max(head_top)], "head_top_max_jump": jumps(head_top),
        "head_cx_range": [min(head_cx), max(head_cx)], "head_cx_max_jump": jumps(head_cx),
        "waist_row": y_w, "waist_l_range": [min(waist_l), max(waist_l)], "waist_r_range": [min(waist_r), max(waist_r)],
        "waist_max_jump": max(jumps(waist_l), jumps(waist_r)),
        "holes_max_px": max(holes), "holes_rest_px": holes[0],
        "eye_dev_max": round(max(eye_dev), 2), "eye_closed_frames": [i for i, v in enumerate(eye_dev) if v > max(eye_dev) * 0.5],
        "mouth_dev_max": round(max(mouth_dev), 2), "mouth_active_frames": int(sum(v > 4 for v in mouth_dev)),
        "flicker_share_max": round(max(flicker), 5) if flicker else 0,
        "eye_change_outside_px_max": max(eye_leak), "mouth_change_outside_px_max": max(mouth_leak),
        "holes_worst_frame": int(np.argmax(holes)),
        "series": {"head_top": head_top, "head_cx": [round(v, 1) for v in head_cx], "waist_l": waist_l, "waist_r": waist_r,
                   "eye_dev": [round(v, 2) for v in eye_dev], "mouth_dev": [round(v, 2) for v in mouth_dev], "holes": holes},
    }
    (HERE / "assets" / "measure.json").write_text(json.dumps(res, indent=1))
    for kk, v in res.items():
        if kk != "series":
            print(f"{kk}: {v}")


if __name__ == "__main__":
    main()
