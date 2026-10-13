#!/usr/bin/env python3
"""Prüft die ganze Dialogszene in einer eigenen Aufnahme (ergänzt measure.py, das nur die Figur misst).

    .venv/bin/python styles/lebendes-portraet/tools/check_scene.py

Misst in 180 Bildern (30 fps, wie capture.py):
  - Aussetzer der Aufnahme: Movie Maker schreibt unter Last gelegentlich dasselbe Bild mehrfach
    (godot.log meldet dann weniger als 180 aufgenommene Bilder); identische Folgebilder werden gezählt
  - Schalende: mittlere Bildänderung im Bereich des Schalendes in den ersten 12 Bildern gegen den Rest
    (ohne settle() schwang es aus der Senkrechten ein: bis 8,9 Stufen je Bild)
  - Leuchtturmstrahl: größter Helligkeitssprung entlang der Strahlachse im Posterbild (harte Kante?)
  - Wasser: Standardabweichung der Helligkeit je Wasserpixel über alle Bilder (Anteil still/bewegt),
    ohne die Flächen unter Textfeld und Antworten
Schreibt assets/scene_check.json und assets/scene_motion.png (Bewegungskarte, verstärkt).
"""
import json, pathlib, re, subprocess, sys, tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
DEMO = HERE / "demo"
N = 180
SCARF_BOX = (330, 400, 450, 600)   # x0, y0, x1, y1 im Bild (Schalende)
POSTER = 108                        # capture.py: --poster-at 0.6
UI_BOXES = [(606, 575, 1262, 720), (878, 438, 1262, 576)]


def main():
    lay = json.loads((DEMO / "art" / "bg_layout.json").read_text())
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
        r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                            "--write-movie", str(td / "f.png"), "--fixed-fps", "30", "--quit-after", str(N)],
                           capture_output=True, text=True)
        log = r.stdout + r.stderr
        if re.search(r"\bERROR\b|SCRIPT ERROR", log):
            sys.exit("Godot-Fehler: " + [l for l in log.splitlines() if "ERROR" in l][0])
        m = re.search(r"(\d+) frames at", log)
        recorded = int(m.group(1)) if m else -1
        frames = [np.asarray(Image.open(p).convert("RGB"), np.int16) for p in sorted(td.glob("f*.png"))]
    dupes = [i for i in range(1, len(frames)) if np.array_equal(frames[i], frames[i - 1])]

    x0, y0, x1, y1 = SCARF_BOX
    sc = [float(np.abs(frames[i][y0:y1, x0:x1] - frames[i - 1][y0:y1, x0:x1]).mean()) for i in range(1, len(frames))]

    lx, ly = lay["lamp"]
    # rechts von der Parameterleiste (endet bei x = 722) bis kurz vor den Lampenschein
    row = frames[POSTER][ly, max(0, lx - 400):lx - 60].astype(np.float32).mean(-1)
    beam_step = float(np.abs(np.diff(row)).max())

    lum = np.stack([f.mean(-1).astype(np.float32) for f in frames])
    std = lum.std(0)
    water = np.asarray(Image.open(DEMO / "art" / "bg_masks.png").convert("RGB"))[..., 0] > 128
    for bx0, by0, bx1, by1 in UI_BOXES:
        water[by0:by1, bx0:bx1] = False
    Image.fromarray(np.clip(std * 20, 0, 255).astype(np.uint8)).save(HERE / "assets" / "scene_motion.png")

    res = {
        "frames": len(frames), "recorded_by_godot": recorded, "duplicate_frames": dupes,
        "scarf_change_first12_max": round(max(sc[:12]), 2), "scarf_change_rest_median": round(float(np.median(sc[12:])), 2),
        "scarf_change_rest_max": round(max(sc[12:]), 2),
        "beam_axis_max_step_poster": round(beam_step, 1),
        "water_px_visible": int(water.sum()),
        "water_still_share_std_lt_0_5": round(float((std[water] < 0.5).mean()), 3),
        "water_moving_share_std_gt_1_5": round(float((std[water] > 1.5).mean()), 3),
        "water_std_median": round(float(np.median(std[water])), 2),
    }
    (HERE / "assets" / "scene_check.json").write_text(json.dumps(res, indent=1))
    for k, v in res.items():
        print(f"{k}: {v}")
    if dupes or recorded != N:
        print(f"WARNUNG: Aufnahme mit Aussetzern ({recorded} von {N} Bildern aufgenommen, {len(dupes)} identische Folgebilder) – erneut laufen lassen")


if __name__ == "__main__":
    main()
