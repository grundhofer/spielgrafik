#!/usr/bin/env python3
"""Effekt-Texturen und Vordergrund-Silhouetten (nur NumPy/Pillow, fester Seed, bitgleich wiederholbar).

  halo.png       weicher Lichthof (weiß, Gauß + breiter Saum), für additive Lichter mit HDR-Glow
  beam.png       Lichtkegel des Leuchtfeuers: am Ursprung schmal und hell, nach außen breit und weich
  puff.png       Rauchwolke: weicher Fleck mit Pinseltextur (für den Schornstein)
  mote.png       kleiner leuchtender Punkt (Funken, Schwebeteilchen)
  streak.png     waagerechter Glanzstrich (Wasserglitzern, Spiegelung)
  foreground.png Vordergrund-Silhouetten: Felsen, Strandgras und ein schräger, verjüngter Pfahl mit Astansatz
                 und warmer Lichtkante links; fast schwarz, unscharf (Tiefenunschärfe), warme Kanten oben
"""
import json, pathlib, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

S = pathlib.Path(__file__).resolve().parent.parent
OUT = S / "assets" / "fx"
ART = S / "demo" / "art"
RNG = np.random.default_rng(20261010)


def save(arr, name):
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    im.save(OUT / name, optimize=True)
    print(name, im.size)
    return im


def radial(n):
    y, x = np.mgrid[0:n, 0:n]
    c = (n - 1) / 2
    return np.sqrt((x - c) ** 2 + (y - c) ** 2) / c


def white(alpha):
    h, w = alpha.shape
    return np.dstack([np.full((h, w, 3), 255.0), np.clip(alpha, 0, 1) * 255])


def halo():
    r = radial(256)
    a = 0.75 * np.exp(-(r / 0.22) ** 2) + 0.35 * np.exp(-(r / 0.5) ** 2) + 0.08 * np.clip(1 - r, 0, 1)
    a *= np.clip((1 - r) / 0.15, 0, 1)                 # Rand sicher auf 0
    return save(white(a / a.max()), "halo.png")


def beam():
    w, h = 512, 160
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    u = x / (w - 1)                                     # 0 am Leuchtfeuer, 1 am Ende
    half = 0.04 + 0.42 * u                               # halbe Höhe (relativ), Kegel
    v = np.abs(y - (h - 1) / 2) / ((h - 1) / 2) / np.maximum(half / 0.46, 1e-3)
    across = np.exp(-(v / 0.55) ** 2)
    along = np.clip(u / 0.02, 0, 1) * np.exp(-u * 2.2) * (1 - np.clip((u - 0.8) / 0.2, 0, 1))
    # leichte Streifen wie gemalte Pinselzüge im Lichtkegel
    stripes = 1 + 0.12 * np.sin(v * 9 + 1.3) * u
    a = across * along * stripes
    return save(white(a / a.max()), "beam.png")


def puff():
    n = 128
    r = radial(n)
    base = np.exp(-(r / 0.55) ** 2.4)
    noise = RNG.normal(0, 1, (16, 16)).astype(np.float32)
    noise = np.asarray(Image.fromarray(noise).resize((n, n), Image.BICUBIC))
    fine = RNG.normal(0, 1, (48, 48)).astype(np.float32)
    fine = np.asarray(Image.fromarray(fine).resize((n, n), Image.BICUBIC))
    a = base * np.clip(0.75 + 0.22 * noise + 0.08 * fine, 0, 1.2)
    a = np.clip((a - 0.08) / 0.8, 0, 1) * np.clip((1 - r) / 0.2, 0, 1)
    return save(white(a), "puff.png")


def mote():
    r = radial(32)
    a = np.exp(-(r / 0.28) ** 2) + 0.25 * np.exp(-(r / 0.7) ** 2)
    a *= np.clip((1 - r) / 0.2, 0, 1)
    return save(white(a / a.max()), "mote.png")


def streak():
    w, h = 64, 12
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    a = np.exp(-((x - 31.5) / 20) ** 2) * np.exp(-((y - 5.5) / 2.2) ** 2)
    return save(white(a / a.max()), "streak.png")


