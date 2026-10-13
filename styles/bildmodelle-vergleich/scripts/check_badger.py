#!/usr/bin/env python3
"""Misst den Dachs der Schlussszene in der Godot-Ausgabe (nicht in den Zellen): Fußzeile, Standfuß, Kopf.

    .venv/bin/python styles/bildmodelle-vergleich/scripts/check_badger.py <tmpdir>

Rendert die Demo zweimal mit --final (Schlussszene von Anfang an sichtbar), einmal mit und einmal ohne Dachs
(--no-badger), und nimmt die Differenz als Figurmaske. Gemessen in Szenenpixeln (Ausgabe / 4):
- Fußzeile (unterste Zeile der Maske) in jedem Bild
- Füße: deckende Läufe in den untersten 3 Zeilen, in Weltkoordinaten
- Standfuß: Spitze des vorderen Fußes im Kontaktbild, Spitze im folgenden Durchgangsbild und Spitze des hinteren
  Fußes im nächsten Kontaktbild müssen auf ±1 px übereinstimmen
- Kopf: oberste Zeile und Schnauzenspitze (rechtester Punkt im oberen Drittel) je Bild
Schreibt assets/badger_check.json.
"""
import json, pathlib, subprocess, sys
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
DEMO = ENTRY / "demo"


def render(out, extra):
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "180",
                        "--", "--final"] + extra, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    if errs:
        print("\n".join(errs[:10]))
    return sorted(out.glob("f*.png"))


def runs(mask):
    idx = np.flatnonzero(mask)
    if not len(idx):
        return []
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > 1:
            out.append((int(s), int(p)))
            s = i
        p = i
    out.append((int(s), int(p)))
    return out


def main():
    tmp = pathlib.Path(sys.argv[1])
    a = render(tmp / "with", [])
    b = render(tmp / "without", ["--no-badger"])
    rows = []
    for i, (fa, fb) in enumerate(zip(a, b)):
        x = np.asarray(Image.open(fa).convert("RGB"), dtype=np.int16)[::4, ::4]   # Szenenpixel (×4, nearest)
        y = np.asarray(Image.open(fb).convert("RGB"), dtype=np.int16)[::4, ::4]
        m = np.abs(x - y).max(axis=2) > 0
        if not m.any():
            continue
        ys = np.flatnonzero(m.any(1))
        top, bot = int(ys[0]), int(ys[-1])
        band = m[bot - 2:bot + 1].any(0)
        feet = runs(band)
        h = bot - top + 1
        upper = m[top:top + h // 3]
        snout = int(np.flatnonzero(upper.any(0))[-1])
        rows.append({"frame": i, "t": round(i / 30, 3), "top": top, "foot_row": bot, "feet": feet, "snout_x": snout})
    # Bildwechsel des Dachses erkennen (Maske ändert sich)
    poses, last = [], None
    for r in rows:
        key = (r["top"], tuple(map(tuple, r["feet"])), r["snout_x"])
        if key != last:
            poses.append(r)
            last = key
    # Standfuß prüfen: Folgen Kontakt -> Durchgang -> Kontakt
    def kind(f):
        if len(f) >= 2 and f[-1][0] - f[0][1] >= 5:
            return "contact"
        return "passing"
    checks = []
    for k in range(len(poses) - 2):
        p0, p1, p2 = poses[k], poses[k + 1], poses[k + 2]
        if kind(p0["feet"]) == "contact" and kind(p1["feet"]) == "passing" and kind(p2["feet"]) == "contact":
            toes = [p0["feet"][-1][1], p1["feet"][-1][1], p2["feet"][0][1]]
            checks.append({"t": p0["t"], "stance_toe_x": toes, "spread": max(toes) - min(toes)})
    foot_rows = sorted({r["foot_row"] for r in rows})
    res = {"frames_measured": len(rows), "pose_changes": len(poses), "foot_rows": foot_rows,
           "stance_checks": checks, "max_stance_spread": max((c["spread"] for c in checks), default=None),
           "head_top_rows": sorted({r["top"] for r in rows}), "poses": poses}
    (ENTRY / "assets" / "badger_check.json").write_text(json.dumps(res, indent=1))
    print("Fußzeilen:", foot_rows)
    print("Kopf oben:", res["head_top_rows"])
    for c in checks:
        print("Standfuß", c)
    print("größte Abweichung Standfuß:", res["max_stance_spread"], "px")
    for p in poses:
        print(f"  t={p['t']:5.2f} top={p['top']} foot={p['foot_row']} feet={p['feet']} snout={p['snout_x']}")


if __name__ == "__main__":
    main()
