#!/usr/bin/env python3
"""Asset-Aufbereitung für den Eintrag hintergrund-serie (nur Pillow + NumPy).

Aufruf aus dem Projektordner:
    .venv/bin/python styles/hintergrund-serie/tools/prep.py [--raw DIR] [--walk-fallback] [schritt ...]
Schritte: layout, fx, ui, bg, lut, walk, all (Standard: all = fx ui bg lut walk)

  layout  Layout-Referenz für den Laufzyklus-Auftrag: shared/badger/walk_painted.png mittig auf Magenta, 3:2
          (assets/raw/walk_layout_ref.png, geht als erste Referenz an genimg)
  fx      prozedurale Effekt-Texturen im Aquarell-Look (Lichthof, Rauch, Strahl, Glanz, Möwe, Rauschen, Papier)
  ui      Papierkarte für die Textbox
  bg      Rohbilder (3:2, beliebige Größe) auf 1280 px Breite skalieren und je Ort mit eigenem Versatz auf
          1280x720 schneiden
  lut     Farbabgleich: Palette des Ankers (tools/sprites.py palette), je Ort eine 3D-LUT (32^3 als 1024x32-Streifen),
          Vergleichsbild, Serienblatt und Messwerte zur Stildrift (drift.json)
  walk    Laufzyklus zerlegen, Magenta-Saum entfernen, am Kopf ausrichten, verkleinern, Vorschub je Bildwechsel aus
          dem Standfuß messen (walk.json)

Echte Ergebnisse und Platzhalter werden getrennt:
  - Stammt ein Ergebnis nur aus echten Rohbildern in assets/raw/, landet es in assets/ und als Kopie in demo/art/;
    Berichte (drift.json, lut_compare.png, series_sheet.png, palette_anchor.png) kommen nach assets/.
  - Fehlt ein Rohbild, baut der Schritt einen beschrifteten Platzhalter. Platzhalter und alles, was davon abhängt,
    landen nur in demo/art/ (damit die Demo läuft), Berichte im Temp-Ordner. demo/art/placeholders.json listet sie.
  - --raw DIR nimmt Ersatzbilder aus DIR (Test der Kette mit fremden Bildern); auch das gilt als Platzhalter.
  - Ohne raw/walk.png nimmt walk shared/badger/walk_painted.png als Platzhalter; mit --walk-fallback wird das
    bewusst als echtes Ergebnis übernommen (nur, wenn der Laufzyklus-Auftrag endgültig gescheitert ist).

Alles ist deterministisch (feste Seeds), ein zweiter Lauf erzeugt dieselben Dateien.
"""
import json, pathlib, subprocess, sys, tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SD = pathlib.Path(__file__).resolve().parent.parent          # styles/hintergrund-serie
ROOT = SD.parent.parent
RAW_DEFAULT, ASSETS, ART = SD / "assets" / "raw", SD / "assets", SD / "demo" / "art"
RAW = RAW_DEFAULT                                             # mit --raw umstellbar
TMP = pathlib.Path(tempfile.gettempdir()) / "hintergrund-serie" / "prep"
W, H = 1280, 720
LOCS = ["hafen", "leuchtturm", "stube", "klippe"]
# Oberkante des 1280x720-Ausschnitts als Anteil der Bildhöhe des auf 1280 px Breite skalierten Rohbilds
# (bei 3:2 sind das 853 px; 0.117 = 100 px, unten fallen dann 33 px weg). Die Prompts legen den Bildaufbau in
# Prozent der Bildhöhe fest (Augenhöhe 40 %, Laufstreifen 58–72 %, unteres Viertel ruhig); mit 0.117 liegt die
# Augenhöhe auf Bildschirmzeile 241, der Laufstreifen auf 395–514 und die Textbox (ab 534) über dem ruhigen
# Vordergrund. Nach Sichtung je Ort anpassen, falls ein Bild den Aufbau verfehlt.
# Nach Sichtung der Codex-Bilder (gemessene Horizontzeile im Rohbild 1536x1024: Hafen 405 = 39,6 %, Klippe 382 =
# 37,3 %, Meer in den Leuchtturmfenstern 415 = 40,5 %, Meer im Stubenfenster 367 = 35,8 %): Schnitt je Ort so, dass
# der Horizont überall auf Bildschirmzeile 256 liegt. Beim Hafen sitzt die Leuchtturmlampe sonst am oberen Rand
# (mit 0.117 bei y = 8); mit 0.0955 liegt sie bei y = 27, die Kaikante bleibt über der Textbox.
CROP_TOP = {"hafen": 0.0955, "leuchtturm": 0.1055, "stube": 0.0586, "klippe": 0.0727}
LAYOUT = {"eye": 0.40, "walk": (0.58, 0.72), "calm": 0.75}   # Bildaufbau laut Prompt (Anteil der Bildhöhe)
UI_TOP = 534                                                  # Oberkante der Textbox-Karte auf dem Bildschirm
# Stilanker für den Farbabgleich: sein Ausschnitt liefert Palette und Lab-Statistik, seine LUT ist die Identität.
# Normal der Hafen (erstes Bild, Referenz der anderen). Nur ändern, wenn der Hafen misslingt und ein anderes Bild
# den Stil besser trifft (dann in style.json begründen).
ANCHOR = "hafen"
# Stärke des Farbabgleichs je Ort: global (Mittelwert/Streuung in Lab, g_l für L, g_ab für a/b) und Zug zur
# Ankerpalette (snap); 0 = aus, 1 = voll. Für den Anker gilt immer die Identität.
LUT_PARAMS = {
    "hafen": {"g_l": 0.5, "g_ab": 0.6, "snap": 0.5},
    "leuchtturm": {"g_l": 0.5, "g_ab": 0.6, "snap": 0.5},
    "stube": {"g_l": 0.5, "g_ab": 0.6, "snap": 0.5},
    "klippe": {"g_l": 0.5, "g_ab": 0.6, "snap": 0.5},
}
N_LUT = 32
PAL_COLORS = 24


PLACEHOLDERS = {}        # Ausgabe in demo/art -> Grund (nur für Platzhalter-Läufe)
PRODUCED = []            # alle in diesem Lauf nach demo/art geschriebenen Namen


def show(path):
    path = pathlib.Path(path)
    return path.relative_to(SD) if SD in path.parents else path


def save(im, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, optimize=True)
    print(f"{show(path)}  {im.size[0]}x{im.size[1]}")


def both(im, name, real=True, why=""):
    """Asset in assets/ und als Kopie in demo/art/ ablegen; Platzhalter nur in demo/art/."""
    if real:
        save(im, ASSETS / name)
        PLACEHOLDERS.pop(name, None)
    else:
        PLACEHOLDERS[name] = why or "Platzhalter"
    PRODUCED.append(name)
    save(im, ART / name)


def report_dir(real):
    """Berichte aus echten Bildern nach assets/, sonst in den Temp-Ordner des Eintrags."""
    d = ASSETS if real else TMP
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(show(path))