def silhouette(crop, scale, blur, rim_px):
    """Requisit zur Vordergrund-Silhouette: vergrößern, fast schwarz tönen, warme Oberkante, unscharf."""
    crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.LANCZOS)
    a = np.asarray(crop)[..., 3].astype(np.float32) / 255
    rgb = np.asarray(crop)[..., :3].astype(np.float32)
    lum = rgb.mean(-1, keepdims=True) / 255
    dark = np.array([14, 22, 28], np.float32) + lum * np.array([22, 30, 34], np.float32)
    # Kantenlicht: Alpha minus nach unten verschobenes Alpha = Oberkanten
    sh = np.zeros_like(a); sh[rim_px:] = a[:-rim_px]
    rim = np.clip(a - sh, 0, 1)
    rim = np.asarray(Image.fromarray((rim * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))) / 255
    col = dark + rim[..., None] * np.array([150, 105, 60], np.float32)
    out = Image.fromarray(np.dstack([np.clip(col, 0, 255), a * 255]).astype(np.uint8), "RGBA")
    pad = int(blur * 3) + 2
    big = Image.new("RGBA", (out.width + 2 * pad, out.height + 2 * pad), (0, 0, 0, 0))
    big.paste(out, (pad, pad))
    # unscharf: Farbe und Alpha getrennt weichzeichnen (Farbe mit Alpha vormultipliziert)
    arr = np.asarray(big).astype(np.float32)
    pm = arr[..., :3] * arr[..., 3:4] / 255
    pm = np.dstack([pm, arr[..., 3:4]])
    pm = np.asarray(Image.fromarray(np.clip(pm, 0, 255).astype(np.uint8), "RGBA").filter(ImageFilter.GaussianBlur(blur))).astype(np.float32)
    al = pm[..., 3:4]
    rgb = np.where(al > 0, pm[..., :3] * 255 / np.maximum(al, 1), 0)
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), al]).astype(np.uint8), "RGBA")


def grass(w, h, n, seed):
    rng = np.random.default_rng(seed)
    ss = 3
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i in range(n):
        x0 = rng.uniform(0.05, 0.95) * w
        height = rng.uniform(0.45, 1.0) * h
        lean = rng.uniform(-0.35, 0.35) * height
        width = rng.uniform(3.0, 6.0)
        pts = []
        for k in range(9):
            t = k / 8
            pts.append(((x0 + lean * t * t) * ss, (h - height * t) * ss))
        col = (255, 255, 255, 255)
        for k in range(len(pts) - 1):
            wk = max(1, int(width * ss * (1 - k / 9)))
            d.line([pts[k], pts[k + 1]], fill=col, width=wk)
    return im.resize((w, h), Image.LANCZOS)


def shape_layer(w, h, draw_fn, ss=3):
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), ss)
    return im.resize((w, h), Image.LANCZOS)


def tint_silhouette(mask_im, blur, rim_dir=(0, 1), rim_px=4):
    """Maske -> fast schwarze, unscharfe Silhouette mit warmer Lichtkante.
    rim_dir: Richtung zum Licht in Pixeln (x, y); (0, 1) = Licht von oben."""
    a = np.asarray(mask_im)[..., 3].astype(np.float32) / 255
    def shifted(dx, dy):
        out = np.zeros_like(a)
        h, w = a.shape
        ys0, ys1 = max(0, dy), h + min(0, dy)
        xs0, xs1 = max(0, dx), w + min(0, dx)
        out[ys0:ys1, xs0:xs1] = a[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
        return out
    rim = np.clip(a - shifted(0, rim_px), 0, 1) * 0.8
    if rim_dir[0]:
        rim = np.maximum(rim, np.clip(a - shifted(int(np.sign(rim_dir[0])) * -rim_px, 0), 0, 1) * 0.7)
    rim = np.asarray(Image.fromarray((np.clip(rim, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))) / 255
    yy = np.linspace(0, 1, a.shape[0])[:, None]
    base = np.array([20, 30, 36], np.float32) * (1 - 0.35 * yy[..., None]) + 0 * a[..., None]
    col = base + rim[..., None] * np.array([150, 100, 58], np.float32)
    out = Image.fromarray(np.dstack([np.clip(col, 0, 255), a * 255]).astype(np.uint8), "RGBA")
    arr = np.asarray(out).astype(np.float32)
    pm = np.dstack([arr[..., :3] * arr[..., 3:4] / 255, arr[..., 3:4]])
    pm = np.asarray(Image.fromarray(np.clip(pm, 0, 255).astype(np.uint8), "RGBA").filter(ImageFilter.GaussianBlur(blur))).astype(np.float32)
    al = pm[..., 3:4]
    rgb = np.where(al > 0, pm[..., :3] * 255 / np.maximum(al, 1), 0)
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), al]).astype(np.uint8), "RGBA")


