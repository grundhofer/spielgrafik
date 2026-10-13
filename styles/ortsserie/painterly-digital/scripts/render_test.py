#!/usr/bin/env python3
"""Prüft die Szenen in einer KOPIE des Demo-Ordners und nimmt Einzelbilder auf (parallele Agenten stören sich nicht).

    .venv/bin/python -I styles/ortsserie/painterly-digital/scripts/render_test.py --work DIR [ort ...]
        [--frames 180] [--still 4.0] [--method forward_plus|mobile|gl_compatibility] [--keep-stills] [-- extra]

1. Kopie: styles/ortsserie/demo/project.godot (unverändert) und styles/ortsserie/demo/painterly-digital/ nach
   DIR/demo_test (ohne .import/.godot), dann godot --headless --import
2. je Ort: godot --write-movie DIR/frames/<ort>/f.png --fixed-fps 30 --quit-after N res://painterly-digital/<ort>.tscn
   Fehlerzeilen (ERROR, SCRIPT ERROR) werden gemeldet; die fehlende res://main.tscn des gemeinsamen Projekts nicht
   (die Hauptszene baut ein späterer Schritt, hier wird jede Szene direkt gestartet)
3. --keep-stills: Bild bei --still Sekunden als assets/<ort>_scene.png ablegen
Schreibt DIR/render_report.json (Fehlerzeilen, Bilderzahl, Bewegung je Ort: Anteil Pixel, die sich zwischen zwei
Zeitpunkten um mehr als 6/255 ändern).
"""
import argparse, json, pathlib, shutil, subprocess, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
E = HERE.parent
ROOT = E.parents[2]
DEMO = ROOT / "styles" / "ortsserie" / "demo"
ORDER = ["leuchtturm", "stube", "klippe"]
IGNORE = ("res://main.tscn",)


def bad_lines(log):
    out = []
    for l in log.splitlines():
        if ("ERROR" in l or "SCRIPT ERROR" in l) and not any(s in l for s in IGNORE):
            out.append(l.strip())
    # die Zeile nach einem ignorierten ERROR ("at: ...") gehört dazu und ist keine eigene Meldung
    return [l for l in out if not l.startswith("at:")]


def copy_demo(dst):
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    shutil.copy2(DEMO / "project.godot", dst / "project.godot")
    shutil.copytree(DEMO / "painterly-digital", dst / "painterly-digital",
                    ignore=shutil.ignore_patterns("*.import", ".godot"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("orte", nargs="*", default=ORDER)
    ap.add_argument("--work", required=True)
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--still", type=float, default=4.0)
    ap.add_argument("--method", default="")
    ap.add_argument("--keep-stills", action="store_true")
    ap.add_argument("--no-copy", action="store_true")
    ap.add_argument("extra", nargs="*")
    a = ap.parse_args()
    work = pathlib.Path(a.work)
    proj = work / "demo_test"
    report = {}
    if not a.no_copy:
        copy_demo(proj)
        imp = subprocess.run(["godot", "--headless", "--path", str(proj), "--import"], capture_output=True,
                             text=True, timeout=600)
        report["import_errors"] = bad_lines(imp.stdout + imp.stderr)
    for ort in a.orte:
        out = work / "frames" / (ort + (f"_{a.method}" if a.method else ""))
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        cmd = ["godot", "--path", str(proj), "--position", "20000,20000", "--resolution", "1280x720",
               "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(a.frames)]
        if a.method:
            cmd += ["--rendering-method", a.method]
        cmd += [f"res://painterly-digital/{ort}.tscn"]
        if a.extra:
            cmd += ["--"] + a.extra
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        log = p.stdout + p.stderr
        (out / "godot.log").write_text(log)
        frames = sorted(out.glob("f*.png"))
        rep = {"frames": len(frames), "errors": bad_lines(log)}
        if frames:
            i = min(len(frames) - 1, int(round(a.still * 30)))
            f_still = frames[i]
            if a.keep_stills:
                shutil.copy2(f_still, E / "assets" / f"{ort}_scene.png")
            # Bewegung: Bildpaare im Abstand von 0,5 s
            moves = []
            for k in range(0, len(frames) - 15, 15):
                x = np.asarray(Image.open(frames[k]).convert("RGB"), np.int16)
                y = np.asarray(Image.open(frames[k + 15]).convert("RGB"), np.int16)
                moves.append(float((np.abs(x - y).max(-1) > 6).mean()))
            rep["moving_share_per_0_5s"] = [round(m, 4) for m in moves]
            rep["still_frame"] = f_still.name
        report[ort] = rep
        print(ort, json.dumps(rep, ensure_ascii=False))
    (work / "render_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    errs = report.get("import_errors", []) + [e for o in a.orte for e in report[o]["errors"]]
    print("Fehlerzeilen:", len(errs))
    for e in errs[:20]:
        print("  ", e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
