#!/usr/bin/env python3
"""Vergleicht die Demo-Aufnahme (Basisauflösung) zwischen Forward+, Mobile und Compatibility und prüft, ob zwei
Forward+-Läufe bitgleich sind.

    .venv/bin/python styles/amiga-illustration/scripts/compare_renderers.py
"""
import pathlib, subprocess, tempfile
import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent


def record(td, method):
    args = ['godot', '--path', str(STYLE / 'demo'), '--position', '20000,20000', '--resolution', '1280x720',
            '--write-movie', f'{td}/f.png', '--fixed-fps', '30', '--quit-after', '180']
    if method:
        args += ['--rendering-method', method]
    r = subprocess.run(args, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if 'ERROR' in l]
    return [np.asarray(Image.open(p).convert('RGB')).astype(int) for p in sorted(pathlib.Path(td).glob('f*.png'))], errs


with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b, \
        tempfile.TemporaryDirectory() as c, tempfile.TemporaryDirectory() as d:
    ref, e0 = record(a, None)
    again, e1 = record(b, None)
    print('Forward+ zweimal:', len(ref), 'Bilder, bitgleich:', all((x == y).all() for x, y in zip(ref, again)), e0[:2])
    for td, m in ((c, 'mobile'), (d, 'gl_compatibility')):
        fr, e = record(td, m)
        diff = [float((np.abs(x - y).max(-1) > 0).mean()) for x, y in zip(ref, fr)]
        mx = max(int(np.abs(x - y).max()) for x, y in zip(ref, fr))
        print(f'{m}: {len(fr)} Bilder, Fehler {e[:2]}, Anteil abweichender Pixel max {max(diff):.4%}, '
              f'größte Kanalabweichung {mx}')
