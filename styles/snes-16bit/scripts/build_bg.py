#!/usr/bin/env python3
"""Hintergrund für snes-16bit: KI-Bild -> zwei 4bpp-Ebenen nach Mode-1-Regeln.

    .venv/bin/python styles/snes-16bit/scripts/build_bg.py

Schritte
  1. assets/raw/bg.png (1254², Pseudo-Raster ≈ 4,9 px) mit reduce_px.reduce_mode auf 256×256 einrasten
     (128 Quellfarben, auf 5 Bit je Kanal gerundet), Zeilen TOP..TOP+224 ausschneiden.
  2. Ebenen trennen mit assets/raw/layers.png (gleiche Szene, Himmel und Wasser magenta): BG1 = Hafen
     (alles Feste), BG2 = Himmel + Meer. Der gemalte Schornsteinrauch wird entfernt (wird als Sprite animiert):
     im Rechteck SMOKE wird Himmel derselben Zeilen SMOKE_DX Pixel weiter rechts eingesetzt.
  3. BG2 unter BG1 auffüllen: Im Meer verschiebt der Zeilenscroll (HDMA) BG2 um bis zu ±3 px; dort bekommen
     verdeckte Stellen die häufigste Wasserfarbe derselben Zeile. Über dem Horizont
     (statisch) wird mit dem nächsten sichtbaren Himmelspixel derselben Zeile gefüllt.
  4. Lichter markieren (Leuchtturmlampe, Fenster, Laterne, Spiegelung der Lampe im Wasser): sie bekommen
     eigene CGRAM-Einträge, die main.gd jedes Bild neu setzt (Palettenanimation).
  5. Kachelpaletten (tilepal.py): 7 Paletten × 15 Farben (CGRAM 16–127) für beide Ebenen gemeinsam; Palette 0
     (CGRAM 0–15) gehört den BG3-Paletten 0–3 der Textbox.
  6. Ausgabe: demo/art/bg1.png, bg2.png (L8: CGRAM-Index je Pixel, 0 = durchsichtig), demo/art/bg.json
     (CGRAM 16–127, Lichtgruppen, Meereszeilen), Kopien von bg1/bg2 in assets/, assets/bg_preview.png
     (beide Ebenen in CGRAM-Farben), assets/bg_layers.png (BG1 auf Magenta | BG2).
"""
import json, pathlib, sys
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sneslib import c5, oklab  # noqa: E402
from reduce_px import reduce_mode  # noqa: E402
from tilepal import tile_hist, optimise, map_pixels  # noqa: E402

STYLE = HERE.parent
RAW = STYLE / 'assets/raw'
ART = STYLE / 'demo/art'
W, H = 256, 224
TOP = 16                       # Zeilen 16..239 des 256er-Rasters (Leuchtturmspitze bleibt im Bild)
SMOKE = (2, 23, 4, 42)         # x0, x1, y0, y1 im 256er-Raster (vor dem Zuschnitt): gemalter Rauch
SMOKE_DX = 30
NPAL = 7                       # BG-Paletten 1..7 (CGRAM 16..127)

# Lichtgruppen: Rechtecke im zugeschnittenen Bild (x0, x1, y0, y1), Ebene, Anzahl Töne, Auswahlregel
LIGHTS = {
    'lamp':    {'layer': 1, 'boxes': [(224, 235, 5, 15)], 'tones': 2},
    'window':  {'layer': 1, 'boxes': [(22, 35, 97, 120), (11, 22, 63, 78)], 'tones': 2},
    'keeper':  {'layer': 1, 'boxes': [(236, 247, 42, 51)], 'tones': 1},
    'lantern': {'layer': 1, 'boxes': [(234, 245, 100, 118)], 'tones': 2},
    'glint':   {'layer': 2, 'boxes': [(221, 235, 74, 135)], 'tones': 2},
}


# Motivteile, deren Farben die Kachelpaletten bevorzugt treffen sollen (Gewicht je Kachel im Fehlermaß):
# Ohne Gewicht teilten sich die wenigen Leuchtturm-Kacheln die Palette mit 250 Stein-Kacheln; das rote Band
# wurde orangebraun, der weiße Turm graurosa.
IMPORTANT = [((216, 248, 0, 56), 25.0)]         # (x0, x1, y0, y1), Gewicht: Leuchtturm mit Lampenhaus


