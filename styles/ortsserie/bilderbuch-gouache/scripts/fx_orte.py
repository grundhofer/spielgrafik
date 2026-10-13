"""Gemalte Effekt-Texturen der Ortsserie im Duktus von bilderbuch-gouache.

Wiederverwendet aus styles/bilderbuch-gouache/scripts/build_scene.py (nur gelesen, kein Bytecode-Cache dort):
halo (Lichthof aus Farbringen), rays (Pinselstrahlen), stroke (Glitzerstrich), star, smoke_puff, band, paper.
Neu hier, mit denselben Pinseln aus styles/bilderbuch-gouache/tools/gouache.py: Flammen-Tupfer, Dampftupfer,
heller senkrechter Strich für die Lichtwanderung in der Linse, breiter dunkler Fleck hinter dem Text.
Alles wird in doppelter Größe gemalt und halbiert; feste Seeds, zwei Läufe ergeben dieselben Dateien.
"""
import pathlib, sys

import numpy as np

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parents[4]
GD = ROOT / "styles/bilderbuch-gouache"
sys.path.insert(0, str(GD / "scripts"))
sys.path.insert(0, str(GD / "tools"))
import build_scene as BS  # noqa: E402
from gouache import ellipse_sdf, to_image  # noqa: E402

halo, rays, stroke, star, smoke_puff, band, paper = (BS.halo, BS.rays, BS.stroke, BS.star, BS.smoke_puff, BS.band,
                                                      BS.paper)


def flame(seed, w=64, h=104, lean=0.0):
    """Flammen-Tupfer: drei deckende Tropfenformen (Koralle, Orange, Creme-Gelb), oben spitz, unten rund.
    Fußpunkt unten Mitte. lean verschiebt die Spitze waagerecht (Flackern über mehrere Bilder)."""
    H, W = h * 2, w * 2
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    rgb = np.zeros((H, W, 3), np.float32)
    al = np.zeros((H, W), np.float32)
    for i, (sc, col, tint) in enumerate([(1.0, (226, 108, 72), (238, 132, 80)), (0.72, (246, 164, 80), (250, 186, 96)),
                                         (0.42, (255, 228, 156), (255, 242, 196))]):
        bottom = H - 6
        ry = (H - 14) * 0.5 * sc
        cy = bottom - ry
        rx = W * 0.4 * sc
        u = np.clip((y - (cy - ry)) / (2 * ry), 0, 1)            # 0 oben, 1 unten
        f = 0.12 + 0.88 * np.sqrt(u)                             # oben schmal
        cx = W / 2 + lean * W * 0.18 * (1 - u) ** 2
        q = np.sqrt(((x - cx) / (rx * f + 1e-3)) ** 2 + ((y - cy) / ry) ** 2)
        sdf = (1 - q) * min(rx, ry) * 0.6
        c, a = BS.layer(H, W, sdf, col, seed + i * 5, wobble=2.5, wobble_cell=18, streak=3, streak_cells=(14, 3),
                        soft=1.1, holes=0.12, streak_amp=0.05, grain_amp=0.03, cells=(20, 3), tint=tint, tint_amp=0.5)
        rgb, al = BS.over(rgb, al, c, a)
    return BS.half(to_image(rgb, al))


def steam_puff(seed, size=120):
    """Dampftupfer: wie der Rauchtupfer, aber heller und kleiner (Kesseldampf in der Stube)."""
    h = w = size
    r = size * 0.36
    sdf = ellipse_sdf(h, w, w / 2, h / 2 + 2, r * 1.08, r)
    rgb, a = BS.layer(h, w, sdf, (222, 216, 214), seed, wobble=4, wobble_cell=22, streak=3, streak_cells=(6, 22),
                      soft=1.2, holes=0.16, streak_amp=0.05, grain_amp=0.03, cells=(5, 20), tint=(236, 222, 206),
                      tint_amp=0.5)
    sdf2 = ellipse_sdf(h, w, w / 2 - r * 0.18, h / 2 - r * 0.2, r * 0.75, r * 0.65)
    rgb2, a2 = BS.layer(h, w, sdf2, (248, 242, 232), seed + 50, wobble=4, wobble_cell=20, streak=3.5,
                        streak_cells=(5, 20), soft=1.2, holes=0.2, streak_amp=0.04, grain_amp=0.03, cells=(5, 18))
    rgb, a = BS.over(rgb, a, rgb2, a2 * a)
    return BS.half(to_image(rgb, a))


def sweep_light(seed, w=84, h=230):
    """Lichtwanderung in der Glaslinse: senkrecht gestreckter Lichthof aus flachen Farbringen (wie halo, aber als
    hohe Ellipse), damit der vorbeiziehende Lichtstreifen gemalt wirkt und nicht wie ein Leuchten."""
    H, W = h * 2, w * 2
    rgb = np.zeros((H, W, 3), np.float32)
    al = np.zeros((H, W), np.float32)
    for i, (rr, col, op) in enumerate(zip([1.0, 0.7, 0.42, 0.2],
                                          [(250, 226, 176), (252, 234, 190), (255, 242, 206), (255, 250, 230)],
                                          [0.16, 0.26, 0.45, 0.9])):
        sdf = ellipse_sdf(H, W, W / 2, H / 2, rr * W / 2 - 2, (0.55 + 0.45 * rr) * H / 2 - 2)
        c, a = BS.layer(H, W, sdf, col, seed + i * 7, wobble=3, wobble_cell=30, streak=3, streak_cells=(30, 4),
                        soft=1.4, holes=0.1, streak_amp=0.04, grain_amp=0.03, cells=(30, 4))
        rgb, al = BS.over(rgb, al, c, a * op)
    return BS.half(to_image(rgb, al))


def text_band(seed, w=700, h=150):
    """Breiter dunkler Pinselfleck hinter dem Text (wie der Fleck hinter den Antworten im Hafen)."""
    return band(seed, w=w, h=h)
