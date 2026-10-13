#!/usr/bin/env python3
"""Misst den laufenden Dachs in der gerenderten Godot-Demo (PIPELINE.md -> Figuren und Animation).

Aufruf aus dem Projektordner:
    .venv/bin/python styles/oelmalerei/tools/measure_walk.py [--frames DIR]

Ohne --frames rendert das Skript die Prüfszene demo/check/measure_walk.tscn (die Demo mit allem außer dem Dachs
ausgeblendet, auf Magenta, ohne Nachbearbeitung) mit 30 fps in ein Temp-Verzeichnis. Gemessen wird je Bild:
  - Füße: Spaltengruppen der deckenden Pixel in den untersten 8 Zeilen über der Fußlinie (FEET_Y in main.gd).
  - Standfuß: zwischen zwei aufeinanderfolgenden Bildern die Verschiebung (-8..8 px), bei der ein Fuß des alten
    Bilds am besten (IoU) auf einem Fuß des neuen liegt. Beim Laufen soll sie 0 sein (±1 px durch den
    Boil-Shader, der Texel um 1 px springen lässt).
  - Stehen: unterste deckende Zeile und Fußgruppen nach dem Halt.
  - Kopf: oberste Zeile und waagerechter Schwerpunkt des oberen Viertels der Figur (nur zur Information).
"""
import argparse, json, pathlib, subprocess, sys, tempfile

import numpy as np
from PIL import Image

SD = pathlib.Path(__file__).resolve().parent.parent
FEET_Y = 676          # main.gd: FEET_Y
BAND = 8


def render(out):
    demo = SD / "demo"
    subprocess.run(["godot", "--headless", "--path", str(demo), "--import"], capture_output=True)
    r = subprocess.run(["godot", "--path", str(demo), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "180",
                        "res://check/measure_walk.tscn"], capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "SCRIPT ERROR" in l or "SHADER ERROR" in l]
    if errs:
        sys.exit("\n".join(errs))


