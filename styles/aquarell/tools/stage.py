#!/usr/bin/env python3
"""Stellt die Assets für die Godot-Demo zusammen (assets/ -> demo/art/) und schreibt demo/art/scene.json mit dem
vollständigen Ablauf der Figur (ein Eintrag je Figurenbild bei 15 Bildern/s: Bogen, Bild, x, Flags).

    .venv/bin/python styles/aquarell/tools/stage.py [--bg auto|ai|3d] [--badger auto|ai|3d]

Hintergrund:  ai = KI-Bild (prep_bg_ai.py: assets/bg_ai_painted.png, scene_ai.json, *_mask_ai.png)
              3d = Blender-Hafen als Aquarell gerechnet (paint_bg.py: assets/bg_3d.png, *_mask_3d.png)
Figur:        ai = KI-Bögen (prep_badger_ai.py: badger_ai_walk.png, badger_ai_stand.png, badger_ai_meta.json)
              3d = Blender-Dachs als Aquarell gerechnet (paint_badger.py: badger_<clip>.png, badger_meta.json)
auto nimmt jeweils ai, wenn die verarbeiteten KI-Dateien vorhanden sind, sonst 3d.
"""
import argparse, json, pathlib, shutil, subprocess, sys

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
A_ = ROOT / "assets"
ART = ROOT / "demo/art"
PY = sys.executable
FPS = 15                 # Figurenbilder je Sekunde (jedes Bild zwei Takte bei 30 fps)
N = 90                   # 6 s
BREATHE = 1              # Flag: Atmen im Shader (gestauchte Höhe um die Fußlinie)


def stance_dx(feet_a, feet_b):
    """Vorschub zwischen zwei Bildern (3D-Figur): Der Fuß, der in beiden Bildern am Boden steht, rutscht in der
    Animation (auf der Stelle) nach hinten; um genau so viel muss die Figur nach vorn."""
    best = None
    for s in "LR":
        ha, hb = feet_a[s]["ankle_y"], feet_b[s]["ankle_y"]
        score = -min(ha, hb)
        d = feet_a[s]["ankle_x"] - feet_b[s]["ankle_x"]
        if best is None or score < best[1]:
            best = (d, score)
    return round(best[0], 3) if best else 0.0


def scene_3d():
    cfg = json.loads((A_ / "raw/bg_passes/cam.json").read_text())
    p = cfg["points"]
    return {"variant": "3d", "lamp": p["LighthouseLight"], "lantern": p["LanternLight"],
            "chimney": p["ChimneySmoke"], "window": p["CottageWindow"], "feet_y": p["walk_left"][1],
            "top": 22.0, "side": 18.0, "bottom": 612.0, "badger_height": 170.0, "stop_x": 380.0,
            "water_band": [376, 480], "window_glow_scale": 0.75, "lantern_glow_scale": 0.6,
            "clouds": [[0, 220.0, 70.0, 9.0, 0.55], [2, 760.0, 120.0, 7.0, 0.5], [1, 1100.0, 60.0, 10.0, 0.45],
                       [3, 480.0, 210.0, 4.5, 0.4], [4, 1000.0, 250.0, 4.0, 0.35]],
            "gulls": [[-40.0, 150.0, 58.0, 0.8, 0.0], [300.0, 96.0, 44.0, 0.6, 0.45]]}


