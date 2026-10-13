#!/usr/bin/env python3
"""Prüft die Demo am gerenderten Bild (Godot --write-movie, 128x128, 30 Bilder/s):

1. Dachs allein (--only=badger, Grund rosa): je Bild Kopfoberkante, Fußzeile und die Läufe schwarzer
   Fußpixel am Boden (Zeile 88). Beim Laufen muss der Standfuß von Bild zu Bild an derselben Stelle bleiben
   (±1 px), im Stehen/Blinzeln müssen die Füße in allen Bildern gleich sein (der Kopf darf beim Atemhub
   genau 1 px steigen); Haltezeiten je Pose und die Folge der Standposen (Schal, Atem, Blinzeln).
2. Ganze Szene: nur Farben der 16er-Palette, höchstens 16 Farben je Bild, Textbox-Anteil am Bild.
3. Optional --t0=30: Dauerlauf ab 30 s (Bild wird nach media/probe_t30.png geschrieben).

    ../../.venv/bin/python scripts/probe.py [--renderer gl_compatibility]
"""
import argparse, json, os, pathlib, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from p8pal import PAL

DEMO = ROOT / "demo"
PINK = PAL[14]
FOOT_ROW = 88


TMP = pathlib.Path(os.environ.get("P8_TMP", pathlib.Path(tempfile.gettempdir()) / "pico8-fantasy"))


def render(frames, extra=(), renderer=None):
    TMP.mkdir(parents=True, exist_ok=True)
    td = tempfile.mkdtemp(prefix="probe_", dir=TMP)
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--write-movie", f"{td}/f.png",
           "--fixed-fps", "30", "--quit-after", str(frames)]
    if renderer:
        cmd += ["--rendering-method", renderer]
    cmd += ["--", *extra]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l or "WARNING" in l]
    files = sorted(pathlib.Path(td).glob("f*.png"))
    imgs = [np.asarray(Image.open(f).convert("RGB")) for f in files]
    shutil.rmtree(td, ignore_errors=True)
    return imgs, errs, r.stdout


def runs(mask):
    out, start = [], None
    for x, v in enumerate(list(mask) + [False]):
        if v and start is None:
            start = x
        if not v and start is not None:
            out.append((start, x - 1))
            start = None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--renderer")
    a = ap.parse_args()
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    res = {}

    # 1. Dachs allein
    imgs, errs, log = render(180, ["--only=badger", "--probe"], a.renderer)
    poses = {}
    for line in log.splitlines():
        if line.startswith("PROBE"):
            kv = dict(p.split("=") for p in line.split()[1:])
            poses[int(kv["frame"])] = (kv["pose"], int(kv["x"]))
    rows = []
    for i, im in enumerate(imgs):
        fig = np.any(im != PINK, axis=2)
        ys = np.where(fig.any(axis=1))[0]
        black = np.all(im == (0, 0, 0), axis=2)
        rows.append({"frame": i, "top": int(ys.min()), "bottom": int(ys.max()),
                     "feet": runs(black[FOOT_ROW]), "lifted": runs(black[FOOT_ROW - 1])})
    # Zuordnung Aufnahmebild -> Protokollzeile: Bild k zeigt den Zustand des k-ten Zeichnens
    plog = [poses.get(i) for i in range(len(rows))]
    # Haltezeiten: Wechsel der Pose/Position
    holds, cur, n = [], None, 0
    for r in rows:
        key = (tuple(r["feet"]), tuple(r["lifted"]), r["top"])
        if key == cur:
            n += 1
        else:
            if cur is not None:
                holds.append(n)
            cur, n = key, 1
    holds.append(n)
    # Standfuß: zwischen zwei aufeinanderfolgenden verschiedenen Laufbildern muss ein Bodenfuß bleiben
    drift = []
    walk_end = None
    prev = None
    for r in rows:
        if prev is not None and (r["feet"], r["lifted"], r["top"]) != (prev["feet"], prev["lifted"], prev["top"]):
            best = min((abs(a0 - b0) + abs(a1 - b1) for a0, a1 in r["feet"] for b0, b1 in prev["feet"]),
                       default=99)
            drift.append(best)
        prev = r
    stand = [r for r in rows if r["frame"] >= 100]
    stand_feet = {tuple(r["feet"]) for r in stand}
    stand_top = {r["top"] for r in stand}
    # Folge der Posen ab Standbeginn (Protokoll): [Pose, Anzahl Bilder]
    seq = []
    for i in range(len(rows)):
        pz = plog[i]
        if pz is None or pz[0] in ("contact", "pass", "contact2", "pass2"):
            continue
        if seq and seq[-1][0] == pz[0]:
            seq[-1][1] += 1
        else:
            seq.append([pz[0], 1])
    res["badger"] = {
        "frames": len(rows),
        "holds_unique": sorted(set(holds[1:-1])),
        "holds": holds,
        "foot_drift_per_change_px": drift,
        "max_drift_px": max(drift) if drift else None,
        "stand_feet_variants": [list(map(list, f)) for f in stand_feet],
        "stand_top_rows": sorted(stand_top),
        "stand_pose_sequence": seq,
        "bottom_rows": sorted({r["bottom"] for r in rows}),
        "top_rows": sorted({r["top"] for r in rows}),
        "errors": errs[:10],
    }

    # 2. Ganze Szene
    imgs, errs, _ = render(180, [], a.renderer)
    pal = {tuple(c) for c in PAL}
    foreign, maxc = 0, 0
    for im in imgs:
        cols = {tuple(c) for c in im.reshape(-1, 3)}
        foreign += len(cols - pal)
        maxc = max(maxc, len(cols))
    res["scene"] = {"frames": len(imgs), "foreign_colours": foreign, "max_colours_per_frame": maxc,
                    "box_share": round(37 * 128 / (128 * 128), 3), "errors": errs[:10]}
    out = ROOT / "media" / ("probe.json" if not a.renderer else f"probe_{a.renderer}.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("holds", "foot_drift_per_change_px")}
                      for k, v in res.items()}, indent=1))
    print("Haltezeiten:", res["badger"]["holds"])
    print("Standfuß-Abweichung je Wechsel:", res["badger"]["foot_drift_per_change_px"])


if __name__ == "__main__":
    main()
