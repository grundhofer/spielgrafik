#!/usr/bin/env python3
"""Papier, Papierzahn und Boil-Rauschen aus Code (fester Seed, bitgleich reproduzierbar).

    .venv/bin/python styles/bleistift-skizze/scripts/make_paper.py

Ergebnis (in assets/ und als Kopie in demo/art/):
  paper.png   1280x720  kariertes Skizzenbuchblatt: 20-px-Karo, Spiralbindung oben, leichte Faser- und Wolkentöne
  tooth.png   256x256   kachelbares Papierkorn (Zahn), auf dem der Grafit hängen bleibt
  boil.png    256x256   kachelbares, weiches Rauschen: R/G = Versatz, B = Druckschwankung für den Line-Boil
"""
import json, pathlib, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSETS, ART = ROOT / "assets", ROOT / "demo/art"
W, H = 1280, 720
CELL = 20            # Karo 20 px
GRID_X0, GRID_Y0 = 0, 40   # erste Karolinie (oben unter der Bindung)
PAGE_TOP = 10        # darüber liegt der dunkle Rückendeckel
rng = np.random.default_rng(20261011)


def tile_noise(n, scale, octaves=3, seed=0):
    """Kachelbares Wertrauschen über FFT-gefiltertes weißes Rauschen (periodisch per Konstruktion)."""
    r = np.random.default_rng(seed)
    out = np.zeros((n, n))
    amp = 1.0
    for o in range(octaves):
        white = r.standard_normal((n, n))
        f = np.fft.fft2(white)
        ky = np.fft.fftfreq(n)[:, None]
        kx = np.fft.fftfreq(n)[None, :]
        k = np.sqrt(kx ** 2 + ky ** 2)
        sigma = 1.0 / (scale / (2 ** o))
        filt = np.exp(-(k / sigma) ** 2)
        layer = np.real(np.fft.ifft2(f * filt))
        layer /= layer.std() + 1e-9
        out += amp * layer
        amp *= 0.5
    out /= out.std() + 1e-9
    return out


def paper():
    ss = 4
    base = np.array([246, 244, 236], np.float32) / 255.0
    img = np.ones((H, W, 3), np.float32) * base
    # leichte Wolkigkeit und Fasern
    cloud = tile_noise(1280, 180, 3, seed=11)[:H, :W]
    img *= (1.0 + 0.012 * cloud)[..., None]
    fib = rng.standard_normal((H, W)).astype(np.float32)
    fib = np.asarray(Image.fromarray(((fib * 18) + 128).clip(0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(0.6)), np.float32) / 255.0 - 0.5
    img *= (1.0 + 0.035 * fib)[..., None]
    # Karo: blaugraue Linien, 1 px, gedruckt (leicht schwankende Deckung)
    grid = np.zeros((H, W), np.float32)
    line_rgb = np.array([150, 178, 205], np.float32) / 255.0
    for x in range(GRID_X0, W, CELL):
        grid[:, x] = np.maximum(grid[:, x], 0.55)
    for y in range(GRID_Y0, H, CELL):
        grid[y, :] = np.maximum(grid[y, :], 0.55)
    grid *= (0.85 + 0.15 * (rng.random((H, W)) > 0.08))
    grid[:GRID_Y0 - CELL // 2, :] = 0   # Rand unter der Bindung frei
    img = img * (1 - grid[..., None]) + (img * line_rgb) * grid[..., None]
    # Rand leicht dunkler (Blatt liegt nicht ganz plan)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vig = ((xx - W / 2) / (W / 2)) ** 2 * 0.5 + ((yy - H / 2) / (H / 2)) ** 2 * 0.5
    img *= (1.0 - 0.035 * vig)[..., None]
    im = Image.fromarray((img.clip(0, 1) * 255).astype(np.uint8))

    # Spiralbindung oben, 4-fach überabgetastet
    big = Image.new("RGBA", (W * ss, 48 * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rectangle([0, 0, W * ss, PAGE_TOP * ss], fill=(46, 42, 39, 255))           # Rückendeckel
    d.rectangle([0, PAGE_TOP * ss, W * ss, (PAGE_TOP + 2) * ss], fill=(0, 0, 0, 40))  # Schatten Blattkante
    pitch = 26
    x0 = (W - (W // pitch - 1) * pitch) // 2
    for i in range(W // pitch):
        cx = x0 + i * pitch
        hx0, hy0 = cx - 4, 17
        # Loch (zeigt den dunklen Deckel)
        d.rounded_rectangle([hx0 * ss, hy0 * ss, (hx0 + 8) * ss, (hy0 + 9) * ss], radius=3 * ss,
                            fill=(52, 47, 43, 255))
        d.rounded_rectangle([hx0 * ss, (hy0 + 6) * ss, (hx0 + 8) * ss, (hy0 + 9) * ss], radius=2 * ss,
                            fill=(70, 64, 58, 255))
        # Draht: vom Loch über die Kante nach oben, leicht schräg
        pts = [((cx - 1) * ss, (hy0 + 5) * ss), ((cx + 1) * ss, (hy0 - 6) * ss), ((cx + 3) * ss, 2 * ss)]
        d.line(pts, fill=(58, 58, 62, 255), width=5 * ss, joint="curve")
        d.line([(p[0] - 1 * ss, p[1]) for p in pts], fill=(150, 152, 158, 255), width=2 * ss, joint="curve")
        d.line([(p[0] - 1.5 * ss, p[1]) for p in pts[1:]], fill=(214, 216, 220, 255), width=1 * ss)
    small = big.resize((W, 48), Image.LANCZOS)
    im.paste(small, (0, 0), small)
    return im


def tooth():
    n = 256
    t = tile_noise(n, 2.2, 2, seed=5)       # feines Korn
    t2 = tile_noise(n, 9.0, 2, seed=6)      # gröbere Struktur
    v = 0.75 * t + 0.35 * t2
    v = (v - v.min()) / (v.max() - v.min())
    return Image.fromarray((v * 255).astype(np.uint8), "L")


def boil():
    n = 256
    ch = [tile_noise(n, 22.0, 2, seed=s) for s in (21, 22, 23)]
    out = np.stack([(0.5 + 0.18 * c).clip(0, 1) for c in ch], -1)
    return Image.fromarray((out * 255).astype(np.uint8), "RGB")


def main():
    ASSETS.mkdir(exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    for name, im in (("paper.png", paper()), ("tooth.png", tooth()), ("boil.png", boil())):
        im.save(ASSETS / name)
        shutil.copy(ASSETS / name, ART / name)
        print("ok", ASSETS / name, im.size)
    (ASSETS / "paper.json").write_text(json.dumps({"cell": CELL, "grid_x0": GRID_X0, "grid_y0": GRID_Y0,
                                                    "page_top": PAGE_TOP}, indent=1))


if __name__ == "__main__":
    main()
