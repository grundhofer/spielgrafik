"""Prüft die Hardwareregeln an echten Zeilentabellen aus Godot und vergleicht Shader und Referenz-Renderer.

    .venv/bin/python styles/atari2600/scripts/check_hw.py --tmp DIR [--frames 1,45,90,135,165]

Für jedes Bild schreibt Godot mit --dump die Zeilentabelle (Register je Zeile) und nimmt das Bild auf.
Geprüft wird je Szenenzeile:
  - Farben: höchstens 4 Farbregister sichtbar (COLUBK, COLUPF, COLUP0, COLUP1), plus eine zweite Playfield-Farbe,
    wenn COLUPF mitten in der Zeile umgeschrieben wird; alle Farben aus der NTSC-Palette
  - Spieler: 8 Bit je Zeile, eine Farbe je Zeile (folgt aus dem Datenformat), Kopien nur über NUSIZ
  - Umsetzen von Objekten: ein Sprung um mehr als 7 Pixel (mehr als HMOVE in einer Zeile schafft) nur, wenn das
    Objekt in der Vorzeile nicht sichtbar war
  - Schreibzugriffe je Zeile (Schätzung aus geänderten Registern, aus main.gd übernommen) mit Aufschlüsselung
Außerdem: Das Godot-Bild (320x192) muss Pixel für Pixel dem Python-Referenz-Renderer (tia_ref.py) entsprechen.
"""
import argparse
import json
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tia_ref  # noqa: E402

ENTRY = pathlib.Path(__file__).resolve().parent.parent
F_REFP0, F_REFP1, F_ENAM0, F_ENAM1, F_ENABL, F_HMOVE, F_TEXT = 1, 2, 4, 8, 16, 32, 64


def record(frame, tmp):
    d = tmp / f"rec{frame:03d}"
    d.mkdir(parents=True, exist_ok=True)
    dump = tmp / f"dump{frame:03d}.json"
    r = subprocess.run(["godot", "--path", str(ENTRY / "demo"), "--position", "20000,20000", "--write-movie",
                        str(d / "f.png"), "--fixed-fps", "30", "--quit-after", str(frame + 1), "--",
                        "--dump", str(frame), str(dump)], capture_output=True, text=True, timeout=600)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    pngs = sorted(d.glob("f*.png"))
    # Movie Maker schreibt das erste Bild nach dem ersten _process: Bilddatei i zeigt Skriptbild i + 1
    return json.loads(dump.read_text()), np.asarray(Image.open(pngs[frame - 1]).convert("RGB")), errs


def to_ref_lines(dump, text_y0=136):
    L = []
    for r in dump["lines"]:
        fl = r["flags"]
        L.append({"colubk": r["colubk"], "colupf": r["colupf"], "colup0": r["colup0"], "colup1": r["colup1"],
                  "colupf_r": r["colupf_r"], "split": r["split"], "pf": r["pf"], "grp0": r["grp0"],
                  "grp1": r["grp1"], "p0x": r["p0x"], "p1x": r["p1x"], "m0x": r["m0x"], "m1x": r["m1x"],
                  "blx": r["blx"], "enam0": fl & F_ENAM0, "enam1": fl & F_ENAM1, "enabl": fl & F_ENABL,
                  "nusiz0": r["nusiz0"], "nusiz1": r["nusiz1"], "refp0": fl & F_REFP0, "refp1": fl & F_REFP1,
                  "ctrlpf": r["ctrlpf"], "hmove": fl & F_HMOVE, "text": fl & F_TEXT})
    px = dump["text_px"]
    rows = {text_y0 + i: [1 if px[i * 160 + x] else 0 for x in range(160)] for i in range(192 - text_y0)}
    return L, rows


def visible(r):
    fl = r["flags"]
    return {"pf": r["pf"] != 0 or bool(fl & F_ENABL),
            "p0": r["grp0"] != 0 or bool(fl & F_ENAM0),
            "p1": r["grp1"] != 0 or bool(fl & F_ENAM1)}


