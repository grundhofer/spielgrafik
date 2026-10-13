#!/usr/bin/env python3
"""N64-Texturen per Code bauen (ohne KI-Bilder).

    .venv/bin/python styles/n64/scripts/build_textures.py

Jede Kachel entsteht in vierfacher Größe (128×128) aus periodischem Rauschen, Voronoi-Zellen und
Reihenmustern auf einem Torus (dadurch nahtlos), wird dann mit einem Boxfilter auf 32×32 verkleinert
(weiche Kanten wie bei gemalten und verkleinerten Texturen der Zeit), im linearen Licht auf die
glTF-Materialfarbe aus shared/3d/harbor_notes.md abgeglichen (Szenenpalette bleibt vergleichbar) und
auf 5 Bit je Kanal gerundet (Format RGBA16 wie im 4-KB-Texturspeicher der Konsole: 32×32×2 Byte = 2 KB,
mit Mipmaps 2,7 KB).

Ausgaben (assets/textures/ und Kopie in demo/textures/):
  paving, stone, stonedark, wood, wooddark, roof, whitepaint, redpaint, rope, metal, rock, sand, grass,
  water, barrel, crate         32×32 Materialtexturen
  smoke, glow, shadow           32×32 Effekte (mit Alpha)
  clouds                        128×32 Wolkenband für den Himmel (mit Alpha)
  stars                         256×128 Sterne für den Himmel
  textures_sheet.png            Übersicht (8-fach vergrößert, 2×2 gekachelt) zum Ansehen
"""
import pathlib
import shutil

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
OUT = HERE / "assets" / "textures"
DEMO = HERE / "demo" / "textures"
S = 128          # Arbeitsgröße
T = 32           # Zielgröße


# --- Farbe ------------------------------------------------------------------------------------------------
def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64) / 255.0