# ---------------------------------------------------------------------------------------------------------------
# Rauschen
# ---------------------------------------------------------------------------------------------------------------
def value_noise(h, w, cells, rng):
    g = rng.random((cells + 1, int(cells * w / h) + 2)).astype(np.float32)
    im = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return np.asarray(im, np.float32) / 255


def fbm(h, w, rng, base=4, octaves=5, gain=0.55):
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        out += amp * value_noise(h, w, base * 2 ** o, rng)
        tot += amp
        amp *= gain
    out /= tot
    return (out - out.min()) / (out.max() - out.min() + 1e-6)


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def rgba(rgb, alpha):
    a = np.dstack([np.broadcast_to(np.asarray(rgb, np.float32), alpha.shape + (3,)), alpha * 255])
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA")


# ---------------------------------------------------------------------------------------------------------------
# fx: Effekt-Texturen
# ---------------------------------------------------------------------------------------------------------------
def wash_blob(size, rng, rim=0.18, edge_noise=0.22, falloff=1.6, scale=0.8):
    """Aquarell-Fleck: weicher Kern, unregelmäßiger Rand mit dunklerem Trockenrand, Granulation."""
    s = size
    y, x = np.mgrid[0:s, 0:s].astype(np.float32)
    r = np.hypot(x - s / 2 + 0.5, y - s / 2 + 0.5) / (s / 2)
    r_n = r / scale                                  # Fleck kleiner als die Textur, damit der Rand Platz hat
    n = fbm(s, s, rng, base=3, octaves=4)
    r_eff = r_n / (1 + edge_noise * (n - 0.5) * 2)
    body = (1 - smooth(0.0, 1.0, r_eff)) ** falloff
    ring = rim * np.exp(-((r_eff - 0.86) / 0.05) ** 2) * (r_eff < 1.0)
    grain = fbm(s, s, rng, base=24, octaves=2)
    a = (body + ring) * (0.82 + 0.18 * grain)
    a *= smooth(1.0, 0.86, r)                        # sicher transparent am Texturrand
    return np.clip(a, 0, 1)


