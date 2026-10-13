#!/usr/bin/env python3
"""Messläufe der Demo in 320×240 (ohne tools/capture.py): Verdeckung, Füße, Treue des Hintergrunds.

    .venv/bin/python styles/vorgerendert-fixkamera/scripts/probe.py [--keep DIR]

Läufe (je 180 Bilder, --fixed-fps 30, Godot schreibt die Basisauflösung):
  normal     wie die Aufnahme (zweimal: Reproduzierbarkeit)
  key        Hintergrund magenta, Tiefe aktiv, ohne Oberfläche/Schatten -> Figurenmaske mit Verdeckung
  key_nod    wie key, aber --no-depth -> Figurenmaske ohne Verdeckung
  noanim     --no-anim -> Anteil der Pixel, die das Bildfolge-Overlay ändert
  feet       --feet-log -> Weltlage der Fußknochen je Bild
Ausgabe: Kennzahlen als JSON (stdout) und probe.json im Eintragsordner unter assets/probe/.
"""
import argparse
import json
import pathlib
import re
import subprocess
import tempfile

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
DEMO = STYLE / "demo"
N = 180


def run(out_dir, args, log=False):
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--write-movie", str(out_dir / "f.png"),
           "--fixed-fps", "30", "--quit-after", str(N)]
    if args:
        cmd += ["--"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
    return r.stdout, errs


def frames(d):
    return [np.asarray(Image.open(p).convert("RGB")) for p in sorted(d.glob("f*.png"))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", default=None)
    a = ap.parse_args()
    td = pathlib.Path(a.keep) if a.keep else pathlib.Path(tempfile.mkdtemp(prefix="probe_"))
    res = {"errors": []}
    outs = {}
    for name, args in [("normal", []), ("normal2", []), ("key", ["--key"]), ("key_nod", ["--key", "--no-depth"]),
                       ("noanim", ["--no-anim"]), ("feet", ["--feet-log", "--key"]),
                       ("perpixel", ["--per-pixel"]), ("noui", ["--no-ui"])]:
        so, errs = run(td / name, args)
        outs[name] = so
        res["errors"] += [f"{name}: {e}" for e in errs]

    nf, nf2 = frames(td / "normal"), frames(td / "normal2")
    res["frames"] = len(nf)
    res["size"] = list(nf[0].shape[1::-1])
    res["identical_runs"] = all(np.array_equal(x, y) for x, y in zip(nf, nf2)) and len(nf) == len(nf2)

    # Figurenmasken
    key, nod = frames(td / "key"), frames(td / "key_nod")
    mag = np.array([255, 0, 255])
    mk = [np.any(f != mag, axis=2) for f in key]
    mn = [np.any(f != mag, axis=2) for f in nod]
    occl = []
    for i, (a1, b1) in enumerate(zip(mk, mn)):
        tot = int(b1.sum())
        hid = int((b1 & ~a1).sum())
        occl.append((i, tot, hid))
    vis = [(i, tot, hid) for i, tot, hid in occl if tot > 0]
    res["badger_visible_frames"] = [vis[0][0], vis[-1][0]] if vis else None
    res["occlusion"] = {f"{i}": [tot, hid, round(hid / tot, 3)] for i, tot, hid in occl if tot > 0 and i % 6 == 0}
    hidden = [i for i, tot, hid in occl if tot > 0 and hid / tot > 0.02]
    res["frames_with_occlusion_gt2pct"] = [hidden[0], hidden[-1], len(hidden)] if hidden else []
    # erstes Bild, in dem die Figur in der Totale sichtbar wird (mit Tiefe)
    first_vis = next((i for i, m in enumerate(mk) if m.sum() > 0), None)
    res["first_visible_frame_with_depth"] = first_vis
    res["first_visible_frame_without_depth"] = next((i for i, m in enumerate(mn) if m.sum() > 0), None)

    # Kopf und Fußzeile je Bild (aus der Maske ohne Verdeckung)
    rows = {}
    for i, m in enumerate(mn):
        ys, xs = np.nonzero(m)
        if len(ys):
            rows[i] = (int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max()))
    res["badger_box_every_15"] = {str(i): rows[i] for i in sorted(rows) if i % 15 == 0}

    # Overlay: Anteil geänderter Pixel durch die Bildfolge
    na = frames(td / "noanim")
    diff = [float((np.abs(x.astype(int) - y.astype(int)).max(axis=2) > 8).mean()) for x, y in zip(nf, na)]
    res["anim_changed_share"] = {"min": round(min(diff), 4), "max": round(max(diff), 4),
                                 "mean": round(float(np.mean(diff)), 4)}

    # Gouraud je Eckpunkt gegen dieselbe Rechnung je Pixel
    pp = frames(td / "perpixel")
    res["gouraud_vs_perpixel_px_gt3"] = int(sum((np.abs(x.astype(int) - y.astype(int)).max(axis=2) > 3).sum()
                                               for x, y in zip(nf, pp)))

    # Treue: Godot zeigt das Renderbild unverändert? Erwartung aus den Bake-Dateien (Overlay-Bild des Takts,
    # mit Maske gemischt), verglichen außerhalb von Figur und Laternen-Lichtebene
    nu = frames(td / "noui")
    bgdir = STYLE / "assets" / "bg"
    fid = {}
    for i in (0, 45, 90, 150):
        shot = "totale" if i / 30 < 2.1 else "nah"
        meta = json.loads((bgdir / shot / "meta.json").read_text())
        base = np.asarray(Image.open(bgdir / shot / "base.png").convert("RGB")).astype(float)
        atlas = np.asarray(Image.open(bgdir / shot / "anim.png")).astype(float)
        x, y, w, h = meta["anim"]["rect"]
        fr = int(np.floor(i / 30 * meta["anim"]["fps"] + 0.001)) % meta["anim"]["frames"]
        cy, cx = divmod(fr, meta["anim"]["cols"])
        tile = atlas[cy * h:(cy + 1) * h, cx * w:(cx + 1) * w]
        exp = base.copy()
        a_ = tile[..., 3:4] / 255.0
        exp[y:y + h, x:x + w] = exp[y:y + h, x:x + w] * (1 - a_) + tile[..., :3] * a_
        lan = np.asarray(Image.open(bgdir / shot / "lantern.png").convert("RGB")).max(axis=2) == 0
        zone = np.zeros_like(lan)
        if i in rows:
            y0_, y1_, x0_, x1_ = rows[i]
            zone[max(0, y0_ - 2):y1_ + 8, max(0, x0_ - 12):x1_ + 13] = True   # Figur und Rundschatten
        ok = lan & ~mn[i] & ~mk[i] & ~zone
        d = np.abs(nu[i].astype(float) - exp)[ok].max(axis=1)
        fid[str(i)] = {"compared_px": int(ok.sum()), "max_diff": int(d.max()), "share_gt1": round(float((d > 1).mean()), 4)}
    res["background_fidelity"] = fid

    # Laterne (nur Totale): Helligkeit der Pixel mit merklicher Lichtebene über die Bilder 0-62
    lan = np.asarray(Image.open(bgdir / "totale" / "lantern.png").convert("RGB")).max(axis=2) > 24
    vals = [float(nf[i][lan].mean()) for i in range(0, 63)]
    res["lantern_flicker"] = {"pixels": int(lan.sum()), "mean_min": round(min(vals), 1),
                              "mean_max": round(max(vals), 1)}
    # Blob-Schatten: Abdunklung unter den Füßen (Bild 150) gegenüber dem erwarteten Hintergrund
    i = 150
    y0_, y1_, x0_, x1_ = rows[i]
    meta = json.loads((bgdir / "nah" / "meta.json").read_text())
    x, y, w, h = meta["anim"]["rect"]
    fr = int(np.floor(i / 30 * meta["anim"]["fps"] + 0.001)) % meta["anim"]["frames"]
    cy, cx = divmod(fr, meta["anim"]["cols"])
    atlas = np.asarray(Image.open(bgdir / "nah" / "anim.png")).astype(float)
    tile = atlas[cy * h:(cy + 1) * h, cx * w:(cx + 1) * w]
    base = np.asarray(Image.open(bgdir / "nah" / "base.png").convert("RGB")).astype(float)
    exp = base.copy()
    exp[y:y + h, x:x + w] = exp[y:y + h, x:x + w] * (1 - tile[..., 3:4] / 255) + tile[..., :3] * tile[..., 3:4] / 255
    reg = (slice(y1_ - 6, y1_ + 6), slice(x0_ - 10, x1_ + 10))
    m = ~mn[i][reg]
    dark = (exp[reg] - nu[i][reg].astype(float)).mean(axis=2)[m]
    res["blob_shadow_150"] = {"max_darkening": round(float(dark.max()), 1), "px_darker_than_8": int((dark > 8).sum())}
    tot_fig = sum(int(m_.sum()) for m_ in mk)
    res["gouraud_vs_perpixel_share_of_figure_px"] = round(res["gouraud_vs_perpixel_px_gt3"] / max(tot_fig, 1), 3)

    # Füße: Weltlage der Fußknochen; Standfuß = der tiefere; Rutschen = Versatz zwischen Bildern
    feet = []
    for line in outs["feet"].splitlines():
        if line.startswith("FEET "):
            m = re.findall(r"(foot\.[LR])=\(([-\d.]+),([-\d.]+),([-\d.]+)\)\|\(([-\d.]+),([-\d.]+)\)", line)
            tt = float(re.search(r"t=([\d.]+)", line).group(1))
            feet.append((tt, {k: tuple(map(float, v)) for k, *v in m}))
    slides = []
    for (t0, f0), (t1, f1) in zip(feet, feet[1:]):
        for k in ("foot.L", "foot.R"):
            a0, a1 = f0[k], f1[k]
            if a0[1] < 0.02 and a1[1] < 0.02:     # Sohlenmitte am Boden (Figur steht auf 1 cm)
                d = ((a1[0] - a0[0]) ** 2 + (a1[2] - a0[2]) ** 2) ** 0.5
                sp = ((a1[3] - a0[3]) ** 2 + (a1[4] - a0[4]) ** 2) ** 0.5
                slides.append((t1, k, d, sp))
    walk = [s for s in slides if s[0] < 3.8]
    res["planted_foot_world_step_mm"] = {
        "walk_median": round(1000 * float(np.median([s[2] for s in walk])), 2) if walk else None,
        "walk_p90": round(1000 * float(np.percentile([s[2] for s in walk], 90)), 2) if walk else None,
    }
    res["planted_foot_screen_step_px"] = {
        "walk_median": round(float(np.median([s[3] for s in walk])), 3) if walk else None,
        "walk_p90": round(float(np.percentile([s[3] for s in walk], 90)), 3) if walk else None,
        "walk_max": round(float(np.max([s[3] for s in walk])), 3) if walk else None,
    }
    # Fußzeile im Stand (Bild 115-179): unterste Maskenzeile muss gleich bleiben
    stand = [rows[i][1] for i in range(115, N) if i in rows]
    res["feet_row_standing"] = sorted(set(stand))
    out = STYLE / "assets" / "probe"
    out.mkdir(parents=True, exist_ok=True)
    (out / "probe.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    print("Rohbilder:", td)


if __name__ == "__main__":
    main()