def srgb_to_lin(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def rgb555(img8, alpha_levels=2):
    """Kanäle auf 5 Bit runden (Vielfache von 255/31). Alpha: 2 Stufen wie RGBA5551, für Effekte 16 Stufen
    (4 Bit wie im IA8-Format der Konsole)."""
    a = img8.astype(np.float64)
    a[..., :3] = np.round(np.round(a[..., :3] * 31 / 255) * 255 / 31)
    if a.shape[-1] == 4:
        k = alpha_levels - 1
        a[..., 3] = np.round(np.round(a[..., 3] / 255 * k) * 255 / k)
    return a.astype(np.uint8)


# --- periodische Grundbausteine ---------------------------------------------------------------------------
def value_noise(n, cells, rng, smooth=True):
    """Periodisches Wertrauschen n×n mit cells×cells Stützstellen (kosinusinterpoliert)."""
    g = rng.random((cells, cells))
    x = np.arange(n) * cells / n
    i0 = np.floor(x).astype(int)
    f = x - i0
    if smooth:
        f = (1 - np.cos(f * np.pi)) / 2
    i1 = (i0 + 1) % cells
    i0 %= cells
    a = g[i0][:, i0] * (1 - f)[None, :] + g[i0][:, i1] * f[None, :]
    b = g[i1][:, i0] * (1 - f)[None, :] + g[i1][:, i1] * f[None, :]
    return a * (1 - f)[:, None] + b * f[:, None]


def fbm(n, base, octaves, rng, gain=0.5):
    out = np.zeros((n, n))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        out += amp * value_noise(n, base * 2 ** o, rng)
        tot += amp
        amp *= gain
    return out / tot


def voronoi(n, grid, rng, jitter=0.8, stretch=(1.0, 1.0)):
    """Periodische Voronoi-Zellen aus einem gejitterten grid=(gx, gy)-Raster.
    Gibt (Zellindex, Abstand zur nächsten Kante in Pixeln) zurück. stretch dehnt den Abstand (sx, sy)."""
    gx, gy = grid
    pts = []
    for j in range(gy):
        for i in range(gx):
            pts.append(((i + 0.5 + jitter * (rng.random() - 0.5)) * n / gx,
                        (j + 0.5 + jitter * (rng.random() - 0.5)) * n / gy))
    pts = np.array(pts)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    d = []
    for px, py in pts:
        dx = np.abs(xx - px)
        dx = np.minimum(dx, n - dx) * stretch[0]
        dy = np.abs(yy - py)
        dy = np.minimum(dy, n - dy) * stretch[1]
        d.append(np.hypot(dx, dy))
    d = np.stack(d)
    order = np.argsort(d, axis=0)
    d1 = np.take_along_axis(d, order[:1], 0)[0]
    d2 = np.take_along_axis(d, order[1:2], 0)[0]
    return order[0], (d2 - d1) / 2


def shade_relief(h, light=(-1.0, -1.0), k=1.0):
    """Licht von oben links aus einem Höhenfeld (periodische Ableitung)."""
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / 2
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / 2
    lx, ly = light
    return np.clip(1.0 + k * (gx * lx + gy * ly), 0.3, 1.8)


def finish(rgb_lin, target_hex=None, alpha=None, size=T, keep_mean=False, alpha_levels=16):
    """Linear-RGB-Arbeitsbild (S×S×3) -> verkleinert, abgeglichen, 5 Bit, uint8."""
    img = rgb_lin
    if target_hex is not None and not keep_mean:
        tgt = srgb_to_lin(hexrgb(target_hex))
        mean = img.reshape(-1, 3).mean(0)
        img = img * (tgt / np.maximum(mean, 1e-6))
    f = img.shape[0] // size
    small = img.reshape(size, f, size, f, 3).mean(axis=(1, 3))            # Boxfilter im linearen Licht
    out = (lin_to_srgb(small) * 255 + 0.5).astype(np.uint8)
    if alpha is not None:
        a = alpha.reshape(size, f, size, f).mean(axis=(1, 3))
        out = np.dstack([out, (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)])
    return rgb555(out, alpha_levels)


# --- Materialtexturen --------------------------------------------------------------------------------------
def paving(rng):
    """Unregelmäßige Pflastersteine (3×3 Zellen je Kachel; main.gd legt eine Kachel auf 2,4 m, Steine also etwa
    0,8 m, ein Texel 7,5 cm, damit die Weichzeichnung des Texturfilters im Vordergrund sichtbar wird), dunkle
    Fugen, Licht von oben links.
    Jeder Stein bekommt einen Ton aus einer kleinen Palette (Sandstein, Ocker, Blaugrau, Rötlich), wie bei
    gemalten Texturen der Zeit; der Mittelwert wird auf einen etwas wärmeren Ton als Stone abgeglichen."""
    cid, edge = voronoi(S, (3, 3), rng, jitter=0.7)
    nc = cid.max() + 1
    pal = np.array([[1.10, 1.0, 0.84], [1.16, 1.0, 0.74], [0.9, 0.96, 1.1], [1.1, 0.94, 0.9], [1.0, 1.0, 0.95]])
    hue = pal[rng.integers(0, len(pal), nc)]
    ntone = 0.8 + 0.4 * rng.random(nc)
    grain = fbm(S, 8, 3, rng)
    h = np.clip(edge / 6.0, 0, 1) ** 0.6 + 0.15 * grain
    rel = shade_relief(h * 6.0, k=0.35)
    col = (ntone[cid] * (0.85 + 0.3 * grain) * rel)[..., None] * hue[cid]
    mortar = np.clip((edge - 1.2) / 2.0, 0, 1)[..., None]
    col = col * mortar + 0.3 * (1 - mortar) * np.array([0.95, 0.85, 0.75])
    return finish(col, "958977")


def stone(rng):
    """Bruchsteinmauer: liegende Steine (Voronoi gedehnt), helle Kalkfugen, Steine warm- und kaltgrau."""
    cid, edge = voronoi(S, (3, 5), rng, jitter=0.6, stretch=(0.75, 1.25))
    nc = cid.max() + 1
    tone = 0.7 + 0.55 * rng.random(nc)
    warm = rng.random(nc) * 0.2 - 0.1
    grain = fbm(S, 8, 3, rng)
    h = np.clip(edge / 5.0, 0, 1) ** 0.5
    rel = shade_relief(h * 7.0 + grain * 2, k=0.3)
    col = np.stack([tone[cid] * (1 + warm[cid]), tone[cid], tone[cid] * (1 - warm[cid])], -1)
    col *= (0.85 + 0.3 * grain)[..., None] * rel[..., None]
    mortar = np.clip((edge - 1.0) / 1.8, 0, 1)[..., None]
    col = col * mortar + 1.35 * (1 - mortar) * np.array([1.0, 0.97, 0.9])
    return finish(col, "8C877D")


def stonedark(rng):
    """Behauene Quader in Lagen (2 Reihen × 2 Steine, versetzt), dunkle Fugen, gemeißelte Körnung."""
    yy, xx = np.mgrid[0:S, 0:S]
    row = yy // (S // 2)
    off = np.where(row % 2 == 0, 0, S // 4)
    bx = ((xx + off) % S) // (S // 2)
    bid = row * 2 + bx
    lx = ((xx + off) % (S // 2))
    ly = yy % (S // 2)
    edge = np.minimum(np.minimum(lx, S // 2 - 1 - lx), np.minimum(ly, S // 2 - 1 - ly)).astype(np.float64)
    tone = 0.75 + 0.5 * rng.random(4)
    grain = fbm(S, 16, 3, rng)
    h = np.clip(edge / 5.0, 0, 1) ** 0.5
    rel = shade_relief(h * 6.0, k=0.35)
    col = (tone[bid] * (0.8 + 0.4 * grain) * rel)[..., None] * np.array([1.0, 0.97, 0.93])
    mortar = np.clip((edge - 0.8) / 1.6, 0, 1)[..., None]
    col = col * mortar + 0.35 * (1 - mortar)
    return finish(col, "5A5650")


def planks(rng, target, n=4, gap_dark=0.35):
    """Bretter entlang u (n je Kachel = 1 m), Maserung als gedehntes Rauschen, Astlöcher, dunkle Fugen."""
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float64)
    pw = S / n
    pid = (yy // pw).astype(int)
    ly = yy - pid * pw
    tone = 0.75 + 0.5 * rng.random(n)
    shift = rng.random(n) * S
    gr = np.zeros((S, S))
    for k in range(n):
        g = value_noise(S, 4, rng)                           # langsame Welle der Maserung
        line = np.sin((yy + 6 * g + 3 * fbm(S, 8, 2, rng)) * 1.9) * 0.5 + 0.5
        gr = np.where(pid == k, line, gr)
    streak = fbm(S, 16, 2, rng)
    streak = np.roll(streak, 0, 1)
    col = tone[pid] * (0.78 + 0.22 * gr) * (0.85 + 0.3 * streak)
    # Astlöcher
    for _ in range(2):
        cx, cy = rng.random() * S, (rng.integers(n) + 0.5) * pw
        dx = np.minimum(np.abs(xx - cx), S - np.abs(xx - cx)) / 2.2
        dy = np.abs(yy - cy)
        r = np.hypot(dx, dy)
        col *= 1 - 0.45 * np.exp(-(r / 2.2) ** 2)
    edge = np.minimum(ly, pw - 1 - ly)
    rel = np.where(ly < 2.5, 1.18, 1.0) * np.where(pw - 1 - ly < 2.5, 0.8, 1.0)
    col = col * rel
    gap = np.clip((edge - 0.5) / 1.2, 0, 1)
    col = col * gap + gap_dark * (1 - gap)
    # Brettenden (je Brett ein Stoß an anderer Stelle)
    for k in range(n):
        x0 = int(shift[k])
        m = (pid == k) & (np.minimum(np.abs(xx - x0), S - np.abs(xx - x0)) < 1.2)
        col = np.where(m, col * 0.45, col)
    return finish(col[..., None] * np.array([1.0, 0.92, 0.85]), target)


def roof(rng):
    """Schieferplatten in versetzten Reihen (4 Reihen je Kachel), Schatten unter jeder Reihe."""
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float64)
    rh = S / 4
    row = (yy // rh).astype(int)
    off = np.where(row % 2 == 0, 0, S / 6)
    tw = S / 3
    col_i = ((xx + off) % S // tw).astype(int)
    tid = row * 3 + col_i
    tone = 0.75 + 0.5 * rng.random(12)
    ly = yy - row * rh
    lx = (xx + off) % tw
    grain = fbm(S, 16, 2, rng)
    shade = 0.75 + 0.45 * (ly / rh)                        # unten heller (Kante), oben im Schatten der Reihe darüber
    col = tone[tid] * shade * (0.85 + 0.3 * grain)
    gap = np.clip((np.minimum(lx, tw - 1 - lx) - 0.4) / 1.0, 0, 1)
    col = col * gap + 0.3 * (1 - gap)
    col = np.where(ly < 1.5, 0.35, col)
    return finish(col[..., None] * np.array([0.95, 1.0, 1.1]), "4A5361")


def paint(rng, target, streak_amp=0.12):
    """Gestrichene Fläche: senkrechte Pinselspuren, leichte Flecken (Farbe, Putz)."""
    st = value_noise(S, 32, rng)
    st = np.repeat(st[:1, :], S, 0) * 0.6 + value_noise(S, 4, rng) * 0.4
    blot = fbm(S, 4, 3, rng)
    col = 1.0 + streak_amp * (st - 0.5) * 2 + 0.1 * (blot - 0.5)
    return finish(np.repeat(col[..., None], 3, -1), target)


def rope(rng):
    """Drei Litzen schräg (Kachel 0,25 m), helle Kuppen, dunkle Rillen."""
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float64)
    ph = (xx + yy) / S * 2 * np.pi * 3
    ridge = (np.sin(ph) * 0.5 + 0.5) ** 0.7
    fib = fbm(S, 32, 2, rng)
    col = 0.45 + 0.75 * ridge * (0.85 + 0.3 * fib)
    return finish(np.repeat(col[..., None], 3, -1), "BFA77A")


def metal(rng):
    """Dunkles Eisen mit Rostflecken und Hammerschlag."""
    n = fbm(S, 8, 4, rng)
    rust = np.clip((fbm(S, 4, 3, rng) - 0.55) * 4, 0, 1)
    base = 0.85 + 0.35 * n
    col = np.stack([base, base, base * 1.05], -1)
    col = col * (1 - rust[..., None]) + rust[..., None] * np.array([1.6, 0.9, 0.55]) * base[..., None]
    return finish(col, "3C3D40")


def rock(rng):
    """Fels: gebänderte Schichten, Risse (Voronoi-Kanten), Relief von oben links (Kachel 3 m)."""
    n = fbm(S, 4, 5, rng)
    yy = np.mgrid[0:S, 0:S][0]
    strata = np.sin((yy / S * 2 * np.pi * 4) + 4 * n) * 0.5 + 0.5
    cid, edge = voronoi(S, (4, 4), rng, jitter=0.9)
    crack = np.clip(edge / 2.5, 0, 1) ** 0.5
    h = n * 4 + strata * 1.0 + crack * 2.0
    rel = shade_relief(h * 3, k=0.35)
    tone = (0.75 + 0.5 * rng.random(cid.max() + 1))[cid]
    col = (0.7 + 0.35 * strata) * (0.8 + 0.4 * n) * tone * rel * (0.55 + 0.45 * crack)
    return finish(col[..., None] * np.array([1.03, 1.0, 0.95]), "6E6A64")


def sand(rng):
    n = fbm(S, 8, 3, rng)
    speck = rng.random((S, S))
    yy = np.mgrid[0:S, 0:S][0]
    rip = np.sin(yy / S * 2 * np.pi * 6 + 3 * n) * 0.5 + 0.5
    col = 0.85 + 0.2 * n + 0.12 * rip + np.where(speck > 0.97, 0.35, 0) - np.where(speck < 0.03, 0.3, 0)
    return finish(np.repeat(col[..., None], 3, -1), "C9B48A")


def grass(rng):
    """Gras: fleckig, dunkle Halmstriche (kurze senkrechte Striche), hellere Spitzen (Kachel 2,5 m)."""
    n = fbm(S, 4, 4, rng)
    col = 0.75 + 0.5 * n
    yy, xx = np.mgrid[0:S, 0:S]
    blades = np.zeros((S, S))
    for _ in range(260):
        x, y, L = rng.integers(S), rng.integers(S), rng.integers(5, 12)
        lean = rng.random() * 2 - 1
        for k in range(L):
            blades[(y - k) % S, int(x + lean * k * 0.3) % S] += 1.0 - k / L
    blades = np.clip(blades, 0, 1)
    col = col * (1 - 0.35 * blades)
    tips = np.roll(blades, 1, 0) - blades
    col = col + 0.18 * np.clip(tips, 0, 1)
    rgb = col[..., None] * np.array([0.9, 1.0, 0.85])
    yel = np.clip((fbm(S, 8, 2, rng) - 0.6) * 3, 0, 1)
    rgb = rgb * (1 - 0.3 * yel[..., None]) + 0.3 * yel[..., None] * np.array([1.4, 1.25, 0.6])
    return finish(rgb, "6E8048")


def water(rng):
    """Wasser: Zellkanten als helle Kräuselkämme auf blaugrünem Grund (Kachel 3 m)."""
    cid, edge = voronoi(S, (4, 4), rng, jitter=0.9)
    crest = np.exp(-(edge / 2.2) ** 2)
    n = fbm(S, 4, 3, rng)
    col = 0.75 + 0.35 * n
    rgb = col[..., None] * np.array([0.9, 1.0, 1.05]) + crest[..., None] * np.array([0.9, 1.1, 1.15]) * 0.9
    return finish(rgb, "2B5A6B")


def barrel(rng):
    """Fass: 5 Dauben je Kachel (2 Kacheln einmal herum), Maserung senkrecht, Reifen bei v 0,12–0,19 und
    0,79–0,86 (v = 0 unten; Bild oben = v 1)."""
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float64)
    sw = S / 5
    sid = (xx // sw).astype(int)
    lx = xx - sid * sw
    tone = 0.8 + 0.4 * rng.random(5)
    gr = fbm(S, 8, 2, rng).T
    col = tone[sid] * (0.8 + 0.3 * np.sin(xx * 1.7 + 5 * gr) * 0.5 + 0.15)
    col = col * np.where(lx < 1.5, 0.55, 1.0) * np.where(lx > sw - 2.5, 1.12, 1.0)
    rgb = col[..., None] * np.array([1.0, 0.9, 0.82])
    v = 1.0 - (yy + 0.5) / S
    hoop = ((v > 0.12) & (v < 0.19)) | ((v > 0.79) & (v < 0.86))
    hl = ((np.abs(v - 0.185) < 0.012) | (np.abs(v - 0.855) < 0.012))
    iron = srgb_to_lin(hexrgb("3C3D40")) / srgb_to_lin(hexrgb("8E6440")) * 0.9
    rgb = np.where(hoop[..., None], rgb * 0 + iron * (0.9 + 0.3 * fbm(S, 16, 2, rng))[..., None], rgb)
    rgb = np.where(hl[..., None], rgb * 1.8, rgb)
    return finish(rgb, "8E6440", keep_mean=False)


def crate(rng):
    """Kiste: dunkler Rahmen (4/32 der Seite), helle Bretter innen, diagonale Strebe (die klassische Kiste)."""
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float64)
    fw = S * 4 / 32
    frame = (xx < fw) | (xx >= S - fw) | (yy < fw) | (yy >= S - fw)
    d = np.abs(xx - yy) / np.sqrt(2)
    brace = (d < fw * 0.75) & ~frame
    inner = planks(np.random.default_rng(rng.integers(1 << 30)), "8E6440", n=4).astype(np.float64)
    inner_lin = srgb_to_lin(np.asarray(Image.fromarray(inner[..., :3].astype(np.uint8)).resize((S, S), Image.BILINEAR)) / 255.0)
    dark = srgb_to_lin(hexrgb("4E3726")) * (0.85 + 0.3 * fbm(S, 16, 2, rng))[..., None]
    rgb = np.where((frame | brace)[..., None], dark, inner_lin)
    # Kanten von Rahmen und Strebe: helle Oberkante, dunkle Unterkante
    fe = (np.abs(xx - fw) < 1.5) | (np.abs(yy - fw) < 1.5)
    rgb = np.where((fe & ~frame)[..., None], rgb * 0.55, rgb)
    be = (np.abs(d - fw * 0.75) < 1.2) & ~frame
    rgb = np.where(be[..., None], rgb * 0.6, rgb)
    ol = (xx < 1.5) | (yy < 1.5)
    rgb = np.where(ol[..., None], rgb * 1.35, rgb)
    nails = np.zeros((S, S), bool)
    for cx, cy in ((fw / 2, fw / 2), (S - fw / 2, fw / 2), (fw / 2, S - fw / 2), (S - fw / 2, S - fw / 2)):
        nails |= np.hypot(xx - cx, yy - cy) < 2.2
    rgb = np.where(nails[..., None], srgb_to_lin(hexrgb("9A9A9A")), rgb)
    return finish(rgb, None)


# --- Effekte -----------------------------------------------------------------------------------------------
def radial(n):
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    return np.hypot(xx - (n - 1) / 2, yy - (n - 1) / 2) / (n / 2)


def smoke(rng):
    """Rauchwolke: weiche, unregelmäßige Kugel, oben heller (Licht von oben)."""
    r = radial(S)
    n = fbm(S, 4, 3, rng)
    a = np.clip(1.0 - (r + 0.35 * (n - 0.5)) ** 2 * 1.25, 0, 1) ** 1.2
    yy = np.mgrid[0:S, 0:S][0] / S
    lum = 0.75 + 0.35 * (1 - yy) + 0.15 * n
    rgb = srgb_to_lin(np.clip(lum[..., None] * np.array([0.82, 0.8, 0.84]), 0, 1))
    return finish(rgb, None, alpha=a, keep_mean=True)


def glow():
    """Lichthof: Helligkeit fällt weich nach außen ab (additiv; Farbe setzt der Shader)."""
    r = radial(S)
    v = np.clip(1 - r, 0, 1) ** 2.2
    rgb = np.repeat(v[..., None], 3, -1)
    out = finish(rgb ** 2.2, None, keep_mean=True)      # finish wandelt nach sRGB; Werte sollen linear bleiben
    return out


def shadow():
    """Rundschatten: weiche Scheibe, Alpha = Deckkraft."""
    r = radial(S)
    a = np.clip((1.0 - r) / 0.35, 0, 1) ** 1.5
    rgb = np.zeros((S, S, 3))
    return finish(rgb, None, alpha=a, keep_mean=True)


def clouds(rng):
    """Wolkenband 128×32 (einmal um den Horizont gekachelt): flache Schichtwolken, Unterseite vom
    Abendlicht rosa-orange, Oberseite dunkel violett. Arbeitsgröße 512×128."""
    W, H = 512, 128
    # periodisch in x: Rauschen auf W×W erzeugen und Streifen ausschneiden
    n = np.zeros((W, W))
    for o, amp in ((4, 1.0), (8, 0.5), (16, 0.25), (32, 0.12)):
        n += amp * value_noise(W, o, rng)
    n /= 1.87
    band = n[:H, :]
    v = (np.arange(H) + 0.5)[:, None] / H              # 0 oben, 1 unten (Horizont)
    # mehrere flache Schichten: Dichte nach Höhe
    layer = np.exp(-((v - 0.72) / 0.13) ** 2) + 0.75 * np.exp(-((v - 0.4) / 0.08) ** 2)
    dens = np.clip((band - 0.42) * 3.2 * layer, 0, 1)
    a = np.clip(dens * 1.6, 0, 1)
    # Beleuchtung: Unterkante (v größer, dichter Rand nach unten) hell
    lit = np.clip(np.roll(dens, -6, 0) - dens * 0.6, 0, 1)
    under = np.clip(1 - np.roll(dens, -10, 0), 0, 1)
    top = srgb_to_lin(hexrgb("4A3A66"))
    mid = srgb_to_lin(hexrgb("8A5A86"))
    rim = srgb_to_lin(hexrgb("F2A07A"))
    rgb = top[None, None] * (1 - under[..., None]) + mid[None, None] * under[..., None]
    rgb = rgb * (1 - lit[..., None]) + rim[None, None] * lit[..., None]
    f = 4
    small = rgb.reshape(H // f, f, W // f, f, 3).mean(axis=(1, 3))
    sa = a.reshape(H // f, f, W // f, f).mean(axis=(1, 3))
    out = np.dstack([(lin_to_srgb(small) * 255 + 0.5).astype(np.uint8), (sa * 255 + 0.5).astype(np.uint8)])
    o = out.astype(np.float64)
    o[..., :3] = np.round(np.round(o[..., :3] * 31 / 255) * 255 / 31)
    o[..., 3] = np.round(o[..., 3] / 255 * 7) * 255 / 7          # Alpha in 8 Stufen (wie IA-Formate)
    return o.astype(np.uint8)


def stars(rng):
    """256×128 Sterne (oberer Himmel, zweimal um den Horizont), einzelne Texel in drei Helligkeiten;
    Alpha = Helligkeit."""
    W, H = 256, 128
    img = np.zeros((H, W, 4), np.uint8)
    for _ in range(90):
        x, y = rng.integers(W), rng.integers(H)
        b = rng.choice([150, 200, 255])
        img[y, x] = (255, 248, 230, b)
    return img


# --- Ablauf ------------------------------------------------------------------------------------------------
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    DEMO.mkdir(parents=True, exist_ok=True)
    seed = 20261011
    rng = lambda k: np.random.default_rng(seed + k)
    tex = {
        "paving": paving(rng(1)),
        "stone": stone(rng(2)),
        "stonedark": stonedark(rng(3)),
        "wood": planks(rng(4), "8E6440"),
        "wooddark": planks(rng(5), "4E3726"),
        "roof": roof(rng(6)),
        "whitepaint": paint(rng(7), "E8E4DA", 0.06),
        "redpaint": paint(rng(8), "B02A22", 0.1),
        "rope": rope(rng(9)),
        "metal": metal(rng(10)),
        "rock": rock(rng(11)),
        "sand": sand(rng(12)),
        "grass": grass(rng(13)),
        "water": water(rng(14)),
        "barrel": barrel(rng(15)),
        "crate": crate(rng(16)),
        "smoke": smoke(rng(17)),
        "glow": glow(),
        "shadow": shadow(),
        "clouds": clouds(rng(18)),
        "stars": stars(rng(19)),
    }
    for name, arr in tex.items():
        mode = "RGBA" if arr.shape[-1] == 4 else "RGB"
        p = OUT / f"{name}.png"
        Image.fromarray(arr, mode).save(p)
        shutil.copy(p, DEMO / p.name)
    # Übersicht: Materialtexturen 2×2 gekachelt, 4-fach (nearest) vergrößert
    names = [n for n in tex if tex[n].shape[:2] == (T, T)]
    cols = 6
    rows = (len(names) + cols - 1) // cols
    cell = T * 2 * 4
    sheet = Image.new("RGB", (cols * (cell + 8), rows * (cell + 8)), (24, 24, 30))
    for i, n in enumerate(names):
        a = tex[n]
        if a.shape[-1] == 4:
            bg = np.full(a.shape[:2] + (3,), 60, np.float64)
            al = a[..., 3:4] / 255
            a = (a[..., :3] * al + bg * (1 - al)).astype(np.uint8)
        t2 = np.tile(a, (2, 2, 1))
        im = Image.fromarray(t2, "RGB").resize((cell, cell), Image.NEAREST)
        sheet.paste(im, ((i % cols) * (cell + 8) + 4, (i // cols) * (cell + 8) + 4))
    sheet.save(OUT / "textures_sheet.png")
    for n, a in tex.items():
        cnt = len(np.unique(a.reshape(-1, a.shape[-1]), axis=0))
        print(f"{n:11s} {a.shape[1]}×{a.shape[0]} {cnt:4d} Farben  Mittel {a[..., :3].reshape(-1, 3).mean(0).round(0)}")


if __name__ == "__main__":
    main()
