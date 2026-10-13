#!/usr/bin/env python3
"""Misst den Dachs in gerenderten Godot-Bildern (Prüflauf --probe-badger: nur Figur vor flachem Blau).
Nach styles/holzschnitt/scripts/probe_feet.py, angepasst an den Prüflauf dieser Demo (zwei Einstellungen).

    godot --path styles/ukiyo-e/demo --write-movie <dir>/f.png --fixed-fps 30 --quit-after 180 -- --probe-badger
    .venv/bin/python styles/ukiyo-e/scripts/probe_feet.py <dir>

Je Einstellung (Totale, Nahaufnahme) gilt eine feste Sohlenzeile: die unterste Figurzeile, die in den meisten
Bildern vorkommt (Figur = Abstand vom flachen Grund > 40, damit auch das Sumi-Grau des Fells zählt).
Gemessen wird nur in der festen Sohlenzeile selbst (in der Zeile darüber sind die Füße oft verschmolzen):
  Kontaktgruppen = zusammenhängende Figurspalten der Sohlenzeile (Lücken ab 2 px trennen Füße).
  Drehpunkt: Bei jedem Bildwechsel werden alle Paare sich überdeckender Gruppen verglichen; der Standfuß ist das
        Paar, dessen Ferse (linke Kante) oder Spitze (rechte Kante) am wenigsten wandert (Abrollen über die Spitze,
        Aufsetzen auf der Ferse).
  Aufsetzende Ferse (walk_0 -> walk_1, walk_4 -> walk_5): linke Kante der rechtesten Gruppe in A (vorderer Fuß,
        Ferse setzt auf) gegen die linke Kante der Gruppe in B, die sie überdeckt (derselbe Fuß, jetzt flach).
  Beide sollen höchstens ±1 px betragen.
Gemeldet außerdem: Scheitel, Nasenspitze (rechteste Spalte im oberen Viertel) und Bewegung innerhalb eines Halts.
Ausgabe auch als assets/measure_feet.json.
"""
import json, pathlib, sys
from collections import Counter
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]


def groups(cols):
    if not len(cols):
        return []
    gaps = np.nonzero(np.diff(cols) > 1)[0]
    return [(int(g[0]), int(g[-1])) for g in np.split(cols, gaps + 1)]


