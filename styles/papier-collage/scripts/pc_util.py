"""Gemeinsame Helfer für papier-collage: Magenta-Saum entfernen, Schatten, Speichern."""
import numpy as np
from PIL import Image, ImageFilter


def kill_magenta(rgb, alpha, tol=25, depth=50, blue_over_green=None):
    """Abgedunkelte Reste der Schlüsselfarbe (z. B. zwischen Fellzacken im gemalten Schatten) durchsichtig
    machen: Farbton magenta (R ~ B, G deutlich darunter). Gibt neues Alpha zurück."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mag = (np.abs(r - b) < tol) & (np.minimum(r, b) - g > depth)
    if blue_over_green is not None:   # für Teile ohne Blau/Violett (Figur): Mischung Rot+Magenta usw.
        mag |= (b - g > blue_over_green) & (r > 90)
    return np.where(mag, 0.0, alpha)


def despill_magenta(rgb, alpha, band=6):
    """Magentastich nahe der Freistellkante entfernen.

    Spill = min(R, B) - G (nur positiv); wird von R und B abgezogen. Wirkt nur in einem Band von `band` px
    innerhalb der Kante und auf halbtransparenten Pixeln, damit violette Flächen im Inneren (Himmel) bleiben."""
    a8 = Image.fromarray((alpha > 0.5).astype(np.uint8) * 255)
    inner = np.asarray(a8.filter(ImageFilter.MinFilter(2 * band + 1))) > 0
    zone = (alpha < 0.995) | ~inner
    rgb = rgb.copy()
    spill = np.clip(np.minimum(rgb[..., 0], rgb[..., 2]) - rgb[..., 1], 0, None)
    for ch in (0, 2):
        rgb[..., ch] = np.where(zone, rgb[..., ch] - spill, rgb[..., ch])
    return rgb


def _shift(a, dy, dx):
    """Um (dy, dx) verschieben ohne Umlauf (Rand mit 0)."""
    out = np.zeros_like(a)
    H, W = a.shape[:2]
    out[max(dy, 0):H + min(dy, 0), max(dx, 0):W + min(dx, 0)] = a[max(-dy, 0):H + min(-dy, 0),
                                                                    max(-dx, 0):W + min(-dx, 0)]
    return out


def erode(mask, r):
    return np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(2 * r + 1))) > 0


def dilate(mask, r):
    return np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(2 * r + 1))) > 0


def grow_colors(rgb, known, steps):
    """Farben der bekannten Pixel schrittweise nach außen tragen (Mittel der bekannten 8 Nachbarn).
    Rückgabe: Farbfeld und Abstand in Schritten (99 = nicht erreicht)."""
    col = np.where(known[..., None], rgb, 0.0)
    k = known.copy()
    dist = np.where(known, 0, 99).astype(np.int32)
    for i in range(1, steps + 1):
        kf = k.astype(np.float64)
        s = np.zeros_like(col)
        n = np.zeros(k.shape)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy or dx:
                    s += _shift(col * kf[..., None], dy, dx)
                    n += _shift(kf, dy, dx)
        new = ~k & (n > 0)
        col[new] = s[new] / n[new][:, None]
        k = k | new
        dist[new] = i
    return col, dist


def key_green(rgb, lo=0.12, hi=0.45, inset=2, band=4, keep_hue=False, warm=0.82):
    """Eigene Freistellung aus dem Original (genimg: <name>.keyed-src.png) für Magenta mit gemaltem Schatten.

    genimg entfärbt den Rand, indem es R und B auf G senkt; den vom Modell gemalten, abgedunkelten
    Magenta-Schatten (z. B. 156/4/148) macht das zu deckendem Schwarz. Hier dagegen:
    - Magenta und sein Schatten haben fast kein Grün: G / max(R, B) < lo -> durchsichtig, ab hi deckend (a_r).
    - Sauber: deckend und ohne Magentastich (min(R, B) - G < 8; bei keep_hue nur deckend, für violette Wolken).
      Kern = sauber und `inset` px vom Rand entfernt (JPEG verschmiert Magenta etwa 2 px nach innen).
    - Randzone bis `band` px um den Kern: Farbe des nächsten Kerns; Alpha 1 für saubere Pixel, sonst
      G / G_Kern (Grün stammt nur vom Papier, auch vor dem dunklen Schatten), mindestens a_r.
    - Dünne Teile ohne Kern (Taue, Baumenden): eigene Farbe, Magentastich von R und B abgezogen und, falls warm
      gesetzt, je nach Stärke des Stichs zu warmem Papier hin geschoben (B <= warm * G, R <= 1,4 * G).
    Rückgabe: rgb, Alpha (0..1)."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    gr = g / np.maximum(np.maximum(r, b), 1)
    a_r = np.clip((gr - lo) / (hi - lo), 0, 1)
    spill = np.minimum(r, b) - g
    clean = a_r >= 1
    if not keep_hue:
        clean &= spill < 8
    core = erode(clean, inset)
    core |= erode(clean, 1) & ~dilate(core, band)      # schmale Teile (Mast, 4 px): 1 px eingerückt
    fill, dist = grow_colors(rgb, core, band)
    near = ~core & (dist <= band)
    a_g = np.clip((g - 4) / np.maximum(fill[..., 1] - 4, 12), 0, 1)
    A = np.where(clean, 1.0, np.where(a_r > 0, np.maximum(a_g, a_r), 0.0))
    A = np.where(near | core, A, a_r)
    own = rgb.astype(np.float64).copy()
    if not keep_hue:
        s = np.clip(spill, 0, None)
        own[..., 0] -= s
        own[..., 2] -= s
        if warm is not None:   # zu warmem Papier: B <= warm * G, R <= 1,4 * G (sonst rote Baumenden)
            w = np.clip(spill / 12.0, 0, 1)
            own[..., 2] -= w * np.clip(own[..., 2] - warm * own[..., 1], 0, None)
            own[..., 0] -= w * np.clip(own[..., 0] - 1.4 * own[..., 1], 0, None)
    out = np.where(core[..., None], rgb, np.where(near[..., None], fill, own))
    return np.clip(out, 0, 255), A


