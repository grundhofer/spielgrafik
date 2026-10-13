#!/usr/bin/env python3
"""Prüflauf: Demo mit Movie Maker in Basisauflösung (426x240) aufnehmen und messen.

    .venv/bin/python styles/farbzyklus/scripts/probe.py OUTDIR [--at 0.5,2,4,5.5] [--zoom 3] [--crop x0,y0,x1,y1]
        [--feet] [--t0 S] [--frames 180] [--method forward_plus|mobile|gl_compatibility] [--keep]

Immer: zählt Farben je Bild (alles muss aus der 256er-Palette kommen) und prüft, ob die Hintergrundpixel nur
Farben der aktuellen Palette tragen.
--holds: Lauf mit --probe-log; listet, welches Dachsbild in welchem Aufnahmebild steht und wie lange es gehalten
wird (Aufnahmebild i zeigt den Stand nach dem (i+1)-ten _process-Aufruf; der Aufruf in _ready wird nicht
aufgenommen). Haltezeiten müssen bei 15 Bildern/s gerade sein. Ergebnis OUTDIR/holds.txt.
--feet: zweiter Lauf mit --probe (Dachs in reinem Magenta). Je Bild: Kopfoberkante, Kopfmitte (oberes Viertel)
und die Spalten der Sohlenzeile; Prüfung: Standfuß beim Gehen ortsfest (±1 px), Sohlenzeile in allen Bildern
gleich, Stehbilder ohne Sprung. Ergebnis OUTDIR/feet.txt.
"""
import argparse, pathlib, subprocess, tempfile, shutil
import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
DEMO = STYLE / 'demo'


def run(frames, extra, td, method=None):
    subprocess.run(['godot', '--headless', '--path', str(DEMO), '--import'], capture_output=True)
    cmd = ['godot', '--path', str(DEMO), '--position', '20000,20000', '--resolution', '1280x720',
           '--write-movie', f'{td}/f.png', '--fixed-fps', '30', '--quit-after', str(frames)]
    if method:
        cmd[1:1] = ['--rendering-method', method]
    if extra:
        cmd += ['--'] + extra
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if 'ERROR' in l or 'WARNING' in l]
    return sorted(pathlib.Path(td).glob('f*.png')), errs