def make_fx():
    rng = np.random.default_rng(20261010)
    fx = "fx/"
    both(rgba((255, 255, 255), wash_blob(256, rng, rim=0.04, edge_noise=0.12, falloff=1.8, scale=0.92)), fx + "glow.png")
    for i in range(3):
        both(rgba((255, 255, 255), wash_blob(128, rng, rim=0.25, edge_noise=0.35, falloff=0.9)), fx + f"smoke{i + 1}.png")
    # Leuchtturmstrahl: langer Keil, am Lampenhaus schmal, mit Granulationsstreifen in Längsrichtung
    bw, bh = 640, 160
    y, x = np.mgrid[0:bh, 0:bw].astype(np.float32)
    u = x / bw
    half = 0.08 + 0.92 * u                                # relative halbe Breite wächst mit der Länge
    v = np.abs(y - bh / 2 + 0.5) / (bh / 2) / np.maximum(half, 1e-3)
    rows = (rng.random((bh // 12, 1)) * 255).astype(np.uint8)         # ein Zufallswert je 12 Zeilen = weiche Längsstreifen
    streak = np.asarray(Image.fromarray(rows).resize((1, bh), Image.BICUBIC), np.float32) / 255
    a = (1 - smooth(0.55, 1.0, v)) * (1 - smooth(0.35, 1.0, u)) * smooth(0.0, 0.06, u)
    a *= (0.8 + 0.2 * streak) * (0.65 + 0.35 * fbm(bh, bw, rng, base=3, octaves=4))
    both(rgba((255, 255, 255), np.clip(a, 0, 1)), fx + "beam.png")
    # Glanzstrich auf Wasser: flache Ellipse mit Pinselende
    gw, gh = 48, 10
    y, x = np.mgrid[0:gh, 0:gw].astype(np.float32)
    e = np.hypot((x - gw / 2 + 0.5) / (gw / 2), (y - gh / 2 + 0.5) / (gh / 2))
    a = (1 - smooth(0.4, 1.0, e)) * (0.6 + 0.4 * value_noise(gh, gw, 2, rng))
    both(rgba((255, 255, 255), np.clip(a, 0, 1)), fx + "glint.png")
    # Möwe: drei Flügelstellungen als Pinselbogen, 4-fach überabgetastet
    frames = []
    for wing in (-0.55, 0.0, 0.45):
        S = 4
        im = Image.new("L", (64 * S, 32 * S), 0)
        d = ImageDraw.Draw(im)
        cx, cy = 32 * S, 18 * S
        for side in (-1, 1):
            pts = []
            for k in range(13):
                t = k / 12
                px = cx + side * t * 26 * S
                py = cy - wing * 14 * S * np.sin(t * np.pi * 0.9) - (1 - wing) * 3 * S * t * t + 5 * S * t * t * (wing > 0.3)
                pts.append((px, py))
            for k in range(len(pts) - 1):
                wdt = int((3.6 - 2.6 * k / 12) * S)
                d.line([pts[k], pts[k + 1]], fill=255, width=max(S, wdt))
        d.ellipse([cx - 3 * S, cy - 2 * S, cx + 3 * S, cy + 2 * S], fill=255)
        im = im.resize((64, 32), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.4))
        frames.append(np.asarray(im, np.float32) / 255)
    strip = np.concatenate(frames, axis=1)
    both(rgba((40, 38, 62), strip), fx + "gull.png")
    # Flamme (Kamin, Kerze): vier Bilder, tropfenförmige Lasuren (Spitze oben, runder Fuß unten), Fußpunkt unten
    fl = []
    for i in range(4):
        fw, fh = 48, 80
        y, x = np.mgrid[0:fh, 0:fw].astype(np.float32)
        t = np.clip((y - 4) / (fh - 8), 0, 1)             # 0 Spitze, 1 Fuß
        lean = 0.78 + 0.1 * (1 + np.sin(i * 2.1))         # Höhe der Spitze schwankt je Bild (höchstens 0.98)
        t = np.clip(1 - (1 - t) / lean, 0, 1)
        sway = (2.5 + i % 2) * np.sin((1 - t) * 4.0 + i * 1.7) * (1 - t) ** 1.5
        prof = t ** 0.75 * np.sqrt(np.clip(1 - t, 0, 1)) / 0.431        # Tropfenprofil, Maximum 1 bei t = 0.6
        half = 15.0 * prof * (0.92 + 0.08 * np.cos(i * 1.3))
        d = np.abs(x - fw / 2 + 0.5 - sway) / np.maximum(half, 0.3)
        a = (1 - smooth(0.5, 1.0, d)) * (half > 0.3) * (0.75 + 0.25 * smooth(0.0, 0.5, t))
        core = (1 - smooth(0.0, 0.65, d)) * smooth(0.35, 0.85, t)
        tip = 1 - smooth(0.0, 0.4, t)                     # Spitze tiefer rot
        col = np.dstack([np.full_like(a, 255), 150 + 95 * core - 60 * tip, 50 + 130 * core - 30 * tip])
        im = np.dstack([col, a * 255]).clip(0, 255).astype(np.uint8)
        fl.append(im)
    both(Image.fromarray(np.concatenate(fl, axis=1), "RGBA"), fx + "flame.png")
    # Schatten unter der Figur
    both(rgba((40, 34, 70), wash_blob(128, rng, rim=0.1, edge_noise=0.15, falloff=1.2)), fx + "shadow.png")
    # Rauschen für die nasse Überblendung (Graustufen) und Papier für Seitenrückseite und Textbox
    n = fbm(360, 640, rng, base=3, octaves=6, gain=0.6)
    # Histogramm ausgleichen (Rang -> gleichverteilt), damit die Rauschmaske die Überblendung formt
    n = np.argsort(np.argsort(n.ravel())).reshape(n.shape) / (n.size - 1)
    save(Image.fromarray((n * 255).astype(np.uint8), "L"), ART / "noise.png")
    paper = paper_rgb(360, 640, rng)
    save(Image.fromarray(paper), ART / "paper.png")


def paper_rgb(h, w, rng, base=(236, 226, 204)):
    g = fbm(h, w, rng, base=6, octaves=5) - 0.5
    fine = rng.random((h, w)).astype(np.float32) - 0.5
    fibers = np.zeros((h, w), np.float32)
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    for _ in range(int(w * h / 900)):
        x0, y0 = rng.random() * w, rng.random() * h
        ang = rng.random() * np.pi
        ln = 4 + rng.random() * 12
        d.line([(x0, y0), (x0 + np.cos(ang) * ln, y0 + np.sin(ang) * ln)], fill=int(40 + rng.random() * 60), width=1)
    fibers = np.asarray(im.filter(ImageFilter.GaussianBlur(0.6)), np.float32) / 255
    lum = 1 + 0.07 * g + 0.035 * fine - 0.06 * fibers
    return (np.asarray(base, np.float32)[None, None] * lum[..., None]).clip(0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------------------------------------------
# ui: Papierkarte für die Textbox (mit Schatten-Rand)
# ---------------------------------------------------------------------------------------------------------------
UI_BOX = (24, 548, 1256, 704)         # Karte auf dem Bildschirm (x0, y0, x1, y1)
UI_PAD = 14                           # Rand für Schatten und ausgefranste Kante


def make_ui():
    rng = np.random.default_rng(7)
    x0, y0, x1, y1 = UI_BOX
    cw, ch = x1 - x0, y1 - y0
    w, h = cw + 2 * UI_PAD, ch + 2 * UI_PAD
    paper = paper_rgb(h, w, rng).astype(np.float32)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    # Abstand zum Kartenrand (negativ = innen), Rand mit Rauschen ausfransen
    dx = np.maximum(UI_PAD - x, x - (w - 1 - UI_PAD))
    dy = np.maximum(UI_PAD - y, y - (h - 1 - UI_PAD))
    dist = np.maximum(dx, dy)
    edge = (fbm(h, w, rng, base=40, octaves=3) - 0.5) * 5.0
    inside = smooth(1.2, -0.6, dist + edge)
    # Aquarell-Lasur am Rand (kühles Grau-Blau), ungleichmäßig, mit Trockenrand
    wash_n = fbm(h, w, rng, base=5, octaves=4)
    soft_edge = (fbm(h, w, rng, base=10, octaves=3) - 0.5) * 6.0
    band = smooth(-26 - 18 * wash_n, -4, dist + soft_edge)
    tide = np.exp(-((dist + soft_edge + 24 + 16 * wash_n) / 1.8) ** 2) * 0.18
    wash = np.asarray((118, 132, 160), np.float32)
    # senkrechter Pinselstrich als Trenner zwischen Text- und Antwortspalte (Kartenkoordinate x = 716)
    xd = UI_PAD + 716
    wob = (fbm(h, w, rng, base=6, octaves=3) - 0.5) * 3.0
    vy = np.clip((y - UI_PAD - 18) / (ch - 36), 0, 1)
    width = 1.6 + 1.2 * np.sin(vy * np.pi)                      # in der Mitte breiter, an den Enden spitz
    stroke = np.exp(-((x - xd - wob) / width) ** 2) * smooth(0.0, 0.12, vy) * smooth(1.0, 0.88, vy)
    stroke *= (y > UI_PAD + 18) & (y < h - UI_PAD - 18)
    k = (0.30 * band + tide + 0.35 * stroke)[..., None]
    rgb = paper * (1 - k) + wash * k * (paper / 236.0)
    # weicher Schatten nach rechts unten
    sh = Image.fromarray((inside * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5))
    sh = np.roll(np.asarray(sh, np.float32) / 255, (4, 3), (0, 1)) * 0.45
    a = np.maximum(inside, sh)
    col = rgb * inside[..., None] + np.asarray((20, 18, 34), np.float32) * (1 - inside[..., None])
    im = np.dstack([col, a * 255 * np.where(inside > 0.01, 0.94, 1.0)]).clip(0, 255).astype(np.uint8)
    both(Image.fromarray(im, "RGBA"), "ui/textbox.png")


# ---------------------------------------------------------------------------------------------------------------
# bg: Hintergründe
# ---------------------------------------------------------------------------------------------------------------
def raw_path(loc):
    p = RAW / f"{loc}.png"
    return p if p.exists() else None


def is_real(loc):
    """Echt heißt: Rohbild aus genimg in assets/raw/ (nicht --raw, nicht Platzhalter)."""
    return RAW == RAW_DEFAULT and (RAW_DEFAULT / f"{loc}.png").exists()


def crop_y(loc, height):
    return int(min(max(0, round(CROP_TOP[loc] * height)), height - H))


def scaled(loc):
    src = Image.open(raw_path(loc)).convert("RGB")
    return src.resize((W, round(src.height * W / src.width)), Image.LANCZOS)


def make_bg():
    for loc in LOCS:
        if raw_path(loc) is None:
            print(f"ACHTUNG fehlt: {RAW / (loc + '.png')} – beschrifteter Platzhalter")
            both(placeholder(loc), f"bg_{loc}.png", real=False, why=f"fehlt: assets/raw/{loc}.png")
            continue
        im = scaled(loc)
        if im.height < H:
            raise SystemExit(f"{raw_path(loc)}: zu flach für 1280x720 ({im.size})")
        y = crop_y(loc, im.height)
        print(f"{loc}: {raw_path(loc).name} -> {im.width}x{im.height}, Ausschnitt ab y={y}")
        both(im.crop((0, y, W, y + H)), f"bg_{loc}.png", real=is_real(loc), why=f"Ersatzbild {raw_path(loc)}")


def screen_row(frac, loc="hafen", height=853):
    """Zeile im 1280x720-Ausschnitt für einen Anteil der Bildhöhe (Bildaufbau laut Prompt)."""
    return round(frac * height) - crop_y(loc, height)


def placeholder(loc):
    """Beschrifteter Platzhalter mit den Hilfslinien des verlangten Bildaufbaus (Augenhöhe, Laufstreifen)."""
    rng = np.random.default_rng(LOCS.index(loc))
    top = np.array([[40, 50, 90], [60, 50, 40], [70, 55, 45], [40, 60, 90]][LOCS.index(loc)], np.float32)
    bot = np.array([[200, 120, 70], [150, 120, 90], [170, 120, 80], [110, 130, 90]][LOCS.index(loc)], np.float32)
    t = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    img = top * (1 - t) + bot * t + 30 * (fbm(H, W, rng)[..., None] - 0.5)
    im = Image.fromarray(np.broadcast_to(img, (H, W, 3)).clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    eye = screen_row(LAYOUT["eye"], loc)
    w0, w1 = (screen_row(f, loc) for f in LAYOUT["walk"])
    d.rectangle([0, w0, W, w1], outline=(240, 230, 200), width=2)
    d.line([0, eye, W, eye], fill=(255, 200, 120), width=2)
    font = ImageFont.load_default(size=40)
    small = ImageFont.load_default(size=22)
    d.text((40, 60), f"PLATZHALTER  {loc}", font=font, fill=(255, 245, 225))
    d.text((40, 112), "wartet auf assets/raw/%s.png (image_jobs.json)" % loc, font=small, fill=(255, 245, 225))
    d.text((40, eye - 30), "Augenhoehe / Horizont 40 %", font=small, fill=(255, 220, 160))
    d.text((40, w0 + 8), "Laufstreifen 58-72 %", font=small, fill=(240, 230, 200))
    return im


# ---------------------------------------------------------------------------------------------------------------
# lut: Farbabgleich auf die Palette des Ankers
# ---------------------------------------------------------------------------------------------------------------
M_RGB2XYZ = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                      [0.0193339, 0.1191920, 0.9503041]])
WHITE = np.array([0.95047, 1.0, 1.08883])


def srgb_to_lab(rgb):
    c = np.asarray(rgb, np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = lin @ M_RGB2XYZ.T / WHITE
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def lab_to_srgb(lab):
    fy = (lab[..., 0] + 16) / 116
    fx = fy + lab[..., 1] / 500
    fz = fy - lab[..., 2] / 200
    f = np.stack([fx, fy, fz], -1)
    xyz = np.where(f ** 3 > 216 / 24389, f ** 3, (116 * f - 16) / (24389 / 27)) * WHITE
    lin = xyz @ np.linalg.inv(M_RGB2XYZ).T
    lin = np.clip(lin, 0, 1)
    c = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
    return np.clip(c * 255, 0, 255)


def palette_of(path, n):
    """Palette über tools/sprites.py palette (Median Cut), wie im Auftrag verlangt. PNG im Temp-Ordner."""
    TMP.mkdir(parents=True, exist_ok=True)
    out = TMP / f"_pal_{path.stem}.png"
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "sprites.py"), "palette", str(path), str(out),
                        "--colors", str(n)], capture_output=True, text=True, check=True)
    hexes = r.stdout.split()
    return np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in hexes], np.float64), out


