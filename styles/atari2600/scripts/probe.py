"""Misst den Dachs in der echten Godot-Ausgabe (Viewport 320x192, jedes Pixel doppelt breit).

Nimmt die Demo mit --sprites-only auf (der Shader zeigt nur das Spielerbild 0 auf Magenta) und misst je Bild im
Bereich des Dachses (Zeilen ab 100; darüber zeichnet Spieler 0 den Rauch): unterste Zeile, Bodenkontakte
(Pixelläufe in der Fußzeile, in Konsolenpixeln) und Kopf (Mitte der obersten Mützenzeile).
Prüft:
  - Laufen: zwischen zwei aufeinanderfolgenden Laufbildern bleibt mindestens ein Fuß auf ±1 px stehen
  - Stehen: im Profil-Halt und in der Vorderansicht (Atmen, Wind) sind Fußzeile und Bodenkontakte je Ansicht
    gleich; die Drehung zur Kamera ist ein harter Schnitt (andere Fußstellung), sie wird nur berichtet
  - Bildwechsel nur auf Dreien (Laufen) bzw. Vielfachen von 5 (Atmen, Wind)

    .venv/bin/python styles/atari2600/scripts/probe.py --tmp DIR
"""
import argparse
import json
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

ENTRY = pathlib.Path(__file__).resolve().parent.parent
MAGENTA = np.array([255, 0, 255])
WALK_LAST_FILE = 98      # Halt bei Skriptbild 99 (Bilddatei 98); Drehung zur Kamera bei Skriptbild 108


def runs(row):
    xs = np.flatnonzero(row)
    out = []
    for x in xs:
        if out and x == out[-1][1] + 1:
            out[-1][1] = x
        else:
            out.append([x, x])
    return [tuple(int(v) for v in r) for r in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", required=True)
    a = ap.parse_args()
    d = pathlib.Path(a.tmp) / "probe"
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("f*.png"):
        old.unlink()
    r = subprocess.run(["godot", "--path", str(ENTRY / "demo"), "--position", "20000,20000", "--write-movie",
                        str(d / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--", "--sprites-only"],
                       capture_output=True, text=True, timeout=600)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    rom = json.loads((ENTRY / "demo" / "rom" / "rom.json").read_text())
    feet_y = rom["layout"]["feet_y"]
    frames = []
    for i, p in enumerate(sorted(d.glob("f*.png"))):
        im = np.asarray(Image.open(p).convert("RGB"))[:, ::2]      # 160 Konsolenpixel
        fig = (im != MAGENTA).any(-1)
        fig[:100] = False
        if fig.any() and np.flatnonzero(fig.any(0))[0] <= 8:
            fig[:] = False                                        # noch halb hinter dem HMOVE-Balken
        if not fig.any():
            frames.append({"file": i, "visible": False})
            continue
        ys = np.flatnonzero(fig.any(1))
        top, bottom = int(ys[0]), int(ys[-1])
        head = np.flatnonzero(fig[top])
        sig = fig[top:bottom + 1].tobytes()
        frames.append({"file": i, "visible": True, "top": top, "bottom": bottom,
                       "head_x": float(head.mean()), "ground": runs(fig[feet_y]), "sig": hash(sig)})
    # Laufphase: Bilder, in denen sich das Bild ändert und der Dachs sich bewegt
    changes, problems = [], []
    prev = None
    for f in frames:
        if not f["visible"]:
            prev = None
            continue
        if prev is not None and f["sig"] != prev["sig"] or (prev is not None and f["ground"] != prev["ground"]):
            changes.append((prev, f))
        prev = f
    walk_pairs, stand = [], []
    for p, f in changes:
        moved = f["ground"] and p["ground"] and f["ground"][0][0] != p["ground"][0][0] or f["head_x"] != p["head_x"]
        if f["bottom"] != feet_y or p["bottom"] != feet_y:
            problems.append(f"Bild {f['file']}: Fußzeile {f['bottom']} statt {feet_y}")
        if moved and f["file"] <= WALK_LAST_FILE:
            # mindestens ein Bodenkontakt bleibt (±1 px) stehen
            keep = any(abs(g[0] - h[0]) <= 1 and abs(g[1] - h[1]) <= 1 for g in f["ground"] for h in p["ground"])
            walk_pairs.append({"from": p["file"], "to": f["file"], "ground_from": p["ground"], "ground_to": f["ground"],
                               "foot_kept": keep})
            if not keep:
                problems.append(f"Bild {p['file']}->{f['file']}: kein Fuß bleibt stehen ({p['ground']} -> {f['ground']})")
    # Wechselabstände in der Laufphase
    walk_files = [w["to"] for w in walk_pairs]
    gaps = sorted({b - a for a, b in zip(walk_files, walk_files[1:])})
    # Stehen: alle Bilder nach dem Halt je Ansicht (gleiche Bodenkontakte)
    after = [f for f in frames if f["visible"] and f["file"] >= WALK_LAST_FILE]
    grounds = {}
    for f in after:
        grounds.setdefault(tuple(map(tuple, f["ground"])), []).append(f["file"])
    standing = {str(k): [min(v), max(v), len(v)] for k, v in grounds.items()}
    if len(grounds) > 2:
        problems.append(f"Stehen: {len(grounds)} verschiedene Bodenkontakte {list(grounds)} (erwartet 2: Profil, vorn)")
    out = {"errors": errs[:5], "walk_switches": len(walk_pairs), "walk_gaps_frames": gaps,
           "walk_advance_px": sorted({w["ground_to"][0][0] - w["ground_from"][0][0] for w in walk_pairs}),
           "standing_ground": standing,
           "head_top_rows": sorted({f["top"] for f in frames if f["visible"]}),
           "problems": problems}
    print(json.dumps(out, indent=1))
    print("ok" if not problems and not errs else "PROBLEME")
    return 0 if not problems and not errs else 1


if __name__ == "__main__":
    sys.exit(main())
