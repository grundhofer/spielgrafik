#!/usr/bin/env python3
"""Misst die VN-Figur in der laufenden Godot-Demo (Messmodus: nur die Figur vor Magenta).

Aufruf aus dem Projektordner:
    .venv/bin/python styles/anime-visual-novel/tools/measure.py

Geprüft wird Bild für Bild (6 s, 30 fps):
  - Silhouette (oben, links, rechts, unten) und Kopfmitte (Schwerpunkt im oberen Viertel der Figur).
  - In Ruhephasen (nach dem Auftritt, außerhalb der Hüpfer) müssen Silhouette und Kopfmitte auf den Pixel
    gleich bleiben, auch wenn die Mimik wechselt.
  - Haltezeiten der Gesichtszustände (Mund/Augen/Mimik, am Kopf ausgerichtet, auch während der Hüpfer): jede
    Fassung muss mindestens 3 Bilder stehen (Lippen im 3-Bilder-Takt, Blinzeln 3 Bilder, harte Mimikwechsel);
    kürzere Haltezeiten werden gemeldet und führen zu Rückgabe 1.
  - Zwischen zwei Ruhebildern dürfen sich nur Pixel am Kopf ändern (head aus demo/art/sprite.json, nach unten um
    20 % verlängert, weil ein offener Mund bis in den Schal reicht, und um die Bereiche der Gesichtsteile
    erweitert, falls sprite.json "regions" enthält), nie am Körper.
Ausgabe: Tabelle der Abweichungen und media/measure.json (mit --out DIR stattdessen DIR/measure.json, z. B. für
Probeläufe mit Testbildern, damit media/ sauber bleibt). Rückgabe 1, wenn Silhouette oder Kopf in Ruhe springen
oder sich Pixel außerhalb des Kopfes ändern.
"""
import argparse, json, pathlib, subprocess, sys, tempfile

import numpy as np
from PIL import Image