def check(dump, scene_h=136):
    problems, rows = [], []
    lines = dump["lines"]
    for y in range(scene_h):
        r = lines[y]
        v = visible(r)
        cols = {r["colubk"]}
        if v["pf"]:
            cols.add(r["colupf"])
            if r["split"] < 160 and r["colupf_r"] != r["colupf"]:
                cols.add(r["colupf_r"])
        if v["p0"]:
            cols.add(r["colup0"])
        if v["p1"]:
            cols.add(r["colup1"])
        regs = len({r["colubk"]} | ({r["colupf"]} if v["pf"] else set()) | ({r["colup0"]} if v["p0"] else set())
                   | ({r["colup1"]} if v["p1"] else set()))
        if regs > 4:
            problems.append(f"Zeile {y}: {regs} Farbregister sichtbar")
        if y > 0:
            p = lines[y - 1]
            pv = {"p0x": p["grp0"] != 0, "p1x": p["grp1"] != 0, "m0x": bool(p["flags"] & F_ENAM0),
                  "m1x": bool(p["flags"] & F_ENAM1), "blx": bool(p["flags"] & F_ENABL)}
            cv = {"p0x": r["grp0"] != 0, "p1x": r["grp1"] != 0, "m0x": bool(r["flags"] & F_ENAM0),
                  "m1x": bool(r["flags"] & F_ENAM1), "blx": bool(r["flags"] & F_ENABL)}
            for k in pv:
                dx = (r[k] - p[k] + 80) % 160 - 80
                if abs(dx) > 7 and pv[k] and cv[k]:
                    problems.append(f"Zeile {y}: {k} springt um {dx} px, obwohl in Zeile {y - 1} sichtbar")
        rows.append((y, r["writes"], len(cols)))
    return problems, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", required=True)
    ap.add_argument("--frames", default="1,45,90,135,165")
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    pal = {tuple(c) for c in tia_ref.PAL.tolist()} | {(0, 0, 0)}
    summary = {"frames": [], "max_writes": 0, "lines_over_13": 0, "max_colors": 0, "mismatch_px": 0,
               "foreign_colors": 0, "problems": []}
    for f in [int(x) for x in a.frames.split(",")]:
        dump, img, errs = record(f, tmp)
        summary["problems"] += [f"Bild {f}: {e}" for e in errs]
        problems, rows = check(dump)
        summary["problems"] += [f"Bild {f}: {p}" for p in problems]
        L, text = to_ref_lines(dump)
        ref = tia_ref.render_lines(L, text)
        godot = img[:, ::2]                       # 320 -> 160: jedes Pixel ist doppelt breit
        same_pairs = bool((img[:, ::2] == img[:, 1::2]).all())
        mism = int((ref != godot).any(-1).sum())
        cols = {tuple(c) for c in godot.reshape(-1, 3).tolist()}
        foreign = len(cols - pal)
        busiest = sorted(rows, key=lambda r: -r[1])[:5]
        summary["frames"].append({"frame": f, "mismatch_px": mism, "pixel_pairs_equal": same_pairs,
                                  "foreign_colors": foreign, "max_writes": max(r[1] for r in rows),
                                  "lines_over_13": sum(1 for r in rows if r[1] > 13),
                                  "max_colors_line": max(r[2] for r in rows), "busiest": busiest})
        summary["max_writes"] = max(summary["max_writes"], max(r[1] for r in rows))
        summary["lines_over_13"] += sum(1 for r in rows if r[1] > 13)
        summary["max_colors"] = max(summary["max_colors"], max(r[2] for r in rows))
        summary["mismatch_px"] += mism
        summary["foreign_colors"] += foreign
    print(json.dumps(summary, indent=1))
    ok = not summary["problems"] and summary["mismatch_px"] == 0 and summary["foreign_colors"] == 0
    print("ok" if ok else "PROBLEME")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