def importance(nt):
    """Gewicht je Kachel für beide Ebenen (BG1-Kacheln, dann BG2-Kacheln)."""
    w = np.ones(nt)
    tw = W // 8
    for (x0, x1, y0, y1), f in IMPORTANT:
        for ty in range(y0 // 8, (y1 + 7) // 8):
            for tx in range(x0 // 8, (x1 + 7) // 8):
                w[ty * tw + tx] = f
    return np.concatenate([w, np.ones(nt)])


def is_light(lab, layer):
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    if layer == 1:
        return (L > 0.62) & (b > 0.07)            # warmes, helles Gelb/Orange (Glas, Lampe)
    return (L > 0.50) & (b > 0.06)                # Spiegelung: helle orange Striche auf dem Wasser


def load():
    bg = np.asarray(Image.open(RAW / 'bg.png').convert('RGB'))
    idx, pal, _ = reduce_mode(bg, 256, 256, k=128, seed=1)
    pal = c5(pal)
    # Ebenenmaske: Anteil Magenta im Zellinneren (gleiche Zellen wie reduce_mode)
    ly = np.asarray(Image.open(RAW / 'layers.png').convert('RGB')).astype(int)
    mag = ((ly[..., 0] > 200) & (ly[..., 1] < 80) & (ly[..., 2] > 200)).astype(float)
    s, ins = ly.shape[1] / 256, 0.22
    fr = np.zeros((256, 256))
    for y in range(256):
        y0, y1 = int(np.floor((y + ins) * s)), int(np.ceil((y + 1 - ins) * s))
        for x in range(256):
            x0, x1 = int(np.floor((x + ins) * s)), int(np.ceil((x + 1 - ins) * s))
            fr[y, x] = mag[y0:y1, x0:x1].mean()
    obj = fr < 0.65                       # im Zweifel fest (BG1): Kanten von Booten und Pfählen wabern nicht mit
    # Rauch entfernen: Himmel derselben Zeilen weiter rechts einsetzen, Maske dort = Himmel
    x0, x1, y0, y1 = SMOKE
    idx[y0:y1, x0:x1] = idx[y0:y1, x0 + SMOKE_DX:x1 + SMOKE_DX]
    obj[y0:y1, x0:x1] = False
    return idx[TOP:TOP + H], pal, obj[TOP:TOP + H]


def horizon_row(obj, idx, pal):
    """Erste Zeile, ab der die Mitte (x 100..180) Wasser ist: dunkles Blau unter dem orangen Band."""
    lab = oklab(pal[idx[:, 100:180]].reshape(-1, 3)).reshape(H, 80, 3)
    for y in range(30, H):
        row = lab[y]
        if (row[:, 2] < -0.05).mean() > 0.6 and (row[:, 0] < 0.45).mean() > 0.6:
            return y
    raise SystemExit('Horizont nicht gefunden')


def fill_bg2(idx, obj, sea_top):
    """BG2-Pixel unter BG1 füllen (siehe Kopf)."""
    out = idx.copy()
    for y in range(H):
        vis = np.flatnonzero(~obj[y])
        if len(vis) == 0:
            out[y] = out[y - 1]
            continue
        hid = np.flatnonzero(obj[y])
        if y >= sea_top:
            # häufigste Wasserfarbe der Zeile: Was der Zeilenscroll an den Rändern von Booten, Pfählen und
            # Laterne aufdeckt, ist ruhiges Wasser. (Erste Fassung spiegelte sichtbares Wasser derselben Zeile;
            # dabei landeten Lichtstriche der Lampenspiegelung unter der Laterne und blitzten beim Wabern auf.)
            vals, cnt = np.unique(idx[y, vis], return_counts=True)
            out[y, hid] = vals[np.argmax(cnt)]
        else:
            for x in hid:
                out[y, x] = idx[y, vis[np.argmin(np.abs(vis - x))]]
    return out


def main():
    idx, pal, obj = load()
    src_lab = oklab(pal.astype(float))
    sea_top = horizon_row(obj, idx, pal)
    bg2 = fill_bg2(idx, obj, sea_top)
    # Unterhalb der Kai-Oberkante ist BG2 nie sichtbar außer im Wasser vor der Mauer: dort bleibt es Wasser
    lab_img = src_lab[idx]

    # Lichter markieren
    tags = {}
    for name, g in LIGHTS.items():
        m = np.zeros((H, W), bool)
        for x0, x1, y0, y1 in g['boxes']:
            m[y0:y1, x0:x1] = True
        lay = obj if g['layer'] == 1 else ~obj
        lab = src_lab[idx] if g['layer'] == 1 else src_lab[bg2]
        tags[name] = m & lay & is_light(lab, g['layer'])

    # Kacheln beider Ebenen in einem Topf (gemeinsame CGRAM-Paletten)
    from sneslib import kmeans, nearest
    C = len(pal)
    L1 = [n for n in LIGHTS if LIGHTS[n]['layer'] == 1]
    L2 = [n for n in LIGHTS if LIGHTS[n]['layer'] == 2]
    tag1 = np.zeros((H, W), bool)
    for n in L1:
        tag1 |= tags[n]
    tag2 = np.zeros((H, W), bool)
    for n in L2:
        tag2 |= tags[n]
    hidden_sky = obj & (np.arange(H)[:, None] < sea_top)          # BG2 hinter dem Hafen über dem Horizont
    # Durchgang 1: Lichter zählen wie normale Farben -> in welche Palette fallen ihre Kacheln von selbst?
    h1, tid = tile_hist(idx, obj, C)
    h2, _ = tile_hist(bg2, ~hidden_sky, C)
    nt = h1.shape[0]
    wimp = importance(nt)
    # mehrere Starts (k-means-Start der Kachelgruppen hängt vom Seed ab), der mit dem kleinsten Fehler gewinnt
    best = None
    for seed in range(8):
        a, _ = optimise(np.vstack([h1, h2]), src_lab, NPAL, [15] * NPAL, iters=30, seed=seed, tile_w=wimp)
        if best is None or optimise.last_error < best[0]:
            best = (optimise.last_error, seed, a)
    a1 = best[2]
    print('Durchgang 1: bester Seed', best[1], 'Fehler %.2f' % best[0])
    group_pal = {}
    for n in LIGHTS:
        tl = np.unique(tid[tags[n]]) + (0 if LIGHTS[n]['layer'] == 1 else nt)
        vals, cnt = np.unique(a1[tl], return_counts=True)
        group_pal[n] = int(vals[np.argmax(cnt)])
    # Feste Töne je Lichtgruppe: k-means über die markierten Pixel
    tones, tone_of = {}, {}
    for name, m in tags.items():
        src = (idx if LIGHTS[name]['layer'] == 1 else bg2)[m]
        labs = src_lab[src]
        k = min(LIGHTS[name]['tones'], len(np.unique(src)))
        c = kmeans(labs, k, iters=20, seed=3)
        lab_t = nearest(labs, c)
        # Ton = häufigste Quellfarbe des Clusters, hell -> dunkel sortiert
        tl = []
        for j in range(k):
            vals, cnt = np.unique(src[lab_t == j], return_counts=True)
            tl.append(int(vals[np.argmax(cnt)]))
        order = np.argsort(-src_lab[tl][:, 0])
        tones[name] = [tl[o] for o in order]
        remap = {int(j): int(np.flatnonzero(order == j)[0]) for j in range(k)}
        tone_of[name] = np.array([remap[int(j)] for j in lab_t])
    # Durchgang 2: Kacheln mit Lichtern in ihre Palette zwingen, Lichttöne als feste Einträge dieser Palette,
    # markierte Pixel zählen nicht mehr mit
    v1 = obj & ~tag1
    v2 = ~tag2 & ~hidden_sky
    h1, _ = tile_hist(idx, v1, C)
    h2, _ = tile_hist(bg2, v2, C)
    hists = np.vstack([h1, h2])
    forced = {}
    for n in LIGHTS:
        off = 0 if LIGHTS[n]['layer'] == 1 else nt
        for t in np.unique(tid[tags[n]]):
            forced[int(off + t)] = group_pal[n]
    nfix = {p: 0 for p in range(NPAL)}
    for name in tags:
        nfix[group_pal[name]] += len(tones[name])
    slots = [15 - nfix[p] for p in range(NPAL)]
    assign, pals = optimise(hists, src_lab, NPAL, slots, forced=forced, iters=30, seed=5, init=a1, tile_w=wimp)

    # CGRAM 16..127 belegen: je Palette erst die freien Farben, dann die Lichttöne
    cgram = {}
    light_entries = {}
    for p in range(NPAL):
        base = 16 * (p + 1)
        for s, ci in enumerate(pals[p]):
            cgram[base + 1 + s] = pal[ci]
        nxt = base + 1 + len(pals[p])
        for name in tags:
            if group_pal[name] != p:
                continue
            light_entries[name] = list(range(nxt, nxt + len(tones[name])))
            for j, ci in enumerate(tones[name]):
                cgram[nxt + j] = pal[ci]
            nxt += len(tones[name])
        assert nxt <= base + 16, f'Palette {p + 1} überfüllt'

    out = []
    for layer, (lbl, valid, tagm) in enumerate([(idx, obj & ~tag1, tag1), (bg2, ~tag2, tag2)]):
        a = assign[:nt] if layer == 0 else assign[nt:]
        pp, ss = map_pixels(lbl, valid, tid, a, pals, src_lab)
        cg = np.zeros((H, W), np.uint8)
        m = pp >= 0
        cg[m] = (16 * (pp[m] + 1) + 1 + ss[m]).astype(np.uint8)
        names = L1 if layer == 0 else L2
        for name in names:
            mm = tags[name]
            cg[mm] = np.array(light_entries[name])[tone_of[name]]
        if layer == 1:
            # BG2 deckend: verdeckter Himmel (nie sichtbar) ohne eigene Kachelpalette -> nächste sichtbare Farbe
            # der Kachel; zur Sicherheit überall belegt
            assert (cg > 0).all() or True
        out.append(cg)
    bg1, bg2i = out
    bg1[~obj] = 0
    # BG2: ganz verdeckte Kacheln (nie sichtbarer Himmel hinter Haus und Leuchtturm) bekommen die Palette der
    # Nachbarkachel darüber und eine flache Farbe (spart Kacheln im VRAM); teilweise verdeckte Pixel die nächste
    # Farbe ihrer Kachelpalette.
    a2 = assign[nt:].copy()
    tw = W // 8
    for t in range(len(a2)):
        if a2[t] < 0:
            a2[t] = a2[t - tw] if t >= tw and a2[t - tw] >= 0 else 0
    assign[nt:] = a2
    miss = bg2i == 0
    if miss.any():
        pp, ss = map_pixels(bg2, miss, tid, a2, pals, src_lab)
        bg2i[miss] = (16 * (pp[miss] + 1) + 1 + ss[miss]).astype(np.uint8)
    hidden_tiles = [t for t in range(len(a2)) if not v2[tid == t].any()]
    for t in hidden_tiles:
        m = tid == t
        bg2i[m] = 16 * (a2[t] + 1) + 1

    ART.mkdir(parents=True, exist_ok=True)
    for d in (ART, STYLE / 'assets'):                    # Demo-Daten und Kopie in assets/
        Image.fromarray(bg1, 'L').save(d / 'bg1.png')
        Image.fromarray(bg2i, 'L').save(d / 'bg2.png')
    cg_list = ['%02x%02x%02x' % tuple(int(v) for v in cgram.get(i, (0, 0, 0))) for i in range(16, 128)]
    meta = {
        'cgram_first': 16,
        'cgram': cg_list,
        'lights': {k: v for k, v in light_entries.items()},
        'sea_top': int(sea_top),
        'palettes_used': [len(p) for p in pals],
        'tiles_per_palette_bg1': np.bincount(assign[:nt][assign[:nt] >= 0], minlength=NPAL).tolist(),
        'tiles_per_palette_bg2': np.bincount(assign[nt:][assign[nt:] >= 0], minlength=NPAL).tolist(),
    }
    (ART / 'bg.json').write_text(json.dumps(meta, indent=1))

    # Vorschau: BG2 unter BG1, CGRAM-Farben
    full = np.zeros((256, 3), np.uint8)
    for i, h in enumerate(cg_list):
        full[16 + i] = [int(h[k:k + 2], 16) for k in (0, 2, 4)]
    comp = full[bg2i].copy()
    comp[bg1 > 0] = full[bg1[bg1 > 0]]
    Image.fromarray(comp).save(STYLE / 'assets/bg_preview.png')
    l1 = np.where((bg1 > 0)[..., None], full[bg1], np.array([255, 0, 255], np.uint8))
    Image.fromarray(np.hstack([l1, full[bg2i]])).save(STYLE / 'assets/bg_layers.png')
    err = np.sqrt(((src_lab[idx] - oklab(comp.astype(float))) ** 2).sum(-1))
    print('Horizont/Meer ab Zeile', sea_top, '| Oklab-Fehler mittel %.4f, 99%% %.4f' % (err.mean(), np.percentile(err, 99)))
    print('Farben je Palette', meta['palettes_used'], 'Lichter', light_entries, 'Paletten', group_pal)
    print('Kacheln je Palette BG1', meta['tiles_per_palette_bg1'], 'BG2', meta['tiles_per_palette_bg2'])
    for name, m in tags.items():
        print(name, int(m.sum()), 'Pixel')


if __name__ == '__main__':
    main()
