#!/usr/bin/env python3
"""Misst, ob die Boote gezeichnet werden und ob ihr Schaukeln im 320x200-Bild sichtbar ist.

  .venv/bin/python styles/polygon-kino/scripts/measure_boats.py [--seconds 6]

1. Polygone je Boot und Einstellung aus data/scenes.json (Marken boatA/boatB), Umriss (mit Mast und Leinen),
   sichtbare Pixel in Ruhelage (Ebene "near" davor, ohne Dachs) und größte Eckverschiebung bei vollem Ausschlag
   (Drehung "rock" und Heben "heave" aus ART in main.gd).
2. Zwei Aufnahmen in nativer Auflösung: normal und mit --probe-norock (Boote ruhig). Alles andere läuft gleich,
   jeder abweichende Pixel stammt also vom Schaukeln. Je Bild: abweichende Pixel; dazu die Zahl verschiedener
   Bootslagen je Einstellung (Muster der geänderten Pixel im Ausschnitt um jedes Boot; die ruhige Lage zählt
   als eine).
Temporäre Bilder liegen in einem Ordner unter $TMPDIR und werden gelöscht.
Ergebnis: assets/boat_measure.json
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import polyvec as pv  # noqa: E402

ENTRY = pathlib.Path(__file__).resolve().parent.parent


def movie(td, name, frames, extra):
    out = td / name
    out.mkdir()
    subprocess.run(["godot", "--path", str(ENTRY / "demo"), "--position", "20000,20000", "--write-movie",
                    str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames), "--"] + extra,
                   capture_output=True)
    return [np.asarray(Image.open(f).convert("RGB")).astype(np.int16) for f in sorted(out.glob("f*.png"))]


def main():
    seconds = float(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 6.0
    data = json.load(open(ENTRY / "demo/data/scenes.json"))
    src = (ENTRY / "demo/main.gd").read_text()
    cut = float(src.split("const CUT := ")[1].split()[0])
    res = {"boats": {}}
    boxes = {}
    amp = [(float(r), float(h)) for r, h in re.findall(r'"rock": ([0-9.]+), "heave": ([0-9.]+)', src)]
    for si, (key, sd) in enumerate(data["shots"].items()):
        rock, heave = amp[si]
        for b in ("boatA", "boatB"):
            recs = [r for r in sd["layers"]["boats"] if data["tags"][r[1]] == b]
            xs = [v for r in recs for v in r[2][0::2]]
            ys = [v for r in recs for v in r[2][1::2]]
            box = [int(min(xs)), int(min(ys)), int(max(xs)) + 1, int(max(ys)) + 1] if recs else None
            boxes[(key, b)] = box
            # sichtbare Bootspixel in Ruhelage: Boot gerastert, darüber die Ebene "near" (ohne Dachs)
            img = np.full((148, 320), -1, np.int32)
            for r in recs:
                pv.raster(img, list(zip(r[2][0::2], r[2][1::2])), 1)
            for r in sd["layers"]["near"]:
                pv.raster(img, list(zip(r[2][0::2], r[2][1::2])), 0)
            ax, ay = (round(v) for v in sd["anchors"]["BoatA" if b == "boatA" else "BoatB"])
            a = np.radians(rock)
            shift = max((np.hypot(x - ax, y - ay) * 2 * np.sin(a / 2) for x, y in zip(xs, ys)), default=0.0) + heave
            res["boats"][f"{key}_{b}"] = {"polygons": len(recs), "points": len(xs),
                                          "box_px": box, "size_px": [box[2] - box[0], box[3] - box[1]] if box else None,
                                          "visible_px": int((img == 1).sum()),
                                          "rock_deg": rock, "heave_px": heave,
                                          "max_vertex_shift_px": round(float(shift), 2)}
        res["boats"][f"{key}_untagged"] = sum(1 for r in sd["layers"]["boats"]
                                              if data["tags"][r[1]] not in ("boatA", "boatB"))
    td = pathlib.Path(tempfile.mkdtemp(prefix="pk_boats_"))
    n = int(seconds * 30)
    rock = movie(td, "rock", n, [])
    calm = movie(td, "calm", n, ["--probe-norock"])
    per = {"A": [], "B": []}
    crops = {k: set() for k in boxes}
    for i, (a, b) in enumerate(zip(rock, calm)):
        key = "A" if i / 30.0 < cut else "B"
        per[key].append(int((np.abs(a - b).max(axis=2) > 0).sum()))
        for (k, bn), box in boxes.items():
            if k == key and box:
                x0, y0, x1, y1 = box
                sl = (slice(max(y0 - 3, 0), y1 + 3), slice(max(x0 - 3, 0), x1 + 3))
                ca, cb = a[sl], b[sl]                     # nur die vom Schaukeln geänderten Pixel zählen
                crops[(k, bn)].add(np.where((ca != cb).any(axis=2)[..., None], ca, -1).tobytes())
    res["rocking"] = {}
    for key, v in per.items():
        if v:
            res["rocking"][key] = {"frames": len(v), "frames_changed": sum(c > 0 for c in v),
                                   "changed_px_mean": round(float(np.mean(v)), 1), "changed_px_max": max(v),
                                   "distinct_boat_images": {bn: len(crops[(key, bn)]) for bn in ("boatA", "boatB")}}
    shutil.rmtree(td)
    (ENTRY / "assets/boat_measure.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
