#!/usr/bin/env python3
"""Nimmt die Godot-Demo eines Stils auf und erzeugt die Medien für den Katalog.

    python3 tools/capture.py styles/<slug>            # Standard: 6 s, 30 fps, 1280x720
    python3 tools/capture.py styles/<slug> --seconds 8 --poster-at 0.55

Ablauf:
  1. godot --headless --import (importiert neue Texturen/Modelle des Demo-Projekts)
  2. godot --write-movie mit fester Bildrate (deterministisch, unabhängig von der Rechnerlast).
     Das Fenster wird außerhalb des Bildschirms geöffnet; gerendert wird trotzdem.
  3. ffmpeg: media/demo.mp4 (H.264), media/preview.gif (480 px, 15 fps)
  4. media/poster.png + media/poster.webp (Einzelbild), media/frames.jpg (Kontaktbogen mit
     8 Zeitpunkten für die Sichtprüfung) und media/capture.json (Messwerte).

Abbruch mit Fehlercode, wenn Godot Fehler meldet, Bilder fehlen, alle Bilder gleich sind
(keine Animation) oder das Poster fast einfarbig ist (leere Szene).
"""
import argparse, json, pathlib, re, shutil, subprocess, sys, tempfile

import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("style_dir")
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--resolution", default="1280x720")
    ap.add_argument("--poster-at", type=float, default=0.6, help="Anteil der Laufzeit für das Poster")
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()

    sd = pathlib.Path(a.style_dir).resolve()
    demo, media = sd / "demo", sd / "media"
    if not (demo / "project.godot").exists():
        sys.exit(f"fehlt: {demo / 'project.godot'}")
    media.mkdir(exist_ok=True)
    w, h = map(int, a.resolution.split("x"))
    n = int(round(a.seconds * a.fps))

    imp = sh(["godot", "--headless", "--path", str(demo), "--import"], timeout=a.timeout)
    errors = [l for l in (imp.stdout + imp.stderr).splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]

    with tempfile.TemporaryDirectory() as td:
        frames = pathlib.Path(td)
        run = sh(["godot", "--path", str(demo), "--position", "20000,20000",
                  "--resolution", a.resolution, "--write-movie", str(frames / "f.png"),
                  "--fixed-fps", str(a.fps), "--quit-after", str(n)], timeout=a.timeout)
        log = run.stdout + run.stderr
        errors += [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
        warnings = [l for l in (imp.stdout + imp.stderr + log).splitlines() if re.search(r"\bWARNING\b", l)]
        (media / "godot.log").write_text(imp.stdout + imp.stderr + "\n----\n" + log)
        pngs = sorted(frames.glob("f*.png"))
        if len(pngs) < n * 0.9:
            sys.exit(f"nur {len(pngs)}/{n} Bilder aufgenommen; siehe {media / 'godot.log'}")

        # Movie Maker schreibt die Basisauflösung des Viewports (bei Pixel-Stilen z. B. 320x180).
        # Wie im Spiel: ganzzahlig mit "Nearest" hochskalieren, Rest schwarz auffüllen.
        first = Image.open(pngs[0])
        native = list(first.size)
        if first.size != (w, h):
            f = min(w / first.width, h / first.height)
            k = max(1, int(f)) if f >= 1 else f
            nw, nh = round(first.width * k), round(first.height * k)
            rs = Image.NEAREST if f >= 1 else Image.LANCZOS
            for p in pngs:
                im = Image.open(p).convert("RGB").resize((nw, nh), rs)
                canvas = Image.new("RGB", (w, h), "black")
                canvas.paste(im, ((w - nw) // 2, (h - nh) // 2))
                canvas.save(p)
            first = Image.open(pngs[0])
            print(f"Basisauflösung {native[0]}x{native[1]} -> x{k:g} auf {w}x{h}")

        # Bewegung messen: mittlere Pixeldifferenz zwischen Bildern im Abstand von 0,5 s
        step = max(1, a.fps // 2)
        arr = [np.asarray(Image.open(p).convert("RGB"), dtype=np.int16) for p in pngs[::step]]
        diffs = [float(np.abs(arr[i + 1] - arr[i]).mean()) for i in range(len(arr) - 1)]
        moving = [float((np.abs(arr[i + 1] - arr[i]).max(axis=2) > 24).mean()) for i in range(len(arr) - 1)]

        pi = min(len(pngs) - 1, int(len(pngs) * a.poster_at))
        poster = Image.open(pngs[pi]).convert("RGB")
        poster.save(media / "poster.png")
        sh(["cwebp", "-quiet", "-q", "86", "-m", "6", str(media / "poster.png"), "-o", str(media / "poster.webp")])
        std = float(np.asarray(poster, dtype=np.float32).std())

        # Kontaktbogen: 8 Zeitpunkte, 2 Reihen, mit Zeitstempel
        idx = [int(i * (len(pngs) - 1) / 7) for i in range(8)]
        tw, th = 640, int(640 * h / w)
        sheet = Image.new("RGB", (tw * 4, th * 2), "black")
        d = ImageDraw.Draw(sheet)
        for k, i in enumerate(idx):
            im = Image.open(pngs[i]).convert("RGB").resize((tw, th), Image.LANCZOS)
            x, y = (k % 4) * tw, (k // 4) * th
            sheet.paste(im, (x, y))
            d.rectangle([x, y, x + 64, y + 18], fill="black")
            d.text((x + 4, y + 3), f"t={i / a.fps:4.1f}s", fill="white")
        sheet.save(media / "frames.jpg", quality=85)

        pattern = str(frames / "f%08d.png")
        enc = sh(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-i", pattern,
                  "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "slow",
                  "-movflags", "+faststart", str(media / "demo.mp4")])
        if enc.returncode:
            sys.exit("ffmpeg mp4: " + enc.stderr[-500:])
        gif = sh(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-i", pattern,
                  "-vf", "fps=15,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];"
                         "[b][p]paletteuse=dither=bayer:bayer_scale=4",
                  str(media / "preview.gif")])
        if gif.returncode:
            print("WARNUNG: GIF fehlgeschlagen: " + gif.stderr[-300:])

    info = {
        "frames": len(pngs), "fps": a.fps, "seconds": a.seconds, "size": list(first.size), "native": native,
        "poster_frame": pi, "poster_std": round(std, 1),
        "motion_mean_diff": [round(x, 2) for x in diffs],
        "motion_changed_share": [round(x, 4) for x in moving],
        "godot_errors": errors[:40],
        "godot_warnings": warnings[:40],
    }
    (media / "capture.json").write_text(json.dumps(info, indent=1, ensure_ascii=False))
    print(json.dumps({k: info[k] for k in ("frames", "size", "poster_std")}, ensure_ascii=False))
    print("Bewegung (Anteil geänderter Pixel je 0,5 s):", " ".join(f"{x:.3f}" for x in moving))
    problems = []
    if errors:
        problems.append(f"{len(errors)} Godot-Fehler (erste: {errors[0][:160]})")
    if max(moving, default=0) < 0.002:
        problems.append("keine sichtbare Animation")
    if std < 6:
        problems.append("Poster fast einfarbig")
    if warnings:
        # Warnungen brechen nicht ab, gehören aber geprüft (z. B. "Loaded resource as image file").
        print(f"WARNUNGEN ({len(warnings)}): " + " | ".join(w[:140] for w in warnings[:5]))
    if problems:
        print("PROBLEME: " + "; ".join(problems))
        return 2
    print(f"ok: {media}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
