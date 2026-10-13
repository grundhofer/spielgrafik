#!/usr/bin/env python3
"""Prüfskript für snes-16bit: nimmt die Demo in Basisauflösung (256×224) auf und prüft die Hardware-Regeln
von Mode 1 sowie den Gang des Dachses.

    .venv/bin/python styles/snes-16bit/scripts/probe.py [--tmp DIR] [--seconds 6] [--t0 0] [--render-method M]

Prüfungen
  1. Farben: jeder Ausgabepixel liegt auf dem 5-Bit-Raster (BGR555); Farben je Bild ≤ 256.
  2. BG1/BG2 (Daten demo/art/bg1.png, bg2.png): jede 8×8-Kachel nutzt genau eine Palette (1..7), höchstens
     15 Farben + Transparenz; Palette 0 (CGRAM 0..15) bleibt BG3 vorbehalten. Dazu die Zahl verschiedener
     Kacheln (mit Spiegelung) und der VRAM-Bedarf.
  3. BG3 (gerenderte Bilder mit offenem Fenster): je 8×8-Kachel im Fenster nur Farben einer BG3-Palette
     (Füllung, Hell, Dunkel), höchstens 3.
  4. OBJ: jedes Sprite-Bild nutzt nur Farben seiner OBJ-Palette (≤ 15); je Bildzeile ≤ 32 Sprites und
     ≤ 34 8-px-Streifen (aus dem OAM-Protokoll von main.gd, Spritegrößen 8×8 / 32×32).
  5. Dachs (Lauf mit --only=badger, nur der Dachs auf Schwarz): je Bild Kopfoberkante, Bodenkontakt-Läufe in
     Weltkoordinaten; der Standfuß muss über die Bilder eines Schritts ortsfest sein (±1 px).
"""
import argparse, json, os, pathlib, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
STYLE = HERE.parent
DEMO = STYLE / 'demo'
sys.path.insert(0, str(HERE))
from sneslib import on_grid5  # noqa: E402


def render(out, seconds, only='', t0=0.0, method=''):
    """Godot-Lauf mit Movie Maker in Basisauflösung; Protokoll (OAM, HDMA) über --probe."""
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob('f*.png'):
        f.unlink()
    subprocess.run(['godot', '--headless', '--path', str(DEMO), '--import'], capture_output=True)
    n = int(round(seconds * 30))
    cmd = ['godot', '--path', str(DEMO), '--position', '20000,20000', '--write-movie', str(out / 'f.png'),
           '--fixed-fps', '30', '--quit-after', str(n)]
    if method:
        cmd += ['--rendering-method', method]
    cmd += ['--', f'--probe={out / "probe.json"}']
    if only:
        cmd.append(f'--only={only}')
    if t0:
        cmd.append(f'--t0={t0}')
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if 'ERROR' in l]
    if errs:
        print('Godot-Fehler:', errs[:5])
    frames = sorted(out.glob('f*.png'))
    return frames, json.loads((out / 'probe.json').read_text())


