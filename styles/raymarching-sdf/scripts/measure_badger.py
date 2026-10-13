#!/usr/bin/env python3
"""Füße und Kopf des SDF-Dachses in gerenderten Bildern messen (PIPELINE.md → Figuren und Animation).

    .venv/bin/python styles/raymarching-sdf/scripts/measure_badger.py [--cam x,y,z,tx,ty,tz,fov] [--sheet OUT.png]

Nimmt die ganze Demo (180 Bilder, 30 fps) mit der Messmaske auf (main.gd --debug 4: Körper weiß, linker Fuß
rot, rechter Fuß grün, Kopf blau; ohne FXAA und Oberfläche) mit zwei festen Kameras schräg von oben auf den
ganzen Laufweg: von vorn (Kameraseite, rechter Fuß nah) und von hinten (linker Fuß nah). Jeder Fuß wird mit der
Kamera gemessen, der er zugewandt ist; der ferne Fuß ist hinter Bein und Bauch meist verdeckt. Gleichzeitig
liefert --measure je Bild den Schrittplan (Fuß steht / schwingt).

Geprüft wird in Pixeln des 1280×720-Bildes:
  1. Standfuß: Solange ein Fuß laut Plan steht, darf sich sein Pixelrahmen (links, rechts, unten) gegenüber
     dem ersten Bild der Standphase höchstens um 1 px verschieben. Bilder, in denen der Fuß zu weniger als
     95 % sichtbar ist (verdeckt vom anderen Bein oder vom wedelnden Schwanz), werden übersprungen und gezählt.
  2. Stehen: In allen Bildern nach dem letzten Schritt sind die Fußzeilen (unterste Zeile je Fuß) gleich.
  3. Kopf: Der Abstand zwischen dem Schwerpunkt der Kopfmaske (Kopf, Mütze, Augen, Nase) und dem projizierten
     Kopfmittelpunkt aus dem Gelenkplan springt nicht von Bild zu Bild.
"""
import argparse, json, pathlib, re, subprocess, sys, tempfile

import numpy as np
from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"
CAM = "-0.25,2.2,4.3,-0.25,0.3,1.2,36"
CAM_BACK = "-0.25,2.2,-1.9,-0.25,0.3,1.2,36"


def project(cam, p, w=1280, h=720):
    """Bildpunkt (Pixel, 1280×720) wie im Shader: Look-at, +Y oben, vertikaler Bildwinkel."""
    c, t, fov = np.array(cam[:3]), np.array(cam[3:6]), cam[6]
    f = (t - c) / np.linalg.norm(t - c)
    r = np.cross(f, [0, 1, 0]); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    v = np.array(p) - c
    z = v @ f
    th = np.tan(np.radians(fov) / 2)
    return ((v @ r) / z / th / (w / h) * 0.5 + 0.5) * w, (0.5 - (v @ u) / z / th * 0.5) * h


