#!/usr/bin/env python3
"""Prüfläufe der Demo (Godot --write-movie in ein Temp-Verzeichnis) und Messungen.

    .venv/bin/python styles/kachelsatz/scripts/probe.py tiles      # Godot-Kachelbild == Python-Referenz?
    .venv/bin/python styles/kachelsatz/scripts/probe.py feet       # Standfuß und Fußzeilen des Dachses
    .venv/bin/python styles/kachelsatz/scripts/probe.py terrain    # Godots set_cells_terrain_connect vs. Dual-Grid
    .venv/bin/python styles/kachelsatz/scripts/probe.py renderer   # gl_compatibility / mobile vs. Forward+
    .venv/bin/python styles/kachelsatz/scripts/probe.py long       # Dauerlauf ab t0 = 30 s
"""
import json, pathlib, shutil, subprocess, sys, tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import preview_map as pm  # noqa: E402

ENTRY = HERE.parent
DEMO = ENTRY / "demo"
OUT = ENTRY / "assets" / "probe"


def render(frames, user_args=(), extra=(), fps=30):
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    base = pathlib.Path(tempfile.gettempdir()) / "kachelsatz"     # eigener Unterordner (mehrere Agenten)
    base.mkdir(parents=True, exist_ok=True)
    td = pathlib.Path(tempfile.mkdtemp(prefix="probe_", dir=base))
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", *extra, "--write-movie", str(td / "f.png"),
           "--fixed-fps", str(fps), "--quit-after", str(frames)]
    if user_args:
        cmd += ["--", *user_args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    pngs = sorted(td.glob("f*.png"))
    imgs = [np.asarray(Image.open(p).convert("RGB")) for p in pngs]
    shutil.rmtree(td, ignore_errors=True)
    return imgs, errs


def tiles():
    imgs, errs = render(40, ["--tiles-only"])
    desc = json.loads((ENTRY / "assets" / "tiles" / "tiles.json").read_text())
    rows = pm.load_map(DEMO / "map" / "harbour.txt")
    res = []
    for i in (0, 1, 7, 13, 25, 39):
        g = imgs[i].astype(int)
        best = None
        for wf in range(16):
            for sf in range(6):
                ref = pm.compose(rows, desc, ENTRY / "assets" / "tiles", frames={"water": wf, "sand": sf},
                                 origin=(8, 0))[..., :3].astype(int)
                d = np.abs(ref - g).max(-1)
                n = int((d > 2).sum())
                if best is None or n < best[0]:
                    best = (n, wf, sf, int(d.max()))
        res.append({"frame": i, "t": round(i / 30, 3), "diff_px": best[0], "water_frame": best[1],
                    "sand_frame": best[2], "max_diff": best[3]})
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray(imgs[0].astype(np.uint8)).save(OUT / "tiles_godot.png")
    print(json.dumps({"errors": errs[:5], "compare": res}, indent=1))
    return res


def feet():
    imgs, errs = render(185, ["--badger-only"])
    # Welt um 8 px versetzt: Sohle (Ankerzeile) des Dachses bei y = 96 + 8
    ground = 96 + 8
    data = []
    for i, im in enumerate(imgs):
        a = im.max(-1) > 12
        ys, xs = np.nonzero(a)
        if len(xs) == 0:
            data.append(None)
            continue
        bottom = int(ys.max())
        runs = []
        row = a[ground]
        x = 0
        while x < row.size:
            if row[x]:
                x0 = x
                while x < row.size and row[x]:
                    x += 1
                runs.append((x0, x - 1))
            else:
                x += 1
        top = int(ys.min())
        head = xs[ys <= top + 6]
        data.append({"frame": i, "t": round(i / 30, 3), "bottom": bottom, "top": top, "ground_runs": runs,
                     "head_cx": round(float(head.mean()), 2)})
    # Laufphase: Bilder 0,4 s .. 0,4 + 55/15 s; Standfuß: ein Bodenlauf, der über aufeinanderfolgende Laufbilder
    # an derselben Stelle bleibt
    walk = [d for d in data if d and 0.4 <= d["t"] < 0.4 + 55 / 15]
    phases = []
    for k in range(0, len(walk) - 2, 2):      # je Laufbild (2 Aufnahmebilder) ein Messpunkt
        phases.append(walk[k])
    stance_runs, max_shift = [], 0
    for a, b in zip(phases, phases[1:]):
        # kleinster Versatz zwischen einem Bodenlauf in a und einem in b (Standfuß)
        best = min((abs(ra[0] - rb[0]) + abs(ra[1] - rb[1])) / 2 for ra in a["ground_runs"] for rb in b["ground_runs"]) \
            if a["ground_runs"] and b["ground_runs"] else 99
        stance_runs.append(best)
    over = [s for s in stance_runs if s > 1]
    bottoms = sorted({d["bottom"] for d in data if d})
    idle = [d for d in data if d and d["t"] > 0.4 + 56 / 15]
    idle_runs = sorted({tuple(map(tuple, d["ground_runs"])) for d in idle})
    pre = [d for d in data if d and d["t"] < 0.4]
    # Je Bein: Pixel der Beinfarbe in der Zeile über der Sohle (nahes Bein liegt vorn, fernes kann verdeckt sein)
    near_cols = [(73, 62, 60), (80, 68, 65)]
    far_cols = [(57, 45, 44), (64, 53, 51)]
    legs = {"near": [], "far": []}
    for d in phases:
        im = imgs[d["frame"]]
        for leg, cols in (("near", near_cols), ("far", far_cols)):
            m = np.zeros(im.shape[:2], bool)
            for c in cols:
                m |= (np.abs(im.astype(int) - np.array(c)).max(-1) <= 2)
            xs = np.nonzero(m[ground - 1])[0]
            legs[leg].append((d["frame"], int(xs.min()) if len(xs) else None, int(xs.max()) if len(xs) else None))
    # Standphasen: nahes Bein Phasen 0-3, fernes 4-7 (Laufbild k = (Bild - 12) // 2)
    groups = {"near": [], "far": []}
    for leg, off in (("near", 0), ("far", 4)):
        cur = []
        for (fr, x0, x1) in legs[leg]:
            k = (fr - 12) // 2
            if (k - off) % 8 < 4 and x0 is not None:
                cur.append((k, x0, x1))
            elif cur:
                groups[leg].append(cur); cur = []
        if cur:
            groups[leg].append(cur)
    def spread(g):
        return max(max(a[1] for a in g) - min(a[1] for a in g), max(a[2] for a in g) - min(a[2] for a in g))
    stance = {leg: [spread(g) for g in groups[leg] if len(g) >= 2] for leg in groups}
    summary = {
        "stance_leg_spread_px": stance,
        "errors": errs[:5],
        "walk_steps_measured": len(stance_runs),
        # Nur Hinweis: Bodenläufe verschmelzen beim Durchgang (beide Füße in einem Lauf), daher Ausreißer
        "ground_run_shift_px_max": max(stance_runs) if stance_runs else None,
        "ground_run_shift_over_1px": len(over),
        "bottom_rows_all": bottoms,
        "idle_ground_runs": [list(r) for r in idle_runs],
        "start_ground_runs": sorted({tuple(map(tuple, d["ground_runs"])) for d in pre}),
        "head_cx_walk_steps": [round(b["head_cx"] - a["head_cx"], 2) for a, b in zip(phases, phases[1:])][:16],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "feet.json").write_text(json.dumps({"summary": summary, "frames": data}, indent=1))
    print(json.dumps(summary, indent=1))


def terrain():
    a, e1 = render(2, ["--tiles-only"])
    b, e2 = render(2, ["--tiles-only", "--godot-terrain"])
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray(a[0]).save(OUT / "terrain_dualgrid.png")
    Image.fromarray(b[0]).save(OUT / "terrain_godot.png")
    d = np.abs(a[0].astype(int) - b[0].astype(int)).max(-1) > 8
    print(json.dumps({"errors": (e1 + e2)[:5], "changed_share": round(float(d.mean()), 4)}))


def renderer():
    base, e0 = render(110, [])
    out = {}
    for m in ("gl_compatibility", "mobile"):
        imgs, e = render(110, [], extra=["--rendering-method", m])
        d = [float(np.abs(x.astype(int) - y.astype(int)).mean()) for x, y in zip(base, imgs)]
        ch = [float((np.abs(x.astype(int) - y.astype(int)).max(-1) > 8).mean()) for x, y in zip(base, imgs)]
        out[m] = {"errors": e[:3], "frames": len(imgs), "mean_abs_diff": round(float(np.mean(d)), 3),
                  "max_changed_share": round(float(np.max(ch)), 4)}
        OUT.mkdir(parents=True, exist_ok=True)
        Image.fromarray(imgs[108]).save(OUT / f"render_{m}.png")
    Image.fromarray(base[108]).save(OUT / "render_forward.png")
    print(json.dumps(out, indent=1))


def long_run():
    imgs, errs = render(180, ["--t0=30"])
    OUT.mkdir(parents=True, exist_ok=True)
    for i in (0, 90, 179):
        Image.fromarray(imgs[i]).save(OUT / f"long_t{30 + i / 30:.1f}.png")
    print(json.dumps({"errors": errs[:5], "frames": len(imgs)}))


if __name__ == "__main__":
    {"tiles": tiles, "feet": feet, "terrain": terrain, "renderer": renderer, "long": long_run}[sys.argv[1]]()
