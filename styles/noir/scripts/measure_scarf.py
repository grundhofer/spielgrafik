#!/usr/bin/env python3
"""Prüft in der fertigen Aufnahme (mit Filmlook), ob der Schal rot bleibt und die Figur im Dunkeln Silhouette ist.

    .venv/bin/python styles/noir/scripts/render_frames.py OUT --frames 180
    .venv/bin/python styles/noir/scripts/render_frames.py PROBE --frames 180 -- --probe-badger-only
    .venv/bin/python styles/noir/scripts/measure_scarf.py OUT PROBE [--json assets/measure_scarf.json]

Lage der Figur je Bild: aus dem Prüfmodus (nur Figur auf Magenta) über den Schablonenvergleich mit dem Bogen
(assets/badger.png, Bild und Versatz mit der größten Überdeckung). Schal = Pixel des Bogens mit Sättigung > 0,3 und
Rot als größtem Kanal; hinteres Schalende = Schalpixel links von Spalte 40 und unter Zeile 50 (nur Laufbilder und
stand, dort hängt das Ende hinter dem Rücken). Gemessen wird in der fertigen Aufnahme:
  * Anteil der Schalpixel (ganzer Schal, hinteres Ende) mit Sättigung > 0,3 und Rot als größtem Kanal
  * Anteil der Figurenpixel (Alpha > 0,9, ohne Schal) mit Helligkeit < 0,10
  * Kantenlicht: Anteil der Figurenpixel, die im Prüfmodus heller sind als Albedo × Umgebungslicht + 0,08
"""
import argparse, json, pathlib

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
FW, FH = 120, 186


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float32) / 255.0


