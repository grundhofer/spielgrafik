#!/usr/bin/env python3
"""Effekt-Texturen für die Demo (NumPy, Pillow, feste Seeds): Lichthof, Lichtkegel, Rauchballen, Möwe (3 Flügel-
stellungen), Kontaktschatten.

    .venv/bin/python -I styles/parallax-2-5d/tools/build_fx.py

Ausgabe: assets/fx/*.png, Kopie nach demo/fx/
"""
import pathlib, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

S = pathlib.Path(__file__).resolve().parent.parent
OUT = S / "assets/fx"
DEMO = S / "demo/fx"

IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[params]

compress/mode=0
compress/high_quality=false
compress/lossy_quality=0.7
compress/hdr_compression=1
compress/normal_map=0
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode=0
roughness/src_normal=""
process/fix_alpha_border=true
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""


def save(name, rgba):
    Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA").save(OUT / name)


def halo(n=256):
    y, x = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    r = np.sqrt(x * x + y * y)
    a = np.clip(1 - r, 0, 1) ** 2.2 * 0.75 + np.exp(-(r / 0.12) ** 2) * 0.25
    return np.dstack([np.full_like(a, 255)] * 3 + [a * 255])


def beam(w=512, h=64):
    """Lichtkegel: Ursprung links, nach rechts breiter und schwächer; Längsstreifen für Dunst."""
    x = np.linspace(0, 1, w)[None, :]
    y = np.linspace(-1, 1, h)[:, None]
    width = 0.08 + 0.92 * x
    across = np.clip(1 - (np.abs(y) / width) ** 2, 0, 1)
    along = (1 - x) ** 1.4 * np.clip(x / 0.02, 0, 1)
    rng = np.random.default_rng(3)
    streak = 0.8 + 0.2 * np.interp(y[:, 0], np.linspace(-1, 1, 9), rng.uniform(0, 1, 9))[:, None]
    a = across * along * streak
    return np.dstack([np.full_like(a, 255)] * 3 + [a * 255])


def puff(n=128, seed=5):
    """Rauchballen mit weichem Rand und etwas Pinselstruktur."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    r = np.sqrt(x * x + y * y)
    noise = np.zeros((n, n))
    for k, amp in ((4, 0.5), (8, 0.3), (16, 0.2)):
        g = rng.uniform(-1, 1, (k + 1, k + 1))
        im = Image.fromarray(((g + 1) * 127.5).astype(np.uint8)).resize((n, n), Image.BICUBIC)
        noise += amp * (np.asarray(im) / 127.5 - 1)
    a = np.clip(1 - r * (1 + 0.35 * noise), 0, 1) ** 1.6
    return np.dstack([np.full_like(a, 255)] * 3 + [a * 255])


def gull(phase):
    """Möwe aus der Ferne: geschwungenes „M“ aus zwei sich verjüngenden hellen Flügelbögen mit dunklen Spitzen
    (hebt sich vom dunklen Abendhimmel ab), heller Körper, 3 Stellungen
    (0 Flügel oben, 1 Mitte, 2 unten), 4-fach überabgetastet gezeichnet."""
    n, s = 96, 4
    im = Image.new("RGBA", (n * s, n * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = 48 * s, 50 * s
    elbow = {0: -14, 1: -5, 2: 4}[phase]
    tip = {0: -24, 1: 2, 2: 16}[phase]
    for side in (-1, 1):
        # Bogen Körper -> Ellbogen -> Spitze, Dicke nimmt ab
        pts = []
        for i in range(41):
            u = i / 40
            if u < 0.45:
                k = u / 0.45
                x = side * (3 + 13 * k); y = elbow * (k ** 0.8)
            else:
                k = (u - 0.45) / 0.55
                x = side * (16 + 24 * k); y = elbow + (tip - elbow) * (k ** 1.3)
            pts.append((x, y, 6.5 * (1 - u) + 1.6))
        for j, ((x0, y0, w0), (x1, y1, w1)) in enumerate(zip(pts[:-1], pts[1:])):
            # helle Flügel (letztes Abendlicht), dunkle Spitzen
            colr = (222, 214, 204, 255) if j < 31 else (70, 70, 82, 255)
            d.line([(cx + x0 * s, cy + y0 * s), (cx + x1 * s, cy + y1 * s)], fill=colr,
                   width=max(1, int(round((w0 + w1) * s / 2))))
            r = (w1 * s) / 2
            d.ellipse([cx + x1 * s - r, cy + y1 * s - r, cx + x1 * s + r, cy + y1 * s + r], fill=colr)
    d.ellipse([cx - 7 * s, cy - 4 * s, cx + 9 * s, cy + 4 * s], fill=(240, 236, 228, 255))
    im = im.resize((n, n), Image.LANCZOS)
    return np.asarray(im).astype(np.float32)


def shadow(w=256, h=96):
    y, x = np.mgrid[0:h, 0:w]
    u = (x / (w - 1) * 2 - 1); v = (y / (h - 1) * 2 - 1)
    r = np.sqrt(u * u + v * v)
    a = np.clip(1 - r, 0, 1) ** 1.5
    return np.dstack([np.zeros_like(a)] * 3 + [a * 255])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    save("halo.png", halo())
    save("beam.png", beam())
    save("puff.png", puff())
    for i in range(3):
        save(f"gull{i}.png", gull(i))
    save("shadow.png", shadow())
    DEMO.mkdir(parents=True, exist_ok=True)
    for f in sorted(OUT.glob("*.png")):
        shutil.copy2(f, DEMO / f.name)
        imp = DEMO / (f.name + ".import")
        if not imp.exists():
            imp.write_text(IMPORT)
    print("ok", sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
