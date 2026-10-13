"""Misst, wie deutlich das Tanzen im Takt im Bild steht (Vergleichsschalter, PIPELINE.md → Blender/Effekte).

Rendert die Demo zweimal ohne Filmabzug (--no-film), einmal normal und einmal mit --no-dance (Requisiten stehen
still, Boote ohne Schaukeln), und zählt je Bild den Anteil der Pixel, die sich um mehr als 24 Tonwerte
unterscheiden: im ganzen Bild und je Requisite (Rechteck um die Requisite: deckender Teil der Textur in
Bildschirmlage, seitlich um Biegeweite + 2 px und oben um die Stauchung erweitert, aus assets/scene.json). Dazu
ein Prüfbild mit den Requisiten in beiden Neigungen (Tick 66 und 72) nebeneinander: assets/check/dance_lean.png.
Ergebnis: assets/measure_dance.json

    .venv/bin/python styles/gummischlauch/scripts/measure_dance.py
"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
DEMO = HERE / "demo"
TMP = pathlib.Path(os.environ.get("GUMMI_TMP", pathlib.Path(tempfile.gettempdir()) / "gummischlauch")) / "probe_dance"


def prop_boxes():
    scene = json.loads((HERE / "assets" / "scene.json").read_text())["props"]
    boxes = {}
    for k, m in scene.items():
        a = np.asarray(Image.open(HERE / "assets" / m["file"]).convert("RGBA"))[..., 3] > 8
        ys, xs = np.nonzero(a)
        ox, oy = m["at"][0] - m["anchor"][0], m["at"][1] - m["anchor"][1]
        mx = abs(m.get("bend", 0.0)) + 2 + (4 if k.startswith("boat") else 0)
        mt = m.get("squash", 0.0) * m["content_h"] + 2
        x0, y0 = max(0, int(ox + xs.min() - mx)), max(0, int(oy + ys.min() - mt))
        x1, y1 = min(1280, int(np.ceil(ox + xs.max() + 1 + mx))), min(720, int(np.ceil(oy + ys.max() + 3)))
        boxes[k] = (x0, y0, x1, y1)
    return boxes


BOXES = prop_boxes()


def render(name, extra):
    out = TMP / name
    out.mkdir(parents=True)
    subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                    "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--",
                    "--no-film"] + extra, capture_output=True)
    return sorted(out.glob("f*.png"))


def main():
    if TMP.exists():
        shutil.rmtree(TMP)
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    a_files = render("dance", [])
    b_files = render("still", ["--no-dance"])
    total, per = [], {k: [] for k in BOXES}
    for fa, fb in zip(a_files, b_files):
        a = np.asarray(Image.open(fa).convert("RGB")).astype(int)
        b = np.asarray(Image.open(fb).convert("RGB")).astype(int)
        ch = np.abs(a - b).max(axis=2) > 24
        total.append(float(ch.mean()))
        for k, (x0, y0, x1, y1) in BOXES.items():
            per[k].append(float(ch[y0:y1, x0:x1].mean()))
    res = {"frames": len(total), "boxes": BOXES, "changed_share_image_mean": round(float(np.mean(total)), 4),
           "changed_share_image_max": round(float(np.max(total)), 4),
           "changed_share_per_prop_mean": {k: round(float(np.mean(v)), 3) for k, v in per.items()},
           "changed_share_per_prop_max": {k: round(float(np.max(v)), 3) for k, v in per.items()}}
    (HERE / "assets" / "measure_dance.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    # Prüfbild: Tick 66 (Neigung eine Seite) und Tick 72 (andere Seite), Bild = 2 × Tick
    chk = HERE / "assets" / "check"
    chk.mkdir(exist_ok=True)
    i1, i2 = Image.open(a_files[132]).convert("RGB"), Image.open(a_files[144]).convert("RGB")
    row = []
    for k in ["cottage", "jetty", "lighthouse", "lantern", "crates"]:
        x0, y0, x1, y1 = BOXES[k]
        row += [i1.crop((x0, y0, x1, y1)), i2.crop((x0, y0, x1, y1))]
    h = max(r.height for r in row)
    sheet = Image.new("RGB", (sum(r.width for r in row) + 6 * len(row), h), (255, 255, 255))
    x = 0
    for r in row:
        sheet.paste(r, (x, 0))
        x += r.width + 6
    sheet.save(chk / "dance_lean.png")
    shutil.rmtree(TMP)


if __name__ == "__main__":
    main()