def lab_stats(lab):
    flat = lab.reshape(-1, 3)
    return flat.mean(0), flat.std(0)


def transform_lab(lab, src_stats, dst_stats, pal_lab, p):
    """Globaler Abgleich (Mittelwert/Streuung) und weicher Zug zur Ankerpalette, beides teilweise."""
    (ms, ss), (md, sd) = src_stats, dst_stats
    g = np.array([p["g_l"], p["g_ab"], p["g_ab"]])
    full = (lab - ms) * (sd / np.maximum(ss, 1e-3)) + md
    out = lab + g * (full - lab)
    # Palettenzug: gewichteter Mittelwert der Ankerfarben (Gauß in Lab), L nur halb so stark
    d2 = ((out[..., None, :] - pal_lab) ** 2).sum(-1)
    w = np.exp(-(d2 - d2.min(-1, keepdims=True)) / (2 * 10.0 ** 2))
    target = (w[..., None] * pal_lab).sum(-2) / w.sum(-1, keepdims=True)
    k = p["snap"] * np.array([0.4, 1.0, 1.0])
    return out + k * (target - out)


def build_lut(params, src_stats, dst_stats, pal_lab):
    n = N_LUT
    v = np.arange(n) / (n - 1) * 255
    b, g, r = np.meshgrid(v, v, v, indexing="ij")            # Achsen: b (Scheibe), g (Zeile), r (Spalte)
    rgb = np.stack([r, g, b], -1)
    if params is None:
        out = rgb
    else:
        out = lab_to_srgb(transform_lab(srgb_to_lab(rgb), src_stats, dst_stats, pal_lab, params))
    # Streifen: Scheibe b liegt bei x = b*n .. b*n+n-1, Zeile = g, Spalte = r
    strip = out.transpose(1, 0, 2, 3).reshape(n, n * n, 3)
    return np.round(strip).clip(0, 255).astype(np.uint8)


def apply_lut(rgb, strip):
    """Wie im Shader: trilineare Abtastung des Streifens (für Messungen und das Vergleichsbild)."""
    n = N_LUT
    lut = strip.astype(np.float64).reshape(n, n, n, 3).transpose(1, 0, 2, 3)  # [b, g, r]
    c = np.asarray(rgb, np.float64) / 255 * (n - 1)
    i0 = np.floor(c).astype(int).clip(0, n - 2)
    f = c - i0
    out = np.zeros(c.shape)
    for db in (0, 1):
        for dg in (0, 1):
            for dr in (0, 1):
                wgt = ((f[..., 2] if db else 1 - f[..., 2]) * (f[..., 1] if dg else 1 - f[..., 1])
                       * (f[..., 0] if dr else 1 - f[..., 0]))
                out += wgt[..., None] * lut[i0[..., 2] + db, i0[..., 1] + dg, i0[..., 0] + dr]
    return out