def masks(png):
    a = np.asarray(Image.open(png).convert("RGB")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    red = (r > 160) & (g < 90) & (b < 90)
    green = (g > 160) & (r < 90) & (b < 90)
    blue = (b > 160) & (r < 90) & (g < 90)
    return red, green, blue


def box(m):
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return None
    return {"x0": int(xs.min()), "x1": int(xs.max()), "y1": int(ys.max()), "n": int(len(xs)),
            "cx": float(xs.mean()), "cy": float(ys.mean())}


def render(cam, frames, sheet=""):
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
               "--write-movie", str(td / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames),
               "--", "--debug", "4", "--measure", "--cam", cam]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        log = r.stdout + r.stderr
        errs = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
        recs = {}
        for l in log.splitlines():
            if l.startswith("MEASURE "):
                d = json.loads(l[8:])
                recs[d["frame"]] = d
        pngs = sorted(td.glob("f*.png"))
        rows = []
        for i, p in enumerate(pngs):
            red, green, blue = masks(p)
            rows.append({"i": i, "L": box(red), "R": box(green), "H": box(blue)})
        if sheet:
            pick = [10, 40, 70, 100, 130, 170]
            sh = Image.new("RGB", (640 * 3, 360 * 2))
            for k, i in enumerate(pick):
                if i < len(pngs):
                    sh.paste(Image.open(pngs[i]).convert("RGB").resize((640, 360)), ((k % 3) * 640, (k // 3) * 360))
            sh.save(sheet)
    return rows, recs, errs


def stance(rows, recs, foot, key, off=1):
    """Größte Verschiebung des Fußrahmens innerhalb jeder Standphase (Pixel)."""
    worst, skipped, checked = 0, 0, 0
    phase = []
    for row in rows + [None]:
        rec = recs.get(row["i"] + off) if row else None
        planted = bool(rec) and not rec["feet"][foot][3]
        if planted:
            phase.append(row)
            continue
        if phase:
            maxn = max((q[key]["n"] for q in phase if q[key]), default=0)
            ref = None
            for q in phase:
                b = q[key]
                if b is None or b["n"] < 0.95 * maxn:
                    skipped += 1
                    continue
                if ref is None:
                    ref = b
                    continue
                dev = max(abs(b["x0"] - ref["x0"]), abs(b["x1"] - ref["x1"]), abs(b["y1"] - ref["y1"]))
                worst = max(worst, dev)
                checked += 1
        phase = []
    return worst, checked, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--sheet", default="")
    a = ap.parse_args()
    off = 1   # Bild i zeigt den Zustand nach dem (i+1)-ten _process (Messzeile frame = i + 1)
    front, recs, errs = render(CAM, a.frames, a.sheet)
    back, recs_b, errs_b = render(CAM_BACK, a.frames)
    print(f"{len(front)} + {len(back)} Bilder, {len(recs)} Messzeilen, Godot-Fehler: {len(errs) + len(errs_b)}")
    wr, cr, sr = stance(front, recs, 1, "R", off)
    wl, cl, sl = stance(back, recs_b, 0, "L", off)
    print(f"Standfuß rechts (Kamera vorn): größte Verschiebung {wr} px ({cr} Bilder geprüft, {sr} verdeckt übersprungen)")
    print(f"Standfuß links (Kamera hinten): größte Verschiebung {wl} px ({cl} Bilder geprüft, {sl} verdeckt übersprungen)")
    # Fußzeilen im Stehen: ab dem ersten Bild, nach dem kein Fuß mehr schwingt
    last_swing = max((row["i"] for row in front if (rec := recs.get(row["i"] + off)) and
                      (rec["feet"][0][3] or rec["feet"][1][3])), default=0)
    stand_rows = {}
    for rows, key, name in ((front, "R", "vorn"), (back, "L", "hinten")):
        ys = sorted({row[key]["y1"] for row in rows if row["i"] > last_swing and row[key]})
        stand_rows[key] = ys
        print(f"Stehen ab Bild {last_swing + 1} (t = {(last_swing + 1) / 30:.2f} s): Fußzeilen {key} (Kamera {name}): {ys}")
    # Kopf: Schwerpunkt der Kopfmaske gegen den projizierten Kopfmittelpunkt aus dem Gelenkplan. Der Abstand
    # (Mütze, Schnauze) ändert sich nur langsam; ein Sprung zwischen zwei Bildern wäre ein Fehler.
    cam = [float(v) for v in CAM.split(",")]
    resid = []
    for row in front:
        rec = recs.get(row["i"] + off)
        if not rec or not row["H"]:
            resid.append(None)
            continue
        px = project(cam, rec["head"])
        resid.append((row["H"]["cx"] - px[0], row["H"]["cy"] - px[1]))
    jumps = [max(abs(b[0] - a_[0]), abs(b[1] - a_[1])) for a_, b in zip(resid, resid[1:]) if a_ and b]
    print(f"Kopf: Abstand Maskenschwerpunkt – Kopfmittelpunkt ändert sich je Bild um höchstens {max(jumps):.2f} px "
          f"(Mittel {np.mean(jumps):.2f} px)")
    out = {"stance_max_px": {"L": wl, "R": wr}, "stance_checked": cl + cr, "stance_skipped": sl + sr,
           "stand_from_frame": last_swing + 1, "stand_rows": stand_rows, "head_jitter_max_px": round(max(jumps), 2)}
    print(json.dumps(out))
    for e in (errs + errs_b)[:5]:
        print("  ", e)


if __name__ == "__main__":
    main()