def neutralize(rgb):
    """Magentastich überall abziehen (für graues Seidenpapier, durch das das Modell Magenta scheinen ließ)."""
    rgb = rgb.copy()
    s = np.clip(np.minimum(rgb[..., 0], rgb[..., 2]) - rgb[..., 1], 0, None)
    rgb[..., 0] -= s
    rgb[..., 2] -= s
    return rgb


def shadow_from_alpha(A, blur, pad):
    """Schwarzer Schatten mit weichgezeichnetem Alpha, `pad` px Rand rundum. A: 0..1."""
    h, w = A.shape
    big = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    big.paste(Image.fromarray((A * 255).astype(np.uint8), "L"), (pad, pad))
    big = big.filter(ImageFilter.GaussianBlur(blur))
    out = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.uint8)
    out[..., 3] = np.asarray(big)
    return Image.fromarray(out, "RGBA")


def resize_premult(rgb, A, size):
    """RGB + Alpha (0..1) vormultipliziert mit Lanczos auf size=(w, h); Rückgabe rgb, A."""
    pm = np.dstack([rgb * A[..., None], A])
    chans = [Image.fromarray(pm[..., i].astype(np.float32), "F").resize(size, Image.LANCZOS) for i in range(4)]
    arr = np.stack([np.asarray(c) for c in chans], -1)
    A2 = np.clip(arr[..., 3], 0, 1)
    rgb2 = np.where(A2[..., None] > 1e-3, arr[..., :3] / np.maximum(A2[..., None], 1e-3), 0)
    return np.clip(rgb2, 0, 255), A2


def save_rgba(path, rgb, A):
    A = np.where(A > 0.985, 1.0, A)
    out = np.dstack([np.clip(rgb, 0, 255), np.clip(A, 0, 1) * 255]).round().astype(np.uint8)
    Image.fromarray(out, "RGBA").save(path)
