#!/usr/bin/env python3
"""Asset-Aufbereitung für den Eintrag oelmalerei (nur Pillow + NumPy).

Aufruf aus dem Projektordner:
    .venv/bin/python styles/oelmalerei/tools/prep.py [schritt ...]
Schritte: bg, edges, portrait, walk, fx, fx_paint, all (Standard: all)

Warum ein eigenes Skript statt tools/sprites.py slice:
  - Das Walk-Sheet hat Bilder, deren Schal und Fuß sich spaltenweise überlappen; ein senkrechter Schnitt
    trennt dann Teile ab. Hier wird über Zusammenhangskomponenten getrennt.
  - gpt-image liefert im transparenten Bereich farbige Glow-Reste (RGB bei Alpha 0..2). Beim linearen
    Filtern in Godot würden sie als Saum sichtbar. clean_alpha() setzt Alpha hart und füllt die RGB-Werte
    transparenter Pixel mit den Randfarben der Figur (Alpha-Bleed).
"""
import json, pathlib, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SD = pathlib.Path(__file__).resolve().parent.parent          # styles/oelmalerei
RAW, ASSETS, DEMO = SD / "assets" / "raw", SD / "assets", SD / "demo" / "art"

# Bildschirmaufteilung der Demo (1280x720): Gemälde links, Dialogpanel rechts
BG_H = 720                      # Hintergrund wird auf volle Höhe skaliert -> 1080 x 720
BADGER_H = 152                  # Höhe des Dachses im Bild (Pixel), passt zu Fässern (90 px) weiter hinten auf dem Kai


def save(im, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, optimize=True)
    print(f"{path.relative_to(SD)}  {im.size[0]}x{im.size[1]}")


