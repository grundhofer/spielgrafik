#!/usr/bin/env python3
"""Lichtkegel ohne Godot ansehen: rechnet shaders/indexed.gdshader in NumPy nach (Indexbild, Palette,
beam.png, beam_lut.png) und schreibt vergrößerte Ausschnitte für mehrere Drehwinkel.

    .venv/bin/python styles/vga-adventure/scripts/beam_preview.py OUTDIR [--zoom 3]

Die Konstanten LEVELS/GAIN/CUT müssen mit dem Shader übereinstimmen (palette.json → beam).
"""
import argparse, json, math, pathlib
import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
ART = STYLE / 'demo/art'
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def render(angle, meta, idx, beam, lut):
    pal = np.array([[int(h[k:k + 2], 16) for k in (0, 2, 4)] for h in meta['palette']], np.uint8)
    bm = meta['beam']
    r, g, b = [beam[..., i] / 255.0 for i in range(3)]
    c, s = math.cos(angle), math.sin(angle)
    halo = (b > 0.3) & (b < 0.7)
    d = np.where(b < 0.5, -c, c)
    I = np.where(halo, max(s, 0.0) ** 8,
                 np.where(d > 0, (1 - smoothstep(d - bm['soft'], d, g)) * (0.45 + 0.55 * d), 0))
    level = r * I * bm['gain']
    H, W = idx.shape
    th = np.tile(BAYER, (H // 4 + 1, W // 4 + 1))[:H, :W]
    # flache Stufen, gedithert wird nur in einem schmalen Übergang um die Stufengrenze (Breite 'band')
    fl = np.floor(level)
    fr = np.clip((level - fl - 0.5) / bm['band'] + 0.5, 0, 1)
    lv = np.floor(fl + fr + th).astype(int)
    lv[level < bm['cut']] = 0
    out = idx.copy()
    on = (r > 0) & (lv >= 1)
    lvl = np.minimum(lv, bm['levels']) - 1
    out[on] = lut[lvl[on], idx[on]]
    return pal[out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--zoom', type=int, default=3)
    ap.add_argument('--crop', default='60,0,320,100')
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    meta = json.loads((ART / 'palette.json').read_text())
    idx = np.asarray(Image.open(ART / 'bg_index.png')).astype(int)
    beam = np.asarray(Image.open(ART / 'beam.png').convert('RGB')).astype(float)
    lut = np.asarray(Image.open(ART / 'beam_lut.png')).astype(int)
    box = tuple(int(v) for v in a.crop.split(','))
    tiles = []
    for name, ang in (('links_voll', math.pi), ('links_schraeg', math.pi * 0.78), ('links_kurz', math.pi * 0.62),
                      ('vorn', math.pi / 2), ('rechts', 0.0)):
        im = Image.fromarray(render(ang, meta, idx, beam, lut)).crop(box)
        im = im.resize((im.width * a.zoom, im.height * a.zoom), Image.NEAREST)
        im.save(out / f'beam_{name}.png')
        tiles.append(im)
    sheet = Image.new('RGB', (tiles[0].width, sum(t.height for t in tiles[:3])))
    y = 0
    for t in tiles[:3]:
        sheet.paste(t, (0, y)); y += t.height
    sheet.save(out / 'beam_sheet.png')
    print('geschrieben:', out)


if __name__ == '__main__':
    main()
