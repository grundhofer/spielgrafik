#!/usr/bin/env python3
"""Misst den Gang des Dachses in der gerenderten Demo (Godot Movie Maker, 180 Bilder).

    .venv/bin/python styles/flat-vektor/scripts/measure_badger.py <tempordner> [--keep]

Zwei Läufe: normal und mit --probe-no-badger. Das Differenzbild trennt den Dachs vom (gleich animierten)
Hintergrund. Gezählt werden nur Pixel in den beiden Fellfarben (flache Farben, daher exakt prüfbar), so zählen
Schatten und Kantenglättung nicht mit.
  * Bodenkontakt: Fellpixel in der untersten Pfotenzeile (GROUND-1). Jede zusammenhängende Strecke ist eine
    aufstehende Pfote. Eine Pfote, die in zwei Folgebildern aufsteht, darf sich höchstens um 1 px verschieben
    (beim Aufsetzen mit der Ferse oder beim Verschmelzen zweier Pfoten zählt die stehende Kante).
  * Fußlinie: unterste Fellzeile je Bild (muss in allen Bildern GROUND-1 sein).
  * Kopf: oberste Zeile des Dachses (Mütze) je Bild; Sprünge zwischen Folgebildern.
Ergebnis: assets/badger_measure.json (klein), große Bilder werden gelöscht (außer mit --keep).
"""
import json, pathlib, shutil, subprocess, sys
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[3]
STYLE = ROOT / "styles" / "flat-vektor"
DEMO = STYLE / "demo"
GROUND = 574
FUR = [(0x3e, 0x38, 0x48), (0x2b, 0x26, 0x33)]


def render(out, extra):
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--", *extra],
                       capture_output=True, text=True)
    bad = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    if bad:
        sys.exit("Godot-Fehler: " + bad[0])
    return sorted(out.glob("f*.png"))


def runs(row):
    idx = np.flatnonzero(row)
    if idx.size == 0:
        return []
    cuts = np.flatnonzero(np.diff(idx) > 1)
    starts = np.r_[idx[0], idx[cuts + 1]]
    ends = np.r_[idx[cuts], idx[-1]]
    return [(int(a), int(b)) for a, b in zip(starts, ends)]


def main():
    tmp = pathlib.Path(sys.argv[1])
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    a = render(tmp / "with", ["--probe-no-ui"])
    b = render(tmp / "without", ["--probe-no-ui", "--probe-no-badger"])
    frames = []
    for pa, pb in zip(a, b):
        A = np.asarray(Image.open(pa).convert("RGB"), dtype=np.int16)
        B = np.asarray(Image.open(pb).convert("RGB"), dtype=np.int16)
        diff = np.abs(A - B).max(axis=2) > 6
        fur = np.zeros(diff.shape, bool)
        for c in FUR:
            fur |= np.abs(A - np.array(c)).max(axis=2) <= 3
        fur &= diff
        ys, xs = np.nonzero(diff)
        fy = np.nonzero(fur.any(axis=1))[0]
        frames.append({
            "contacts": runs(fur[GROUND - 1]),
            "foot_line": int(fy.max()) if fy.size else None,
            "top": int(ys.min()) if ys.size else None,
            "x_range": [int(xs.min()), int(xs.max())] if xs.size else None,
        })
    # Rutschen: Pfoten, die in zwei Folgebildern aufstehen, über Überlappung zuordnen
    slips, landings, max_slip, planted_pairs = [], [], 0, 0
    for i in range(1, len(frames)):
        for c0 in frames[i - 1]["contacts"]:
            for c1 in frames[i]["contacts"]:
                if c1[0] <= c0[1] and c0[0] <= c1[1]:
                    planted_pairs += 1
                    # Gleiche Breite: dieselbe Pfote, beide Kanten müssen stehen. Andere Breite: Ferse setzt auf und
                    # die Pfote legt sich flach, oder zwei Pfoten verschmelzen; dann muss eine Kante stehen bleiben.
                    dl, dr = abs(c1[0] - c0[0]), abs(c1[1] - c0[1])
                    s = max(dl, dr) if (c1[1] - c1[0]) == (c0[1] - c0[0]) else min(dl, dr)
                    if (c1[1] - c1[0]) != (c0[1] - c0[0]):
                        landings.append({"frame": i, "from": c0, "to": c1})
                    max_slip = max(max_slip, s)
                    if s > 1:
                        slips.append({"frame": i, "from": c0, "to": c1})
    lines = sorted({f["foot_line"] for f in frames if f["foot_line"] is not None})
    tops = [f["top"] for f in frames]
    jumps = [abs(tops[i] - tops[i - 1]) for i in range(1, len(tops)) if tops[i] is not None and tops[i - 1] is not None]
    stand = [i for i in range(len(frames)) if i / 30 > 3.75]
    stand_contacts = {tuple(map(tuple, frames[i]["contacts"])) for i in stand}
    res = {
        "frames": len(frames),
        "foot_lines": lines,
        "planted_pairs": planted_pairs,
        "max_slip_px": max_slip,
        "slips_over_1px": slips[:20],
        "landing_or_merge_events": landings,
        "head_top_range": [min(t for t in tops if t is not None), max(t for t in tops if t is not None)],
        "head_max_jump_px": max(jumps) if jumps else None,
        "standing_frames": len(stand),
        "standing_contact_sets": [list(s) for s in stand_contacts],
        "per_frame": [{"f": i, **f} for i, f in enumerate(frames)],
    }
    (STYLE / "assets" / "badger_measure.json").write_text(json.dumps(res, ensure_ascii=False))
    print(json.dumps({k: v for k, v in res.items() if k != "per_frame"}, ensure_ascii=False))
    if "--keep" not in sys.argv:
        shutil.rmtree(tmp / "with", ignore_errors=True)
        shutil.rmtree(tmp / "without", ignore_errors=True)


if __name__ == "__main__":
    main()
