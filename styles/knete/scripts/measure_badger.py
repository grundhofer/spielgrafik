#!/usr/bin/env python3
"""Messungen für den Knete-Dachs (PIPELINE.md → Figuren und Animation).

    .venv/bin/python styles/knete/scripts/measure_badger.py TMP_DIR [--keep]

Vier Godot-Läufe über die vollen 6 s (30 fps, wie tools/capture.py):
  A  --measure            Knochen und Sohlenpunkte (Ferse, Zehen) je Bild, Welt und Bild (px)
  B  --mask --no-boil     Dachs weiß auf Schwarz, ohne Formrauschen
  C  --mask               Dachs weiß auf Schwarz, mit Formrauschen
  D  (normal, mit UI)     fertiges Bild
Geprüft wird:
  1. Stufen: Ein Bild darf sich nur ändern, wenn ein neues Figurenbild (15/s) oder Umgebungsbild (10/s) beginnt.
  2. Standfuß im Lauf: Ferse oder Zehen des tragenden Fußes bewegen sich zwischen zwei Animationsbildern nicht.
  3. Stehen/Winken: Sohlenpunkte fest; Fußzeile (unterste Zeile des Umrisses) in allen Bildern gleich.
  4. Kopf: oberste Zeile des Umrisses (Mütze) je Phase.
  5. Formrauschen: Umriss mit und ohne Rauschen, Änderung von Animationsbild zu Animationsbild im Stehen.
Schreibt styles/knete/assets/measure/measure_badger.json (nur Zahlen). Bilder liegen in TMP_DIR und werden
ohne --keep danach gelöscht.
"""
import json, math, pathlib, re, shutil, subprocess, sys

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRAMES = 180