def mask_of(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    return (np.abs(a[..., 0] - 255) + a[..., 1] + np.abs(a[..., 2] - 255)) > 90


def feet(m):
    band = m[FEET_Y - BAND:FEET_Y + 1]
    xs = np.nonzero(band.any(0))[0]
    if len(xs) == 0:
        return []
    groups, s0, prev = [], xs[0], xs[0]
    for c in xs[1:]:
        if c > prev + 1:
            groups.append((s0, prev))
            s0 = c
        prev = c
    groups.append((s0, prev))
    out = []
    for g0, g1 in groups:
        f = np.zeros_like(band)
        f[:, g0:g1 + 1] = band[:, g0:g1 + 1]
        if f.sum() > 12:
            out.append((int(g0), int(g1), f))
    return out


def drawings():
    """Alphamasken der Laufbilder aus walk.png (zur Zuordnung: welches Bild zeigt ein gerendertes Bild?)."""
    meta = json.loads((SD / "demo" / "art" / "walk.json").read_text())
    a = np.asarray(Image.open(SD / "demo" / "art" / "walk.png"))[..., 3] > 128
    cw = meta["frame_w"]
    return [a[:, i * cw:(i + 1) * cw] for i in range(meta["frames"])], meta


def classify(m, draws, meta):
    """Bild-Nr. eines gerenderten Bilds: beste IoU der Figur gegen jedes Laufbild (Fußlinie fest, x frei)."""
    fy = meta["feet_y"]
    ys, xs = np.nonzero(m)
    best = (-1.0, None)
    for k, d in enumerate(draws):
        h = d.shape[0]
        region = m[FEET_Y - fy:FEET_Y - fy + h]
        dxs = np.nonzero(d.any(0))[0]
        for ox in range(xs.min() - dxs.min() - 4, xs.min() - dxs.min() + 5):
            if ox < 0 or ox + d.shape[1] > m.shape[1]:
                continue
            r = region[:, ox:ox + d.shape[1]]
            iou = (r & d).sum() / max(1, (r | d).sum())
            if iou > best[0]:
                best = (iou, k)
    return best[1]


def stance_shift(fa, fb, rng=8):
    """Beste Verschiebung eines Fußes. Liegt der Fuß ganz in der verschmolzenen Silhouette der Durchgangspose,
    ist die IoU über mehrere dx exakt gleich; dann zählt das dx mit dem kleinsten Betrag (0, wenn der Fuß
    ortsfest sein kann)."""
    best, dxs = -1.0, [None]
    for _, _, ma in fa:
        for _, _, mb in fb:
            sc = np.array([(np.roll(ma, dx, 1) & mb).sum() / max(1, (np.roll(ma, dx, 1) | mb).sum())
                           for dx in range(-rng, rng + 1)])
            if sc.max() > best:
                best, dxs = sc.max(), list(np.nonzero(sc >= sc.max() - 1e-9)[0] - rng)
    return best, int(min(dxs, key=abs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", help="Ordner mit f00000000.png ... aus der Prüfszene")
    ap.add_argument("--band", type=int, default=BAND, help="Zeilen über der Fußlinie für die Fußerkennung")
    a = ap.parse_args()
    globals()["BAND"] = a.band
    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(a.frames) if a.frames else pathlib.Path(td)
        if not a.frames:
            render(d)
        files = sorted(d.glob("f*.png"))
        masks = [mask_of(p) for p in files]
    draws, meta = drawings()
    rows = []
    for i, m in enumerate(masks):
        ys, xs = np.nonzero(m)
        if len(xs) == 0 or xs.min() <= 0:
            rows.append(None)                       # Figur (noch) nicht ganz im Bild
            continue
        top, bot = ys.min(), ys.max()
        head = m[top:top + (bot - top) // 4]
        hx = float((head.sum(0) * np.arange(m.shape[1])).sum() / head.sum())
        rows.append({"top": int(top), "bot": int(bot), "head_x": hx, "feet": feet(m), "m": m,
                     "draw": classify(m, draws, meta)})
    walk, change = [], []
    for i in range(1, len(rows)):
        r0, r1 = rows[i - 1], rows[i]
        if r0 is None or r1 is None:
            continue
        changed = r0["draw"] != r1["draw"]
        moved = (r0["m"] ^ r1["m"]).sum() / max(1, r1["m"].sum()) > 0.25   # Körper versetzt (Vorschub)
        iou, dx = stance_shift(r0["feet"], r1["feet"])
        rec = (i, dx, round(float(iou), 2), f"{r0['draw']}->{r1['draw']}")
        (change if (changed or moved) else walk).append(rec)
    # Stehen: ab dem letzten Bildwechsel
    last = change[-1][0] if change else 0
    stand = [r for r in rows[last:] if r is not None]
    bots = sorted({r["bot"] for r in stand})
    print(f"Bilder ausgewertet: {sum(r is not None for r in rows)} von {len(rows)} (Figur ganz im Bild)")
    print(f"Bildwechsel beim Laufen: {len(change)}; Standfuß-Verschiebung je Wechsel (px): "
          f"{[c[1] for c in change]}")
    per = {}
    for c in change:
        per.setdefault(c[3], []).append(c[1])
    print("  je Wechsel (Bild alt->neu): " + ", ".join(f"{k}: {v}" for k, v in sorted(per.items())))
    bad = [c for c in change if abs(c[1]) > 1]
    print(f"  max |Verschiebung| beim Wechsel: {max(abs(c[1]) for c in change) if change else 0} px; "
          f"Wechsel über ±1 px: {len(bad)} {bad}")
    print(f"Haltebilder (gleiche Zeichnung, nur Boil): max |Verschiebung| "
          f"{max(abs(w[1]) for w in walk) if walk else 0} px")
    print(f"Stehen ab Bild {last}: unterste Zeile {bots}, Fußgruppen "
          f"{sorted({tuple((g0, g1) for g0, g1, _ in r['feet']) for r in stand})[:4]} ...")
    hx = [r["head_x"] for r in rows if r is not None]
    dh = np.diff(hx)
    print(f"Kopf: Schwerpunkt-Sprünge je Bild beim Laufen min/max {dh.min():.1f}/{dh.max():.1f} px")
    ok = not bad and len(bots) <= 2 and (bots[-1] - bots[0] <= 1)
    print("ok" if ok else "PRÜFEN")


if __name__ == "__main__":
    main()
