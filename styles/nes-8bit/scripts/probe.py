#!/usr/bin/env python3
"""Prüflauf für nes-8bit: nimmt die Demo in Konsolenauflösung (256x224) auf und misst

  1. Dachs allein (--only=badger, Grundfarbe Hellblau): Kopfoberkante je Pose (Auf und Ab), Fußzeile,
     Fußstücke je Bild; beim Laufen bleibt zwischen zwei Posen ein Fuß an derselben Stelle (Standfuß),
     Stehbilder gleiche Füße; Zahl der verschiedenen Laufbilder (a- und b-Posen müssen sich unterscheiden).
  2. Hintergrund allein (--only=bg): jede 16x16-Zelle nutzt nur Schwarz + die Farben ihrer Attributpalette,
     jede 8x8-Kachel höchstens 4 Farben, alle Farben im Bild höchstens 13.
  3. Ganzes Bild: jede Ausgabefarbe liegt in der Systempalette; Sprites je Zeile aus dem Protokoll von main.gd;
     Haltezeiten von Wolken, Möwen und Wasser in Bildern, Blitzzeiten; Abstand über dem Fenstertitel.
  4. Renderer: Forward+, Mobile und Compatibility pixelgleich? (60 Bilder)
  5. Dauerlauf ab t = 30 s ohne Fehler.
Aufruf: .venv/bin/python styles/nes-8bit/scripts/probe.py [--quick]
"""
import json, os, pathlib, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
DEMO = ENTRY / "demo"
# Temporäre Aufnahmen in einem eigenen Unterordner (mehrere Agenten arbeiten gleichzeitig)
TMP = pathlib.Path(os.environ.get("NES8_TMP", pathlib.Path(tempfile.gettempdir()) / "nes-8bit"))
TMP.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE))
import neslib  # noqa: E402


def run(n, user=(), rendering=None):
    td = pathlib.Path(tempfile.mkdtemp(prefix="run_", dir=TMP))
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--write-movie", str(td / "f.png"),
           "--fixed-fps", "30", "--quit-after", str(n)]
    if rendering:
        cmd += ["--rendering-method", rendering]
    cmd += ["--"] + list(user)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    log = r.stdout + r.stderr
    errs = [l for l in log.splitlines() if "ERROR" in l or "SCRIPT ERROR" in l]
    frames = [np.asarray(Image.open(p).convert("RGB")) for p in sorted(td.glob("f*.png"))]
    hw = [l for l in log.splitlines() if l.startswith("HWSTAT")]
    return frames, errs, (json.loads(hw[-1][7:]) if hw else {}), td


def segments(row):
    xs = np.flatnonzero(row)
    if xs.size == 0:
        return []
    segs, s0, prev = [], xs[0], xs[0]
    for x in xs[1:]:
        if x != prev + 1:
            segs.append((int(s0), int(prev)))
            s0 = x
        prev = x
    segs.append((int(s0), int(prev)))
    return segs


