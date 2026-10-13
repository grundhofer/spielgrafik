#!/usr/bin/env python3
"""Bereitet alle Bilder für die Godot-Demo auf und schreibt demo/art/scene.json.

    .venv/bin/python styles/textoberflaeche/scripts/prep.py

Der Eintrag braucht keine eigenen KI-Bilder (assets/image_jobs.json ist leer, Begründung in NOTES.md):
  1. Gemälde: das KI-Hauptbild von styles/painterly-digital (assets/raw/master.png, agy), NUR LESEND genutzt,
     mit Lanczos auf 640 px Breite (640×429). Alle Oberflächen zeigen es im selben Maßstab, nur mit anderem
     Ausschnitt (Vollbild, Band oben, Hochformat-Streifen); eine Hafen-Szene wird von allen vier geteilt.
  2. Effekt-Texturen aus Code: Leuchtturmkegel, Glitzerstrich, Rauchwolke, Papierseite.
  3. Inventar-Icons aus Code (scripts/draw_icons.py).
  4. Dachs als Schnittfigur aus shared/badger/walk_painted.png (scripts/badger_rig.py), 56 px hoch.
  5. scene.json mit allen Lagen (im 640er-Gemälde von Hand gemessen, siehe ANCHORS) und dem Laufplan.
Ein zweiter Lauf erzeugt bitgleiche Dateien.
"""
import json, pathlib, sys

import numpy as np
from PIL import Image, ImageFilter

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
ROOT = ENTRY.parents[1]
ASSETS = ENTRY / "assets"
ART = ENTRY / "demo" / "art"
sys.path.insert(0, str(HERE))
import badger_rig  # noqa: E402
import draw_icons  # noqa: E402

BG_SRC = ROOT / "styles" / "painterly-digital" / "assets" / "raw" / "master.png"   # nur lesen
W = 640  # Breite des Gemäldes in der Demo

# Lagen im 640er-Gemälde (x, y in Pixeln), von Hand gemessen (Rasterbild in NOTES.md beschrieben).
ANCHORS = {
    "lamp": [540, 109],      # Lampenhaus des Leuchtturms (gemalter Lichtpunkt)
    "lantern": [227, 243],   # Glas der Laterne am Pfosten
    "window": [152, 253],    # erleuchtetes Fenster des Hafenmeisterhäuschens
    "chimney": [136, 137],   # Oberkante der beiden Schornsteintöpfe
}
GLINTS = [  # Zonen x0, y0, x1, y1, Anzahl, warm (1) / kühl (0)
    [236, 204, 470, 214, 7, 1],    # Spiegelung des Horizontstreifens
    [508, 250, 576, 276, 5, 1],    # unter dem Leuchtturm
    [240, 262, 300, 288, 4, 1],    # unter der Laterne, links vom Steg
    [420, 240, 500, 262, 3, 0],    # kühle Lichter im Dunst
]
GULLS = [  # x, y, vx (px/s), Spannweite, Strichstärke, Phase
    [292, 112, 8.0, 5.5, 1.3, 0.0],
    [352, 128, 6.0, 4.5, 1.1, 2.1],
]
BADGER_H = 56                 # Figurenhöhe (Mütze bis Sohle) in px; Tür des Häuschens ≈ 60 px
WALK = {
    "ground_y": 322,          # Fußlinie auf der Kaikante (vor Tauen und Kisten, deren Unterkante bei ≈ 312 liegt)
    "step": 14.0,             # Schrittlänge (Abstand der Aufsetzpunkte), px
    "speed": 32.0,            # px/s im gleichmäßigen Teil
    "decel": 0.7,             # Abbremsen in s
    "steps": 9,               # ganze Schritte vor dem letzten halben (Stehen in Mittelstellung)
    "stop_x": 252,            # Hüfte beim Stehen: rechts neben dem Laternenpfosten
    "lift": 2.5,              # Hub des Schwungfußes, px
    "far_dx": -2.0,           # fernes Bein: Versatz nach hinten, abgedunkelt
    "far_shade": 0.62,
    "shadow_w": 24,
}
PARCEL = {"pos": [300, 322], "size": 16}
# Ausschnitte (linke obere Ecke im 640er-Gemälde) je Oberfläche
CROPS = {"choice": [400, 16], "illustrated": [0, 92], "fullscreen": [0, 69]}
BAND_H = 234                  # Höhe des Bildbands der illustrierten Oberfläche (Leuchtturmspitze bis Fußlinie)
BEAM_PHASE = 2.2
BEAM_LEN = 1.0


def save(img, rel, demo=True):
    """Speichert in assets/ und (Kopie) in demo/art/."""
    for base in ((ASSETS, ART) if demo else (ASSETS,)):
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        img.save(p, optimize=False)


def make_bg():
    im = Image.open(BG_SRC).convert("RGB")
    h = round(im.height * W / im.width)
    bg = im.resize((W, h), Image.LANCZOS)
    save(bg, "bg_640.png")
    return bg


