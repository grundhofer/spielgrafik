#!/usr/bin/env python3
"""Prüflauf: Demo mit Movie Maker in Basisauflösung aufnehmen, Farben je Bild zählen, Ausschnitte vergrößern.

    .venv/bin/python styles/vga-adventure/scripts/probe.py OUTDIR [--at 0.5,3.6] [--crop x0,y0,x1,y1] [--zoom 4] [--feet]

--feet: findet den Dachs über seine Palettenfarben (Einträge 12..29) und schreibt je Bild die Kopfoberkante, den
Kopf-Schwerpunkt und die Ausdehnung der Fußzeilen 143..146 nach OUTDIR/feet.txt (Prüfung: Standfuß ortsfest,
Stehbilder gleich, Auf und Ab beim Gehen).
Immer: zählt Farben je Bild und Farben außerhalb des 6-Bit-DAC-Rasters (Kanalwert v muss (v>>2)<<2 | v>>6 sein).
"""
import argparse, json, pathlib, subprocess, tempfile
import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument('out')
ap.add_argument('--at', default='0.5,1.7,2.6,3.6,5.0')
ap.add_argument('--crop', default='0,0,320,200')
ap.add_argument('--zoom', type=int, default=4)
ap.add_argument('--frames', type=int, default=180)
ap.add_argument('--feet', action='store_true')
a = ap.parse_args()


def runs(row):
    xs = np.flatnonzero(row)
    out = []
    for x in xs:
        if out and x == out[-1][1] + 1:
            out[-1][1] = x
        else:
            out.append([x, x])
    return ','.join(f'{s}-{e}' for s, e in out)

out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
subprocess.run(['godot', '--headless', '--path', str(STYLE / 'demo'), '--import'], capture_output=True)
with tempfile.TemporaryDirectory() as td:
    r = subprocess.run(['godot', '--path', str(STYLE / 'demo'), '--position', '20000,20000', '--resolution', '1280x720',
                        '--write-movie', f'{td}/f.png', '--fixed-fps', '30', '--quit-after', str(a.frames)],
                       capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if 'ERROR' in l]
    print('Fehler:', errs[:5])
    pngs = sorted(pathlib.Path(td).glob('f*.png'))
    counts, allc, off = [], set(), []
    for p in pngs:
        im = np.asarray(Image.open(p).convert('RGB'))
        u = np.unique(im.reshape(-1, 3), axis=0)
        counts.append(len(u))
        v = u.astype(int)
        off.append(int(((((v >> 2) << 2) | (v >> 6)) != v).any(1).sum()))
        allc.update(map(tuple, u))
    print('Bilder', len(pngs), 'Größe', Image.open(pngs[0]).size, 'Farben je Bild min/max', min(counts), max(counts))
    print('Farben außerhalb des 6-Bit-DAC-Rasters je Bild max', max(off), '| verschiedene Farben über alle Bilder',
          len(allc))
    box = tuple(int(v) for v in a.crop.split(','))
    for ts in a.at.split(','):
        i = min(len(pngs) - 1, int(float(ts) * 30))
        im = Image.open(pngs[i]).convert('RGB').crop(box)
        im.resize((im.width * a.zoom, im.height * a.zoom), Image.NEAREST).save(out / f'probe_{ts}.png')
    # Zeitreihe: Ausschnitt über alle Bilder (jedes 3.) nebeneinander für Bewegungsprüfung
    np.save(out / 'counts.npy', np.array(counts))
    if a.feet:
        pal = json.loads((STYLE / 'demo/art/palette.json').read_text())['palette']
        sprite = np.array([[int(h[k:k + 2], 16) for k in (0, 2, 4)] for h in pal[12:30]])
        lines = []
        for i, p in enumerate(pngs):
            im = np.asarray(Image.open(p).convert('RGB')).astype(int)
            reg = im[100:150, 166:320]          # rechts vom Paket am Kai (gleiche Farben)
            m = (reg[:, :, None, :] == sprite[None, None]).all(-1).any(-1)
            ys, xs = np.nonzero(m)
            if not len(ys):
                lines.append(f'{i:3d} {i / 30:5.2f} -'); continue
            top = ys.min()
            head = xs[ys < top + 10].mean() + 166
            feet = ' '.join(f'{y}:' + runs(np.pad(m[y - 100], (166, 0))) for y in range(143, 147))
            lines.append(f'{i:3d} {i / 30:5.2f} kopf_y={top + 100} kopf_x={head:6.1f} {feet}')
        (out / 'feet.txt').write_text('\n'.join(lines) + '\n')
        print('Fußzeilen:', out / 'feet.txt')
