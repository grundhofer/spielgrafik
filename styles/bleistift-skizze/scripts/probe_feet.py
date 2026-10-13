#!/usr/bin/env python3
"""Misst den Dachs in der gerenderten Godot-Demo: Fußlinie, Standfuß bei jedem Bildwechsel, Kopf.
Vorgehen nach styles/kupferstich/scripts/probe_feet.py, vereinfacht.

    .venv/bin/python styles/bleistift-skizze/scripts/probe_feet.py [--frames 180] [--boil] [--keep DIR]

Rendert die Demo mit --probe-badger-only (nur die Figur auf Magenta, Figur schwarz, ohne Line-Boil; mit --boil
bleibt der Boil an, um seinen Einfluss auf die Füße zu messen), dann je Bild:
  - Deckung = Pixel, die deutlich nicht Magenta sind (Abstand > 200); Sohle = unterste deckende Zeile
  - Bodenkontakt = deckende Spalten in den 4 Zeilen über der gemeinsamen Fußlinie, als Läufe
  - Kopf = oberste Zeile und Schwerpunkt-x des obersten Viertels der Figur
Bei jedem Bildwechsel wird jeder Kontaktlauf des alten Bildes (mindestens 10 px) als Schablone (untere 12 Zeilen;
ganzer Fuß) im neuen Bild um -20..+20 px verschoben gesucht; die beste Übereinstimmung ist der
Standfuß, ihre Verschiebung der Schlupf. Zweite Messung: kleinster Abstand Ferse–Ferse oder Spitze–Spitze in den untersten 2 und 4 Zeilen
zwischen Läufen, die sich überlappen, also demselben Fuß (beim Abrollen ändert sich die Fußform, Ferse oder
Spitze bleiben aber stehen), dazu dasselbe gegen die Läufe einzelner der untersten 3 Zeilen des neuen Bildes (im
Doppelstand ist die Spitze des hinteren Fußes nur dort vom landenden Fuß getrennt). Gewertet wird die kleinste Zahl.
Kopf beim Laufen: Vorrücken des Kopfschwerpunkts je Laufbildwechsel (soll gleichmäßig und nie rückwärts sein).
Bild i zeigt Takt i + 1 der Ablauftabelle.
Ergebnis: assets/measure_badger.json (bzw. measure_badger_boil.json) und eine Zusammenfassung.
"""
import argparse, json, pathlib, sys, tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from render_frames import render  # noqa: E402

SD = pathlib.Path(__file__).resolve().parents[1]


def runs(row_mask):
    out, start = [], None
    for i, v in enumerate(row_mask):
        if v and start is None:
            start = i
        if not v and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(row_mask) - 1))
    return out