def make_beam():
    # Kegel: an der Lampe schmal, nach außen breiter, weich auslaufend; horizontal nach rechts.
    L, H = 420, 120
    x = np.linspace(0, 1, L)[None, :]
    y = np.linspace(-1, 1, H)[:, None]
    half = 0.08 + 0.92 * x                     # halbe Breite relativ
    edge = np.clip(1.0 - np.abs(y) / half, 0, 1) ** 1.6
    along = np.clip(1.0 - x, 0, 1) ** 1.3 * np.clip(x * 25, 0, 1)
    a = (edge * along * 255).astype(np.uint8)
    rgb = np.full((H, L, 3), 255, np.uint8)
    save(Image.fromarray(np.dstack([rgb, a]), "RGBA"), "beam.png")


def make_glint():
    L, H = 14, 4
    x = np.linspace(-1, 1, L)[None, :]
    y = np.linspace(-1, 1, H)[:, None]
    a = np.clip(1 - x ** 2, 0, 1) * np.clip(1 - y ** 2 * 0.8, 0, 1)
    rgb = np.full((H, L, 3), 255, np.uint8)
    save(Image.fromarray(np.dstack([rgb, (a * 255).astype(np.uint8)]), "RGBA"), "glint.png")


def make_smoke():
    # Weiche Wolke mit unregelmäßigem, gemaltem Rand: Radialverlauf + Rauschen, leicht weichgezeichnet.
    S = 96
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:S, 0:S] / (S - 1) * 2 - 1
    r = np.sqrt(xx ** 2 + yy ** 2)
    noise = Image.fromarray((rng.random((12, 12)) * 255).astype(np.uint8)).resize((S, S), Image.BICUBIC)
    n = np.asarray(noise, np.float32) / 255
    a = np.clip((0.82 + 0.28 * (n - 0.5) - r) * 3.2, 0, 1)
    img = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    rgb = np.full((S, S, 3), 255, np.uint8)
    save(Image.fromarray(np.dstack([rgb, np.asarray(img)]), "RGBA"), "smoke.png")


def make_paper():
    # Papierseite für die Auswahl-Oberfläche: warmes Off-White, weiche Flecken, feines Korn (fester Seed).
    w, h = 404, 360
    rng = np.random.default_rng(11)
    base = np.array([237, 228, 208], np.float32)
    low = Image.fromarray((rng.random((9, 10)) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    low = (np.asarray(low, np.float32) / 255 - 0.5) * 10
    grain = (rng.random((h, w)) - 0.5) * 7
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.clip(1 - np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy)) / 40.0, 0, 1) ** 2 * 10
    img = base[None, None, :] + (low + grain - edge)[:, :, None] * np.array([1.0, 1.0, 1.15])[None, None, :]
    save(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB"), "paper.png")


def make_icons():
    for n in draw_icons.NAMES:
        save(draw_icons.render(n), f"icons/{n}.png")
    # Die Icons werden 2- bis 4-fach verkleinert angezeigt: Mipmaps verhindern Flimmern an den Konturen.
    for n in draw_icons.NAMES:
        imp = ART / "icons" / f"{n}.png.import"
        if imp.exists():
            imp.write_text(imp.read_text().replace("mipmaps/generate=false", "mipmaps/generate=true"))
        else:
            imp.write_text('[remap]\n\nimporter="texture"\ntype="CompressedTexture2D"\n\n[params]\n\n'
                           "compress/mode=0\nmipmaps/generate=true\ndetect_3d/compress_to=0\n")


def make_badger():
    body, leg, rig = badger_rig.build(BADGER_H)
    save(body, "badger_body.png")
    save(leg, "badger_leg.png")
    save(badger_rig.preview(body, leg, rig, 6), "badger_preview.png", demo=False)
    return dict(rig, body="badger_body.png", leg="badger_leg.png")


def scene_json(bg, rig):
    walk = dict(WALK)
    walk["distance"] = WALK["step"] * (WALK["steps"] + 0.5)
    walk["start_x"] = WALK["stop_x"] - walk["distance"]
    data = {
        "bg": {"file": "bg_640.png", "w": bg.width, "h": bg.height,
               "source": "styles/painterly-digital/assets/raw/master.png (nur lesend)"},
        "anchors": ANCHORS,
        "glints": GLINTS,
        "gulls": GULLS,
        "beam_phase": BEAM_PHASE,
        "beam_len": BEAM_LEN,
        "parcel": PARCEL,
        "badger": rig,
        "walk": walk,
        "crops": CROPS,
        "band_h": BAND_H,
    }
    (ART / "scene.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))


def main():
    bg = make_bg()
    make_beam()
    make_glint()
    make_smoke()
    make_paper()
    make_icons()
    rig = make_badger()
    scene_json(bg, rig)
    print("ok", bg.size, "Dachs", rig["height_px"], "px")


if __name__ == "__main__":
    main()
