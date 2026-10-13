"""Palettentest: Liegen Kacheln, Requisiten, Dachs und Porträt auf der gemeinsamen Palette (isopal.all_colors())?

  .venv/bin/python styles/iso-pixel/scripts/check_palette.py

Kacheln und Kleinteile (Poller, Paket, Felsen, Grasbüschel) dürfen zusätzlich die benannten Zusatzfarben aus
build_tiles.EXTRA tragen (Wasserlicht, Abendrot-Glanz, Schaum, Algen, Meeresgrund); sie werden einzeln ausgewiesen.
Alles andere außerhalb der Palette ist ein Fehler. Himmel und Effekt-Sprites (demo/art/sky.png, demo/art/fx:
Lichthöfe, Rauch, Wolken, Möwen) sind bewusst nicht Teil der Palette und werden nicht geprüft.
Exit-Code 1, wenn ein geprüftes Bild fremde Farben enthält.
"""
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isopal  # noqa: E402
import build_tiles  # noqa: E402

ENTRY = HERE.parent
ART = ENTRY / "demo/art"
PAL = set(isopal.all_colors())
EXTRA = {}
for k, v in build_tiles.EXTRA.items():
    for c in (v if isinstance(v, list) else [v]):
        EXTRA[tuple(c)] = k


def colors(path):
    a = np.asarray(Image.open(path).convert("RGBA"))
    px = a[a[..., 3] > 0][:, :3]
    return {tuple(int(x) for x in c) for c in np.unique(px, axis=0)}


def main():
    bad = 0
    print(f"Palette: {len(PAL)} Farben (isopal.all_colors())")
    checks = [("Requisite", p) for p in sorted((ART / "props").glob("*.png"))]
    checks += [("Dachs", ART / "badger.png"), ("Porträt", ART / "portrait.png"),
               ("Porträt", ART / "portrait_blink.png")]
    for kind, p in checks:
        cs = colors(p)
        off = sorted(cs - PAL)
        bad += bool(off)
        print(f"  {kind:9s} {p.name:20s} {len(cs):3d} Farben, außerhalb: {len(off)} {off[:6] if off else ''}")
    for p in (ART / "tiles.png", ART / "jetty.png"):
        cs = colors(p)
        extra = sorted({EXTRA[c] for c in cs if c in EXTRA})
        off = sorted(c for c in cs - PAL if c not in EXTRA)
        bad += bool(off)
        print(f"  Kacheln   {p.name:20s} {len(cs):3d} Farben, Zusatzfarben: {extra}, außerhalb: {len(off)} "
              f"{off[:6] if off else ''}")
    other = [p for p in sorted(ART.glob("*.png")) if p.name not in
             ("badger.png", "portrait.png", "portrait_blink.png", "tiles.png", "jetty.png", "sky.png")]
    for p in other:
        cs = colors(p)
        extra = sorted({EXTRA[c] for c in cs if c in EXTRA})
        off = sorted(c for c in cs - PAL if c not in EXTRA)
        bad += bool(off)
        print(f"  Kleinteil {p.name:20s} {len(cs):3d} Farben, Zusatzfarben: {extra}, außerhalb: {len(off)}")
    print("FEHLER: fremde Farben" if bad else "ok: Requisiten, Dachs, Porträt, Kacheln und Kleinteile liegen auf der "
          "Palette (Kacheln und Felsen zusätzlich mit den benannten Wasserfarben)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
