#!/usr/bin/env python3
"""NumPy-Nachbau der Palettenmaschine aus demo/scripts/cycler.gd: rendert den Hintergrund zu beliebigen Zeiten,
ohne Godot. Zum schnellen Ausprobieren von Zyklus-Profilen, Lichtkegel und Überblendung.

    .venv/bin/python styles/farbzyklus/scripts/simulate.py OUTDIR [--at 0,1.5,3,4.5,6] [--gif 0:6] [--zoom 2]
"""
import argparse, json, math, pathlib
import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
ART = STYLE / 'demo/art'
TL = json.loads((STYLE / 'demo/art/timeline.json').read_text()) if (STYLE / 'demo/art/timeline.json').exists() else {}


def smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def pal_arr(hexes):
    return np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in hexes], np.float64)


class Engine:
    def __init__(self):
        self.meta = json.loads((ART / 'palette.json').read_text())
        self.idx = np.asarray(Image.open(ART / 'bg_index.png'))
        p = self.meta['palettes']
        self.P = [pal_arr(p['evening']), pal_arr(p['night']), pal_arr(p['rain'])]
        tl = self.meta.get('timeline', {})
        self.night = tl.get('night', [1.4, 3.4])
        self.rain = tl.get('rain', [4.0, 5.0])
        self.period = tl.get('beam_period', 4.0)
        self.angle0 = tl.get('beam_angle0', 2.6)
        rng = np.random.default_rng(3)
        self.noise = rng.random(512)

    def flick(self, t, rate, off):
        x = t * rate + off
        i = int(math.floor(x)); f = x - i
        a, b = self.noise[i % 512], self.noise[(i + 1) % 512]
        return a + (b - a) * (f * f * (3 - 2 * f))

    def palette(self, t):
        src = np.arange(256)
        theta = self.angle0 + 2 * math.pi * t / self.period
        for c in self.meta['cycles']:
            n, s, d = c['len'], c['start'], c['dir']
            if c['rate'] == 'beam':
                steps = int(math.floor(theta / (2 * math.pi) * n * 2))
            else:
                steps = int(math.floor(t * c['rate']))
            j = np.arange(n)
            src[s:s + n] = s + (j - d * steps) % n
        w1 = smoothstep(*self.night, t)
        w2 = smoothstep(*self.rain, t)
        P = self.P[0][src] * (1 - w1) + self.P[1][src] * w1
        P = P * (1 - w2) + self.P[2][src] * w2
        # Lichtkegel
        b = self.meta['beam']
        light = np.array(b['light_evening']) * (1 - w1) + np.array(b['light_night']) * w1
        gain = (0.42 + 0.58 * w1) * (1 + 0.3 * w2) * b['gain']
        c, s_ = math.cos(theta), math.sin(theta)
        for bn in b['bins']:
            if not bn.get('n'):
                continue
            if bn['side'] == 'halo':
                I = max(s_, 0) ** 4 * 1.0 + 0.15
            else:
                L = b['left'] if bn['side'] == 'left' else b['right']
                dirv = -c if bn['side'] == 'left' else c
                if dirv <= 0:
                    continue
                vis = L * dirv
                u = min(bn['d'] / L, 1.0)
                I = (1 - smoothstep(vis - 0.18 * L, vis, bn['d'])) * (0.45 + 0.55 * dirv) * (1 - u) ** b['falloff']
            for k in range(bn['n']):
                e = bn['start'] + k
                P[e] = np.clip(P[e] + light * I * gain, 0, 255)
        # Lampe blitzt auf, wenn der Strahl zur Kamera zeigt
        flash = max(s_, 0) ** 4
        for e in b.get('lamp', []):
            P[e] = np.clip(P[e] + light * flash * 0.6, 0, 255)
        # Laterne und Fenster flackern
        fl = self.meta['flicker']
        f1 = self.flick(t, 9.0, 0.0); f2 = self.flick(t, 4.0, 100.0)
        k_core = 0.86 + 0.22 * f1
        k_halo = 0.70 + 0.42 * f1
        for e in fl['lantern_core']:
            P[e] = np.clip(P[e] * k_core, 0, 255)
        for e in fl['lantern_halo']:
            P[e] = np.clip(P[e] * k_halo, 0, 255)
        for e in fl['window']:
            P[e] = np.clip(P[e] * (0.94 + 0.08 * f2), 0, 255)
        return np.round(P).astype(np.uint8)

    def frame(self, t):
        return self.palette(t)[self.idx]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--at', default='0,0.9,1.8,2.7,3.6,4.5,5.2,6.0')
    ap.add_argument('--gif')
    ap.add_argument('--zoom', type=int, default=2)
    ap.add_argument('--crop')
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    eng = Engine()
    ts = [float(x) for x in a.at.split(',')]
    frames = [Image.fromarray(eng.frame(t)) for t in ts]
    if a.crop:
        box = tuple(int(v) for v in a.crop.split(','))
        frames = [f.crop(box) for f in frames]
    w, h = frames[0].size
    cols = 2
    sheet = Image.new('RGB', (w * cols, h * ((len(frames) + cols - 1) // cols)))
    for i, f in enumerate(frames):
        sheet.paste(f, ((i % cols) * w, (i // cols) * h))
    sheet.resize((sheet.width * a.zoom, sheet.height * a.zoom), Image.NEAREST).save(out / 'sim_sheet.png')
    if a.gif:
        t0, t1 = (float(v) for v in a.gif.split(':'))
        gf = []
        for i in range(int((t1 - t0) * 30)):
            im = Image.fromarray(eng.frame(t0 + i / 30))
            if a.crop:
                im = im.crop(box)
            gf.append(im.resize((im.width * a.zoom, im.height * a.zoom), Image.NEAREST))
        gf[0].save(out / 'sim.gif', save_all=True, append_images=gf[1:], duration=33, loop=0)
        # Einzelbilder für genaue Prüfung
        for i in (0, 1, 2, 3):
            gf[i].save(out / f'sim_f{i}.png')


if __name__ == '__main__':
    main()