def clean_alpha(im, lo=24, hi=200, bleed=6):
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    al = a[..., 3]
    al = np.clip((al - lo) / (hi - lo), 0, 1) * 255
    rgb = a[..., :3].copy()
    known = al > 127
    # Alpha-Bleed: RGB der Randpixel schrittweise nach außen schieben
    for _ in range(bleed):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(al.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            k = np.roll(known, (dy, dx), (0, 1))
            acc += np.roll(rgb, (dy, dx), (0, 1)) * k[..., None]
            cnt += k
        grow = (~known) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        known = known | grow
    if (~known).any():
        rgb[~known] = rgb[known].mean(0)
    return Image.fromarray(np.dstack([rgb, al]).clip(0, 255).astype(np.uint8), "RGBA")


def label(mask):
    """Zusammenhangskomponenten (4er-Nachbarschaft) per Minimum-Propagation, nur NumPy."""
    h, w = mask.shape
    lab = np.where(mask, np.arange(h * w).reshape(h, w) + 1, 0).astype(np.int64)
    big = h * w + 10
    while True:
        cur = np.where(mask, lab, big)
        m = cur.copy()
        m[1:] = np.minimum(m[1:], cur[:-1]); m[:-1] = np.minimum(m[:-1], cur[1:])
        m[:, 1:] = np.minimum(m[:, 1:], cur[:, :-1]); m[:, :-1] = np.minimum(m[:, :-1], cur[:, 1:])
        new = np.where(mask, m, 0)
        if (new == lab).all():
            return lab
        lab = new


def components(im, scale=4, min_share=0.02):
    """Große Bildteile finden; kleine Splitter dem nächstgelegenen großen Teil zuordnen."""
    al = np.asarray(im)[..., 3]
    small = np.asarray(Image.fromarray(al).resize((al.shape[1] // scale, al.shape[0] // scale), Image.BOX)) > 40
    lab = label(small)
    ids, counts = np.unique(lab[lab > 0], return_counts=True)
    main = [i for i, c in zip(ids, counts) if c > counts.max() * min_share]
    boxes = []
    for i in main:
        ys, xs = np.nonzero(lab == i)
        boxes.append([xs.min() * scale, ys.min() * scale, (xs.max() + 1) * scale, (ys.max() + 1) * scale])
    # Splitter (kleine Komponenten) in die Box des nächsten großen Teils aufnehmen
    for i, c in zip(ids, counts):
        if i in main:
            continue
        ys, xs = np.nonzero(lab == i)
        cx, cy = xs.mean() * scale, ys.mean() * scale
        d = [abs(cx - (b[0] + b[2]) / 2) + abs(cy - (b[1] + b[3]) / 2) for b in boxes]
        b = boxes[int(np.argmin(d))]
        b[0], b[1] = min(b[0], xs.min() * scale), min(b[1], ys.min() * scale)
        b[2], b[3] = max(b[2], (xs.max() + 1) * scale), max(b[3], (ys.max() + 1) * scale)
    return boxes, lab, scale


def isolate(im, box, lab, scale, pad=8):
    """Box ausschneiden; Pixel, die zu einer anderen großen Komponente gehören, ausblenden."""
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(im.width, x1 + pad), min(im.height, y1 + pad)
    crop = np.asarray(im.crop((x0, y0, x1, y1))).copy()
    sub = lab[y0 // scale:(y1 + scale - 1) // scale, x0 // scale:(x1 + scale - 1) // scale]
    ids, counts = np.unique(sub[sub > 0], return_counts=True)
    if len(ids) > 1:
        own = ids[np.argmax(counts)]
        others = np.isin(sub, ids[ids != own])
        big = np.kron(others, np.ones((scale, scale), bool))[:crop.shape[0], :crop.shape[1]]
        big = np.asarray(Image.fromarray(big.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(9))) > 0
        crop[..., 3][big] = 0
    return Image.fromarray(crop, "RGBA")


def tight(im):
    a = np.asarray(im)[..., 3] > 8
    ys, xs = np.nonzero(a)
    return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


# Rohbild des Hintergrunds. bg.png (erster Versuch) war detailreiche Postkarten-Romantik; bg2/bg3 mit
# geschärftem Stilblock (große Pinsel, Spachtel, gebrochene Farben). bg3 ist gröber und wurde genommen.
BG_SRC = "bg3.png"

# Gemalte Rauchfahne über dem Schornstein (Bildschirmkoordinaten 1080x720). Das Bildmodell malt Rauch statisch
# mit; die animierten Wolken liegen darüber. Damit es keinen doppelten, halb eingefrorenen Rauch gibt, wird die
# Fahne mit Himmel von rechts daneben übermalt (weiche Maske nur dort, wo es heller ist als der Ersatz).
SMOKE_BOX = (70, 90, 116, 182)
SMOKE_DX = 30


def remove_painted_smoke(bg):
    a = np.asarray(bg, np.float32).copy()
    x0, y0, x1, y1 = SMOKE_BOX
    src = a[y0:y1, x0:x1]
    rep = a[y0:y1, x0 + SMOKE_DX:x1 + SMOKE_DX]
    ys, xs = np.mgrid[y0:y1, x0:x1]
    inside = np.clip(np.minimum.reduce([xs - x0, x1 - 1 - xs, ys - y0]) / 6, 0, 1)
    inside *= np.clip((y1 - 1 - ys) / 2, 0, 1)                 # unten bis an den Schornsteinkopf
    diff = np.abs(src - rep).max(2)                              # Fahne ist heller oder bräunlicher
    m = np.clip((diff - 6) / 16, 0, 1) * inside
    m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), np.float32) / 255
    a[y0:y1, x0:x1] = src * (1 - m[..., None]) + rep * m[..., None]
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def step_bg():
    im = Image.open(RAW / BG_SRC).convert("RGB")
    w = round(im.width * BG_H / im.height)
    bg = remove_painted_smoke(im.resize((w, BG_H), Image.LANCZOS))
    save(bg, ASSETS / "bg.png")
    save(bg, DEMO / "bg.png")
    # Relief-/Normalkarte aus der Helligkeit: pastose Farbe = Höhenfeld. Hochpass, damit nur die
    # Pinselstriche (nicht die großen Hell-Dunkel-Flächen) Relief bekommen.
    lum = np.asarray(bg.convert("L"), np.float32) / 255
    blur = np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)),
                      np.float32) / 255
    h = np.asarray(Image.fromarray(((lum - blur) * 0.5 + 0.5).clip(0, 1).__mul__(255).astype(np.uint8))
                   .filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255
    gx = np.zeros_like(h); gy = np.zeros_like(h)
    gx[:, 1:-1] = (h[:, 2:] - h[:, :-2]) * 0.5
    gy[1:-1] = (h[2:] - h[:-2]) * 0.5
    strength = 5.0
    n = np.dstack([-gx * strength, -gy * strength, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    # Godot-Normalmaps: Y nach oben positiv (OpenGL-Konvention) -> G invertieren
    rgb = np.dstack([n[..., 0] * 0.5 + 0.5, -n[..., 1] * 0.5 + 0.5, n[..., 2] * 0.5 + 0.5])
    save(Image.fromarray((rgb * 255).astype(np.uint8)), DEMO / "bg_normal.png")


def step_edges():
    """Kantenmaske für das Pinselstrich-Flimmern (canvas_post.gdshader): lange, eher senkrechte Linien und
    Kanten (Masten, Laternenpfahl, Leuchtturmkante, Fensterrahmen) sollen nicht springen, sonst zerfallen sie bei
    jedem Flimmerschritt zu Zickzack. Gesucht wird mit einem Linienfilter (41 px lang, 45..135°) über
    (a) dünne Linien (Abweichung von der Umgebung) und (b) starke Kanten (Gradient). Kurze Spachtelstriche
    erreichen die Schwelle nicht und flimmern weiter. Danach 2 px Sicherheitsrand (größte Sprungweite 1 px)."""
    bg = Image.open(ASSETS / "bg.png").convert("RGB")
    lum = np.asarray(bg.convert("L"), np.float32) / 255

    def blur(a, r):
        return np.asarray(Image.fromarray((a * 255).clip(0, 255).astype(np.uint8))
                          .filter(ImageFilter.GaussianBlur(r)), np.float32) / 255

    ridge = np.abs(lum - blur(lum, 2.0))
    gy, gx = np.gradient(blur(lum, 1.0))
    grad = np.hypot(gx, gy)
    L = 20

    def linefilt(e):
        best = np.zeros_like(e)
        for th in np.radians(np.arange(45, 136, 7.5)):
            acc = np.zeros_like(e)
            for k in range(-L, L + 1):
                acc += np.roll(e, (int(round(k * np.sin(th))), int(round(k * np.cos(th)))), (0, 1))
            best = np.maximum(best, acc / (2 * L + 1))
        return best

    thin = linefilt(np.clip(ridge / 0.12, 0, 1))
    edge = linefilt(np.clip(grad / 0.06, 0, 1))
    m = np.maximum(np.clip((thin - 0.5) / 0.15, 0, 1), np.clip((edge - 0.66) / 0.15, 0, 1))
    # Lücken entlang senkrechter Linien schließen (Mast kreuzt Felsen o. Ä.): senkrechtes Closing über 21 px
    m = np.maximum.reduce([np.roll(m, k, 0) for k in range(-10, 11)])
    m = np.minimum.reduce([np.roll(m, k, 0) for k in range(-10, 11)])
    mask = (Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
            .filter(ImageFilter.GaussianBlur(1)))
    print(f"  Kantenmaske: {np.mean(np.asarray(mask) > 127) * 100:.1f} % der Bildfläche springen nicht")
    save(mask, DEMO / "edge_mask.png")


def step_portrait():
    im = Image.open(RAW / "portrait.png").convert("RGB")
    # Ausschnitt: Kopf und Schultern, hochformatig wie ein gerahmtes Porträt
    s = im.width / 1254
    crop = im.crop((int(120 * s), int(0 * s), int(1180 * s), int(1130 * s)))
    p = crop.resize((300, round(300 * crop.height / crop.width)), Image.LANCZOS)
    save(p, ASSETS / "portrait.png")
    save(p, DEMO / "portrait.png")


# Walk-Sheet: walk.png (gpt-image, erster Versuch) war dunkel, mit Gegenlicht und Plüsch-Look. walk3.png ist eine
# Neumalung desselben Bogens mit agy (Codex hatte kein Guthaben mehr): alter Bogen als Layout-Referenz, Porträt als
# Stilreferenz. agy liefert JPEG auf Magenta, genimg.py stellt frei; der Magenta-Saum wird hier entfernt.
WALK_SRC = "walk3.png"


def despill_magenta(im, width=3):
    """Magenta-Saum am Rand freigestellter agy-Bilder entfernen: in einem Streifen von `width` Pixeln am Rand
    den Anteil min(R, B) - G aus R und B herausrechnen und den Rand um 1 px zurücknehmen."""
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    solid = a[..., 3] > 250
    inner = np.asarray(Image.fromarray(solid.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(2 * width + 1))) > 0
    band = (a[..., 3] > 0) & ~inner
    spill = np.clip(np.minimum(a[..., 0], a[..., 2]) - a[..., 1], 0, None) * band
    a[..., 0] -= spill
    a[..., 2] -= spill
    al = np.asarray(Image.fromarray(a[..., 3].astype(np.uint8)).filter(ImageFilter.MinFilter(3)), np.float32)
    a[..., 3] = al
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA")


def grade_costume(rgb, alpha):
    """Kostümfarben retten: Oliv (Mütze, Weste) Richtung Dunkelgrün drehen und sättigen, Schatten leicht anheben.
    Arbeitet auf float-RGB 0..1. Braun (Tasche, Paket) und Creme (Hemd) liegen außerhalb des Farbtonbereichs."""
    mx, mn = rgb.max(2), rgb.min(2)
    d = mx - mn
    s = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.where(mx == r, (g - b) / np.maximum(d, 1e-6) % 6,
                 np.where(mx == g, (b - r) / np.maximum(d, 1e-6) + 2, (r - g) / np.maximum(d, 1e-6) + 4)) / 6
    h = np.where(d < 1e-6, 0, h)
    w = (np.clip((h - 0.115) / 0.025, 0, 1) * (1 - np.clip((h - 0.42) / 0.08, 0, 1))
         * np.clip((s - 0.16) / 0.14, 0, 1) * (alpha > 0))
    h = (h + 0.075 * w) % 1
    s = np.clip(s * (1 + 0.3 * w), 0, 1)
    v = mx
    i = np.floor(h * 6).astype(int) % 6
    f = h * 6 - np.floor(h * 6)
    pp, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    out = np.choose(i[..., None].repeat(3, 2) * 0 + i[..., None], [
        np.dstack([v, t, pp]), np.dstack([q, v, pp]), np.dstack([pp, v, t]),
        np.dstack([pp, q, v]), np.dstack([t, pp, v]), np.dstack([v, pp, q])])
    return np.clip(out, 0, 1) ** 0.9                       # Schatten anheben (Gamma 0,9)


def paint_strokes(im, seed, radii=(16, 9, 4, 2), thresh=(0.0, 0.035, 0.05, 0.06), fine_top=0.32):
    """Malt ein freigestelltes Bild mit Pinselstrichen neu (Schichten grob -> fein, nach Hertzmann 1998):
    Jede Schicht vergleicht die bisherige Leinwand mit einer weichgezeichneten Vorlage und setzt dort, wo der
    Fehler groß ist, einen Strich entlang der Kante (quer zum Helligkeitsgradienten) in der Vorlagenfarbe.
    Feine Striche nur, wo Details sind (Augenstreifen, Paketschnur), große Flächen bleiben grob.
    Jedes Laufbild bekommt eigene Striche -> beim Abspielen flimmern sie wie gemalte Einzelbilder.
    Gemalt wird in doppelter Spielgröße (step_walk) und danach halbiert; die Radien sind darauf abgestimmt,
    damit die Striche im Spiel so breit sind wie die Spachtelstriche des Hintergrunds. Die feinste Schicht
    (R=2) malt nur im oberen Teil der Figur (fine_top: Mütze, Gesicht). Die Silhouette kommt aus den Strichen
    selbst (ausgefranster Rand statt sauberer Freistellkante)."""
    rng = np.random.default_rng(seed)
    a = np.asarray(im.convert("RGBA")).astype(np.float32) / 255
    alpha = a[..., 3]
    rgb = grade_costume(a[..., :3], alpha)
    h, w = alpha.shape
    SS = 2                                                  # Überabtastung beim Zeichnen (Kantenglättung)
    base = Image.fromarray((rgb * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radii[0]))
    canvas = base.resize((w * SS, h * SS), Image.BILINEAR)
    acanvas = Image.new("L", (w * SS, h * SS), 0)           # Deckung der gemalten Striche
    rows = np.nonzero(alpha.max(1) > 0.3)[0]
    head_y = rows.min() + fine_top * (rows.max() - rows.min())
    for li, (R, T) in enumerate(zip(radii, thresh)):
        finest = li == len(radii) - 1
        ref_im = Image.fromarray((rgb * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(R * 0.5))
        ref = np.asarray(ref_im, np.float32) / 255
        cur = np.asarray(canvas.resize((w, h), Image.BOX), np.float32) / 255
        lum = ref @ np.array([0.299, 0.587, 0.114], np.float32)
        gy, gx = np.gradient(lum)
        err = np.abs(cur - ref).mean(2) * (alpha > 0.3)
        strokes = []
        for y0 in range(0, h, R):
            if finest and y0 > head_y:
                continue
            for x0 in range(0, w, R):
                cell = err[y0:y0 + R, x0:x0 + R]
                if cell.size == 0 or alpha[y0:y0 + R, x0:x0 + R].max() < 0.3:
                    continue
                if cell.mean() <= T:
                    continue
                iy, ix = np.unravel_index(np.argmax(cell), cell.shape)
                y, x = y0 + iy, x0 + ix
                mag = np.hypot(gx[y, x], gy[y, x])
                ang = np.arctan2(gy[y, x], gx[y, x]) + np.pi / 2 if mag > 0.004 else 0.5 + rng.normal(0, 0.3)
                ang += rng.normal(0, 0.12)
                # Farbe der Vorlage, Helligkeit und Temperatur je Strich leicht gestreut (warm/kühl)
                tw = rng.uniform(-0.035, 0.035)
                col = np.clip(ref[y, x] * (1 + rng.uniform(-0.09, 0.09)) + np.array([tw, 0, -tw]), 0, 1)
                strokes.append((x, y, ang, col))
        rng.shuffle(strokes)
        d, da = ImageDraw.Draw(canvas), ImageDraw.Draw(acanvas)
        L, W = R * (3.0 if R > 3 else 2.0), R * 1.5
        for x, y, ang, col in strokes:
            ca, sa = np.cos(ang), np.sin(ang)
            ln = L * rng.uniform(0.8, 1.2)
            # Strich als Polygon mit leicht verjüngten Enden, dazu Borstenlinien heller/dunkler
            pts = []
            for t, wf in ((-0.5, 0.55), (-0.35, 1.0), (0.35, 1.0), (0.5, 0.7)):
                pts.append((t * ln, -wf * W / 2))
            for t, wf in ((0.5, 0.7), (0.35, 1.0), (-0.35, 1.0), (-0.5, 0.55)):
                pts.append((t * ln, wf * W / 2))
            poly = [((x + 0.5 + px_ * ca - py_ * sa) * SS, (y + 0.5 + px_ * sa + py_ * ca) * SS) for px_, py_ in pts]
            d.polygon(poly, fill=tuple(int(c * 255) for c in col))
            da.polygon(poly, fill=255)
            if R > 3:
                for _ in range(3 if R > 8 else 2):
                    off, k = rng.uniform(-0.4, 0.4), rng.choice([1.14, 0.88])
                    bc = tuple(int(np.clip(c * k, 0, 1) * 255) for c in col)
                    p0 = (x + 0.5 - 0.42 * ln * ca - off * W * sa, y + 0.5 - 0.42 * ln * sa + off * W * ca)
                    p1 = (x + 0.5 + 0.42 * ln * ca - off * W * sa, y + 0.5 + 0.42 * ln * sa + off * W * ca)
                    d.line([(p0[0] * SS, p0[1] * SS), (p1[0] * SS, p1[1] * SS)], fill=bc,
                           width=max(1, SS * (2 if R > 8 else 1)))
        print(f"  Schicht R={R}: {len(strokes)} Striche")
    out = np.asarray(canvas.resize((w, h), Image.LANCZOS), np.float32) / 255
    # Rand: innen (2 px eingezogen) immer deckend, außen bis 2 px über die Freistellkante nur dort, wo Striche
    # liegen -> ausgefranste, gemalte Silhouette
    stroke_a = np.asarray(acanvas.resize((w, h), Image.BOX), np.float32) / 255
    am = Image.fromarray((alpha * 255).astype(np.uint8))
    grow = np.asarray(am.filter(ImageFilter.MaxFilter(5)), np.float32) / 255
    shrink = np.asarray(am.filter(ImageFilter.MinFilter(5)), np.float32) / 255
    al = np.maximum(shrink, np.minimum(stroke_a, grow))
    return Image.fromarray((np.dstack([out, al]) * 255).clip(0, 255).astype(np.uint8), "RGBA")


def step_walk():
    im = clean_alpha(despill_magenta(Image.open(RAW / WALK_SRC)))
    boxes, lab, sc = components(im)
    boxes = sorted(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)[:6]
    boxes.sort(key=lambda b: b[0])
    frames = [tight(isolate(im, b, lab, sc)) for b in boxes]
    print("Rohbilder:", [f.size for f in frames])
    # In doppelter Spielgröße malen, dann halbieren: so werden die Striche im Spiel so breit wie die
    # Spachtelstriche des Hintergrunds (vorher: in Rohgröße mit R = 9/5/2 gemalt, Striche viel feiner).
    k2 = 2 * BADGER_H / max(f.height for f in frames)
    frames = [f.resize((round(f.width * k2), round(f.height * k2)), Image.LANCZOS) for f in frames]
    frames = [paint_strokes(f, seed=100 + i) for i, f in enumerate(frames)]
    frames = [f.resize((round(f.width / 2), round(f.height / 2)), Image.LANCZOS) for f in frames]
    # Nur schwach nachschärfen (Augenstreifen); stärkeres Schärfen ließ die Figur wie aufgeklebt wirken
    frames = [Image.merge("RGBA", (*f.convert("RGB").filter(ImageFilter.UnsharpMask(1.0, 35, 2)).split(),
                                  f.getchannel("A"))) for f in frames]
    # Ausrichten: Füße auf gemeinsamer Grundlinie, waagerecht nach dem Schwerpunkt der oberen 45 %
    # (Kopf/Rumpf), damit der Körper beim Abspielen nicht hin- und herspringt.
    anchors = []
    for f in frames:
        a = np.asarray(f)[..., 3].astype(np.float32) / 255
        top = a[: int(f.height * 0.45)]
        anchors.append((top.sum(0) * np.arange(f.width)).sum() / top.sum())
    pad = 10                    # Rand je Zelle: der Shader tastet Nachbartexel ab (Boil, Kantenlicht)
    left = max(anchors) + pad
    right = max(f.width - ax for f, ax in zip(frames, anchors)) + pad
    cw, ch = int(np.ceil(left + right)), max(f.height for f in frames) + 2 * pad
    strip = Image.new("RGBA", (cw * len(frames), ch), (0, 0, 0, 0))
    for i, (f, ax) in enumerate(zip(frames, anchors)):
        strip.alpha_composite(f, (i * cw + round(left - ax), ch - pad - f.height))
    strip = clean_alpha(strip, lo=1, hi=255, bleed=4)
    save(strip, ASSETS / "walk.png")
    save(strip, DEMO / "walk.png")
    meta = {"frames": len(frames), "frame_w": cw, "frame_h": ch, "anchor_x": round(left), "feet_y": ch - pad}
    # Vorschub je Bildwechsel aus dem Standfuß messen (PIPELINE: nicht mit konstantem Tempo schieben)
    meta["seq"] = WALK_SEQ
    meta["advance"] = walk_advance(strip, meta)
    (DEMO / "walk.json").write_text(json.dumps(meta))
    print(meta)


# Bildfolge des Laufzyklus: die 6 KI-Bilder enthalten nur eine Durchgangspose (Bild 2); erst
# 0,1,2,3,4,5,2,1 ergibt zwei Schritte (weit, mittel, Durchgang, Hoch | weit, mittel, Durchgang, mittel).
WALK_SEQ = [0, 1, 2, 3, 4, 5, 2, 1]


def foot_blobs(strip, meta, i, band=7):
    """Füße eines Laufbilds: zusammenhängende Spaltengruppen in den untersten `band` Zeilen."""
    cw, fy = meta["frame_w"], meta["feet_y"]
    a = np.asarray(strip)[fy - band:fy, i * cw:(i + 1) * cw, 3] > 128
    xs = np.nonzero(a.any(0))[0]
    groups, s0, prev = [], xs[0], xs[0]
    for c in xs[1:]:
        if c > prev + 1:
            groups.append((s0, prev))
            s0 = c
        prev = c
    groups.append((s0, prev))
    out = []
    for g0, g1 in groups:
        m = np.zeros_like(a)
        m[:, g0:g1 + 1] = a[:, g0:g1 + 1]
        if m.sum() > 15:
            out.append(m)
    return out


def walk_advance(strip, meta):
    """Für jeden Bildwechsel seq[k-1] -> seq[k]: um wie viele Pixel der Körper vorrücken muss, damit der
    Standfuß ortsfest bleibt. Gesucht wird die Verschiebung dx (0..40 px), bei der ein Fuß des alten Bilds
    am besten (IoU) auf einem Fuß des neuen liegt. Bei Wechseln in und aus der Durchgangspose (Bild 2) liegt
    der Standfuß ganz in der verschmolzenen Silhouette beider Füße; dann ist die IoU über mehrere dx exakt
    gleich (z. B. 2 -> 1: 20..28 px), genommen wird die Mitte dieses Plateaus."""
    adv = []
    for k in range(len(WALK_SEQ)):
        fa, fb = foot_blobs(strip, meta, WALK_SEQ[k - 1]), foot_blobs(strip, meta, WALK_SEQ[k])
        best, dxs = -1.0, []
        for ma in fa:
            for mb in fb:
                scores = []
                for dx in range(0, 41):
                    sh = np.zeros_like(ma)
                    sh[:, :ma.shape[1] - dx] = ma[:, dx:]
                    scores.append((sh & mb).sum() / max(1, (sh | mb).sum()))
                scores = np.array(scores)
                if scores.max() > best:
                    best, dxs = scores.max(), np.nonzero(scores >= scores.max() - 1e-9)[0]
        adv.append(int(round(float(np.mean(dxs)))))
    return adv


# Feste Ausschnitte im Effekt-Sheet (1254x1254): die Elemente liegen in drei Reihen ohne Überlappung,
# kleine Rauchtropfen gehören zur jeweiligen Wolke (automatische Gruppierung trennt sie ab).
FX_BOXES = {
    "gull1": (40, 20, 410, 380), "gull2": (385, 170, 860, 370), "gull3": (860, 200, 1240, 470),
    "smoke1": (30, 470, 345, 895), "smoke2": (380, 470, 630, 900), "smoke3": (630, 520, 900, 890),
    "smoke4": (880, 560, 1245, 830),
    "glint1": (20, 915, 325, 1050), "glint2": (330, 915, 620, 1050), "glint3": (635, 915, 920, 1050),
    "glint4": (950, 915, 1240, 1050),
    "beam1": (35, 1070, 1245, 1215),
}
FX_SIZE = {"smoke": 120, "glint": 64, "beam": 440}
GULL_W = 41                     # Breite der Möwe mit waagerechten Flügeln = Anzeigegröße der vorderen Möwe
# (vorher 66 px, in Godot auf 0,62 verkleinert: ohne Mipmaps flimmerten die weißen Kanten hart und fotografisch)
GULL_SKY = np.array([0.50, 0.48, 0.56], np.float32)    # Himmelston um die Flugbahn (Grauviolett)


def drop_border_parts(crop):
    """Teile eines Nachbarelements entfernen, die seitlich in den Ausschnitt ragen (alles außer der größten
    Komponente, das den linken oder rechten Rand berührt)."""
    a = np.asarray(crop).copy()
    small = np.asarray(Image.fromarray(a[..., 3]).resize((a.shape[1] // 2, a.shape[0] // 2), Image.BOX)) > 20
    lab = label(small)
    ids, counts = np.unique(lab[lab > 0], return_counts=True)
    if len(ids) < 2:
        return crop
    keep = ids[np.argmax(counts)]
    edge = set(np.unique(np.concatenate([lab[:, 0], lab[:, -1]]))) - {0, keep}
    if edge:
        m = np.isin(lab, list(edge))
        m = np.kron(m, np.ones((2, 2), bool))
        full = np.zeros(a.shape[:2], bool)
        full[:m.shape[0], :m.shape[1]] = m[:a.shape[0], :a.shape[1]]
        full = np.asarray(Image.fromarray(full.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))) > 0
        a[..., 3][full] = 0
    return Image.fromarray(a, "RGBA")


def step_fx():
    im = clean_alpha(Image.open(RAW / "fx.png"))
    s = im.width / 1254
    gulls = []
    for k, b in FX_BOXES.items():
        f = tight(drop_border_parts(im.crop(tuple(int(v * s) for v in b))))
        kind = k.rstrip("0123456789")
        if kind == "gull":
            gulls.append(f)
            continue
        t = FX_SIZE[kind]
        k2 = t / (f.width if kind in ("beam", "glint") else max(f.size))
        f = f.resize((round(f.width * k2), round(f.height * k2)), Image.LANCZOS)
        save(clean_alpha(f, lo=1, hi=255, bleed=4), DEMO / "fx" / f"{k}.png")
    # Möwe: drei Flügelstellungen mit gemeinsamem Maßstab, ausgerichtet an der Schnabelspitze
    # (rechtester deckender Punkt, die Möwe fliegt nach rechts), als Streifen für AnimatedSprite/Sprite2D.
    k = GULL_W / gulls[1].width
    gulls = [g.resize((round(g.width * k), round(g.height * k)), Image.LANCZOS) for g in gulls]
    tips = []
    for g in gulls:
        a = np.asarray(g)[..., 3] > 100
        xs = np.nonzero(a.any(0))[0]
        x = xs.max()
        tips.append((int(x), int(np.nonzero(a[:, x])[0].mean())))
    left = max(tx for tx, _ in tips) + 2
    up = max(ty for _, ty in tips) + 2
    down = max(g.height - ty for g, (_, ty) in zip(gulls, tips)) + 2
    cw, ch = left + 4, up + down
    strip = Image.new("RGBA", (cw * 3, ch), (0, 0, 0, 0))
    for i, (g, (tx, ty)) in enumerate(zip(gulls, tips)):
        strip.alpha_composite(g, (i * cw + left - tx, up - ty))
    save(tone_gulls(clean_alpha(strip, lo=1, hi=255, bleed=3)), DEMO / "fx" / "gull.png")
    (DEMO / "fx" / "gull.json").write_text(json.dumps({"frames": 3, "frame_w": cw, "frame_h": ch}))


def tone_gulls(strip):
    """Möwen in den Himmel einfügen: Weiß war der hellste, schärfste Punkt im Bild und wirkte fotografisch.
    Entsättigen, Tonwerte zum Himmelston stauchen (Weiß -> helles Grauviolett), Kanten weichzeichnen."""
    a = np.asarray(strip, np.float32) / 255
    rgb, al = a[..., :3], a[..., 3]
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    rgb = rgb * 0.75 + lum[..., None] * 0.25
    rgb = GULL_SKY * 0.22 + rgb * 0.68
    pm = np.dstack([rgb * al[..., None], al])
    pm = np.dstack([np.asarray(Image.fromarray((pm[..., c] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.4)),
                               np.float32) / 255 for c in range(4)])
    al = pm[..., 3]
    rgb = np.where(al[..., None] > 1e-3, pm[..., :3] / np.maximum(al[..., None], 1e-3), GULL_SKY)
    return clean_alpha(Image.fromarray((np.dstack([rgb, al]) * 255).clip(0, 255).astype(np.uint8), "RGBA"),
                       lo=1, hi=255, bleed=3)


def step_fx_paint():
    """Aus den gemalten Effekt-Strichen abgeleitete Texturen (kein weiteres KI-Bild):
    - beam_cone.png: Leuchtturmstrahl als Kegel, am Lampenhaus schmal, zur Spitze breiter. Farbe und Grate aus
      beam1.png (am Ursprung warmes Gold, nach außen helles Creme), Deckung mit in Strahlrichtung gestreckten
      Borstenspuren moduliert (vorher wirkte er als graues, glattes Band).
    - halo.png: gemalter Lichthof aus gedrehten, gestapelten Glanzlicht-Strichen statt glattem Radialverlauf.
    - shadow.png: Kontaktschatten des Dachses als dunkelvioletter Spachtel-Tupfer statt glattem Verlauf."""
    src = np.asarray(Image.open(DEMO / "fx" / "beam1.png").convert("RGBA"), np.float32) / 255
    sh, sw = src.shape[:2]
    L, H = 420, 96
    ys, xs = np.mgrid[0:H, 0:L].astype(np.float32)
    u = (xs + 0.5) / L
    half = 5 + 41 * u ** 0.85                               # halbe Breite: 5 px am Lampenhaus, 46 px an der Spitze
    v = (ys + 0.5 - H / 2) / half                           # -1..1 quer zum Strahl
    sx = np.clip(8 + u * 400, 0, sw - 1)                    # ganzer gemalter Strich, das trockene Ende an der Spitze
    sy = np.clip(sh / 2 + v * 15, 0, sh - 1)
    x0, y0 = sx.astype(int), sy.astype(int)
    x1, y1 = np.minimum(x0 + 1, sw - 1), np.minimum(y0 + 1, sh - 1)
    fx_, fy_ = (sx - x0)[..., None], (sy - y0)[..., None]
    smp = (src[y0, x0] * (1 - fx_) * (1 - fy_) + src[y0, x1] * fx_ * (1 - fy_)
           + src[y1, x0] * (1 - fx_) * fy_ + src[y1, x1] * fx_ * fy_)
    lum = smp[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    # Farbe: am Lampenhaus warmes Gold aus dem gemalten Strich, nach außen helles Creme (eine gelbe Lasur auf dem
    # grauvioletten Himmel wird sonst grau). Die Grate des Strichs bleiben als Helligkeitsunterschied erhalten.
    warm = np.clip(smp[..., :3] * 1.15 + 0.05, 0, 1)
    pale = np.array([0.98, 0.94, 0.82], np.float32) * (0.85 + 0.3 * lum[..., None])
    rgb = np.clip(warm + (pale - warm) * np.clip((u[..., None] - 0.08) / 0.55, 0, 1), 0, 1)
    edge = np.clip((1 - np.abs(v)) * 3, 0, 1)
    # Deckung: am Ursprung fast deckend, Mitte halb, Spitze läuft aus
    along = (np.clip(u / 0.03, 0, 1) * (1 - 0.45 * np.clip(u / 0.5, 0, 1))
             * (1 - np.clip((u - 0.5) / 0.5, 0, 1)) ** 1.3)
    # Borstenspuren: 18 Spuren quer zum Strahl, jede mit eigenem, in Strahlrichtung gestrecktem Rauschen
    # (Länge der Flecken 30..60 px) -> Striche, die abreißen und wieder ansetzen (Trockenpinsel)
    rng = np.random.default_rng(3)
    NR = 18
    noise = np.asarray(Image.fromarray((rng.uniform(0, 1, (NR, 10)) * 255).astype(np.uint8))
                       .resize((L, NR), Image.BICUBIC), np.float32) / 255           # NR x L
    base = rng.uniform(0.55, 1.0, NR)
    kf = np.clip((v + 1) / 2 * (NR - 1), 0, NR - 1)
    k0 = np.minimum(kf.astype(int), NR - 2)
    f = kf - k0
    f = f * f * (3 - 2 * f)                                 # schmale Übergänge -> deutliche Spuren
    xi = np.minimum(xs.astype(int), L - 1)
    tr = (noise[k0, xi] * base[k0]) * (1 - f) + (noise[k0 + 1, xi] * base[k0 + 1]) * f
    bristle = np.clip((tr - 0.18) / 0.55, 0, 1)
    dense = np.clip((u - 0.04) / 0.3, 0, 1)                 # am Lampenhaus dicht gemalt, außen Trockenpinsel
    alpha = np.clip(smp[..., 3] * 1.2, 0, 1) * edge * along * (1 - dense + dense * bristle)
    out = np.dstack([rgb, alpha])
    save(Image.fromarray((out * 255).astype(np.uint8), "RGBA"), DEMO / "fx" / "beam_cone.png")

    # Kontaktschatten: dunkelvioletter Spachtel-Tupfer aus den Glanzlicht-Strichen (nur deren Form und Grate),
    # flach und breit, zu den Enden hin ausgefranst. Farbe und Deckung im Bild über modulate.
    SW, SH = 168, 36
    shadow = np.zeros((SH, SW), np.float32)
    ridges = np.zeros((SH, SW), np.float32)
    rng = np.random.default_rng(11)
    for k in range(5):
        g = Image.open(DEMO / "fx" / f"glint{k % 4 + 1}.png").convert("RGBA")
        g = g.resize((round(g.width * rng.uniform(1.7, 2.3)), round(g.height * rng.uniform(0.9, 1.25))),
                     Image.LANCZOS).rotate(rng.uniform(-4, 4), Image.BICUBIC, expand=True)
        layer = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
        layer.alpha_composite(g, (round(SW / 2 - g.width / 2 + rng.uniform(-24, 24)),
                                  round(SH / 2 - g.height / 2 + (k - 2) * 2.5)))
        la = np.asarray(layer, np.float32) / 255
        shadow = np.maximum(shadow, la[..., 3])
        ridges = np.maximum(ridges, la[..., 3] * (la[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)))
    yy, xx = np.mgrid[0:SH, 0:SW]
    ell = np.hypot((xx - SW / 2 + 0.5) / (SW / 2), (yy - SH / 2 + 0.5) / (SH / 2))
    shadow *= np.clip((1 - ell) / 0.35, 0, 1)
    # Farbe: dunkles Violett, Grate des Spachtels etwas heller (Farbe am Rand des Messers dünner)
    col = np.array([0.09, 0.055, 0.12], np.float32)[None, None] * (0.9 + 0.35 * ridges[..., None])
    save(clean_alpha(Image.fromarray((np.dstack([col.clip(0, 1), shadow]) * 255).astype(np.uint8), "RGBA"),
                     lo=1, hi=255, bleed=3), DEMO / "fx" / "shadow.png")

    # Lichthof: 6 Spachtel-Tupfer aus den Glanzlicht-Strichen, fast waagerecht übereinander gesetzt und
    # radial ausgeblendet (wie mit dem Messer aufgesetztes Licht, kein Strahlenkranz)
    S = 128
    halo = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    rng = np.random.default_rng(7)
    for k in range(6):
        g = Image.open(DEMO / "fx" / f"glint{k % 4 + 1}.png").convert("RGBA")
        sc = rng.uniform(1.0, 1.5)
        g = g.resize((round(g.width * sc), round(g.height * sc * 1.4)), Image.LANCZOS)
        g = g.rotate(rng.uniform(-22, 22), Image.BICUBIC, expand=True)
        ox, oy = rng.uniform(-10, 10), (k - 2.5) * 6 + rng.uniform(-3, 3)
        layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        layer.alpha_composite(g, (round(S / 2 - g.width / 2 + ox), round(S / 2 - g.height / 2 + oy)))
        halo = Image.alpha_composite(halo, layer)
    a = np.asarray(halo, np.float32) / 255
    yy, xx = np.mgrid[0:S, 0:S]
    r = np.hypot(xx - S / 2 + 0.5, yy - S / 2 + 0.5) / (S / 2)
    a[..., 3] *= np.clip(1 - (r - 0.25) / 0.75, 0, 1) ** 1.5
    lum = a[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    a[..., :3] = np.clip(0.6 * lum[..., None] + 0.4 * a[..., :3] + 0.15, 0, 1)   # hell; Farbton per modulate
    save(clean_alpha(Image.fromarray((a * 255).astype(np.uint8), "RGBA"), lo=1, hi=255, bleed=3),
         DEMO / "fx" / "halo.png")


def mirror():
    """Verarbeitete Assets liegen laut PIPELINE.md auch unter assets/ (Kopie der Demo-Dateien)."""
    for f in DEMO.rglob("*"):
        if f.is_file() and f.suffix in (".png", ".json"):
            dst = ASSETS / f.relative_to(DEMO)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(f.read_bytes())


if __name__ == "__main__":
    steps = sys.argv[1:] or ["all"]
    for name in ("bg", "edges", "portrait", "walk", "fx", "fx_paint"):
        if "all" in steps or name in steps:
            globals()["step_" + name]()
    mirror()
