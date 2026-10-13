#!/usr/bin/env python3
"""Baut den „Sendestrom“ der Demo: Grundseite plus Zeilen-Aktualisierungen für alle Animationen.

    .venv/bin/python styles/videotext/scripts/build_stream.py

Videotext kennt keine Sprites. Bewegung entsteht, indem der Sender einzelne Zeilen der Seite neu überträgt; der
Decoder im Fernseher zeigt sofort den neuen Inhalt. Jede Animationsphase wird hier als Zielbild gezeichnet und
nur in den Spalten neu kodiert, in denen sich das Ziel ändert (Fenster ± 3 Zellen, Start- und Endzustand des
Decoders wie in der Grundzeile). Dadurch bleibt der Rest der Zeile Byte für Byte gleich, und jede Phase hält
die Regeln ein (Steuerzeichen belegen Zellen, eine Vorder- und eine Hintergrundfarbe je Zelle).

Ausgabe: demo/data/stream.json (von main.gd gelesen), assets/badger_frames.png (Vorschau), Bericht.
"""
import json

import numpy as np
from PIL import Image

import build_page as BP
import scene
import sprites_ttx as S
import ttxenc as E
import ttxlib as T

HERE = T.HERE
FPS = 30
SKY_ROWS, WATER_ROWS, BADGER_ROWS = [3, 4, 5], [11, 12], [15, 16, 17, 18, 19]
SKY_FRAMES, WATER_FRAMES = 6, 9               # Bilder je Phase (0,2 s bzw. 0,3 s)


def clusters(cols, gap=4):
    cols = sorted(cols)
    out = []
    for c in cols:
        if out and c - out[-1][1] <= gap:
            out[-1][1] = c
        else:
            out.append([c, c])
    return out


