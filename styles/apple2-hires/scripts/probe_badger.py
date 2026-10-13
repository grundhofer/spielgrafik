"""Misst den Dachs im gerenderten Bild (Godot, --only=badger): Kopfzeile, Fußzeile, Lage der Füße je Bild und
ob der Standfuß beim Laufen und beim Anhalten in der Welt stehen bleibt.

    .venv/bin/python styles/apple2-hires/scripts/probe_badger.py [tmpdir]

Schreibt media/probe_badger.json. Nahes Bein = helle Punkte (weiß mit Säumen), fernes Bein = violette Punkte.
Gemessen wird in der Fußzeile (unterste Zeile der Figur): Ein Bein steht, wenn es dort Punkte hat; ein angehobenes
Bein endet eine Zeile höher.

Zuordnung Bild <-> Pose: --probe schreibt je _render() eine Zeile (Bildnummer f, Pose, x). Die Bilder aus
--write-movie sind gegenüber f versetzt (das erste Bild der Folge zeigt nicht f = 0). Der Versatz wird nicht
angenommen, sondern gemessen: Für jeden Kandidaten k muss die linke Kante der Mützenkuppe (lokale Spalte 7)
in allen ganz sichtbaren Bildern genau bei x(f = i + k) + 7 liegen; genau ein k darf passen.

Zusätzlich (ohne Godot, aus assets/picture_build.npz und demo/data/sprites.json, Farbmodell wie der Shader):
Bildpunkte des Ortsbilds außerhalb der Figur, deren Farbe sich ändert, weil das Sprite Bit 7 der berührten
Bytes setzt (Farbgruppen-Konflikt mit dem Hintergrund).
"""
import json, pathlib, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
sys.path.insert(0, str(HERE))
from a2lib import render  # noqa: E402

VIOLET = np.array([208, 67, 229])
HEAD_COL = 7          # lokale Spalte, an der die Mützenkuppe beginnt (Zeile 0 von UPPER in build_sprites.py)
FEET_Y = 158          # wie main.gd: Bildzeile unter den Füßen
LEGS = ("near", "far")