FG_SIZE = (1800, 460)        # in Godot bei (-100, 360): Bildschirm-y 360..820


def rock(d, ss, cx, cy, rx, ry, seed):
    """Felsbrocken: Ellipse mit verrauschtem Radius, unten flach."""
    rng = np.random.default_rng(seed)
    k = rng.normal(0, 1, 9)
    pts = []
    for i in range(72):
        t = i / 72 * 2 * np.pi
        r = 1 + 0.07 * sum(k[j] * np.sin((j + 2) * t + k[-1 - j]) for j in range(4))
        x, y = cx + rx * r * np.cos(t), cy - ry * r * max(np.sin(t), -0.15)
        pts.append((x * ss, y * ss))
    d.polygon(pts, fill=(255, 255, 255, 255))


def stake(d, ss, x0, y0, x1, y1, w0, w1):
    """Schräg stehender, oben abgebrochener Holzpfahl als Viereck."""
    dx, dy = x1 - x0, y1 - y0
    n = np.hypot(dx, dy); nx, ny = -dy / n, dx / n
    pts = [(x0 + nx * w0, y0 + ny * w0), (x1 + nx * w1, y1 + ny * w1), (x1 + nx * w1 * 0.2, y1 - 6),
           (x1 - nx * w1, y1 - ny * w1), (x0 - nx * w0, y0 - ny * w0)]
    d.polygon([(x * ss, y * ss) for x, y in pts], fill=(255, 255, 255, 255))


def fg_left(d, ss):
    rock(d, ss, 120, 238, 150, 72, 11)
    rock(d, ss, 262, 250, 84, 42, 12)


def fg_right(d, ss):
    rock(d, ss, 130, 262, 96, 48, 21)
    rock(d, ss, 236, 268, 70, 36, 22)


