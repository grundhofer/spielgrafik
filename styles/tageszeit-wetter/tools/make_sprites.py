#!/usr/bin/env python3
"""Zeichnet die kleinen Partikel- und Schattentexturen der Demo (Code, keine KI).

    .venv/bin/python styles/tageszeit-wetter/tools/make_sprites.py

rain.png (Regenstrich), flake.png (Schneeflocke), puff.png (Rauchballen), splash.png (Spritzer),
shadow.png (Kontaktschatten des Dachses). Weiß mit Alpha, Farbe kommt aus Shader bzw. modulate.
"""
import pathlib, shutil

import numpy as np
from PIL import Image

ENTRY = pathlib.Path(__file__).resolve().parent.parent
OUT, ART = ENTRY / "assets" / "fx", ENTRY / "demo" / "art" / "fx"


def save(name, alpha):
    a = np.clip(alpha, 0, 1)
    rgba = np.zeros(a.shape + (4,), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (a * 255 + 0.5).astype(np.uint8)
    Image.fromarray(rgba).save(OUT / name)
    shutil.copy2(OUT / name, ART / name)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    # Regen: 4×64, quer gaußsch, längs von oben (Schweif) nach unten heller werdend
    y, x = np.mgrid[0:64, 0:4].astype(np.float32)
    across = np.exp(-((x - 1.5) / 0.9) ** 2)
    along = np.clip(y / 63, 0, 1) ** 1.6 * np.clip((64 - y) / 6, 0, 1)
    save("rain.png", across * along)
    # Schneeflocke: 16×16 weiche Scheibe mit festem Kern
    y, x = np.mgrid[0:16, 0:16].astype(np.float32)
    r = np.hypot(x - 7.5, y - 7.5)
    save("flake.png", np.clip(1.15 - r / 6.5, 0, 1) ** 1.4)
    # Rauch: 64×64 weicher Ballen mit leichtem, festem Rauschen am Rand
    rng = np.random.default_rng(7)
    y, x = np.mgrid[0:64, 0:64].astype(np.float32)
    ang = np.arctan2(y - 31.5, x - 31.5)
    wobble = sum(rng.uniform(0.02, 0.06) * np.cos(k * ang + rng.uniform(0, 6.28)) for k in (2, 3, 5))
    r = np.hypot(x - 31.5, y - 31.5) / 30.0 * (1 + wobble)
    save("puff.png", np.clip(1 - r, 0, 1) ** 1.6)
    # Spritzer: 16×8 flacher Ring (Aufprall auf dem Kai), oben offen
    y, x = np.mgrid[0:8, 0:16].astype(np.float32)
    e = np.hypot((x - 7.5) / 7.0, (y - 4.5) / 3.0)
    save("splash.png", np.exp(-((e - 0.75) / 0.18) ** 2) * np.clip((y - 1) / 3, 0, 1))
    # Kontaktschatten: 128×32 Ellipse
    y, x = np.mgrid[0:32, 0:128].astype(np.float32)
    e = np.hypot((x - 63.5) / 62, (y - 15.5) / 15)
    save("shadow.png", np.clip(1 - e, 0, 1) ** 1.3)


if __name__ == "__main__":
    main()