def runs(row):
    xs = np.flatnonzero(row)
    out = []
    for x in xs:
        if out and x == out[-1][1] + 1:
            out[-1][1] = x
        else:
            out.append([x, x])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--at', default='0.2,1.5,2.5,3.5,4.5,5.5')
    ap.add_argument('--zoom', type=int, default=3)
    ap.add_argument('--crop')
    ap.add_argument('--feet', action='store_true')
    ap.add_argument('--t0', type=float, default=0.0)
    ap.add_argument('--frames', type=int, default=180)
    ap.add_argument('--method')
    ap.add_argument('--keep', action='store_true', help='alle Bilder nach OUTDIR/frames kopieren')
    ap.add_argument('--holds', action='store_true')
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    extra = [f'--t0={a.t0}'] if a.t0 else []
    with tempfile.TemporaryDirectory() as td:
        pngs, errs = run(a.frames, extra, td, a.method)
        print('Meldungen:', errs[:6])
        counts = []
        for p in pngs:
            im = np.asarray(Image.open(p).convert('RGB'))
            counts.append(len(np.unique(im.reshape(-1, 3), axis=0)))
        print('Bilder', len(pngs), 'Größe', Image.open(pngs[0]).size, 'Farben je Bild min/max', min(counts), max(counts))
        for ts in a.at.split(','):
            i = min(len(pngs) - 1, int(round(float(ts) * 30)))
            im = Image.open(pngs[i]).convert('RGB')
            if a.crop:
                im = im.crop(tuple(int(v) for v in a.crop.split(',')))
            im.resize((im.width * a.zoom, im.height * a.zoom), Image.NEAREST).save(out / f'probe_{ts}.png')
        if a.keep:
            fd = out / 'frames'; fd.mkdir(exist_ok=True)
            for p in pngs:
                shutil.copy(p, fd / p.name)
    if a.holds:
        log = pathlib.Path.home() / 'Library/Application Support/Godot/app_userdata' / \
            'Farbzyklus – Hafen von Lornholm/probe.txt'
        if log.exists():
            log.unlink()
        with tempfile.TemporaryDirectory() as td:
            run(a.frames, extra + ['--probe-log'], td, a.method)
        rows = [l.split() for l in log.read_text().splitlines() if l.strip()]
        names = [r[2] for r in rows[1:]]           # ohne den Aufruf aus _ready
        holds = []
        for i, nm in enumerate(names):
            if holds and holds[-1][1] == nm:
                holds[-1][2] += 1
            else:
                holds.append([i, nm, 1])
        txt = '\n'.join(f'Bild {i:3d}: {nm} x{n}' for i, nm, n in holds)
        (out / 'holds.txt').write_text(txt + '\n')
        odd = [(i, nm, n) for i, nm, n in holds[:-1] if n % 2]
        print('Haltezeiten (Aufnahmebilder):', sorted({n for _, _, n in holds[:-1]}), '| ungerade:', odd,
              '| Blinzeln ab Bild', [i for i, nm, _ in holds if nm == 'blink'])
    if a.feet:
        with tempfile.TemporaryDirectory() as td:
            pngs, errs = run(a.frames, extra + ['--probe'], td, a.method)
            lines, rec = [], []
            for i, p in enumerate(pngs):
                im = np.asarray(Image.open(p).convert('RGB')).astype(int)
                m = (im[..., 0] == 255) & (im[..., 1] == 0) & (im[..., 2] == 255)
                ys, xs = np.nonzero(m)
                if not len(ys):
                    lines.append(f'{i:3d} -'); continue
                top, bot = ys.min(), ys.max()
                head = xs[ys < top + 12].mean()
                sole = runs(m[bot])
                lines.append(f'{i:3d} {i / 30:5.2f} kopf_y={top} kopf_x={head:6.1f} sohle_y={bot} '
                             + ' '.join(f'{s}-{e}' for s, e in sole))
                rec.append((i, top, head, bot, [tuple(r) for r in sole]))
            (out / 'feet.txt').write_text('\n'.join(lines) + '\n')
            # Auswertung: Sohlenzeile, Standfuß (ein Sohlenlauf, der in aufeinanderfolgenden Bildern gleich bleibt),
            # Kopfsprünge zwischen aufeinanderfolgenden Bildern
            soles = sorted({r[3] for r in rec})
            jumps = [abs(b[2] - a[2]) for a, b in zip(rec, rec[1:])]
            runs_all = [set(r[4]) for r in rec]
            hold = []                      # wie viele Bilder ein Sohlenlauf unverändert stehen bleibt
            cur = {}
            for k, rs in enumerate(runs_all):
                new = {}
                for r in rs:
                    new[r] = cur.get(r, 0) + 1
                for r, n in cur.items():
                    if r not in rs:
                        hold.append(n)
                cur = new
            hold += list(cur.values())
            # Standfuß-Drift: Lauf, der im nächsten Bild um 1..3 px verschoben wieder auftaucht (Rutschen)
            slide = 0
            for a, b in zip(runs_all, runs_all[1:]):
                for (s0, e0) in a:
                    if (s0, e0) in b:
                        continue
                    for (s1, e1) in b:
                        if e1 - s1 == e0 - s0 and 1 <= abs(s1 - s0) <= 3:
                            slide += 1
            print(f'Sohlenzeilen: {soles} | größter Kopfsprung zwischen Bildern: {max(jumps):.1f} px | '
                  f'Sohlenläufe stehen {min(hold)}..{max(hold)} Bilder | Rutschen um 1-3 px: {slide}')
            print('Fußmessung:', out / 'feet.txt')


if __name__ == '__main__':
    main()
