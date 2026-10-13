"""Nimmt die Demo wie tools/capture.py auf (fester Takt 30 fps), behält aber alle Einzelbilder in einem Ordner.

    .venv/bin/python styles/textoberflaeche/scripts/grab.py OUTDIR [--seconds 6] [--extra-args ...]
"""
import argparse, pathlib, subprocess, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
DEMO = ROOT / "styles" / "textoberflaeche" / "demo"
ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--seconds", type=float, default=6.0)
ap.add_argument("--method", default="", help="z. B. mobile oder gl_compatibility")
ap.add_argument("--mask", action="store_true", help="Messlauf: nur der Dachs als weiße Maske")
a = ap.parse_args()
out = pathlib.Path(a.out)
shutil.rmtree(out, ignore_errors=True)
out.mkdir(parents=True)
cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
       "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(int(a.seconds * 30))]
if a.method:
    cmd += ["--rendering-method", a.method]
if a.mask:
    cmd += ["--", "--mask"]
p = subprocess.run(cmd, capture_output=True, text=True)
log = p.stdout + p.stderr
(out / "godot.log").write_text(log)
errs = [l for l in log.splitlines() if "ERROR" in l]
print(len(list(out.glob("f*.png"))), "Bilder;", len(errs), "Fehlerzeilen")
for e in errs[:10]:
    print(e)
