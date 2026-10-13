#!/usr/bin/env python3
"""Prüflauf in Basisauflösung (320x200): Farben je Bildschirm zählen, 12-Bit-Raster prüfen, Dachs vermessen.

    .venv/bin/python styles/amiga-illustration/scripts/probe.py OUTDIR [--at 0.5,2.0,3.6] [--zoom 4] [--feet]

Farben: Bildbereich (Zeilen 10..153) höchstens 32 je Bild, Textschirm höchstens 4, alle Kanäle Vielfache von 17
(4 Bit je Kanal). Während die Nahaufnahme herabgezogen wird, stehen zwei Bilder mit je eigenen 32 Registern
übereinander (Palettenwechsel an der Kante wie per Copper): Der Bildbereich wird an ganz schwarzen Zeilen (Kante
des Bildes) geteilt und jedes Stück einzeln gezählt.
--feet: zweiter Lauf mit "-- --probe-badger" (nur der Dachs vor Schwarz). Je Bild: unterste Zeile, Ausdehnung
der Fußzeile und der Zeile darüber, Kopf-Schwerpunkt (oberes Viertel). Standfuß ortsfest = gleiche Spalten über
mehrere Bilder; Stehbilder = gleiche Fußzeilen.
"""
import argparse, pathlib, subprocess, tempfile
import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent


def record(td, extra=()):
    subprocess.run(['godot', '--headless', '--path', str(STYLE / 'demo'), '--import'], capture_output=True)
    r = subprocess.run(['godot', '--path', str(STYLE / 'demo'), '--position', '20000,20000', '--resolution', '1280x720',
                        '--write-movie', f'{td}/f.png', '--fixed-fps', '30', '--quit-after', '180', *extra],
                       capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if 'ERROR' in l]
    return sorted(pathlib.Path(td).glob('f*.png')), errs


def runs(row):
    xs = np.flatnonzero(row)
    out = []
    for x in xs:
        if out and x == out[-1][1] + 1:
            out[-1][1] = x
        else:
            out.append([x, x])
    return ','.join(f'{s}-{e}' for s, e in out)


ap = argparse.ArgumentParser()
ap.add_argument('out')
ap.add_argument('--at', default='0.5,1.5,3.0,3.4,3.7,4.2,5.5')
ap.add_argument('--zoom', type=int, default=4)
ap.add_argument('--crop', default='0,0,320,200')
ap.add_argument('--feet', action='store_true')
a = ap.parse_args()
out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as td:
    pngs, errs = record(td)
    print('Fehler:', errs[:5], 'Bilder', len(pngs), Image.open(pngs[0]).size)
    pic_c, txt_c, bad12, splits = [], [], 0, 0
    for p in pngs[30:]:
        im = np.asarray(Image.open(p).convert('RGB')).astype(int)
        reg = im[10:154]
        black = np.flatnonzero((reg.max(-1) == 0).all(1))
        cuts = [0] + [int(b) for b in black] + [len(reg)]
        splits += len(black) > 0
        for a_, b_ in zip(cuts[:-1], cuts[1:]):
            seg = reg[a_ + (1 if a_ in black else 0):b_].reshape(-1, 3)
            if len(seg):
                pic_c.append(len(np.unique(seg, axis=0)))
        txt = im[155:200].reshape(-1, 3)
        txt_c.append(len(np.unique(np.concatenate([txt, im[0:10].reshape(-1, 3)]), axis=0)))
        bad12 += int((im % 17 != 0).any(-1).sum())
    print(f'Bild: {min(pic_c)}..{max(pic_c)} Farben je Bildstück ({splits} Bilder mit Kante im Bildbereich); '
          f'Text+Status: {min(txt_c)}..{max(txt_c)}; Pixel außerhalb des 12-Bit-Rasters: {bad12}')
    box = tuple(int(v) for v in a.crop.split(','))
    for ts in a.at.split(','):
        i = min(len(pngs) - 1, int(float(ts) * 30))
        im = Image.open(pngs[i]).convert('RGB').crop(box)
        im.resize((im.width * a.zoom, im.height * a.zoom), Image.NEAREST).save(out / f'probe_{ts}.png')
if a.feet:
    with tempfile.TemporaryDirectory() as td:
        pngs, errs = record(td, ['--', '--probe-badger'])
        lines = []
        for i, p in enumerate(pngs):
            im = np.asarray(Image.open(p).convert('RGB')).astype(int)
            reg = im[10:154]
            m = reg.max(-1) > 0
            ys, xs = np.nonzero(m)
            if not len(ys):
                lines.append(f'{i:3d} {i / 30:5.2f} -'); continue
            top, bot = ys.min(), ys.max()
            head = xs[ys < top + max(1, (bot - top) // 4)].mean()
            lines.append(f'{i:3d} {i / 30:5.2f} oben={top + 10} unten={bot + 10} kopf_x={head:6.1f} '
                         f'fuss[{bot + 10}]={runs(m[bot])} [{bot + 9}]={runs(m[bot - 1])}')
        (out / 'feet.txt').write_text('\n'.join(lines) + '\n')
        print('Fußzeilen:', out / 'feet.txt')