def sat_red(rgb):
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1e-3)
    return (sat > 0.3) & (rgb[..., 0] >= mx - 1e-6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("probe_dir")
    ap.add_argument("--json")
    ap.add_argument("--range", default="24-60", help="Bildbereich für die Zusammenfassung (Figur im Dunkeln)")
    a = ap.parse_args()
    sheet = np.asarray(Image.open(ROOT / "assets/badger.png").convert("RGBA")).astype(np.float32) / 255.0
    nfr = sheet.shape[1] // FW
    frames = [sheet[:, i * FW:(i + 1) * FW] for i in range(nfr)]
    alphas = [f[..., 3] > 0.5 for f in frames]
    scarf = [sat_red(f[..., :3]) & (f[..., 3] > 0.5) for f in frames]
    yy, xx = np.mgrid[0:FH, 0:FW]
    rear = [s & (xx < 40) & (yy > 50) if i <= 8 else np.zeros_like(s) for i, s in enumerate(scarf)]

    files = sorted(pathlib.Path(a.frames_dir).glob("f*.png"))
    probes = sorted(pathlib.Path(a.probe_dir).glob("f*.png"))
    rows = []
    for i, (fp, pp) in enumerate(zip(files, probes)):
        pr = np.asarray(Image.open(pp).convert("RGB")).astype(np.int16)
        mag = (np.abs(pr[..., 0] - 255) < 40) & (pr[..., 1] < 40) & (np.abs(pr[..., 2] - 255) < 40)
        fig = ~mag
        ys, xs = np.where(fig)
        if len(ys) == 0:
            rows.append({"i": i, "visible": False})
            continue
        # Bild und Versatz: oberste Zeile und linke Spalte des Bogens auf die Maske legen, ±3 px nachsuchen
        best = (-1, 0, 0, 0)
        P = 140                                      # Rand um das Fenster (größer als ein Bild)
        pad = np.pad(fig, P)
        wy0, wx0 = ys.min() - 8, xs.min() - 8        # Fenster um die Figur (Bildschirmkoordinaten)
        win = pad[wy0 + P:wy0 + P + FH + 16, wx0 + P:wx0 + P + FW + 16]
        for f in range(nfr):
            fy, fx = np.where(alphas[f])
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    oy = ys.min() - fy.min() + dy
                    # links abgeschnitten (Figur kommt ins Bild): an der rechten Kante ausrichten
                    ox = (xs.max() - fx.max() if xs.min() == 0 else xs.min() - fx.min()) + dx
                    sub = np.zeros_like(win)
                    ly, lx = oy - wy0, ox - wx0
                    sy0, sx0 = max(ly, 0), max(lx, 0)
                    sy1, sx1 = min(ly + FH, win.shape[0]), min(lx + FW, win.shape[1])
                    if sy1 <= sy0 or sx1 <= sx0:
                        continue
                    sub[sy0:sy1, sx0:sx1] = alphas[f][sy0 - ly:sy1 - ly, sx0 - lx:sx1 - lx]
                    iou = (sub & win).sum() / max((sub | win).sum(), 1)
                    if iou > best[0]:
                        best = (iou, f, oy, ox)
        iou, f, oy, ox = best
        img = load(fp)
        prb = load(pp)

        def place(m):
            out = np.zeros(fig.shape, bool)
            y0, x0 = max(oy, 0), max(ox, 0)
            y1, x1 = min(oy + FH, fig.shape[0]), min(ox + FW, fig.shape[1])
            out[y0:y1, x0:x1] = m[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
            return out

        sc, re = place(scarf[f]), place(rear[f])
        body = place((frames[f][..., 3] > 0.9) & ~scarf[f]) & fig
        red_now = sat_red(img)
        lum = img @ np.array([0.299, 0.587, 0.114], np.float32)
        # Kantenlicht im Prüfmodus: heller als Albedo × Umgebung (0,24) + 0,08
        alb = np.zeros(img.shape, np.float32)
        y0, x0 = max(oy, 0), max(ox, 0)
        y1, x1 = min(oy + FH, fig.shape[0]), min(ox + FW, fig.shape[1])
        alb[y0:y1, x0:x1] = frames[f][y0 - oy:y1 - oy, x0 - ox:x1 - ox, :3]
        extra = (prb - alb * 0.24).max(-1)
        rows.append({"i": i, "t": round(i / 30, 3), "visible": True, "frame": int(f), "iou": round(float(iou), 3),
                     "scarf_px": int(sc.sum()), "scarf_red": round(float((red_now & sc).sum() / max(sc.sum(), 1)), 3),
                     "rear_px": int(re.sum()),
                     "rear_red": round(float((red_now & re).sum() / re.sum()), 3) if re.sum() else None,
                     "body_px": int(body.sum()), "body_dark": round(float((lum[body] < 0.10).mean()), 3),
                     "body_lum_median": round(float(np.median(lum[body])), 3),
                     "rim_share": round(float((extra[body] > 0.08).mean()), 3)})

    lo, hi = (int(v) for v in a.range.split("-"))
    sel = [r for r in rows if r.get("visible") and lo <= r["i"] <= hi]
    late = [r for r in rows if r.get("visible") and r["i"] >= 70 and r["rear_red"] is not None]
    def rear_txt(r):
        return "-" if r["rear_red"] is None else f"{r['rear_red'] * 100:5.1f} %"

    for r in rows:
        if r.get("visible") and (r["i"] % 6 == 0 or lo <= r["i"] <= hi and r["i"] % 3 == 0):
            print(f"Bild {r['i']:3d} t={r['t']:.2f} Bogenbild {r['frame']:2d} IoU {r['iou']:.3f}  Schal rot "
                  f"{r['scarf_red'] * 100:5.1f} %  hinteres Ende rot "
                  f"{rear_txt(r)} ({r['rear_px']} px)  "
                  f"Figur < 0,10: {r['body_dark'] * 100:5.1f} %  Median {r['body_lum_median']:.3f}  "
                  f"Kantenlicht > 0,08: {r['rim_share'] * 100:4.1f} %")

    def rng(key, rs):
        v = [r[key] for r in rs if r[key] is not None]
        return (round(min(v), 3), round(max(v), 3)) if v else None

    summary = {"range": [lo, hi], "min_iou": rng("iou", [r for r in rows if r.get("visible")])[0],
               "scarf_red": rng("scarf_red", sel), "rear_red": rng("rear_red", sel),
               "rear_red_from_70": rng("rear_red", late), "body_dark": rng("body_dark", sel),
               "body_lum_median": rng("body_lum_median", sel), "rim_share": rng("rim_share", sel)}
    print(json.dumps(summary, ensure_ascii=False))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps({"summary": summary, "frames": rows}, indent=1))


if __name__ == "__main__":
    main()
