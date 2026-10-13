#!/usr/bin/env python3
"""Misst den Dachs in der Godot-Ausgabe: Bodenläufe (Standfuß), Schnauzenspitze, Figurhöhe je Videobild.

    .venv/bin/python styles/ki-spritesheet/scripts/measure_badger.py <tmpdir> [--raw] [--t0 0] [--frames 210]

Rendert die Demo zweimal mit --badger-only (Dachs allein ohne Tönung, einmal vor Magenta, einmal vor Grün) in
<tmpdir> und gewinnt daraus den Alphakanal: a = 1 - (Bild_magenta - Bild_grün) / (Magenta - Grün). Figurpixel
sind Pixel mit Alpha > 0,5 (schwache Kantenpixel zählen nicht). Ausgewertet wird:
  * je Bildwechsel des Sprites: Bodenläufe (Spalten mit Figurpixeln in den 3 Zeilen über GROUND_Y) in Weltkoordinaten
  * Standfuß beim Laufen: Ferse/Zehe des stehenden Fußes vor und nach dem Wechsel (Abweichung in px)
  * Stehen/Idle/Winken: Bodenläufe aller Bilder eines Abschnitts (Spanne in px)
  * Kopf: Schnauzenspitze (Seitenansicht) je Bild; Sprünge zwischen aufeinanderfolgenden Bildern
  * Bodenzeile: unterste Zeile mit Alpha > 0,5 je Bild (soll in allen Bildern am Boden gleich sein)
  * Stehen: Haltezeiten und Bildfolge des letzten Abschnitts (Atemschleife, eingestreute Blinzler)
Schreibt <tmpdir>/measure.json und gibt eine Übersicht aus.
"""
import argparse, json, pathlib, subprocess, sys

import numpy as np
from PIL import Image

E = pathlib.Path(__file__).resolve().parents[1]
GROUND_Y = 656
PLAN = [("walk", 0), ("idle", 80), ("jump", 100), ("idle", 124), ("wave", 130), ("idle", 180)]


def seg(vf):
    s = 0
    for i, (_, f) in enumerate(PLAN):
        if vf >= f:
            s = i
    return s