def measure(png, floor_row=None):
    a = np.asarray(Image.open(png).convert("RGB")).astype(np.int16)
    cover = (np.abs(a[..., 0] - 255) + a[..., 1] + np.abs(a[..., 2] - 255)) > 200
    ys, xs = np.nonzero(cover)
    if len(ys) == 0:
        return None
    sole, top = int(ys.max()), int(ys.min())
    h = sole - top
    fr = floor_row if floor_row is not None else sole
    head = xs[ys <= top + h // 4]
    return {"sole": sole, "top": top, "head_x": round(float(head.mean()), 2), "left": int(xs.min()),
            "contact": runs(cover[fr - 3:fr + 1].any(0)), "contact2": runs(cover[fr - 1:fr + 1].any(0)),
            "rows": [runs(cover[r]) for r in range(fr - 2, fr + 1)],
            "foot": cover[fr - 11:fr + 1].copy()}


def slip(m0, m1):
    """Verschiebung des am besten passenden Fußes (ganzer Kontaktlauf als Schablone) und Anteil abweichender Pixel."""
    best = None
    for a, b in m0["contact"]:
        if b - a < 10:
            continue
        tpl = m0["foot"][:, a:b + 1]
        for s in range(-20, 21):
            if a + s < 0 or b + 1 + s > m1["foot"].shape[1]:
                continue
            err = float((tpl != m1["foot"][:, a + s:b + 1 + s]).mean())
            if best is None or err < best[0] - 1e-9 or (abs(err - best[0]) < 1e-9 and abs(s) < abs(best[1])):
                best = (err, s)
    return (best[1], round(best[0], 3)) if best else (99, 1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--boil", action="store_true")
    ap.add_argument("--keep")
    a = ap.parse_args()
    tl = json.loads((SD / "demo/art/timeline.json").read_text())
    names = tl["frames"]
    seq = tl["timeline"][1:]
    user = ["--probe-badger-only"] + (["--boil-probe"] if a.boil else [])
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(a.keep or td)
        pngs, errs = render(out, a.frames, None, user)
        if errs:
            raise SystemExit("Godot-Fehler: " + errs[0])
        m0 = [measure(p) for p in pngs]
        floor_row = max(x["sole"] for x in m0 if x)
        m = [measure(p, floor_row) for p in pngs]
    changes = []
    for i in range(1, len(m)):
        e0, e1 = seq[i - 1], seq[i]
        if e0["f"] == e1["f"] and e0["x"] == e1["x"]:
            continue
        if m[i - 1]["left"] <= 0 or m[i]["left"] <= 0:
            continue                       # am Bildrand angeschnitten
        sh, err = slip(m[i - 1], m[i])
        ends = []
        for key in ("contact", "contact2"):
            # Ferse zu Ferse oder Spitze zu Spitze, nur zwischen Läufen, die sich überlappen (derselbe Fuß)
            for r0 in m[i - 1][key]:
                for r1 in m[i][key]:
                    if r0[1] - r0[0] >= 6 and r1[1] - r1[0] >= 6 and r0[0] <= r1[1] and r1[0] <= r0[1]:
                        ends.append(min(abs(r0[0] - r1[0]), abs(r0[1] - r1[1])))
        # Abrollen über die Spitze: Im Doppelstand verschmilzt die Spitze des hinteren Fußes in den unteren 4 Zeilen
        # mit dem landenden Fuß; in einzelnen Zeilen ist sie noch getrennt (Lauf ab 3 px)
        for r0 in m[i - 1]["contact"]:
            for row in m[i]["rows"]:
                for r1 in row:
                    if r0[1] - r0[0] >= 6 and r1[1] - r1[0] >= 2 and r0[0] <= r1[1] and r1[0] <= r0[1]:
                        ends.append(min(abs(r0[0] - r1[0]), abs(r0[1] - r1[1])))
        f0, f1 = names[e0["f"]], names[e1["f"]]
        changes.append({"frame": i, "from": f0, "to": f1, "planted_diff_px": int(min([abs(sh), *ends])),
                        "template_shift": sh, "mismatch": err, "end_match": min(ends) if ends else None,
                        "dx_sprite": e1["x"] - e0["x"],
                        "head_dx": round(m[i]["head_x"] - m[i - 1]["head_x"], 1)})
    for x in m:
        x.pop("foot", None)
        x.pop("rows", None)
    walk = [c for c in changes if c["from"].startswith("walk") and c["to"].startswith("walk")]
    # Blinzeln ändert nur die Augen; stand -> turn ist eine Drehung auf der Stelle (kein gemeinsamer Fußabdruck)
    stand = [c for c in changes if "blink" not in (c["from"], c["to"]) and (c["from"], c["to"]) != ("stand", "turn")]
    turn = [c for c in changes if (c["from"], c["to"]) == ("stand", "turn")]
    bad = [c for c in stand if c["planted_diff_px"] > 1]
    still = [x["sole"] for i, x in enumerate(m) if not names[seq[i]["f"]].startswith("walk")]
    res = {"frames": len(m), "boil": a.boil, "floor_row": floor_row,
           "sole_rows_all": sorted({x["sole"] for x in m}),
           "sole_rows_stand_turn_blink": sorted(set(still)),
           "planted_ok": len(stand) - len(bad), "planted_checked": len(stand),
           "planted_max_px": max((c["planted_diff_px"] for c in stand), default=0),
           "walk_changes": len(walk),
           "stand_to_turn_head_dx": [c["head_dx"] for c in turn],
           "head_dx_walk": [min((c["head_dx"] for c in walk), default=0), max((c["head_dx"] for c in walk), default=0)],
           "head_top_range": [min(x["top"] for x in m), max(x["top"] for x in m)],
           "changes": changes}
    name = "measure_badger_boil.json" if a.boil else "measure_badger.json"
    (SD / "assets" / name).write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"Boil {'an' if a.boil else 'aus'}; Fußlinie {floor_row}; Sohlenzeilen aller Bilder {res['sole_rows_all']}, "
          f"in Steh-/Dreiviertel-/Blinzelbildern {res['sole_rows_stand_turn_blink']}")
    print(f"Standfuß bei Bildwechseln: {res['planted_ok']}/{res['planted_checked']} höchstens 1 px, "
          f"max {res['planted_max_px']} px")
    print(f"Kopf je Laufbildwechsel: {res['head_dx_walk'][0]:+.1f} .. {res['head_dx_walk'][1]:+.1f} px "
          f"({res['walk_changes']} Wechsel); oberste Kopfzeile {res['head_top_range']}")
    seen = {}
    for c in walk:
        seen[(c["from"], c["to"])] = c
    for c in sorted(seen.values(), key=lambda c: int(c["from"].split("_")[1])):
        print(f"  {c['from']} -> {c['to']}: Sprite {c['dx_sprite']:+d}, Kopf {c['head_dx']:+.1f}, "
              f"Standfuß {c['planted_diff_px']} px (Schablone {c['template_shift']:+d}/{c['mismatch']}, Ferse/Spitze {c['end_match']})")
    for c in turn:
        print(f"  stand -> turn (Drehung auf der Stelle): Kopfschwerpunkt {c['head_dx']:+.1f} px")
    for c in bad:
        print("  >1 px:", {k: c[k] for k in ("frame", "from", "to", "planted_diff_px", "template_shift", "mismatch")})


if __name__ == "__main__":
    main()