def badger_3d(stop_x):
    """Ablauf der gerechneten 3D-Figur: 5 Laufzyklen, Anhalten, Drehen, Winken, Atmen (Idle)."""
    meta = json.loads((A_ / "badger_meta.json").read_text())
    clips = meta["clips"]
    walk = clips["walk"]["feet"]
    n = len(walk)
    ground = max(f[s]["ankle_y"] for f in walk for s in "LR")
    flat = sorted(walk[i][s]["ankle_x"] - walk[(i + 1) % n][s]["ankle_x"] for i in range(n) for s in "LR"
                  if abs(walk[i][s]["ankle_y"] - ground) < 0.3 and abs(walk[(i + 1) % n][s]["ankle_y"] - ground) < 0.3)
    wdx = flat[len(flat) // 2]
    seq = [walk[-1]] + clips["stop"]["feet"]
    sdx = [stance_dx(seq[i], seq[i + 1]) for i in range(len(seq) - 1)]
    nw = 5 * n
    entries, x = [], 0.0
    for f in range(nw):
        entries.append(["walk", f % n, x, 0])
        x += wdx
    x -= wdx
    for i, d in enumerate(sdx):
        x += d
        entries.append(["stop", i, x, 0])
    for i in range(clips["turn"]["frames"]):
        entries.append(["turn", i, x, 0])
    for i in range(clips["wave"]["frames"]):
        entries.append(["wave", i, x, 0])
    i = 0
    while len(entries) < N:
        entries.append(["idle", i % clips["idle"]["frames"], x, 0])
        i += 1
    shift = stop_x - x
    timeline = [[c, k, int(round(xx + shift)), fl] for c, k, xx, fl in entries[:N]]
    sheets = {c: {"file": f"badger_{c}.png", "hframes": clips[c]["frames"]} for c in clips}
    fp = meta["frame_px"]
    a = np.asarray(Image.open(A_ / "badger_idle.png"))[..., 3] > 128
    ys = np.nonzero(a.any(1))[0]
    return {"source": "3d", "sheets": sheets, "anchor": [fp // 2, int(round(meta["ground_y"]))],
            "height": int(ys.max() - ys.min() + 1), "timeline": timeline,
            "files": [A_ / f"badger_{c}.png" for c in clips]}


def badger_ai(stop_x):
    """Ablauf der KI-Figur: 6 Laufzyklen (48 Bilder, endet auf walk_7), Stehen, Drehen, Vorderansicht, Winken,
    Blinzeln, Sprechen. Fehlende Teile werden übersprungen."""
    meta = json.loads((A_ / "badger_ai_meta.json").read_text())
    names = meta["clips"]["stand"]["names"]
    idx = {n: i for i, n in enumerate(names)}
    wdx = meta["walk_dx"]
    entries, x = [], 0.0
    for f in range(48):
        if f:
            x += wdx[(f - 1) % 8]
        entries.append(["walk", f % 8, x, 0])
    if "stand" in idx:
        x += meta["stand_dx"]
        entries += [["stand", idx["stand"], x, 0]] * 3
    if "front" in idx:
        if "turn" in idx:
            entries += [["stand", idx["turn"], x, 0]] * 2
        seq = ["front"] * 2 + ["wave_raise"] * 2 + ["wave_out"] * 3 + ["wave_in"] * 3 + ["wave_out"] * 3 \
            + ["wave_in"] * 3 + ["wave_out"] * 2 + ["wave_raise"] * 2 + ["front"] * 4 + ["blink"] * 2 + ["front"] * 3 \
            + ["talk"] * 2 + ["front"] + ["talk"] * 2 + ["front"] * 2 + ["talk"] * 2 + ["front"] * 2
        for n in seq:
            n2 = n if n in idx else "front"
            entries.append(["stand", idx[n2], x, BREATHE if n2 in ("front", "blink", "talk") else 0])
    elif "turn" in idx:
        entries += [["stand", idx["turn"], x, BREATHE]] * (N - len(entries))
    while len(entries) < N:
        entries.append(entries[-1])
    shift = stop_x - x
    timeline = [[c, k, int(round(xx + shift)), fl] for c, k, xx, fl in entries[:N]]
    sheets = {"walk": {"file": "badger_walk.png", "hframes": 8},
              "stand": {"file": "badger_stand.png", "hframes": len(names)}}
    return {"source": "ai", "sheets": sheets, "anchor": meta["anchor"], "height": meta["target_height"],
            "timeline": timeline, "names": names,
            "files": {"badger_walk.png": A_ / "badger_ai_walk.png", "badger_stand.png": A_ / "badger_ai_stand.png"}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bg", default="auto", choices=["auto", "ai", "3d"])
    ap.add_argument("--badger", default="auto", choices=["auto", "ai", "3d"])
    a = ap.parse_args()
    bg = a.bg if a.bg != "auto" else ("ai" if (A_ / "bg_ai_painted.png").exists() and (A_ / "scene_ai.json").exists()
                                      else "3d")
    bd = a.badger if a.badger != "auto" else ("ai" if (A_ / "badger_ai_meta.json").exists() else "3d")
    if bg == "ai":
        scene = json.loads((A_ / "scene_ai.json").read_text())
        src, sky, water = A_ / "bg_ai_painted.png", A_ / "sky_mask_ai.png", A_ / "water_mask_ai.png"
    else:
        scene = scene_3d()
        src, sky, water = A_ / "bg_3d.png", A_ / "sky_mask_3d.png", A_ / "water_mask_3d.png"
    subprocess.run([PY, str(ROOT / "tools/finish_bg.py"), str(src), str(A_ / "bg.png"), "--bottom",
                    str(scene["bottom"]), "--top", str(scene["top"]), "--side", str(scene["side"])], check=True)
    B = badger_ai(scene["stop_x"]) if bd == "ai" else badger_3d(scene["stop_x"])
    for d in ("fx", "ui"):
        (ART / d).mkdir(parents=True, exist_ok=True)
    # alte Figurenbögen entfernen (die Varianten haben verschiedene Bögen)
    for f in ART.glob("badger_*.png*"):
        f.unlink()
    shutil.copy2(A_ / "bg.png", ART / "bg.png")
    shutil.copy2(sky, ART / "sky_mask.png")
    shutil.copy2(water, ART / "water_mask.png")
    shutil.copy2(A_ / "paper.png", ART / "paper.png")
    files = B.pop("files")
    if isinstance(files, dict):
        for name, f in files.items():
            shutil.copy2(f, ART / name)
    else:
        for f in files:
            shutil.copy2(f, ART / f.name)
    for d in ("fx", "ui"):
        for f in (A_ / d).glob("*.png"):
            shutil.copy2(f, ART / d / f.name)
    B["scale"] = round(scene["badger_height"] / B["height"], 4) if bd != bg or bd == "ai" else 1.0
    B["fps"] = FPS
    scene["badger"] = B
    scene["variant"] = f"bg {bg}, badger {bd}"
    (ART / "scene.json").write_text(json.dumps(scene, indent=1, ensure_ascii=False))
    xs = [t[2] for t in B["timeline"]]
    print(f"ok: Hintergrund {bg}, Figur {bd}, Maßstab {B['scale']}, x {xs[0]} -> {xs[-1]}, "
          f"{len(B['timeline'])} Figurenbilder")


if __name__ == "__main__":
    main()