SD = pathlib.Path(__file__).resolve().parent.parent
FPS, N = 30, 180
# Zeitfenster mit gewollter Bewegung (aus main.gd): Auftritt, Hüpfer. Bild i zeigt t = (i + 1) / FPS,
# weil _process vor dem Schreiben des Bildes einmal delta addiert.
MOVING = [(0.0, 0.42), (1.80, 1.80 + 0.22 + 0.04), (3.40, 3.40 + 0.26 + 0.04)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(SD / "media"))
    a_ = ap.parse_args()
    sj = json.loads((SD / "demo" / "art" / "sprite.json").read_text())
    hd = sj["head"]
    face = [sj["pos"][0] + hd[0], sj["pos"][1] + hd[1], sj["pos"][0] + hd[2],
            sj["pos"][1] + hd[3] + round(0.2 * (hd[3] - hd[1]))]
    # Gesichtsteile aus prep_config.json (offener Mund reicht in den Schal). Die Masken werden in prep.py am
    # Rechteck abgeschnitten und dann weich gezeichnet (Gauß 2,5 Quellpixel ≈ 2 Anzeigepixel): bis zu 3 px
    # außerhalb des Rechtecks dürfen sich Pixel noch leicht ändern.
    fp = 3
    for r in sj.get("regions", {}).values():
        face = [min(face[0], sj["pos"][0] + r[0] - fp), min(face[1], sj["pos"][1] + r[1] - fp),
                max(face[2], sj["pos"][0] + r[2] + fp), max(face[3], sj["pos"][1] + r[3] + fp)]
    with tempfile.TemporaryDirectory() as td:
        cmd = ["godot", "--path", str(SD / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
               "--write-movie", str(pathlib.Path(td) / "m.png"), "--fixed-fps", str(FPS), "--quit-after", str(N),
               "--", "--measure"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
        if errs:
            print("\n".join(errs[:10]))
        files = sorted(pathlib.Path(td).glob("m*.png"))
        rows, masks = [], []
        for i, f in enumerate(files):
            a = np.asarray(Image.open(f).convert("RGB")).astype(np.int16)
            key = (np.abs(a - np.array([255, 0, 255])).sum(-1) > 90)
            ys, xs = np.where(key)
            if len(xs) == 0:
                rows.append(None)
                masks.append(None)
                continue
            top, bot, left, right = ys.min(), ys.max(), xs.min(), xs.max()
            q = top + (min(bot, 719) - top) // 4
            hy, hx = np.where(key[top:q])
            rows.append({"frame": i, "t": round((i + 1) / FPS, 3), "top": int(top), "bottom": int(bot),
                         "left": int(left), "right": int(right),
                         "head_x": round(float(hx.mean()), 2), "head_y": round(float(hy.mean() + top), 2)})
            masks.append(a)
    rest = [r for r in rows if r and not any(a <= r["t"] < b for a, b in MOVING)]
    ref = rest[0]
    # Gesichtszustände: Gesichtsbereich je Bild am oberen Figurenrand ausgerichtet (Hüpfer verschieben senkrecht)
    states, sig_ids = [], {}
    for r, m in zip(rows, masks):
        if not r or r["t"] < MOVING[0][1]:
            states.append(None)
            continue
        dy = r["top"] - ref["top"]
        crop = m[face[1] + dy:face[3] + dy + 1, face[0]:face[2] + 1]
        key = None
        for k, v in sig_ids.items():   # gleiche Fassung = höchstens Rundungsrauschen
            if v.shape == crop.shape and np.abs(v - crop).max() <= 8:
                key = k
                break
        if key is None:
            key = len(sig_ids)
            sig_ids[key] = crop
        states.append(key)
    holds, cur, start = [], None, None
    for i, st in enumerate(states + [None]):
        if st != cur:
            if cur is not None:
                holds.append({"from_frame": start, "t": round((start + 1) / FPS, 3), "frames": i - start, "state": cur})
            cur, start = st, i
    short = [h for h in holds[1:-1] if h["frames"] < 3]   # erste/letzte Haltezeit sind vom Messfenster abgeschnitten
    bad = []
    for r in rest:
        d = {k: r[k] - ref[k] for k in ("top", "bottom", "left", "right", "head_x", "head_y")}
        if any(abs(v) > 0.01 for v in d.values()):
            bad.append((r["t"], d))
    # Pixeländerungen zwischen aufeinanderfolgenden Ruhebildern
    changes = []
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        if not a or not b or a not in rest or b not in rest:
            continue
        diff = np.abs(masks[i] - masks[i - 1]).max(-1) > 8
        if diff.any():
            ys, xs = np.where(diff)
            changes.append({"t": b["t"], "box": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                            "pixels": int(diff.sum())})
    outside = [c for c in changes if c["box"][0] < face[0] or c["box"][1] < face[1] or c["box"][2] > face[2]
               or c["box"][3] > face[3]]
    union = None
    for c in changes:
        bx = c["box"]
        union = bx if union is None else [min(union[0], bx[0]), min(union[1], bx[1]),
                                          max(union[2], bx[2]), max(union[3], bx[3])]
    print(f"Bilder: {len(rows)}, Ruhebilder: {len(rest)}, Referenz t={ref['t']}: "
          f"oben {ref['top']}, links {ref['left']}, rechts {ref['right']}, Kopfmitte {ref['head_x']}/{ref['head_y']}")
    print(f"Ruhebilder mit abweichender Silhouette/Kopfmitte: {len(bad)}")
    for t, d in bad[:12]:
        print(f"  t={t:.2f}: {d}")
    print(f"Mimikwechsel in Ruhe: {len(changes)} Bildwechsel, alle Änderungen im Rechteck {union}; "
          f"Kopf {face}; außerhalb: {len(outside)}")
    for c in changes:
        print(f"  t={c['t']:.2f}: {c['pixels']:6d} px in {c['box']}")
    print(f"Gesichtszustände: {len(sig_ids)} verschiedene, {len(holds)} Haltezeiten, Bilder je Haltezeit: "
          + " ".join(str(h["frames"]) for h in holds))
    print(f"Haltezeiten unter 3 Bildern: {len(short)}" + "".join(f"\n  t={h['t']:.3f}: {h['frames']} Bild(er), Zustand {h['state']}"
                                                         for h in short))
    hops = [r for r in rows if r and any(a <= r["t"] < b for a, b in MOVING[1:])]
    if hops:
        print("Hüpfer (oben, Kopfmitte y):", " ".join(f"{r['t']:.2f}:{r['top']}" for r in hops))
    out = pathlib.Path(a_.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "measure.json").write_text(json.dumps(
        {"reference": ref, "rest_frames": len(rest), "rest_deviations": bad, "face_changes": changes,
         "face_change_union_box": union, "head_region_screen": face, "changes_outside_face": outside,
         "face_holds": holds, "face_holds_under_3": short,
         "test_images": sj.get("test_images", False), "rows": rows}, indent=1))
    print(f"geschrieben: {out / 'measure.json'}")
    return 1 if bad or outside or short else 0


if __name__ == "__main__":
    sys.exit(main())