def main():
    d = pathlib.Path(sys.argv[1])
    tl = json.loads((ROOT / "assets/timeline.json").read_text())
    names = json.loads((ROOT / "assets/badger.json").read_text())["names"]
    files = sorted(d.glob("f*.png"))
    ref = None
    masks, rows = [], []
    for i, f in enumerate(files):
        im = np.asarray(Image.open(f).convert("RGB")).astype(int)
        if ref is None:
            ref = im[2, 2]
        m = np.abs(im - ref).sum(-1) > 40          # flacher Grund, Fellgrau liegt nur ~110 vom Blau entfernt
        tick = i + 1                      # Movie Maker: Bild i zeigt Takt i + 1
        e = tl["ticks"][min(tick, len(tl["ticks"]) - 1)]
        masks.append(m)
        r = {"img": i, "tick": tick, "shot": e["s"], "frame": names[e["f"]], "x": e["x"]}
        if m.any():
            ys, xs = np.nonzero(m)
            r.update(sole=int(ys.max()), top=int(ys.min()))
            upper = m[r["top"]:r["top"] + (r["sole"] - r["top"]) // 4]
            r["nose"] = int(np.nonzero(upper.any(0))[0].max())
        else:
            r["empty"] = True
        rows.append(r)
    sole_fixed = {}
    for s in (0, 1):
        c = Counter(r["sole"] for r in rows if r["shot"] == s and not r.get("empty"))
        if c:
            sole_fixed[s] = c.most_common(1)[0][0]
    imgs = {}

    def fur_runs(i, row):
        if i not in imgs:
            imgs[i] = np.asarray(Image.open(files[i]).convert("RGB")).astype(int)
        im = imgs[i]
        fur = masks[i][row] & (im[row].sum(-1) > 160)
        return groups(np.nonzero(fur)[0])

    for r, m in zip(rows, masks):
        if r.get("empty"):
            continue
        r["contact"] = groups(np.nonzero(m[sole_fixed[r["shot"]]])[0])
    report = []
    for a, b in zip(rows, rows[1:]):
        if a.get("empty") or b.get("empty") or a["frame"] == b["frame"] or a["shot"] != b["shot"]:
            continue
        best = None
        for ca in a["contact"]:
            for cb in b["contact"]:
                if min(ca[1], cb[1]) - max(ca[0], cb[0]) < 0:
                    continue
                dh, dt = cb[0] - ca[0], cb[1] - ca[1]
                piv = dh if abs(dh) <= abs(dt) else dt
                if best is None or abs(piv) < abs(best[0]):
                    best = (piv, ca, cb, "Ferse" if abs(dh) <= abs(dt) else "Spitze")
        rep = {"img": b["img"], "shot": a["shot"], "change": f'{a["frame"]}->{b["frame"]}', "advance": b["x"] - a["x"],
               "d_nose": b["nose"] - a["nose"], "d_top": b["top"] - a["top"], "d_sole": b["sole"] - a["sole"]}
        if best is not None:
            rep.update(pivot=best[3], d_pivot=best[0], foot_a=best[1], foot_b=best[2])
        if rep["change"] in ("walk_0->walk_1", "walk_4->walk_5") and len(a["contact"]) >= 2:
            heel = a["contact"][-1]
            over = [cb for cb in b["contact"] if min(heel[1], cb[1]) - max(heel[0], cb[0]) >= 0]
            if over:
                rep["heel"] = [heel[0], over[0][0]]
                rep["d_heel"] = over[0][0] - heel[0]
        report.append(rep)
    print("feste Sohlenzeile je Einstellung:", sole_fixed)
    for s_ in (0, 1):
        soles = Counter(r["sole"] for r in rows if r["shot"] == s_ and not r.get("empty"))
        print(f"Einstellung {s_}: unterste Figurzeile je Bild", dict(soles))
    for r in report:
        extra = f'  aufsetzende Ferse {r["heel"][0]}->{r["heel"][1]} ({r["d_heel"]:+d})' if "heel" in r else ""
        piv = f'Fuß {r["foot_a"]} -> {r["foot_b"]} {r["pivot"]:6s} {r["d_pivot"]:+d}' if "pivot" in r else "kein Paar"
        print(f'{r["img"]:4d} E{r["shot"]} {r["change"]:16s} Vorschub {r["advance"]:+3d}  {piv}  '
              f'Nase {r["d_nose"]:+d}  Scheitel {r["d_top"]:+d}{extra}')
    summary = {}
    for s_ in (0, 1):
        walk = [r for r in report if r["shot"] == s_ and r["change"].startswith("walk") and "->walk" in r["change"]]
        if not walk:
            continue
        piv = [r["d_pivot"] for r in walk if "d_pivot" in r]
        heels = [r["d_heel"] for r in walk if "d_heel" in r]
        summary[s_] = {"changes": len(walk), "measured": len(piv),
                       "pivot_hist": {v: piv.count(v) for v in sorted(set(piv))},
                       "heel_hist": {v: heels.count(v) for v in sorted(set(heels))}}
        print(f"Einstellung {s_}: Laufwechsel {len(walk)} (gemessen {len(piv)}); Drehpunkt {summary[s_]['pivot_hist']}; "
              f"aufsetzende Ferse {summary[s_]['heel_hist']}")
    moved = [(a["img"], b["img"]) for a, b in zip(rows, rows[1:]) if not a.get("empty") and not b.get("empty")
             and a["frame"] == b["frame"] and a["shot"] == b["shot"] and
             (a["contact"] != b["contact"] or a["sole"] != b["sole"])]
    print("Bewegung innerhalb eines Halts:", moved[:10] if moved else "keine")
    (ROOT / "assets/measure_feet.json").write_text(json.dumps({"sole_fixed": sole_fixed, "summary": summary,
                                                                "changes": report, "moved_in_hold": moved}, indent=1))


if __name__ == "__main__":
    main()
