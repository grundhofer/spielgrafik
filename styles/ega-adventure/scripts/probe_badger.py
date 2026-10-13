#!/usr/bin/env python3
"""Misst den Dachs in den gerenderten Bildern der Godot-Demo (Basisauflösung 320×200).

Nimmt die Demo zweimal auf (mit und ohne Dachs, sonst bitgleich), die Differenz ist der Dachs.
Je Laufbild (alle 3 Aufnahmebilder bei 10 Bildern/s): linke Kante, Kopfzeile, Fußzeile und Fußstücke in der
Standlinie in Weltkoordinaten (Doppelpixel). Prüft:
  - innerhalb eines Laufbilds keine Änderung (kein Zittern),
  - beim Wechsel zum nächsten Laufbild bleibt mindestens ein Fuß auf ±1 Doppelpixel liegen (Standfuß),
  - in allen Steh-/Vorderbildern liegt die Fußzeile gleich.
Verdeckte Stellen (Fässer, Pfahl) werden mitgezählt, aber gesondert ausgewiesen.
Verdeckung (nur für das KI-Bild mit Nacharbeit, Silhouetten aus scripts/ai_touchup.py POLE/BARRELS):
  - kein Dachspixel innerhalb der sichtbaren Silhouette von Laternenpfahl oder Fass (je Zeile vom ersten bis zum
    letzten schwarzen Konturpixel, ab 4 Zeilen über der Mütze),
  - solange der Dachs ganz in den Spalten des linken Fasses steht, ragen nur Zeilen über dessen Deckel heraus,
  - Prioritätsebene gegen Silhouetten: keine Lücke (Silhouette ohne höheres Band) und keine Überdeckung (höheres Band
    außerhalb der Silhouetten).

    .venv/bin/python styles/ega-adventure/scripts/probe_badger.py [--keep DIR]
"""
import argparse, pathlib, subprocess, sys, tempfile

import numpy as np
from PIL import Image

SD = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SD / "scripts"))
from agipic import H, W, band, replay  # noqa: E402


def picture():
    """Bilddatei, die die Demo gerade zeigt (demo/art/scene.json, sonst Handbild)."""
    import json
    name = "harbor.pic.json"
    if (SD / "demo/art/scene.json").exists():
        name = json.loads((SD / "demo/art/scene.json").read_text()).get("picture", name)
    return json.loads((SD / "demo/art" / name).read_text())


def walk_y():
    """Fußlinie des Bildes, das die Demo gerade zeigt."""
    return int(picture()["layout"]["walk_y"])


FEET_Y = walk_y() + 8     # Standlinie in Bildschirmzeilen (Bild beginnt bei y=8); Handbild: 146 + 8


def silhouettes(vis, top):
    """Sichtbare Silhouetten von Laternenpfahl und Fässern im KI-Bild mit Nacharbeit (Lage aus ai_touchup.py):
    je Zeile ab `top` vom ersten bis zum letzten schwarzen Pixel im Rahmen des Gegenstands."""
    import ai_touchup as at
    px, py0, py1 = at.POLE
    boxes = [("Pfahl", (px - 1, py0, px + 4, py1))]
    boxes += [(f"Fass {k + 1}", (x0, t, x1, b)) for k, (x0, x1, t, b) in enumerate(at.BARRELS)]
    out = []
    for name, (x0, y0, x1, y1) in boxes:
        m = np.zeros((H, W), bool)
        for y in range(max(y0, top), y1 + 1):
            xs = np.flatnonzero(vis[y, x0:x1 + 1] == 0)
            if xs.size:
                m[y, x0 + xs[0]:x0 + xs[-1] + 1] = True
        out.append((name, (x0, y0, x1, y1), m))
    return out