def stake_layer(w, h, x0=170, y0=262, x1=136, y1=40, w0=14, w1=7, ss=3):
    """Schräger, oben abgebrochener Holzpfahl: verjüngt, leicht unregelmäßiger Umriss, Astansatz rechts,
    Maserung entlang der Achse und eine deutliche warme Lichtkante auf der linken Seite (zur Laterne hin).
    Gibt RGBA in Endgröße zurück (noch scharf; unscharf wird er zusammen mit den Felsen)."""
    rng = np.random.default_rng(31)
    dx, dy = x1 - x0, y1 - y0
    n = np.hypot(dx, dy); ux, uy = dx / n, dy / n; nx, ny = -uy, ux        # Achse, Normale (nx<0: nach links)
    k = 40
    t = np.linspace(0, 1, k)
    wob = np.convolve(rng.normal(0, 1, k + 6), np.ones(7) / 7, "valid")[:k] * 1.3
    half = w0 + (w1 - w0) * t ** 0.8
    left = [(x0 + dx * ti - nx * (hw + wb), y0 + dy * ti - ny * (hw + wb)) for ti, hw, wb in zip(t, half, wob)]
    right = [(x0 + dx * ti + nx * (hw - 0.6 * wb), y0 + dy * ti + ny * (hw - 0.6 * wb)) for ti, hw, wb in zip(t, half, wob)]
    # abgebrochene, gezackte Spitze
    tip = [(x1 + nx * w1 * 0.9, y1 + ny * w1 * 0.9 - 2), (x1 + nx * 0.2 * w1 + ux * 7, y1 + uy * 7 - 3),
           (x1 - nx * 0.3 * w1 + ux * 2, y1 + uy * 2 + 1), (x1 - nx * 0.8 * w1 + ux * 10, y1 + uy * 10)]
    poly = left + tip[::-1] + right[::-1]
    # Astansatz rechts auf 58 % der Höhe
    tb = 0.58
    bx, by = x0 + dx * tb + nx * half[int(tb * (k - 1))], y0 + dy * tb + ny * half[int(tb * (k - 1))]
    stub = [(bx - ux * 6, by - uy * 6), (bx + nx * 15 + ux * 4, by + ny * 15 + uy * 4 - 6),
            (bx + nx * 16 + ux * 9, by + ny * 16 + uy * 9 - 4), (bx + ux * 9, by + uy * 9)]
    m = Image.new("L", (w * ss, h * ss), 0)
    dr = ImageDraw.Draw(m)
    dr.polygon([(x * ss, y * ss) for x, y in poly], fill=255)
    dr.polygon([(x * ss, y * ss) for x, y in stub], fill=255)
    a = np.asarray(m.resize((w, h), Image.LANCZOS)).astype(np.float32) / 255
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # Abstand quer zur Achse (links negativ) und entlang der Achse
    across = (xx - x0) * nx + (yy - y0) * ny
    along = (xx - x0) * ux + (yy - y0) * uy
    hw = np.interp(np.clip(along / n, 0, 1), t, half)
    u = np.clip(across / np.maximum(hw, 1), -1.5, 1.5)                       # -1 linke Kante, +1 rechte Kante
    grain = np.asarray(Image.fromarray(rng.normal(0, 1, (h // 24 + 2, w // 2 + 2)).astype(np.float32))
                       .resize((w, h), Image.BICUBIC))
    shade = 0.75 + 0.25 * (-u) + 0.12 * grain                                 # links heller (Licht von links)
    base = np.array([24, 31, 36], np.float32)[None, None] * np.clip(shade, 0.5, 1.4)[..., None]
    rim = np.clip(1 - (u + 1) / 0.6, 0, 1) * (u > -1.6)                       # schmaler Streifen an der linken Kante
    rim *= np.clip(1 - along / n * 0.35, 0.5, 1)                              # unten etwas stärker (Laternennähe)
    col = base + rim[..., None] * np.array([215, 138, 70], np.float32)
    # Oberkante des Astansatzes und Bruchkante ebenfalls leicht beleuchtet
    sh = np.zeros_like(a); sh[3:] = a[:-3]
    top = np.clip(a - sh, 0, 1)
    col += top[..., None] * np.array([120, 80, 45], np.float32)
    return np.dstack([np.clip(col, 0, 255), a * 255])


def blur_rgba(arr, blur):
    pm = np.dstack([arr[..., :3] * arr[..., 3:4] / 255, arr[..., 3:4]])
    pm = np.asarray(Image.fromarray(np.clip(pm, 0, 255).astype(np.uint8), "RGBA")
                    .filter(ImageFilter.GaussianBlur(blur))).astype(np.float32)
    al = pm[..., 3:4]
    rgb = np.where(al > 0, pm[..., :3] * 255 / np.maximum(al, 1), 0)
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), al]).astype(np.uint8), "RGBA")


def foreground():
    W, H = FG_SIZE
    fg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    left = Image.new("RGBA", (380, 360), (0, 0, 0, 0))
    left.alpha_composite(shape_layer(380, 360, fg_left))
    left.alpha_composite(grass(300, 200, 42, 1), (10, 40))
    left.alpha_composite(grass(170, 130, 20, 4), (210, 120))
    right = Image.new("RGBA", (360, 380), (0, 0, 0, 0))
    right.alpha_composite(shape_layer(360, 380, fg_right))
    right.alpha_composite(grass(340, 215, 46, 2), (6, 45))
    mid = grass(360, 60, 16, 3)
    fg.alpha_composite(tint_silhouette(left, 3.0, (1, 1)), (40, 100))
    fg.alpha_composite(tint_silhouette(mid, 2.4), (780, H - 60))
    fg.alpha_composite(blur_rgba(stake_layer(360, 380), 2.2), (1120, 80))     # Pfahl hinter den Felsen
    fg.alpha_composite(tint_silhouette(right, 3.4, (-1, 1)), (1120, 80))
    fg.save(OUT / "foreground.png", optimize=True)
    print("foreground.png", fg.size)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    halo(); beam(); puff(); mote(); streak(); foreground()
    ART.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.png"):
        if f.name == "foreground.png":       # seit 12.10. gemalter Vordergrund (build_sep_layers.py); nur Vergleich
            continue
        shutil.copy2(f, ART / f.name)


if __name__ == "__main__":
    main()