def runs(cols, gap=2):
    idx = np.flatnonzero(cols)
    out = []
    if idx.size:
        s = p = idx[0]
        for i in idx[1:]:
            if i - p > gap:
                out.append([int(s), int(p) + 1])
                s = i
            p = i
        out.append([int(s), int(p) + 1])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tmp")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--frames", type=int, default=210)
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--alpha", type=float, default=0.5)
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    subprocess.run(["godot", "--headless", "--path", str(E / "demo"), "--import"], capture_output=True)
    args = ["--badger-only"] + (["--raw"] if a.raw else []) + ([f"--t0={a.t0}"] if a.t0 else [])
    for key in ("ff00ff", "00ff00"):
        d = tmp / key
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("f*.png"):
            f.unlink()
        r = subprocess.run(["godot", "--path", str(E / "demo"), "--position", "20000,20000", "--resolution",
                            "1280x720", "--write-movie", str(d / "f.png"), "--fixed-fps", "30", "--quit-after",
                            str(a.frames), "--"] + args + [f"--key={key}"], capture_output=True, text=True)
        errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
        if errs:
            print("\n".join(errs[:10]))
    pngs_m = sorted((tmp / "ff00ff").glob("f*.png"))
    pngs_g = sorted((tmp / "00ff00").glob("f*.png"))
    vf0 = int(round(a.t0 * 30))
    rows = []
    prev = None
    for vf_rel, (p, pg) in enumerate(zip(pngs_m, pngs_g)):
        vf = vf0 + vf_rel
        im = np.asarray(Image.open(p).convert("RGB")).astype(int)
        ig = np.asarray(Image.open(pg).convert("RGB")).astype(int)
        # Magenta (255,0,255) minus Grün (0,255,0) = (255,-255,255): je Kanal (1 - a) * Differenz
        diff = (im - ig) * np.array([1, -1, 1])
        alpha = 1.0 - diff.mean(-1) / 255.0
        fig = alpha > a.alpha
        ys = np.flatnonzero(fig.any(1))
        if not ys.size:
            rows.append(None)
            continue
        band = fig[GROUND_Y - 3:GROUND_Y].any(0)
        g = runs(band)
        top, bot = int(ys[0]), int(ys[-1])
        # Schnauzenspitze: rechtester Figurpixel im oberen Drittel
        lim = top + (bot - top) // 3
        sub = fig[top:lim]
        xs = np.flatnonzero(sub.any(0))
        tipx = int(xs[-1])
        tipy = int(top + np.flatnonzero(sub[:, tipx]).mean())
        key = hash(im.astype(np.uint8).tobytes())
        edge = bool(fig[:, 0].any() or fig[:, -1].any())      # Figur am Bildrand angeschnitten
        # Sohlenkante unterpixelgenau: Spalten, die 8 Zeilen über dem Boden deckend sind, Alpha bis zum Boden
        # aufsummieren, 75. Perzentil (wie sole_edge in build_sprites.py, aber im fertigen Bild)
        sub8 = alpha[GROUND_Y - 8:GROUND_Y + 2]
        solid = sub8[0] > 0.9
        sole = round(float(GROUND_Y - 8 + np.percentile(np.clip(sub8[:, solid], 0, 1).sum(0), 75)), 2) \
            if solid.sum() >= 3 else None
        # Movie Maker schreibt das erste Bild nach dem ersten _process: Bild m zeigt Videobild m + 1 der Zeitleiste
        rows.append({"vf": vf, "seg": seg(vf + 1), "anim": PLAN[seg(vf + 1)][0], "ground": g, "top": top, "bottom": bot,
                     "tip": [tipx, tipy], "changed": prev is not None and key != prev, "key": key,
                     "edge": edge, "sole": sole})
        prev = key
    # Bildwechsel: Abschnitte gleicher Bilder
    holds = []
    for r_ in rows:
        if r_ is None:
            continue
        if not holds or r_["changed"]:
            holds.append(dict(r_, n=1))
        else:
            holds[-1]["n"] += 1
    out = {"holds": holds}
    print("Haltezeiten (Videobilder):", [h["n"] for h in holds])
    print("Bild  vf  Zustand  Bodenläufe  Schnauze  Höhe  Sohle")
    for h in holds:
        print(f"{h['vf']:4d} {h['anim']:5s} {str(h['ground']):34s} {h['tip']} {h['bottom'] - h['top'] + 1}"
              f"{'  (Rand)' if h['edge'] else ''}  {h['sole']}")
    # Standfuß beim Laufen: je Wechsel das Paar Bodenläufe mit gemeinsamem Ende (Ferse links oder Zehe rechts)
    walk = [h for h in holds if h["anim"] == "walk"]
    dev = []
    for h0, h1 in zip(walk, walk[1:]):
        best = None
        for r0 in h0["ground"]:
            for r1 in h1["ground"]:
                for e in (0, 1):
                    d = r1[e] - r0[e]
                    if best is None or abs(d) < abs(best[0]):
                        best = (d, "Ferse" if e == 0 else "Zehe", r0, r1)
        dev.append(best)
    out["walk_stand_foot"] = [[b[0], b[1]] for b in dev if b]
    print("Laufen, Standfuß je Wechsel (px, Ende):", [(b[0], b[1]) for b in dev if b])
    # Stehen: Spanne der Bodenläufe je Abschnitt
    for s in range(1, len(PLAN)):
        hs = [h for h in holds if h["seg"] == s and h["ground"]]
        if not hs:
            continue
        lefts = [h["ground"][0][0] for h in hs]
        rights = [h["ground"][-1][1] for h in hs]
        bots = [h["bottom"] for h in hs]
        print(f"{PLAN[s][0]:5s} (Abschnitt {s}): linker Fußrand {min(lefts)}..{max(lefts)}, rechter {min(rights)}.."
              f"{max(rights)}, Unterkante {min(bots)}..{max(bots)}")
        out[f"seg{s}"] = {"left": [min(lefts), max(lefts)], "right": [min(rights), max(rights)],
                          "bottom": [min(bots), max(bots)]}
    # Bodenzeile und Höhe je Zustand (ohne am Bildrand angeschnittene Bilder)
    full = [h for h in holds if not h["edge"]]
    out["ground_rows"] = {}
    for an in ("walk", "idle", "jump", "wave"):
        hs = [h for h in full if h["anim"] == an]
        if not hs:
            continue
        bots = [h["bottom"] for h in hs]
        heights = [h["bottom"] - h["top"] + 1 for h in hs]
        soles = [h["sole"] for h in hs if h["sole"] is not None and h["bottom"] >= GROUND_Y - 2]
        print(f"{an:5s}: Bodenzeile (Alpha > {a.alpha:.2f}) {sorted(set(bots))}, Höhe {min(heights)}–{max(heights)} px"
              + (f", Sohlenkante {min(soles):.2f}–{max(soles):.2f}" if soles else ""))
        out["ground_rows"][an] = sorted(set(bots))
        out[f"height_{an}"] = [min(heights), max(heights)]
        if soles:
            out[f"sole_{an}"] = [min(soles), max(soles)]
    # Stehen im letzten Abschnitt: Bildfolge als (Start-Videobild, Dauer, Bild-ID)
    last = len(PLAN) - 1
    ids = {}
    seq = []
    for h in holds:
        if h["seg"] != last:
            continue
        ids.setdefault(h["key"], len(ids))
        seq.append((h["vf"] + 1, h["n"], ids[h["key"]]))
    if seq:
        print("Stehen ab Videobild", PLAN[last][1], "(Start, Dauer, Bild):", seq)
        out["idle_sequence"] = seq
    for h in holds:
        h.pop("key", None)
    (tmp / "measure.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