def record(out, extra):
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["godot", "--path", str(SD / "demo"), "--position", "20000,20000", "--write-movie",
           str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "180"] + (["--", *extra] if extra else [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    if errs:
        sys.exit("Godot-Fehler: " + errs[0])
    return sorted(out.glob("f*.png"))


def runs(row):
    idx = np.flatnonzero(row)
    if idx.size == 0:
        return []
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i != p + 1:
            out.append((int(s), int(p)))
            s = i
        p = i
    out.append((int(s), int(p)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep")
    a = ap.parse_args()
    base = pathlib.Path(a.keep) if a.keep else pathlib.Path(tempfile.mkdtemp())
    A = record(base / "with", [])
    B = record(base / "without", ["--no-badger"])
    rows = []
    for i, (fa, fb) in enumerate(zip(A, B)):
        x = np.asarray(Image.open(fa).convert("RGB"), np.int16)
        y = np.asarray(Image.open(fb).convert("RGB"), np.int16)
        d = np.abs(x - y).max(-1) > 0
        d[:8] = False
        d[176:] = False
        if not d.any():
            rows.append(None)
            continue
        ys, xs = np.nonzero(d)
        # Doppelpixel: Spalten paarweise zusammenfassen
        du = d[:, 0::2] | d[:, 1::2]
        feet = runs(du[FEET_Y])
        rows.append({"i": i, "top": int(ys.min()) - 8, "bottom": int(ys.max()) - 8, "left": int(xs.min()) // 2,
                     "right": int(xs.max()) // 2, "feet": feet, "mask": du})
    # Laufbilder: Gruppen gleicher Masken
    cels, jitter = [], 0
    prev = None
    for r in rows:
        if r is None:
            continue
        if prev is not None and r["i"] == prev["i"] + 1 and (r["mask"] == prev["mask"]).all():
            cels[-1]["n"] += 1
        else:
            if prev is not None and r["i"] == prev["i"] + 1 and cels and cels[-1]["n"] < 3 and r["i"] < 147:
                jitter += 1
            cels.append(dict(r, n=1))
        prev = r
    print(f"{len(cels)} Einzelbilder (Masken), erstes Aufnahmebild mit Dachs: {cels[0]['i']}")
    print(" Bild  t(s)  Dauer  links rechts  Kopf  Fuß  Fußstücke (Doppelpixel)")
    for c in cels:
        print(f"{c['i']:5d} {c['i'] / 30:5.2f} {c['n']:5d} {c['left']:6d} {c['right']:6d} {c['top']:5d} "
              f"{c['bottom']:4d}  {c['feet']}")
    # Standfuß-Prüfung zwischen aufeinanderfolgenden Laufbildern
    ok = bad = hidden = 0
    for c0, c1 in zip(cels, cels[1:]):
        if c1["i"] > 147:      # danach stehen/vorne
            break
        f0, f1 = c0["feet"], c1["feet"]
        if not f0 or not f1:
            hidden += 1
            continue
        # gleicher Fuß: Stück bleibt auf ±1 liegen oder liegt ganz in einem Stück des nächsten Bilds
        # (beim Anhalten setzt der zweite Fuß neben dem Standfuß auf)
        same = any((abs(a[0] - b[0]) <= 1 and abs(a[1] - b[1]) <= 1) or (b[0] <= a[0] and a[1] <= b[1])
                   for a in f0 for b in f1)
        if same:
            ok += 1
        else:
            bad += 1
            print(f"  Standfuß springt: Bild {c0['i']} {f0} -> Bild {c1['i']} {f1}")
    stand = [c for c in cels if c["i"] >= 150]
    bottoms = sorted({c["bottom"] for c in stand})
    print(f"Standfuß gehalten: {ok}, gesprungen: {bad}, Fuß verdeckt/fehlt: {hidden}; "
          f"Laufbilder kürzer als 3 Aufnahmebilder: {jitter}")
    print(f"Fußzeilen Stehen/Vorderansicht: {bottoms}; Kopfzeilen: {sorted({c['top'] for c in stand})}")
    occlusion(rows)


def occlusion(rows):
    """Verdeckung durch Pfahl und Fässer (siehe Kopf der Datei). Gibt die Zahl der Verstöße aus."""
    pic = picture()
    if pic.get("source") != "ai_bg_flat_touchup":
        print("Verdeckungsprüfung: nur für das KI-Bild mit Nacharbeit (aktiv ist", pic.get("source", "Handbild"), ")")
        return
    vis, pri = replay(pic["commands"])
    wy = int(pic["layout"]["walk_y"])
    top = wy - 34                                      # 4 Zeilen über der Mütze (walk_y - 30)
    sil = silhouettes(vis, top)
    union = np.zeros((H, W), bool)
    for _, _, m in sil:
        union |= m
    front = pri > band(wy)
    front[:top] = False
    gaps = int((union & ~front).sum())
    over = int((front & ~union).sum())
    print(f"Prioritätsebene ab Zeile {top}: Silhouetten {int(union.sum())} Pixel, davon ohne höheres Band {gaps}; "
          f"höheres Band außerhalb der Silhouetten {over}")
    _, (bx0, btop, bx1, _), _ = sil[1]                # linkes Fass
    # Spalte des Dachses je Aufnahmebild wie in main.gd: Aufnahmebild i zeigt Bildzähler fno = i + 1; ab fno 54
    # (WALK_T 1,8 s) alle 3 Bilder ein Laufbild, x = start_x - Vorschub; 30 Laufbilder, danach steht er
    import json
    walk = json.loads((SD / "demo/art/views.json").read_text())["badger"]
    adv, bw = [int(a) for a in walk["walk"]["advance"]], int(walk["w"])

    def badger_x(i):
        n = min(29, (i + 1 - 54) // 3)
        return int(pic["layout"]["start_x"]) - (n // len(adv)) * sum(adv) - sum(adv[:n % len(adv)])
    inside = bad_rows = 0
    behind, shown = [], []
    for r in rows:
        if r is None:
            continue
        bm = r["mask"][8:8 + H]
        n = int((bm & union).sum())
        inside += n
        if n:
            ys, xs = np.nonzero(bm & union)
            print(f"  Dachspixel in einer Silhouette: Bild {r['i']}, {n} Pixel, z. B. ({xs[0]}, {ys[0]})")
        ys, xs = np.nonzero(bm)
        if ys.size and bx0 <= badger_x(r["i"]) and badger_x(r["i"]) + bw - 1 <= bx1:
            behind.append(r["i"])
            shown.append((int(ys.min()), int(ys.max())))
            if ys.max() >= btop:
                bad_rows += 1
                print(f"  Bild {r['i']}: hinter dem linken Fass sichtbar bis Zeile {int(ys.max())} (Deckel ab {btop})")
    if behind:
        lo, hi = min(s[0] for s in shown), max(s[1] for s in shown)
        print(f"ganz hinter dem linken Fass: Bilder {behind[0]}–{behind[-1]} ({len(behind)}), sichtbar nur Zeilen "
              f"{lo}–{hi} (Deckel ab Zeile {btop}); Verstöße {bad_rows}")
    else:
        print("ganz hinter dem linken Fass: kein Bild")
    print(f"Dachspixel innerhalb der Silhouetten von Pfahl und Fässern: {inside} (alle Bilder)")


if __name__ == "__main__":
    main()
