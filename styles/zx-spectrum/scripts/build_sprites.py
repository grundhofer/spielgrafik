#!/usr/bin/env python3
"""Sprites aus Pixeltext -> demo/rom/sprites.json (Bytezeilen mit Maske, wie ein Spectrum-Spiel sie ablegt).

Dachs: scripts/badger.txt (24×40, Oberkörper + Beinposen + Blinzeln). Möwe und Rauch: props.py bzw. hier.
Jede Form wird 32 px breit gespeichert (4 Bytes je Zeile, Figur ab x = 4), damit die um 1 px erweiterte Maske
Platz hat. Maske = Umriss der Figur, um 1 px nach allen Seiten erweitert (Papierrand trennt die Figur vom
Hintergrund). Ausgabe außerdem assets/badger_sheet.png (Vorschau ×6 in den Zellfarben vor Schwarz und Blau).
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
sys.path.insert(0, str(HERE))
import zxlib as zx  # noqa: E402
import props  # noqa: E402

WIDTH, OFF = 32, 4
BANDS = [(4, 1), (7, 1), (2, 1), (4, 1), (7, 1)]   # (INK, BRIGHT) je 8 Zeilen: Grün, Weiß, Rot, Grün, Weiß


def parse(path):
    sec, out = None, {}
    for line in path.read_text().splitlines():
        if " " in line.strip() or not line.strip():  # Kommentare enthalten Leerzeichen, Pixelzeilen nicht
            continue
        if line.startswith("["):
            sec = line.strip()[1:-1]
            out[sec] = []
            continue
        out[sec].append(line.rstrip("\n"))
    for k, rows in out.items():
        for i, r in enumerate(rows):
            if len(r) != 24:
                raise SystemExit(f"{k} Zeile {i}: Breite {len(r)} statt 24: {r!r}")
    return out


def to_planes(rows):
    h = len(rows)
    bits = np.zeros((h, WIDTH), np.uint8)
    sil = np.zeros((h, WIDTH), bool)
    for yy, r in enumerate(rows):
        for xx, ch in enumerate(r):
            X = xx + OFF
            if ch == ".":
                continue
            sil[yy, X] = True
            if ch == "#" or (ch == ":" and (xx + yy) % 2 == 0):
                bits[yy, X] = 1
    mask = sil.copy()
    mask[1:] |= sil[:-1]
    mask[:-1] |= sil[1:]
    mask[:, 1:] |= sil[:, :-1]
    mask[:, :-1] |= sil[:, 1:]
    return bits, mask.astype(np.uint8)


def rows_bytes(plane):
    return [list(int(v) for v in np.packbits(r)) for r in plane]


def badger_poses():
    art = parse(HERE / "badger.txt")
    body = art["body"]
    assert len(body) == 31, len(body)
    poses = {}
    for name in ("stand", "contact1", "pass1", "contact2", "pass2"):
        legs = art["legs:" + name]
        assert len(legs) == 9, (name, len(legs))
        poses[name] = body + legs
    blink = list(poses["stand"])
    blink[10] = art["blink"][0]
    poses["blink"] = blink
    flutter = list(poses["stand"])
    flutter[19:22] = art["flutter"]
    poses["flutter"] = flutter
    return poses


def text_shape(s):
    rows = [l for l in s.strip("\n").split("\n")]
    w = max(len(r) for r in rows)
    bits = np.zeros((len(rows), WIDTH), np.uint8)
    for yy, r in enumerate(rows):
        for xx, ch in enumerate(r):
            if ch == "1":
                bits[yy, xx + OFF] = 1
    return bits, w


SMOKE = [
    """
.11.
1111
.11.
""",
    """
..111.
.11111
111111
.1111.
""",
    """
..1.11..
.1111111
11111111
.111111.
..1111..
""",
    """
.1...1..
11.1.11.
.1...1.1
..1.1...
""",
]


def preview(poses):
    names = list(poses)
    sc = 6
    cell_w, cell_h = WIDTH * sc, 40 * sc
    sheet = Image.new("RGB", (cell_w * len(names), cell_h * 2), (0, 0, 0))
    for row, paper in enumerate([(0, 0, 0), (0, 0, 0xD7)]):
        for i, n in enumerate(names):
            bits, mask = to_planes(poses[n])
            img = np.zeros((40, WIDTH, 3), np.uint8)
            img[:] = (40, 40, 40) if row == 0 else (0, 0, 0x60)       # Hintergrund außerhalb der Maske
            img[mask == 1] = paper
            for band, (ink, br) in enumerate(BANDS):
                sl = slice(band * 8, band * 8 + 8)
                col = zx.PAL16[br * 8 + ink]
                sub = img[sl]
                sub[bits[sl] == 1] = col
            im = Image.fromarray(img).resize((cell_w, cell_h), Image.NEAREST)
            sheet.paste(im, (i * cell_w, row * cell_h))
    sheet.save(ENTRY / "assets/badger_sheet.png")


def main():
    poses = badger_poses()
    out = {"width": WIDTH, "offset": OFF, "bands": BANDS, "badger": {}, "gull": [], "smoke": []}
    for n, rows in poses.items():
        bits, mask = to_planes(rows)
        out["badger"][n] = {"h": 40, "data": rows_bytes(bits), "mask": rows_bytes(mask)}
    for s in props.GULL:
        bits, _ = text_shape(s)
        out["gull"].append({"h": bits.shape[0], "data": rows_bytes(bits)})
    for s in SMOKE:
        bits, _ = text_shape(s)
        out["smoke"].append({"h": bits.shape[0], "data": rows_bytes(bits)})
    (ENTRY / "demo/rom/sprites.json").write_text(json.dumps(out))
    preview(poses)
    # Unterschiede der Posen (Pixel)
    pl = {n: to_planes(r)[0] for n, r in poses.items()}
    for a, bb in [("contact1", "contact2"), ("pass1", "pass2"), ("stand", "blink"), ("stand", "flutter")]:
        print(f"{a}/{bb}: {int((pl[a] != pl[bb]).sum())} Pixel verschieden")


if __name__ == "__main__":
    main()