def check_bg():
    meta = json.loads((DEMO / 'art/bg.json').read_text())
    res = {}
    vram = 0
    for name in ('bg1', 'bg2'):
        a = np.asarray(Image.open(DEMO / f'art/{name}.png'))
        bad, maxc, uniq = 0, 0, set()
        for ty in range(0, a.shape[0], 8):
            for tx in range(0, a.shape[1], 8):
                t = a[ty:ty + 8, tx:tx + 8].astype(int)
                nz = t[t % 16 != 0]
                pals = set((nz // 16).tolist())
                if len(pals) > 1 or 0 in pals:
                    bad += 1
                maxc = max(maxc, len(set(nz.tolist())))
                c = t % 16
                keys = [c, c[:, ::-1], c[::-1], c[::-1, ::-1]]
                uniq.add(min(k.tobytes() for k in keys))
        res[name] = {'tiles_bad': bad, 'max_colors_per_tile': maxc, 'unique_tiles': len(uniq),
                     'vram_bytes': len(uniq) * 32}
        vram += len(uniq) * 32
    res['vram_bg_tiles_bytes'] = vram
    res['cgram_bg_entries'] = sum(1 for h in meta['cgram'] if h != '000000')
    return res


def check_obj(log):
    spr = json.loads((DEMO / 'art/sprites.json').read_text())
    atlas = np.asarray(Image.open(DEMO / 'art/sprites.png').convert('RGBA'))
    pals = {int(k): {tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) for h in v} for k, v in spr['obj_palettes'].items()}
    out = {'palette_sizes': {k: len(v) for k, v in pals.items()}, 'foreign_colors': 0}
    # Sprite-Bilder gegen ihre Palette (Dachs/Paket 0, Rauch 1, Möwe 2)
    groups = [(spr['frames'].values(), 0)]
    sm = spr['small']
    groups += [([v for k, v in sm.items() if k.startswith('smoke')], 1), ([v for k, v in sm.items() if k.startswith('gull')], 2),
               ([sm['parcel']], 0)]
    for rects, p in groups:
        for x, y, w, h in rects:
            sub = atlas[y:y + h, x:x + w]
            cols = {tuple(c) for c in sub[sub[..., 3] > 0][:, :3].tolist()}
            out['foreign_colors'] += len(cols - pals[p])
    # Sprites je Zeile: Dachs = ein 32×32-OBJ, alles andere 8×8-OBJs (Paket: zwei)
    max_spr, max_sl = 0, 0
    for fr in log:
        lines = np.zeros(224, int)
        slivers = np.zeros(224, int)
        for x, y, w, h, p, name in fr['oam']:
            if w == 32:
                objs = [(x, y, 32)]
            else:
                objs = [(x + 8 * i, y, 8) for i in range((w + 7) // 8)]
            for ox, oy, s in objs:
                if ox + s <= 0 or ox >= 256:
                    continue
                y0, y1 = max(0, oy), min(224, oy + s)
                lines[y0:y1] += 1
                slivers[y0:y1] += s // 8
        max_spr = max(max_spr, int(lines.max()))
        max_sl = max(max_sl, int(slivers.max()))
    out['max_sprites_per_line'] = max_spr
    out['max_slivers_per_line'] = max_sl
    out['max_oam_entries'] = max(sum((w + 7) // 8 if w != 32 else 1 for x, y, w, h, p, n in fr['oam']) for fr in log)
    return out


def check_frames(frames, log):
    bad5, maxcol = 0, 0
    bg3_bad = 0
    from bg3_spec import BOX, TITLE, bg3_palettes
    pals = bg3_palettes()
    for i, f in enumerate(frames):
        a = np.asarray(Image.open(f).convert('RGB'))
        bad5 += int((~on_grid5(a)).sum())
        maxcol = max(maxcol, len(np.unique(a.reshape(-1, 3), axis=0)))
        t = log[i]['t'] if i < len(log) else 0
        rects = []
        if t >= 0.4:
            rects.append(TITLE)
        if t >= 3.4:
            rects.append(BOX)
        for x0, y0, w, h in rects:
            for ty in range(y0, y0 + h, 8):
                for tx in range(x0, x0 + w, 8):
                    t8 = a[ty:ty + 8, tx:tx + 8].reshape(-1, 3)
                    m = np.ones(64, bool)
                    # durchsichtige Eckpixel ausnehmen (Szene scheint durch)
                    for (cx, cy) in [(0, 0), (1, 0), (0, 1)]:
                        for X, Y in [(x0 + cx, y0 + cy), (x0 + w - 1 - cx, y0 + cy), (x0 + cx, y0 + h - 1 - cy), (x0 + w - 1 - cx, y0 + h - 1 - cy)]:
                            if tx <= X < tx + 8 and ty <= Y < ty + 8:
                                m[(Y - ty) * 8 + (X - tx)] = False
                    cols = {tuple(c) for c in t8[m].tolist()}
                    if len(cols) > 3 or not any(cols <= p for p in pals):
                        bg3_bad += 1
    return {'pixels_off_5bit_grid': bad5, 'max_colors_per_frame': maxcol, 'bg3_tiles_bad': bg3_bad}


def vram(frames, bg):
    """VRAM-Schätzung (64 KB): BG1/BG2-Kacheln (4bpp, 32 B), BG3-Kacheln des offenen Fensters (2bpp, 16 B,
    gezählt im letzten Bild), alle OBJ-Kacheln des Sprite-Atlas (4bpp, 8×8, 32 B), drei Kachelkarten à 2 KB."""
    from bg3_spec import BOX, TITLE
    a = np.asarray(Image.open(frames[-1]).convert('RGB'))
    uniq = set()
    for x0, y0, w, h in (BOX, TITLE):
        for ty in range(y0, y0 + h, 8):
            for tx in range(x0, x0 + w, 8):
                uniq.add(a[ty:ty + 8, tx:tx + 8].tobytes())
    at = np.asarray(Image.open(DEMO / 'art/sprites.png').convert('RGBA'))
    objt = set()
    for ty in range(0, at.shape[0], 8):
        for tx in range(0, at.shape[1], 8):
            t = at[ty:ty + 8, tx:tx + 8]
            if t[..., 3].any():
                objt.add(t.tobytes())
    out = {'bg12_tiles': bg['vram_bg_tiles_bytes'], 'bg3_tiles': len(uniq) * 16, 'obj_tiles': len(objt) * 32,
           'tilemaps': 3 * 2048}
    out['total_bytes'] = sum(out.values())
    return out


def feet(frames, log):
    """Dachs allein auf Schwarz: Kopfoberkante und Bodenkontakt (Zeile über der Sohle) in Weltkoordinaten."""
    rows = []
    for i, f in enumerate(frames):
        a = np.asarray(Image.open(f).convert('RGB')).astype(int)
        op = a.sum(-1) > 0
        ys, xs = np.nonzero(op)
        if not len(ys):
            continue
        bottom = ys.max()
        ground = 148                                # Sohlenzeile (Kai): nur aufgesetzte Füße haben hier Pixel
        g = np.flatnonzero(op[ground])
        runs = np.split(g, np.flatnonzero(np.diff(g) > 1) + 1)
        runs = [(int(r[0]), int(r[-1])) for r in runs if len(r)]
        top = int(ys.min())
        name = log[i]['oam'][0][5] if i < len(log) else ''
        rows.append({'frame': i, 't': round(log[i]['t'], 3), 'img': name, 'top': top, 'bottom': int(bottom), 'ground_runs': runs})
    return rows


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tmp', default=os.path.join(tempfile.gettempdir(), 'snes-16bit'))
    ap.add_argument('--seconds', type=float, default=6.0)
    ap.add_argument('--render-method', default='')
    ap.add_argument('--skip-feet', action='store_true')
    ap.add_argument('--t0', type=float, default=0.0)
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    res = {'bg': check_bg()}
    frames, log = render(tmp / ('full' + (a.render_method or '') + (f'_t{a.t0:g}' if a.t0 else '')), a.seconds,
                         t0=a.t0, method=a.render_method)
    res['obj'] = check_obj(log)
    res['frames'] = check_frames(frames, log)
    res['frames']['count'] = len(frames)
    res['vram'] = vram(frames, res['bg'])
    print(json.dumps(res, indent=1))
    if not a.skip_feet:
        frames, log = render(tmp / 'badger', a.seconds, only='badger')
        rows = feet(frames, log)
        (tmp / 'feet.json').write_text(json.dumps(rows, indent=1))
        last = None
        for r in rows:
            if r['img'] != last or r['frame'] % 2 == 0:
                print(r['frame'], r['t'], r['img'], 'Kopf', r['top'], 'Sohle', r['bottom'], 'Boden', r['ground_runs'])
            last = r['img']