def palette_distance(img_rgb, pal_lab, n=16):
    """Mittlerer Abstand (ΔE76) jedes Bildpixels zur nächsten Ankerfarbe, auf 1/4 verkleinert."""
    small = np.asarray(Image.fromarray(img_rgb.astype(np.uint8)).resize((W // 4, H // 4), Image.BOX), np.float64)
    lab = srgb_to_lab(small).reshape(-1, 3)
    d = np.sqrt(((lab[:, None, :] - pal_lab[None]) ** 2).sum(-1)).min(1)
    return float(d.mean()), float(np.percentile(d, 90))


def texture_energy(img_rgb):
    """Anteil feiner Struktur: mittlere Helligkeitsabweichung vom 3-px-Weichzeichner (Pinsel/Papier-Maß)."""
    lum = Image.fromarray(img_rgb.astype(np.uint8)).convert("L")
    a = np.asarray(lum, np.float64)
    b = np.asarray(lum.filter(ImageFilter.GaussianBlur(3)), np.float64)
    return float(np.abs(a - b).mean())


EXTERIOR = {"hafen", "klippe"}


def horizon_row(img_rgb):
    """Horizont als die Zeile mit dem stärksten waagerechten Hell-Dunkel-Sprung über die ganze Bildbreite
    (Median über die Spalten, damit nur durchgehende Kanten zählen), gesucht in den Zeilen 120–400."""
    lab = srgb_to_lab(img_rgb[:, ::4])
    L = lab[..., 0]
    g = np.abs(L[4:] - L[:-4])                        # Sprung über 4 Zeilen
    med = np.median(g, axis=1)
    med = np.convolve(med, np.ones(5) / 5, mode="same")
    y0, y1 = 120, 400
    k = int(np.argmax(med[y0:y1])) + y0 + 2
    return k, round(float(med[k - 2]), 1)


def look_metrics(img_rgb):
    """Kennzahlen für die Stildrift: Lichtrichtung, Buntheit, warme Lichtinseln (alles über der Textbox)."""
    top = img_rgb[:UI_TOP]
    lab = srgb_to_lab(top[::2, ::2])
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    third = L.shape[1] // 3
    chroma = np.hypot(a, b)
    hue = np.degrees(np.arctan2(b, a)) % 360
    warm_light = (L > 60) & (chroma > 25) & (hue > 30) & (hue < 95)
    return {
        "L_mean": round(float(L.mean()), 1),
        "L_left_minus_right": round(float(L[:, :third].mean() - L[:, -third:].mean()), 1),
        "chroma_mean": round(float(chroma.mean()), 1),
        "warm_light_share": round(float(warm_light.mean()), 4),
        "dark_share_L_lt_20": round(float((L < 20).mean()), 3),
    }


def make_lut():
    bgs = {loc: np.asarray(Image.open(ART / f"bg_{loc}.png").convert("RGB"), np.float64) for loc in LOCS}
    anchor_real = is_real(ANCHOR)
    rep = report_dir(anchor_real and all(is_real(l) for l in LOCS))
    anchor_path = ART / f"bg_{ANCHOR}.png"
    pal, pal_png = palette_of(anchor_path, PAL_COLORS)
    pal_lab = srgb_to_lab(pal)
    Image.open(pal_png).save(rep / "palette_anchor.png")
    print("Ankerpalette:", " ".join("%02x%02x%02x" % tuple(int(v) for v in c) for c in pal))
    dst_stats = lab_stats(srgb_to_lab(bgs[ANCHOR][::4, ::4]))
    report = {"anchor": ANCHOR, "palette_anchor": ["%02x%02x%02x" % tuple(int(v) for v in c) for c in pal],
              "sources": {loc: ("assets/raw/%s.png" % loc if is_real(loc) else
                                str(raw_path(loc)) if raw_path(loc) else "Platzhalter") for loc in LOCS},
              "layout_rows_expected": {"eye": screen_row(LAYOUT["eye"]),
                                       "walk": [screen_row(f) for f in LAYOUT["walk"]], "ui_top": UI_TOP},
              "locations": {}}
    rows = []
    for loc in LOCS:
        img = bgs[loc]
        real = anchor_real and is_real(loc)
        src_stats = lab_stats(srgb_to_lab(img[::4, ::4]))
        params = None if loc == ANCHOR else LUT_PARAMS[loc]
        strip = build_lut(params, src_stats, dst_stats, pal_lab)
        both(Image.fromarray(strip), f"lut/lut_{loc}.png", real=real,
             why="LUT aus Platzhalter oder Ersatzbild")
        graded = apply_lut(img, strip)
        st_after = lab_stats(srgb_to_lab(graded[::4, ::4]))
        pd0, pd0_90 = palette_distance(img, pal_lab)
        pd1, pd1_90 = palette_distance(graded, pal_lab)
        diff = np.sqrt(((srgb_to_lab(img[::4, ::4]) - srgb_to_lab(graded[::4, ::4])) ** 2).sum(-1))
        r = {
            "lab_mean_before": [round(float(v), 1) for v in src_stats[0]],
            "lab_std_before": [round(float(v), 1) for v in src_stats[1]],
            "lab_mean_after": [round(float(v), 1) for v in st_after[0]],
            "lab_std_after": [round(float(v), 1) for v in st_after[1]],
            "mean_dE_to_anchor_mean_before": round(float(np.linalg.norm(src_stats[0] - dst_stats[0])), 1),
            "mean_dE_to_anchor_mean_after": round(float(np.linalg.norm(st_after[0] - dst_stats[0])), 1),
            "palette_dE_mean_before": round(pd0, 1), "palette_dE_p90_before": round(pd0_90, 1),
            "palette_dE_mean_after": round(pd1, 1), "palette_dE_p90_after": round(pd1_90, 1),
            "lut_change_dE_mean": round(float(diff.mean()), 1),
            "lut_changed_share_dE_gt_5": round(float((diff > 5).mean()), 3),
            "texture_energy": round(texture_energy(img), 2),
            "look_before": look_metrics(img),
            "look_after": look_metrics(graded),
            "params": params,
        }
        if loc in EXTERIOR:
            r["horizon_row"], r["horizon_edge"] = horizon_row(img)
        report["locations"][loc] = r
        rows.append((loc, img, graded))
    write_json(rep / "drift.json", report)
    for loc, r in report["locations"].items():
        print(f"{loc:11} ΔE Mittel zum Anker {r['mean_dE_to_anchor_mean_before']:5} -> {r['mean_dE_to_anchor_mean_after']:5}"
              f"  Palette ΔE {r['palette_dE_mean_before']:5} -> {r['palette_dE_mean_after']:5}"
              f"  Textur {r['texture_energy']:5}  Licht l-r {r['look_before']['L_left_minus_right']:5}"
              + (f"  Horizont y={r['horizon_row']}" if "horizon_row" in r else ""))
    # Vergleichsbild: links roh, rechts nach LUT, je Ort eine Zeile, Ankerpalette oben
    tw, th = 480, 270
    sheet = Image.new("RGB", (tw * 2 + 30, th * len(rows) + 40 + 10 * len(rows)), (24, 22, 30))
    palimg = Image.open(rep / "palette_anchor.png").resize((tw * 2 + 10, 24), Image.NEAREST)
    sheet.paste(palimg, (10, 8))
    for i, (loc, a, b) in enumerate(rows):
        y = 40 + i * (th + 10)
        sheet.paste(Image.fromarray(a.astype(np.uint8)).resize((tw, th), Image.LANCZOS), (10, y))
        sheet.paste(Image.fromarray(b.round().astype(np.uint8)).resize((tw, th), Image.LANCZOS), (20 + tw, y))
    save(sheet, rep / "lut_compare.png")
    # Serienblatt: die vier Orte nach dem Farbabgleich als 2x2, Hilfslinien für Augenhöhe und Laufstreifen
    tw, th = 640, 360
    grid = Image.new("RGB", (tw * 2 + 6, th * 2 + 6), (24, 22, 30))
    for i, (loc, a, b) in enumerate(rows):
        cell = Image.fromarray(b.round().astype(np.uint8)).resize((tw, th), Image.LANCZOS)
        d = ImageDraw.Draw(cell)
        for yy, col in ((screen_row(LAYOUT["eye"]), (255, 200, 120)),
                        (screen_row(LAYOUT["walk"][0]), (240, 230, 200)),
                        (screen_row(LAYOUT["walk"][1]), (240, 230, 200)), (UI_TOP, (120, 200, 255))):
            for x in range(0, tw, 12):
                d.line([x, yy // 2, x + 5, yy // 2], fill=col, width=1)
        grid.paste(cell, ((i % 2) * (tw + 6), (i // 2) * (th + 6)))
    save(grid, rep / "series_sheet.png")


# ---------------------------------------------------------------------------------------------------------------
# walk: Laufzyklus
# ---------------------------------------------------------------------------------------------------------------
BADGER_H = 140            # Zielhöhe der Figur auf dem Bildschirm (Pixel): auf der Kaikante etwa 1,7 Fässer hoch
# Reihenfolge der Bilder im Zyklus (None = wie im Blatt); nach Sichtung des Codex-Blatts gesetzt. Das Blatt ist kein
# sauberer Zyklus: 0 und 4 sind beide Kontakt (Schritt weit, beide Füße am Boden), 1 hebt das hintere Bein, 2 ist
# der Durchgang (hinteres Bein hoch), 3 holt mit dem vorderen Fuß hoch aus, 5 setzt ihn tief an. Die Beine sind
# gleich gefärbt, also reicht ein Schritt als Zyklus. Gemessen (Standfuß, 140 px): mit 5 als Ansetzen rutscht der
# Körper beim Wechsel 3 -> 5 um 2,5 px zurück, mit 4 statt 0 als Kontakt ebenso (4 -> 0: -1,5 px). Deshalb nur
# Kontakt, Abheben, Durchgang, Ausholen; alle Vorschübe sind dann vorwärts (15 / 6,5 / 30 / 2 px).
WALK_ORDER = [0, 1, 2, 3]
# Stehbild aus Teilen: Das Blatt hat keine Pose mit beiden Füßen beieinander. Aus dem Durchgang (Bild "from",
# Standbein senkrecht) wird das erhobene hintere Bein abgeschnitten (unterhalb cut_y links vom Standbein, in
# Pixeln des Rohblatts) und durch eine Kopie des Standbeins (ab copy_y) ersetzt, die um dx versetzt und abgedunkelt
# dahinter liegt (fernes Bein). Der Standfuß bleibt, deshalb ersetzt das Stehbild beim Anhalten den Durchgang ohne Fußsprung.
WALK_STAND = {"from": 2, "cut_x": 612, "cut_y": 648, "copy_y": 610, "dx": -40, "dark": 0.78}
WALK_SNAP = 0.0           # Zug der Kostümfarben zur Ankerpalette (0 = aus)


def label_components(mask):
    """Zusammenhangskomponenten (8er-Nachbarschaft) per Breitensuche; mask ist klein (verkleinert)."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    cur = 0
    for y0, x0 in zip(*np.nonzero(mask)):
        if lab[y0, x0]:
            continue
        cur += 1
        stack = [(y0, x0)]
        lab[y0, x0] = cur
        while stack:
            y, x = stack.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = cur
                        stack.append((yy, xx))
    return lab


def clean_alpha(rgba_arr, lo=40, hi=200, bleed=4):
    a = rgba_arr.astype(np.float32)
    al = np.clip((a[..., 3] - lo) / (hi - lo), 0, 1) * 255
    rgb = a[..., :3].copy()
    known = al > 127
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
    return np.dstack([rgb, al]).clip(0, 255).astype(np.uint8)


WALK_FALLBACK = False     # --walk-fallback: walk_painted.png bewusst als echtes Ergebnis übernehmen
KEY = np.array([255, 0, 255], np.float32)   # Schlüsselfarbe des Laufzyklus-Auftrags (key_color ff00ff)


def walk_source():
    p = RAW / "walk.png"
    if p.exists():
        return p, RAW == RAW_DEFAULT
    src = ROOT / "shared" / "badger" / "walk_painted.png"
    if WALK_FALLBACK:
        print("ACHTUNG walk: assets/raw/walk.png fehlt, nehme bewusst shared/badger/walk_painted.png (--walk-fallback)")
        return src, True
    print("ACHTUNG walk: assets/raw/walk.png fehlt, nehme shared/badger/walk_painted.png als Platzhalter")
    return src, False


def despill(rgba_arr, width=3):
    """Magenta-Saum am Rand entfernen: in einem Randstreifen den Überschuss min(R,B)-G abziehen."""
    a = rgba_arr.astype(np.float32)
    al = a[..., 3]
    outside = Image.fromarray(((al < 128) * 255).astype(np.uint8))
    near = np.asarray(outside.filter(ImageFilter.MaxFilter(2 * width + 1)), np.uint8) > 0
    edge = near & (al > 0)
    rgb = a[..., :3]
    excess = np.clip(np.minimum(rgb[..., 0], rgb[..., 2]) - rgb[..., 1], 0, None)
    excess *= edge
    rgb[..., 0] -= excess
    rgb[..., 2] -= excess
    return np.dstack([rgb, al]).clip(0, 255).astype(np.uint8), int(edge.sum()), float(excess[edge].mean()) if edge.any() else 0.0


def band_shift(a, b, smax):
    """Vorschub s (Pixel) für den Bildwechsel a -> b aus den Fußzeilen (Bänder, bool, gleiche Breite):
    Der Standfuß bleibt am Boden stehen, also gilt b[x] = a[x + s]. Gesucht wird das s mit der größten
    Überdeckung; bei einer Hochebene die Mitte. Gibt (s, Überdeckung relativ zum kleineren Band) zurück."""
    fw = a.shape[1]
    shifts = list(range(-3, smax + 1))
    score = []
    for s in shifts:
        if s >= 0:
            score.append(int((a[:, s:] & b[:, :fw - s]).sum()))
        else:
            score.append(int((a[:, :fw + s] & b[:, -s:]).sum()))
    score = np.array(score, np.float64)
    k = int(np.argmax(score))
    top = score[k]
    lo = hi = k
    while lo > 0 and score[lo - 1] >= 0.98 * top:
        lo -= 1
    while hi < len(score) - 1 and score[hi + 1] >= 0.98 * top:
        hi += 1
    s = (shifts[lo] + shifts[hi]) / 2
    denom = max(1, min(a.sum(), b.sum()))
    return float(s), float(top / denom)


def was_keyed(src):
    """Nur agy stellt über eine Schlüsselfarbe frei (.json hat dann "transparency", daneben <name>.keyed-src.png).
    Codex liefert echten Alphakanal; dort gibt es keinen Magenta-Saum, der Randabzug würde nur echte Farben
    (bläuliches Grau, Violett) am Rand verfälschen."""
    if src.with_name(src.stem + ".keyed-src.png").exists():
        return True
    try:
        meta = json.loads(src.with_suffix(".json").read_text())
    except (OSError, ValueError):
        return True                                   # unbekannte Herkunft: vorsichtshalber wie bisher
    return "transparency" in meta or meta.get("backend") == "agy"


def stand_source(im, box, cfg):
    """Rohblatt mit Stehbild an der Stelle der Figur `box`: erhobenes Bein weg, Standbein versetzt dahinter.
    Ab cut_y trennt je Zeile eine Grenze die Beine: Hat die Zeile zwei oder mehr deckende Abschnitte, beginnt das
    Standbein mit dem rechten, sonst bei cut_x. Links davon wird gelöscht. Die Kopie des Standbeins beginnt schon bei
    copy_y, damit ihre Oberkante hinter dem Rumpf verschwindet, und liegt um dx versetzt und abgedunkelt hinten."""
    x0, y0, x1, y1, _ = box
    X0, X1 = max(0, x0 - 8), min(im.shape[1], x1 + 8)
    out = im.astype(np.float32).copy()
    al = im[..., 3] > 128
    remove = np.zeros(im.shape[:2], bool)
    sel = np.zeros(im.shape[:2], bool)
    for y in range(cfg["copy_y"], min(im.shape[0], y1 + 8)):
        cols = np.nonzero(al[y, X0:X1])[0] + X0
        bound = cfg["cut_x"]
        if len(cols):
            starts = [cols[0]] + [c for p_, c in zip(cols[:-1], cols[1:]) if c != p_ + 1]
            if len(starts) >= 2 and y >= cfg["cut_y"]:
                bound = starts[-1]
        sel[y, bound:X1] = True
        if y >= cfg["cut_y"]:
            remove[y, X0:bound] = True
    out[..., 3][remove] = 0                                            # erhobenes Bein entfernen
    leg = np.zeros_like(out)
    leg[sel] = im[sel]
    leg = np.roll(leg, cfg["dx"], axis=1)                              # Standbein als fernes Bein versetzen
    leg[..., :3] *= np.array([cfg["dark"], cfg["dark"], cfg["dark"] * 1.06])   # abgedunkelt, leicht kühl
    a_f = out[..., 3:4] / 255.0                                        # vorhandene Figur liegt vorn
    a_l = leg[..., 3:4] / 255.0
    a = a_f + a_l * (1 - a_f)
    rgb = (out[..., :3] * a_f + leg[..., :3] * a_l * (1 - a_f)) / np.maximum(a, 1e-6)
    res = np.dstack([rgb, a * 255]).clip(0, 255).astype(np.uint8)
    return res, (leg[..., 3] > 0)


def make_walk():
    src, real = walk_source()
    keyed = was_keyed(src)
    print(f"walk: {'Schlüsselfarbe (agy), Magenta-Saum wird entfernt' if keyed else 'echter Alphakanal, kein Saumabzug'}")
    im = np.asarray(Image.open(src).convert("RGBA"))
    sc = 4
    small = np.asarray(Image.fromarray(im[..., 3]).resize((im.shape[1] // sc, im.shape[0] // sc), Image.BOX)) > 60
    lab = label_components(small)
    ids, counts = np.unique(lab[lab > 0], return_counts=True)
    big = [i for i, c in zip(ids, counts) if c > counts.max() * 0.25]
    boxes = []
    for i in big:
        ys, xs = np.nonzero(lab == i)
        boxes.append((xs.min() * sc, ys.min() * sc, (xs.max() + 1) * sc, (ys.max() + 1) * sc, i))
    boxes.sort(key=lambda b: b[0])
    print(f"walk: {len(boxes)} Figuren in {src.name} ({'echt' if real else 'Platzhalter'})")
    if len(boxes) != 6:
        print(f"ACHTUNG walk: {len(boxes)} statt 6 Figuren gefunden – Blatt ansehen")
    frames, spill = [], []
    jobs = [(b, im, None) for b in boxes]
    stand = None
    if WALK_STAND and real and len(boxes) > WALK_STAND["from"]:
        st_im, st_added = stand_source(im, boxes[WALK_STAND["from"]], WALK_STAND)
        jobs.append((boxes[WALK_STAND["from"]], st_im, st_added))
        stand = len(boxes)                            # Index des Stehbilds unter den Einzelbildern
    for (x0, y0, x1, y1, i), src_im, added in jobs:
        pad = 8
        X0, Y0, X1, Y1 = max(0, x0 - pad), max(0, y0 - pad), min(im.shape[1], x1 + pad), min(im.shape[0], y1 + pad)
        crop = src_im[Y0:Y1, X0:X1].copy()
        # Pixel anderer Figuren ausblenden (nur die eigene Komponente, großzügig gedehnt)
        own = np.kron(lab[Y0 // sc:(Y1 + sc - 1) // sc, X0 // sc:(X1 + sc - 1) // sc] == i,
                      np.ones((sc, sc), bool))[:crop.shape[0], :crop.shape[1]]
        own = np.asarray(Image.fromarray(own.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(9))) > 0
        if added is not None:
            own |= added[Y0:Y1, X0:X1]                # das versetzte ferne Bein gehört dazu
        crop[..., 3][~own] = 0
        if keyed:
            crop, n_edge, mean_ex = despill(crop)
            spill.append(round(mean_ex, 1))
        a = crop[..., 3] > 128
        ys, xs = np.nonzero(a)
        crop = crop[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        frames.append(clean_alpha(crop))
    if keyed:
        print(f"walk: Magenta-Überschuss im Randstreifen je Bild (Mittel, vor dem Entfernen): {spill}")
    hs = [f.shape[0] for f in frames]
    scale = BADGER_H / float(np.median(hs))
    order = WALK_ORDER or list(range(len(boxes)))
    # Verkleinern auf gemeinsamem Maßstab, ausrichten: x am Kopf (oberes Viertel), y an der Fußlinie
    small_frames, heads = [], []
    for f in frames:
        img = Image.fromarray(f, "RGBA")
        nw, nh = max(1, round(img.width * scale)), max(1, round(img.height * scale))
        # vormultipliziert verkleinern, damit transparente Pixel keine Farbe in den Rand ziehen
        arr = np.asarray(img, np.float32)
        pm = arr.copy(); pm[..., :3] *= arr[..., 3:4] / 255
        pm = np.asarray(Image.fromarray(pm.clip(0, 255).astype(np.uint8), "RGBA").resize((nw, nh), Image.LANCZOS), np.float32)
        al = np.asarray(Image.fromarray(f[..., 3]).resize((nw, nh), Image.LANCZOS), np.float32)
        rgb = np.minimum(pm[..., :3], al[..., None]) / np.maximum(al[..., None], 1) * 255   # Überschwinger begrenzen
        out = np.dstack([rgb, al]).clip(0, 255).astype(np.uint8)
        a = out[..., 3] > 128
        ys, xs = np.nonzero(a)
        top = ys.min(); hgt = ys.max() - top + 1
        q = a[top:top + max(1, hgt // 4)]
        hx = float(np.nonzero(q)[1].mean())
        small_frames.append(out)
        heads.append(hx)
    fw = int(max(f.shape[1] for f in small_frames) + 2 * 40)
    fh = int(max(f.shape[0] for f in small_frames) + 6)
    ax = fw // 2                      # Kopf-Mitte liegt in jedem Bild bei x = ax
    ay = fh - 3                       # Fußlinie (unterste deckende Zeile)
    n = len(order)
    sheet_idx = order + ([stand] if stand is not None else [])    # Stehbild liegt hinter dem Zyklus im Blatt
    sheet = np.zeros((fh, fw * len(sheet_idx), 4), np.uint8)
    for k, idx in enumerate(sheet_idx):
        f = small_frames[idx]
        ox = int(round(ax - heads[idx]))
        oy = ay - f.shape[0] + 1
        sheet[oy:oy + f.shape[0], k * fw + ox:k * fw + ox + f.shape[1]] = f
    if WALK_SNAP > 0:
        pal, _ = palette_of(ART / f"bg_{ANCHOR}.png", PAL_COLORS)
        rgb = sheet[..., :3].astype(np.float64)
        p = {"g_l": 0.0, "g_ab": 0.0, "snap": WALK_SNAP}
        st = (np.zeros(3), np.ones(3))
        sheet[..., :3] = lab_to_srgb(transform_lab(srgb_to_lab(rgb), st, st, srgb_to_lab(pal), p)).round().astype(np.uint8)
    # Vorschub je Bildwechsel aus dem Standfuß: Überdeckung der Fußzeilen (unterste `band` Zeilen) bei Verschiebung
    band = max(4, round(BADGER_H * 0.04))
    bands = [sheet[ay - band + 1:ay + 1, k * fw:(k + 1) * fw, 3] > 128 for k in range(n)]
    adv, fit = [], []
    for k in range(n):
        s, q = band_shift(bands[k], bands[(k + 1) % n], int(BADGER_H * 0.6))
        adv.append(s)
        fit.append(round(q, 2))
    weak = [k for k in range(n) if fit[k] < 0.35]
    if weak:
        good = [adv[k] for k in range(n) if k not in weak]
        med = float(np.median(good)) if good else BADGER_H / 6
        print(f"ACHTUNG walk: Standfuß bei Wechsel {weak} nicht sicher gefunden (Überdeckung {[fit[k] for k in weak]}),"
              f" nehme Median {med:.1f}")
        for k in weak:
            adv[k] = med
    for k in range(n):
        if abs(adv[k]) < 3:
            print(f"ACHTUNG walk: Wechsel {k}->{(k + 1) % n} fast ohne Vorschub ({adv[k]:.1f} px): Posen fast gleich,"
                  f" Bild aus WALK_ORDER nehmen?")
    # Stehbild: Bild mit der schmalsten Fußzeile (Füße beieinander), dort hält die Figur an
    spread = []
    for b in bands:
        cols = np.nonzero(b.any(0))[0]
        spread.append(int(cols.max() - cols.min() + 1) if len(cols) else 0)
    stop = int(np.argmin(spread))
    if stand is not None:
        stop = order.index(WALK_STAND["from"])        # angehalten wird dort, wo der Durchgang käme
    cycle_px = float(sum(adv))
    print(f"walk: Vorschub je Wechsel {[round(v, 1) for v in adv]} (Überdeckung {fit}), je Zyklus {cycle_px:.0f} px, "
          f"Fußzeilen-Breite {spread}, Stehbild {stop}")
    meta = {"frame_w": fw, "frame_h": fh, "count": len(sheet_idx), "anchor": [ax, ay], "cycle": list(range(n)),
            "advance": [round(v, 1) for v in adv], "advance_fit": fit, "foot_band_rows": band,
            "foot_spread": spread, "stop_frame": stop, "cycle_px": round(cycle_px, 1),
            "source": str(src.relative_to(ROOT)) if ROOT in src.parents else str(src),
            "real": real, "keyed": keyed, "scale": round(scale, 4), "order_in_sheet": order}
    if stand is not None:
        meta["stand_frame"] = n                       # Bild im Blatt, das beim Anhalten den Durchgang ersetzt
        meta["stand_from"] = dict(WALK_STAND)
    both(Image.fromarray(sheet, "RGBA"), "walk.png", real=real, why=f"Laufzyklus aus {src.name}")
    if real:
        write_json(ASSETS / "walk.json", meta)
    else:
        PLACEHOLDERS["walk.json"] = f"Laufzyklus aus {src.name}"
    PRODUCED.append("walk.json")
    write_json(ART / "walk.json", meta)


# ---------------------------------------------------------------------------------------------------------------
# layout: Layout-Referenz für den Laufzyklus-Auftrag
# ---------------------------------------------------------------------------------------------------------------
def make_layout():
    src = Image.open(ROOT / "shared" / "badger" / "walk_painted.png").convert("RGBA")
    w = src.width
    h = round(w * 2 / 3)
    bg = Image.new("RGBA", (w, h), (255, 0, 255, 255))
    bg.alpha_composite(src, (0, (h - src.height) // 2))
    save(bg.convert("RGB"), RAW_DEFAULT / "walk_layout_ref.png")


# ---------------------------------------------------------------------------------------------------------------
STEPS = {"layout": make_layout, "fx": make_fx, "ui": make_ui, "bg": make_bg, "lut": make_lut, "walk": make_walk}


def main():
    global RAW, WALK_FALLBACK
    import argparse
    ap = argparse.ArgumentParser(description="Asset-Aufbereitung hintergrund-serie")
    ap.add_argument("steps", nargs="*", default=["all"])
    ap.add_argument("--raw", help="Ersatzordner für Rohbilder (Test der Kette); Ergebnisse gelten als Platzhalter")
    ap.add_argument("--walk-fallback", action="store_true",
                    help="ohne raw/walk.png walk_painted.png als echtes Ergebnis übernehmen")
    a = ap.parse_args()
    if a.raw:
        RAW = pathlib.Path(a.raw).resolve()
    WALK_FALLBACK = a.walk_fallback
    steps = a.steps
    if "all" in steps:
        steps = ["fx", "ui", "bg", "lut", "walk"]
    for s in steps:
        if s not in STEPS:
            ap.error(f"unbekannter Schritt {s!r} (erlaubt: {', '.join(STEPS)}, all)")
    for s in steps:
        print(f"== {s}")
        STEPS[s]()
    # Platzhalter-Liste in demo/art fortschreiben (nur die in diesem Lauf erzeugten Namen ändern)
    pf = ART / "placeholders.json"
    try:
        known = json.loads(pf.read_text())
    except (OSError, ValueError):
        known = {}
    produced = set(PRODUCED)
    known = {k: v for k, v in known.items() if k not in produced}
    known.update(PLACEHOLDERS)
    pf.write_text(json.dumps(dict(sorted(known.items())), indent=1, ensure_ascii=False) + "\n")
    if known:
        print(f"ACHTUNG: {len(known)} Platzhalter in demo/art (siehe demo/art/placeholders.json):")
        for k, v in sorted(known.items()):
            print(f"  {k}: {v}")
    else:
        print("keine Platzhalter in demo/art")


if __name__ == "__main__":
    main()
