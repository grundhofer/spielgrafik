"""Prüft die Godot-Demo gegen die gebackenen Knotenbilder und die 256-Farben-Palette.

    .venv/bin/python styles/vorgerendert-diashow/scripts/check_demo.py OUT_DIR [--method forward_plus|mobile|gl_compatibility]
    .venv/bin/python styles/vorgerendert-diashow/scripts/check_demo.py OUT_DIR --compare OTHER_DIR

1. Nimmt die Demo mit Godots Movie Maker in OUT_DIR auf (180 Bilder, 30 fps, Basisauflösung 640×360), sofern dort
   noch keine Bilder liegen.
2. Palette: Jeder Bildpunkt jedes Bildes muss eine Farbe aus demo/nodes/palette.png sein.
3. Wiedergabe: In ruhigen Abschnitten (kein Knotenwechsel) wird das erwartete Knotenbild aus Standbild, Bildfolgen
   und Dachs-Clip in Python zusammengesetzt (gleiche Rechnung wie main.gd) und mit dem Bildausschnitt verglichen.
   Abweichungen dürfen nur unter dem Mauszeiger liegen (Rahmen höchstens 24×24 px).
4. --compare: Anteil abweichender Bildpunkte je Bild gegenüber einer anderen Aufnahme (z. B. anderer Renderer).
Ausgabe als Text; Zeitpunkte aus den Konstanten in demo/main.gd.
"""
import argparse
import json
import pathlib
import re
import subprocess

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
DEMO = STYLE / "demo"
NODES = DEMO / "nodes"
FPS = 30
N = 180
IMG_X, IMG_Y, W, H = 48, 2, 544, 332


def const(src, name):
    m = re.search(rf"const {name} := (\[[^\]]*\]|[-0-9.]+)", src)
    return json.loads(m.group(1))


def record(out, method):
    out.mkdir(parents=True, exist_ok=True)
    if list(out.glob("f*.png")):
        return
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--write-movie", str(out / "f.png"),
           "--fixed-fps", str(FPS), "--quit-after", str(N)]
    if method:
        cmd[1:1] = ["--rendering-method", method]
    r = subprocess.run(cmd, capture_output=True, text=True)
    (out / "godot.log").write_text(r.stdout + r.stderr)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR|WARNING", l)]
    print("Godot-Meldungen:", errs[:5] if errs else "keine")


def frames(d):
    return [np.asarray(Image.open(p).convert("RGB")) for p in sorted(d.glob("f*.png"))]


class Expected:
    def __init__(self, src):
        self.meta = json.loads((NODES / "nodes_meta.json").read_text())
        self.t_badger = const(src, "T_BADGER")
        self.sheets = {}
        for name, m in self.meta["nodes"].items():
            self.sheets[name] = {"base": np.asarray(Image.open(NODES / name / m["base"]).convert("RGB"))}
            for c in m["clips"]:
                self.sheets[name][c["file"]] = np.asarray(Image.open(NODES / name / c["file"]).convert("RGB"))

    def image(self, name, t):
        origin = self.t_badger if name == "steg" else 0.0
        n = int(np.floor((t - origin) * self.meta["fps"] + 1e-4))
        img = self.sheets[name]["base"].copy()
        for c in self.meta["nodes"][name]["clips"]:
            fr, lf = c["frames"], c["loop_from"]
            if c["kind"] == "badger":
                i = max(n, 0)
                if i >= fr:
                    i = lf + (i - lf) % (fr - lf)
            else:
                i = n % fr
            x, y, w, h = c["rect"]
            sh = self.sheets[name][c["file"]]
            img[y:y + h, x:x + w] = sh[(i // c["cols"]) * h:(i // c["cols"] + 1) * h, (i % c["cols"]) * w:(i % c["cols"] + 1) * w]
        return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--method", default=None)
    ap.add_argument("--compare", default=None)
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    record(out, a.method)
    fs = frames(out)
    print(f"{len(fs)} Bilder, {fs[0].shape[1]}×{fs[0].shape[0]}")

    pal = np.asarray(Image.open(NODES / "palette.png").convert("RGB")).reshape(-1, 3)
    pal_key = set((pal[:, 0].astype(np.int64) << 16 | pal[:, 1].astype(np.int64) << 8 | pal[:, 2]).tolist())
    bad, used = 0, set()
    for f in fs:
        k = (f[..., 0].astype(np.int64) << 16 | f[..., 1].astype(np.int64) << 8 | f[..., 2]).ravel()
        u = set(np.unique(k).tolist())
        used |= u
        bad += len(u - pal_key)
    print(f"Palette: {len(used)} verschiedene Farben in allen Bildern, {bad} Farben außerhalb der Palette")
    band = np.concatenate([f[IMG_Y + H:, :].reshape(-1, 3) for f in fs])
    print("Textzeile: verschiedene Farben", len(np.unique(band, axis=0)))

    src = (DEMO / "main.gd").read_text()
    dis, zoom = const(src, "DISSOLVE"), const(src, "ZOOM")
    ex = Expected(src)
    windows = [("kai", 0.0, dis[0]), ("steg", dis[1], zoom[0]), ("tuer", zoom[1], N / FPS)]
    for shift in (0, 1):
        worst, total, checked = 0, 0, 0
        for name, t0, t1 in windows:
            for k, f in enumerate(fs):
                t = (k + shift) / FPS
                if not (t0 + 1e-6 <= t < t1 - 1e-6):
                    continue
                got = f[IMG_Y:IMG_Y + H, IMG_X:IMG_X + W]
                diff = np.any(got != ex.image(name, t), axis=-1)
                checked += 1
                if diff.any():
                    ys, xs = np.nonzero(diff)
                    box = (xs.max() - xs.min() + 1, ys.max() - ys.min() + 1)
                    worst = max(worst, max(box))
                    total += int(diff.sum())
        print(f"Wiedergabe (Bild k zeigt t = (k+{shift})/30): {checked} Bilder geprüft, abweichende Pixel gesamt "
              f"{total}, größter Abweichungsrahmen {worst} px (Mauszeiger ≤ 24)")

    if a.compare:
        other = frames(pathlib.Path(a.compare))
        sh = [float(np.any(x != y, axis=-1).mean()) for x, y in zip(fs, other)]
        mad = [float(np.abs(x.astype(int) - y.astype(int)).mean()) for x, y in zip(fs, other)]
        print(f"Vergleich mit {a.compare}: abweichende Pixel je Bild max {max(sh):.4%}, Mittel {np.mean(sh):.4%}; "
              f"mittlere Abweichung max {max(mad):.3f} Stufen")


if __name__ == "__main__":
    main()