def godot_frames(tmp):
    for p in tmp.glob("f*.png"):
        p.unlink()
    demo = ENTRY / "demo"
    subprocess.run(["godot", "--headless", "--path", str(demo), "--import"], capture_output=True)
    probe = tmp / "probe.jsonl"
    r = subprocess.run(["godot", "--path", str(demo), "--position", "20000,20000", "--write-movie",
                        str(tmp / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--",
                        "--only=badger", f"--probe={probe}"], capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    by_f = {}
    for l in probe.read_text().splitlines():
        if l.strip():
            p = json.loads(l)
            by_f.setdefault(p["f"], p)
    return sorted(tmp.glob("f*.png")), by_f, errs


def measure(fp):
    im = np.asarray(Image.open(fp).convert("RGB")).astype(int)
    lit = im.sum(2) > 0
    if not lit[100:160].any():
        return None
    ys, xs = np.nonzero(lit[:160])
    head_y, feet_y = int(ys.min()), int(ys.max())
    vio = np.abs(im - VIOLET).sum(2) < 10
    row = feet_y
    near = np.nonzero(lit[row] & ~vio[row])[0]
    far = np.nonzero(vio[row])[0]
    return {"head_y": head_y, "feet_y": feet_y, "head_left": int(xs[ys == head_y].min()),
            "near_foot_x": int(near.min()) if near.size else None,
            "far_foot_x": int(far.min()) if far.size else None,
            "foot_row": [int(v) for v in np.nonzero(lit[row])[0]]}


def calibrate(meas, by_f):
    fits = {}
    for k in (-2, -1, 0, 1, 2, 3):
        vals, n = set(), 0
        for i, m in enumerate(meas):
            p = by_f.get(i + k)
            if m is None or p is None or p.get("x") is None or p["x"] < 0:
                continue
            vals.add(m["head_left"] - p["x"])
            n += 1
        fits[k] = (sorted(vals), n)
    ok = [k for k, (v, n) in fits.items() if v == [HEAD_COL] and n > 20]
    if len(ok) != 1:
        raise SystemExit(f"Versatz Bild <-> Pose nicht eindeutig: {fits}")
    return ok[0], {str(k): {"head_left_minus_x": v, "frames": n} for k, (v, n) in fits.items()}


def scene_conflicts(rows):
    """Bildpunkte außerhalb der Figur (mehr als 2 Punkte waagerecht von ihr entfernt), deren Farbe das Sprite
    über Bit 7 ändert, je Bild. Sprite wie main.gd/_draw_sprite: deckende Punkte setzen/löschen, Bit 7 je Byte."""
    pic = np.load(ENTRY / "assets" / "picture_build.npz")["mem"][:160]
    sj = json.loads((ENTRY / "demo" / "data" / "sprites.json").read_text())
    base = render(pic, "crisp")
    out = []
    for r_ in rows:
        fr = sj["frames"][r_["pose"]]
        x0, y0 = r_["x"], FEET_Y - sj["height"]
        mem = pic.copy()
        opq = np.zeros((160, 280), bool)
        for y, line in enumerate(fr["rows"]):
            yy = y0 + y
            touched = set()
            for x, c in enumerate(line):
                xx = x0 + x
                if c == "." or not (0 <= xx < 280):
                    continue
                b, k = divmod(xx, 7)
                v = int(mem[yy, b])
                mem[yy, b] = ((v | (1 << k)) if c == "#" else (v & ~(1 << k))) & 0xFF
                opq[yy, xx] = True
                touched.add(b)
            for b in touched:
                mem[yy, b] = (int(mem[yy, b]) & 0x7F) | (int(fr["hib"][y]) << 7)
        near = opq.copy()
        for d in (1, 2):
            near[:, d:] |= opq[:, :-d]
            near[:, :-d] |= opq[:, d:]
        changed = (render(mem, "crisp") != base).any(2) & ~near
        out.append(int(changed.sum()))
    return out


def main():
    tmp = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(tempfile.mkdtemp())
    tmp.mkdir(parents=True, exist_ok=True)
    frames, by_f, errs = godot_frames(tmp)
    meas = [measure(fp) for fp in frames]
    k, fits = calibrate(meas, by_f)
    rows = []
    for i, m in enumerate(meas):
        if m is None:
            continue
        p = by_f.get(i + k, {})
        rows.append({"frame": i, "godot_f": i + k, "pose": p.get("pose", ""), "x": p.get("x"), **m})
    full = [r_ for r_ in rows if r_["x"] is not None and r_["x"] >= 0]

    # Posenwechsel: ein Bein, das vorher und nachher in der Fußzeile steht, muss an derselben Spalte bleiben.
    checks = []
    for a, b in zip(full, full[1:]):
        if a["pose"].split("_")[0] == b["pose"].split("_")[0]:
            continue
        c = {"frame": b["frame"], "from": a["pose"].split("_")[0], "to": b["pose"].split("_")[0],
             "x": [a["x"], b["x"]]}
        for leg in LEGS:
            fa, fb = a[f"{leg}_foot_x"], b[f"{leg}_foot_x"]
            c[leg] = [fa, fb]
            if fa is not None and fb is not None:
                c[f"{leg}_planted_dx"] = fb - fa
        checks.append(c)
    planted = [c[f"{leg}_planted_dx"] for c in checks for leg in LEGS if f"{leg}_planted_dx" in c]
    no_support = [c["frame"] for c in checks if not any(f"{leg}_planted_dx" in c for leg in LEGS)]
    stops = [c for c in checks if c["to"] == "stand"]
    # Schrittlängen: Spalte, an der ein Bein jeweils neu aufsetzt
    contacts = {leg: [] for leg in LEGS}
    for leg in LEGS:
        last = None
        for r_ in full:
            v = r_[f"{leg}_foot_x"]
            if v is not None and v != last:
                contacts[leg].append(v)
            last = v
    steps = {leg: sorted({b - a for a, b in zip(v, v[1:])}) for leg, v in contacts.items()}
    walk = [r_ for r_ in full if r_["pose"].startswith("walk")]
    stand = [r_ for r_ in full if r_["pose"].startswith("stand")]
    conflicts = scene_conflicts(full)
    summary = {
        "frame_offset": f"Bild i zeigt Godot-Bild f = i + {k}",
        "frames_with_badger": len(rows),
        "frames_fully_visible": len(full),
        "head_y": sorted({r_["head_y"] for r_ in full}),
        "feet_y_walk": sorted({r_["feet_y"] for r_ in walk}),
        "feet_y_stand": sorted({r_["feet_y"] for r_ in stand}),
        "x_steps": sorted({(b["x"] - a["x"]) for a, b in zip(walk, walk[1:])}),
        "pose_changes": len(checks),
        "planted_checks": len(planted),
        "planted_dx": sorted(set(planted)),
        "changes_without_planted_foot": no_support,
        "foot_step_lengths": steps,
        "stop": stops,
        "first_stand_frame": stand[0]["frame"] if stand else None,
        "scene_colour_changes_max": max(conflicts) if conflicts else 0,
        "scene_colour_changes_frames": sum(1 for c in conflicts if c),
        "godot_errors": errs[:5],
    }
    for r_, c in zip(full, conflicts):
        r_["scene_colour_changes"] = c
    (ENTRY / "media" / "probe_badger.json").write_text(json.dumps(
        {"summary": summary, "offset_fits": fits, "checks": checks, "rows": rows}, indent=0, ensure_ascii=False))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