def patch_row(row, tgt, base_tgt, r, extra_cols=()):
    """Kodiert eine Zeile nur dort neu, wo sich das Ziel (tgt) gegenüber base_tgt ändert."""
    a, b_, ww, sepw = tgt
    ba, bb, _, bsep = base_tgt
    diff = np.nonzero((a != ba).any(0) | (b_ != bb).any(0))[0]
    cols = {int(x) // 2 for x in diff} | set(extra_cols)
    cols |= {c for c in range(40) if sepw[c] != bsep[c]}
    row = list(row)
    windows = []
    for c_lo, c_hi in clusters(cols):
        # Fenster c0..c1-1 frei, ab c1 bleiben die Bytes der Zeile fest; die DP rechnet bis Spalte 39 und
        # berücksichtigt so, wie der Rest der Zeile mit dem neuen Zustand angezeigt wird.
        c0, c1 = max(0, c_lo - 3), min(40, c_hi + 4)
        while True:
            start = E.decoder_state(row, c0)
            fixed = {k: v for k, v in BP.FIXED.get(r, {}).items() if c0 <= k < c1}
            fixed.update({k: row[k] for k in range(c1, 40)})
            try:
                bytes_, cost, _ = E.encode_row(a, b_, ww, sepw, c0=c0, c1=40, start=start, fixed=fixed)
                break
            except RuntimeError:
                c0, c1 = max(0, c0 - 2), min(40, c1 + 2)
        assert bytes_[c1 - c0:] == row[c1:]
        row = row[:c0] + bytes_
        windows.append((c0, c1))
    return row, windows


def targets(t_on, t_off, w, sep, rows):
    return {r: (*BP.target_rows(t_on, t_off, w, r), sep[r - 1]) for r in rows}


def miss_count(row, tgt):
    """Falsch angezeigte Sechstel ab Spalte 1 (Spalte 0 ist in Himmelszeilen zwangsläufig ein Steuerzeichen)."""
    a = tgt[0][:, 2:]
    on, _ = E.shown(row)
    return int(((on[:, 2:] != a) & (a >= 0)).sum())


def sep_errors(row, sepw):
    """Mosaikzellen (nicht leer), deren Trennmodus nicht dem Wunsch der Vorlage entspricht."""
    cells, _ = T.decode_row(row)
    return sum(1 for c, (k, code, sp, *_r) in enumerate(cells)
               if k == T.MOSAIC and code and sepw[c] >= 0 and int(sp) != sepw[c])


def loop_states(base_page, base_tg, n, rows, make):
    states, report = [], []
    for s in range(n):
        t_on, t_off, w, sep = make(s)
        tg = targets(t_on, t_off, w, sep, rows)
        st = []
        for r in rows:
            row, win = patch_row(base_page[r], tg[r], base_tg[r], r)
            st.append(row)
            report.append((s, r, win, sep_errors(row, tg[r][3]), miss_count(row, tg[r])))
        states.append(st)
    return states, report


def badger_schedule():
    """(Pose, x) je Aufnahmebild bis 4,5 s; danach Leerlauf (Vorderansicht, Schal weht).
    0–0,4 s in der Tür, 0,4–2,5 s Laufen (21 Laufbilder, 10 Bilder/s), 2,5–3,0 s Stehen,
    3,0 s Drehung zum Betrachter, 3,4–4,2 s Gruß (Arm hebt sich zweimal), dann Leerlauf.
    Das erste Laufbild steht an derselben Stelle wie die Türpose (walk0 hebt nur den vorderen Fuß, der hintere
    bleibt stehen); der Vorschub von 1 Punkt beginnt mit dem zweiten Laufbild (20 Schritte bis x = 35).
    Vorderansichten sind 12 Spalten breit (Paket links vom Körper) und werden bei x = 34 gesetzt."""
    sched = []
    for f in range(135):
        if f < 12:
            sched.append(("stand0", 15))
        elif f < 12 + 21 * 3:
            k = (f - 12) // 3
            sched.append((f"walk{k % 4}", 15 + k))
        elif f < 90:
            sched.append(("stand0" if (f - 75) < 9 else "stand1", 35))
        elif f < 102:
            sched.append(("front0", 34))
        elif f < 126:
            sched.append(("wave0" if ((f - 102) // 6) % 2 == 0 else "wave1", 34))
        else:
            sched.append(("front1", 34))
    idle = [("front0", 34), ("front1", 34)]
    return sched, idle


def main():
    spr = S.load()
    page, _ = BP.build()
    # Grundseite = Phase 0 aller Schleifen, Dachs in der Tür
    b_on, b_off, b_w, b_sep, _ = scene.draw(water=0, sky=0)
    base_tg = targets(b_on, b_off, b_w, b_sep, range(3, 20))

    def mk_sky(s):
        t_on, t_off, w, sep, _ = scene.draw(water=0, sky=s)
        return t_on, t_off, w, sep

    def mk_water(s):
        t_on, t_off, w, sep, _ = scene.draw(water=s, sky=0)
        return t_on, t_off, w, sep

    sky, sky_rep = loop_states(page, base_tg, scene.N_SKY, SKY_ROWS, mk_sky)
    water, water_rep = loop_states(page, base_tg, scene.N_WATER, WATER_ROWS, mk_water)

    # Dachs: jede Kombination (Pose, x) einmal kodieren
    sched, idle = badger_schedule()
    combos = sorted(set(sched) | set(idle), key=lambda k: (k[1], k[0]))
    b_states, b_index, b_rep = [], {}, []
    for pose, x in combos:
        t_on, t_off, w, sep = b_on.copy(), b_off.copy(), b_w.copy(), b_sep.copy()
        S.paste(t_on, t_off, w, spr[pose], x, scene.BADGER_Y, sep=sep)
        tg = targets(t_on, t_off, w, sep, BADGER_ROWS)
        st = []
        for r in BADGER_ROWS:
            row, win = patch_row(page[r], tg[r], base_tg[r], r)
            st.append(row)
            b_rep.append((pose, x, r, win, sep_errors(row, tg[r][3]), miss_count(row, tg[r])))
        b_index[(pose, x)] = len(b_states)
        b_states.append(st)
    # Grundseite: Dachs in der Tür
    for r, row in zip(BADGER_ROWS, b_states[b_index[sched[0]]]):
        page[r] = row

    hexrows = lambda rows: T.page_to_hex(rows)
    stream = {
        "fps": FPS,
        "base": T.page_to_hex(page),
        "sky": {"rows": SKY_ROWS, "frames_per_state": SKY_FRAMES, "phase": 6, "states": [hexrows(s) for s in sky]},
        "water": {"rows": WATER_ROWS, "frames_per_state": WATER_FRAMES, "states": [hexrows(s) for s in water]},
        "badger": {"rows": BADGER_ROWS, "states": [hexrows(s) for s in b_states],
                   "timeline": [b_index[k] for k in sched],
                   "idle_start": len(sched), "idle_frames_per_state": 12,
                   "idle": [b_index[k] for k in idle],
                   "poses": [f"{p}@{x}" for p, x in combos]},
        "lantern": {"row": BP.LANTERN_ROW, "col": BP.LANTERN_COL,
                    "codes": [T.GFX["w"], T.GFX["y"]], "weights": [0.3, 0.7], "frames_per_draw": 3,
                    "seed": 1974},
        "choice_flash": {"row": 23, "col": 3, "frame": 138},
        "header": {"typed": [[0, "P100"], [120, "P2"], [129, "P20"], [138, "P202"]], "roll_start": 141,
                   "roll_frames": 2, "clock": [18, 42, 7], "service": "LORNTEXT", "date": "Di 13.10."},
        "flash": {"fields_per_cycle": 64, "fields_off": 16, "field_rate": 50},
    }
    json.dump(stream, open(HERE / "demo" / "data" / "stream.json", "w"), indent=0)

    # Bericht
    def summ(rep, label):
        tot = sum(x[-1] for x in rep)
        sep_bad = sum(x[-2] for x in rep)
        wins = [x[-3] for x in rep]
        cells = sum(c1 - c0 for w in wins for c0, c1 in w)
        print(f"{label}: {len(rep)} Zeilen-Updates, Fenster zusammen {cells} Zellen, falsche Sechstel gesamt {tot}, "
              f"Zellen im falschen Trennmodus {sep_bad}")
    summ(sky_rep, "Himmel (Rauch, Leuchtfeuer)")
    summ(water_rep, "Wasser")
    summ(b_rep, "Dachs")
    base_sep = sum(sep_errors(page[r], base_tg[r][3]) for r in range(3, 20) if r not in BADGER_ROWS)
    print(f"Grundseite (ohne Dachszeilen): Zellen im falschen Trennmodus {base_sep}")
    for pose, x, r, win, _, miss in b_rep:
        if miss > 6:
            print("  Dachs", pose, x, "Zeile", r, "falsch", miss, win)

    # Vorschau der Dachsbilder (Ausschnitt Zeilen 14–19)
    tiles = []
    for (pose, x) in combos:
        pg = [row[:] for row in page]
        for r, row in zip(BADGER_ROWS, b_states[b_index[(pose, x)]]):
            pg[r] = row
        img = T.render(T.decode_page(pg))
        x0 = min(max(0, (x // 2 - 2) * T.CW), T.PAGE_W - 9 * T.CW)
        tiles.append(np.pad(img[14 * T.CH:20 * T.CH, x0:x0 + 9 * T.CW], ((4, 4), (4, 4), (0, 0)), constant_values=60))
    rows_ = [np.concatenate(tiles[i:i + 9] + [np.full_like(tiles[0], 60)] * (9 - len(tiles[i:i + 9])), 1)
             for i in range(0, len(tiles), 9)]
    Image.fromarray(np.concatenate(rows_, 0)).save(HERE / "assets" / "badger_frames.png")
    Image.fromarray(BP.compose(T.render(T.decode_page(page)))).save(HERE / "assets" / "page_preview.png")
    print("Posen:", len(combos), "ok")


if __name__ == "__main__":
    main()