def run(out, extra):
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("f*.png"):
        p.unlink()
    cmd = ["godot", "--path", str(ROOT / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(FRAMES), "--"] + extra
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    log = r.stdout + r.stderr
    errs = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
    if errs:
        print("Godot-Fehler:", errs[:5])
    return log, sorted(out.glob("f*.png"))


def load_mask(p):
    return np.asarray(Image.open(p).convert("L")) > 128


def main():
    tmp = pathlib.Path(sys.argv[1])
    keep = "--keep" in sys.argv
    subprocess.run(["godot", "--headless", "--path", str(ROOT / "demo"), "--import"], capture_output=True)
    res = {}

    # --- A: Knochen ---------------------------------------------------------------------------
    log, frames_a = run(tmp / "a", ["--measure", "--no-ui", "--no-boil"])
    (tmp / "a" / "godot.log").write_text(log)
    allrows = [json.loads(l.split("MEASURE ", 1)[1]) for l in log.splitlines() if l.startswith("MEASURE ")]
    # Bild i zeigt den Stand der letzten Zeile mit drawn == i (_process läuft vor dem Zeichnen)
    last = {}
    for r in allrows:
        last[r["drawn"]] = r
    rows = [last[i] for i in range(FRAMES)]
    by_step = {}
    for r in rows:
        by_step.setdefault(r["fig_step"], r)
    steps = sorted(by_step)

    SOLE = ("heel", "mid", "toe")

    def pts(r, foot):
        return {k: r[f"{foot}.{k}"] for k in SOLE}

    # Standfuß im Lauf (Animationsbilder 0..44): tragend = Sohlenpunkt höchstens 6 mm über dem tiefsten
    slides_px, slides_mm, pairs, worst = [], [], 0, []
    for s0, s1 in zip(steps, steps[1:]):
        if s1 > 44:
            break
        r0, r1 = by_step[s0], by_step[s1]
        ground0 = min(p[1] for f in ("foot.L", "foot.R") for p in pts(r0, f).values())
        ground1 = min(p[1] for f in ("foot.L", "foot.R") for p in pts(r1, f).values())
        best = None
        for f in ("foot.L", "foot.R"):
            for k in SOLE:
                a, b = r0[f"{f}.{k}"], r1[f"{f}.{k}"]
                if a[1] < ground0 + 0.006 and b[1] < ground1 + 0.006:
                    mm = 1000 * math.hypot(b[0] - a[0], b[2] - a[2])
                    px = math.hypot(b[3] - a[3], b[4] - a[4])
                    if best is None or px < best[1]:
                        best = (mm, px, f"{f}.{k}", round(1000 * (b[1] - a[1]), 1))
        if best:
            pairs += 1
            slides_mm.append(best[0])
            slides_px.append(best[1])
            worst.append([s0, s1, best[2], round(best[0], 2), round(best[1], 2), best[3]])
    res["walk_stance"] = {
        "pairs": pairs,
        "max_mm": round(max(slides_mm), 2), "mean_mm": round(float(np.mean(slides_mm)), 2),
        "max_px": round(max(slides_px), 2), "mean_px": round(float(np.mean(slides_px)), 2),
        "worst_pairs": sorted(worst, key=lambda w: -w[4])[:5],
        "note": "Animationsbilder 0-44, je Paar der kleinste Weg (Bild, px) eines Sohlenpunkts, der in beiden "
                "Bildern trägt; worst_pairs: Schritt, Schritt, Punkt, mm waagrecht, px, mm senkrecht",
    }
    # Drehung (45-50): linker Knöchel fest?
    piv = [by_step[s] for s in steps if 44 <= s <= 51]
    res["pivot"] = {
        "ankle_L_max_mm": round(max(1000 * math.hypot(r["foot.L"][0] - piv[0]["foot.L"][0], r["foot.L"][2] - piv[0]["foot.L"][2]) for r in piv), 2),
        "toe_R_path_px": round(sum(math.hypot(b["foot.R.toe"][3] - a["foot.R.toe"][3], b["foot.R.toe"][4] - a["foot.R.toe"][4]) for a, b in zip(piv, piv[1:])), 1),
        "toe_R_height_max_mm": round(1000 * max(r["foot.R.toe"][1] - min(r["foot.L.heel"][1], r["foot.L.toe"][1]) for r in piv), 1),
        "note": "Drehung um den linken Knöchel (fest), der rechte Fuß ist dabei in der Luft und setzt erst am Ende auf",
    }
    # Stehen ab Bild 52: alle Sohlenpunkte fest
    stand = [by_step[s] for s in steps if s >= 52]
    drift = 0.0
    for f in ("foot.L", "foot.R"):
        for k in SOLE:
            xs = [r[f"{f}.{k}"][3] for r in stand]
            ys = [r[f"{f}.{k}"][4] for r in stand]
            drift = max(drift, max(xs) - min(xs), max(ys) - min(ys))
    res["stand_sole_drift_px"] = round(drift, 2)

    # --- B/C: Umriss ---------------------------------------------------------------------------
    _, frames_b = run(tmp / "b", ["--mask", "--no-boil", "--no-ui"])
    _, frames_c = run(tmp / "c", ["--mask", "--no-ui"])
    feet_rows, head_rows, boil_px, boil_frac = [], [], [], []
    for i, (pb, pc) in enumerate(zip(frames_b, frames_c)):
        mb, mc = load_mask(pb), load_mask(pc)
        ys, xs = np.nonzero(mb)
        if len(ys) == 0:
            feet_rows.append(None)
            head_rows.append(None)
            continue
        feet_rows.append(int(ys.max()))
        head_rows.append(int(ys.min()))
        diff = int((mb ^ mc).sum())
        boil_px.append(diff)
        # Umfang grob: Randpixel des Umrisses ohne Rauschen
        edge = mb & ~(np.roll(mb, 1, 0) & np.roll(mb, -1, 0) & np.roll(mb, 1, 1) & np.roll(mb, -1, 1))
        boil_frac.append(diff / max(int(edge.sum()), 1))
    stand_frames = [i for i, r in enumerate(rows) if r["fig_step"] >= 52]
    fr = [feet_rows[i] for i in stand_frames if feet_rows[i] is not None]
    walk_frames = [i for i, r in enumerate(rows) if 12 <= r["fig_step"] <= 44]   # ganz im Bild
    fw = [feet_rows[i] for i in walk_frames if feet_rows[i] is not None]
    res["silhouette"] = {
        "feet_row_stand_min_max": [min(fr), max(fr)],
        "feet_row_walk_min_max": [min(fw), max(fw)],
        "head_row_walk_min_max": [min(head_rows[i] for i in walk_frames), max(head_rows[i] for i in walk_frames)],
        "head_row_stand_min_max": [min(head_rows[i] for i in stand_frames), max(head_rows[i] for i in stand_frames)],
        "height_px_stand": max(fr) - min(head_rows[i] for i in stand_frames),
    }
    # Formrauschen: Umrissänderung durch das Rauschen (mittlerer Versatz in px = geänderte Pixel / Umfang)
    res["boil_outline"] = {
        "mean_offset_px": round(float(np.mean(boil_frac)), 3), "max_offset_px": round(float(np.max(boil_frac)), 3),
        "mean_changed_px": int(np.mean(boil_px)),
    }
    # Im Stehen: Änderung von Animationsbild zu Animationsbild mit und ohne Rauschen (Umriss)
    def step_changes(frames):
        out = []
        prev = None
        for i in stand_frames:
            if rows[i]["fig_step"] != rows[i - 1]["fig_step"]:
                m = load_mask(frames[i])
                if prev is not None:
                    out.append(int((m ^ prev).sum()))
                prev = m
        return out
    sb, sc = step_changes(frames_b), step_changes(frames_c)
    res["stand_outline_change_per_step"] = {"no_boil_mean": int(np.mean(sb)), "boil_mean": int(np.mean(sc))}

    # --- D: fertiges Bild, Stufen ----------------------------------------------------------------
    _, frames_d = run(tmp / "d", [])
    bad, fig_only, env_only, both, none = [], 0, 0, 0, 0
    prev = np.asarray(Image.open(frames_d[0]).convert("RGB"), dtype=np.int16)
    bx = None
    for i in range(1, len(frames_d)):
        cur = np.asarray(Image.open(frames_d[i]).convert("RGB"), dtype=np.int16)
        changed = int((np.abs(cur - prev).max(axis=2) > 2).sum())
        fig_new = rows[i]["fig_step"] != rows[i - 1]["fig_step"]
        env_new = rows[i]["env_step"] != rows[i - 1]["env_step"]
        if not fig_new and not env_new:
            none += 1
            if changed:
                bad.append([i, changed])
        elif fig_new and env_new:
            both += 1
        elif fig_new:
            fig_only += 1
        else:
            env_only += 1
        prev = cur
    res["holds"] = {
        "frames_without_new_step": none, "of_those_changed": bad[:20],
        "frames_new_fig_step": fig_only + both, "frames_new_env_step": env_only + both,
        "note": "Bilder ohne neues Figuren- oder Umgebungsbild müssen pixelgleich zum Vorgänger sein",
    }
    out = ROOT / "assets" / "measure"
    out.mkdir(parents=True, exist_ok=True)
    (out / "measure_badger.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))
    if not keep:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