def main():
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True, timeout=600)
    rom = json.loads((DEMO / "rom" / "rom.json").read_text())
    report = {}

    # 1. Dachs
    probe_log = pathlib.Path(tempfile.mkdtemp(prefix="log_", dir=TMP)) / "probe.jsonl"
    frames, errs, hw, _ = run(180, ["--only=badger", f"--probe={probe_log}"])
    poses = [json.loads(l) for l in probe_log.read_text().splitlines()]
    bgc = neslib.SYSPAL[0x21].astype(np.uint8)
    rows = []
    for f in frames:
        m = np.any(f != bgc, axis=2)
        ys = np.flatnonzero(m.any(1))
        if ys.size == 0:
            rows.append(None)
            continue
        top, bot = int(ys[0]), int(ys[-1])
        rows.append({"top": top, "bottom": bot, "feet": segments(m[bot])})
    walk_checks, drift = [], []
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        if a is None or b is None or a["feet"] == b["feet"]:
            continue                      # nur Bildwechsel der Füße
        # Protokollzeile 0 stammt aus _ready, Zeile k+1 aus dem _process vor Aufnahmebild k (gemessen: nur so
        # hat jede Pose genau eine Kopfoberkante)
        pa, pb = poses[i]["pose"], poses[i + 1]["pose"]
        # Standfuß: kleinster Versatz eines Fußstücks zwischen zwei Posen (Weltkoordinaten = Bildkoordinaten)
        # Blick nach links: die linke Kante (Zehen) des Standfußes muss stehen bleiben; im Durchgang
        # verschmelzen beide Füße zu einem Stück, dessen linke Kante der Standfuß ist
        best = min(abs(sa[0] - sb[0]) for sa in a["feet"] for sb in b["feet"])
        drift.append(best)
        walk_checks.append([poses[i + 1]["t"], pa, pb, a["feet"], b["feet"], best])
    stand = [r for r, p in zip(rows, poses[1:]) if r and p["pose"].startswith("stand")]
    # Kopfoberkante je Pose und verschiedene Laufbilder (Ausschnitt 16x24 an der Figurposition, ganz im Bild)
    head_by_pose, patches = {}, {}
    for i in range(len(rows)):
        p, r = poses[i + 1], rows[i]
        if r is None or p["x"] > 240:
            continue
        head_by_pose.setdefault(p["pose"], set()).add(r["top"])
        patch = frames[i][r["bottom"] - 24:r["bottom"] + 1, p["x"]:p["x"] + 16]
        patches.setdefault(p["pose"], set()).add(patch.tobytes())
    walk_imgs = set()
    for k in ("contact_a", "pass_a", "contact_b", "pass_b"):
        walk_imgs |= patches.get(k, set())
    report["badger"] = {
        "frames": len(rows),
        "head_top_rows": sorted({r["top"] for r in rows if r}),
        "head_top_by_pose": {k: sorted(v) for k, v in sorted(head_by_pose.items())},
        "distinct_walk_images": len(walk_imgs),
        "a_b_differ": bool(patches.get("contact_a", set()).isdisjoint(patches.get("contact_b", set())) and
                           patches.get("pass_a", set()).isdisjoint(patches.get("pass_b", set()))),
        "foot_rows": sorted({r["bottom"] for r in rows if r}),
        "pose_changes": len(drift),
        "planted_foot_max_drift_px": max(drift) if drift else None,
        "stand_feet_variants": len({json.dumps(r["feet"]) for r in stand}),
        "examples": walk_checks[:4],
        "errors": errs[:5],
    }

    # 2. Hintergrundregeln
    frames, errs, _, _ = run(60, ["--only=bg", "--t0=2.0"])
    pal = rom["palette"]
    at = rom["attributes"]
    sysrgb = {tuple(int(v) for v in neslib.SYSPAL[i]): i for i in range(64) if neslib.SYSPAL_HEX[i] != "000000"}
    sysrgb[(0, 0, 0)] = 0x0F
    viol_block, viol_tile, colours = 0, 0, set()
    for f in frames[::10]:
        idx = np.zeros(f.shape[:2], np.int32)
        for y in range(f.shape[0]):
            for x in range(f.shape[1]):
                idx[y, x] = sysrgb.get(tuple(int(v) for v in f[y, x]), -1)
        colours |= set(np.unique(idx[:168]).tolist())
        for by in range(15):
            for bx in range(16):
                y0, y1 = by * 16 - 8, by * 16 + 8          # Konsolenzeile -> Bildzeile (8 Zeilen Rand)
                if y1 <= 0 or y0 >= 224:
                    continue
                blk = idx[max(0, y0):min(224, y1), bx * 16:bx * 16 + 16]
                b = at[(by >> 1) * 8 + (bx >> 1)]
                p = (b >> (((by & 1) * 2 + (bx & 1)) * 2)) & 3
                allowed = {pal[0]} | set(pal[p * 4 + 1:p * 4 + 4])
                if not set(np.unique(blk).tolist()) <= allowed:
                    viol_block += 1
        for ty in range(28):
            for tx in range(32):
                if len(np.unique(idx[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8])) > 4:
                    viol_tile += 1
    report["background"] = {"block_violations": viol_block, "tile_violations": viol_tile,
                            "scene_colours": sorted(f"{c:02X}" for c in colours), "n_scene_colours": len(colours),
                            "tiles": rom["stats"], "errors": errs[:5]}

    # 3. Ganzes Bild: Systemfarben, Sprites je Zeile
    probe_log = pathlib.Path(tempfile.mkdtemp(prefix="log_", dir=TMP)) / "probe.jsonl"
    frames, errs, hw, _ = run(180, [f"--probe={probe_log}"])
    allrgb = set(sysrgb)
    bad = 0
    ncol = 0
    for f in frames:
        u = {tuple(int(v) for v in c) for c in np.unique(f.reshape(-1, 3), axis=0)}
        bad += len(u - allrgb)
        ncol = max(ncol, len(u))
    log = [json.loads(l) for l in probe_log.read_text().splitlines()]

    def holds(key):
        vals = [e[key] for e in log]
        runs, n = [], 1
        for a, b in zip(vals, vals[1:]):
            if a == b:
                n += 1
            else:
                runs.append(n)
                n = 1
        return sorted(set(runs[1:]))                 # erste Folge kann angeschnitten sein, letzte fehlt
    lamp_starts = [round(e["t"], 2) for a, e in zip(log, log[1:]) if e["lamp"] and not a["lamp"]]
    # Abstand über dem Titel: Bildzeilen 158 (Kai-Stirnseite), 159-160 schwarz über dem Titel (Spalten 32-175)
    blk = np.zeros(3, np.uint8)
    gap = all(np.all(f[159:161, 32:176] == blk) for f in frames) and all(np.any(f[158, 32:176] != blk) for f in frames)
    report["timing"] = {"cloud_hold_frames": holds("cloud"), "gull_hold_frames": holds("gull"),
                        "water_hold_frames": holds("water"), "lamp_on_starts_s": lamp_starts,
                        "title_black_gap_rows_159_160": bool(gap)}
    report["frame"] = {"non_system_colours": bad, "max_colours_per_frame": ncol,
                       "max_sprites_per_line": max(e["max_line"] for e in log),
                       "max_sprites": max(e["oam"] for e in log), "hwstat": hw, "errors": errs[:5]}
    ref = frames

    if "--quick" not in sys.argv:
        # 4. Renderer
        rend = {}
        for rm in ("mobile", "gl_compatibility"):
            fr, errs, _, _ = run(60, [], rendering=rm)
            diff = sum(int(np.any(a != b)) for a, b in zip(fr, ref[:60]))
            rend[rm] = {"frames_compared": min(len(fr), 60), "frames_different": diff, "errors": errs[:3]}
        report["renderers"] = rend
        # 5. Dauerlauf
        fr, errs, hw, td = run(60, ["--t0=30"])
        Image.fromarray(fr[-1]).save(ENTRY / "media" / "probe_t30.png") if fr else None
        report["t30"] = {"frames": len(fr), "errors": errs[:5], "hwstat": hw}
    shutil.rmtree(TMP, ignore_errors=True)
    out = ENTRY / "media" / "probe.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
