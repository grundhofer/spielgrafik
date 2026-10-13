#!/usr/bin/env python3
"""Rendert ausgewählte Bilder der Demo (Godot --write-movie, 30 fps) in ein Arbeitsverzeichnis.

    .venv/bin/python styles/moebius-linien/scripts/render_frames.py --frames 60,150 --out <tmp> [-- --no-lines]

Schreibt <out>/<tag>_f<NNN>.png für jedes gewünschte Bild; alle übrigen Bilder werden gelöscht.
Vorher läuft --import, damit geänderte Dateien neu eingelesen werden. Gibt Godot-Fehler aus.
"""
import argparse, pathlib, re, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
DEMO = HERE.parent / "demo"


def main():
    argv = sys.argv[1:]
    extra = []
    if "--" in argv:
        i = argv.index("--")
        argv, extra = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True, help="Bildnummern ab 0, durch Komma getrennt")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="r")
    ap.add_argument("--method", default="", help="forward_plus | mobile | gl_compatibility")
    ap.add_argument("--no-import", action="store_true")
    a = ap.parse_args(argv)
    frames = sorted({int(x) for x in a.frames.split(",")})
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if not a.no_import:
        imp = subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True, text=True)
        for l in (imp.stdout + imp.stderr).splitlines():
            if re.search(r"ERROR|WARNING", l):
                print("import:", l)
    with tempfile.TemporaryDirectory(dir=out) as td:
        cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
               "--write-movie", str(pathlib.Path(td) / "f.png"), "--fixed-fps", "30",
               "--quit-after", str(max(frames) + 1)]
        if a.method:
            cmd[1:1] = ["--rendering-method", a.method]
        if extra:
            cmd += ["--"] + extra
        run = subprocess.run(cmd, capture_output=True, text=True)
        log = run.stdout + run.stderr
        bad = [l for l in log.splitlines() if re.search(r"ERROR|WARNING", l)]
        for l in bad[:6]:
            print("run:", l)
        if len(bad) > 6:
            print(f"run: … {len(bad)} Meldungen insgesamt, siehe {a.tag}.log")
        (out / f"{a.tag}.log").write_text(log)
        for f in frames:
            src = pathlib.Path(td) / f"f{f:08d}.png"
            if src.exists():
                shutil.copy(src, out / f"{a.tag}_f{f:03d}.png")
            else:
                print("fehlt:", src.name)
    print("ok", out)


if __name__ == "__main__":
    main()
