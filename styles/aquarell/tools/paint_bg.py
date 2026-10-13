#!/usr/bin/env python3
"""Aquarell-Hintergrund aus einem Blender-Rendering des gemeinsamen Hafens (Ausweichweg ohne Bildmodell).

    .venv/bin/python styles/aquarell/tools/paint_bg.py [--out assets/bg_3d.png]

Verfahren (angelehnt an Bousseau et al. 2006, „Interactive watercolor rendering with temporal coherence and
abstraction“): Himmel als Nass-in-Nass-Verlauf gemalt; Flächen je Objekt und Material vereinfacht (Mittelwert +
weicher lokaler Verlauf), Luftperspektive aus der Tiefe, Kanten durch Rauschen verworfen, Pigmentdichte mit
Wolken- und Körnungsrauschen moduliert, Trockenränder innen an jeder Fläche, Wasser waagerecht verwischt.
Ergebnis: deckendes Bild 1280x720 ohne Vignette (die legt finish_bg.py für alle Hintergründe gleich an).
"""
import argparse, json, pathlib
import numpy as np
from PIL import Image

import wc

ROOT = pathlib.Path(__file__).resolve().parents[1]
P = ROOT / "assets/raw/bg_passes"


def enc(x):
    x = np.asarray(x, dtype=np.float64)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def labels(idimg, table):
    names = list(table)
    cols = np.array([enc(np.array(table[k])) * 255 for k in names])
    rgb = idimg[..., :3].astype(np.float64)
    lab = np.full(rgb.shape[:2], -1, int)
    m = idimg[..., 3] > 0
    flat = rgb[m]
    best = np.zeros(len(flat), int)
    bestd = np.full(len(flat), 1e9)
    for i, c in enumerate(cols):
        d = ((flat - c) ** 2).sum(1)
        sel = d < bestd
        best[sel], bestd[sel] = i, d[sel]
    lab[m] = best
    return lab, names


# Malerpalette (sRGB im Licht) je Material des Hafenmodells
PALETTE = {
    "Stone": "#b4a9a2", "StoneDark": "#857c80", "Wood": "#a57552", "WoodDark": "#6b4c3a", "WhitePaint": "#efe9de",
    "RedPaint": "#c04a3c", "Roof": "#66708c", "Rope": "#c9b088", "Metal": "#555463", "Rock": "#988c88",
    "Sand": "#dcc6a0", "Grass": "#93a36a",
}


def sky(h, w, horizon, seed=3):
    """Abendhimmel nass in nass: oben Ultramarin-Violett, darunter Rosa, am Horizont ein warmes Band."""
    y = np.arange(h)[:, None] / horizon
    top, mid, low = wc.hexc("#a7a8cc"), wc.hexc("#dcbcc6"), wc.hexc("#f3c98f")
    Dt, Dm, Dl = wc.density(top), wc.density(mid), wc.density(low)
    k1 = wc.smoothstep(0.0, 0.62, y)[..., None]
    k2 = wc.smoothstep(0.6, 0.97, y)[..., None]
    D = Dt * (1 - k1) + Dm * k1
    D = D * (1 - k2) + Dl * k2
    n = wc.value_noise(h, w, 160, seed, 4)
    D = D * (0.8 + 0.4 * n)[..., None]
    # zwei, drei weiche Wolkenschleier tief am Himmel (die ziehenden Wolken kommen in Godot dazu)
    st = wc.value_noise(h, w, 90, seed + 1, 3, aniso=(5.0, 0.6))
    band = wc.smoothstep(0.55, 0.75, y) * (1 - wc.smoothstep(0.85, 0.95, y))
    D = D + (wc.smoothstep(0.55, 0.8, st) * band)[..., None] * wc.density(wc.hexc("#c9b2c4")) * 0.8
    return np.broadcast_to(D, (h, w, 3)).copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "assets/bg_3d.png"))
    a = ap.parse_args()
    info = json.loads((P / "cam.json").read_text())
    col = np.asarray(Image.open(P / "color.png").convert("RGBA")).astype(np.float64) / 255.0
    idi = np.asarray(Image.open(P / "id.png").convert("RGBA"))
    dep = np.asarray(Image.open(P / "depth.png")).astype(np.float64)
    dep = dep / (65535.0 if dep.max() > 255 else 255.0) * 400.0
    if dep.ndim == 3:
        dep = dep[..., 0]
    H, W = col.shape[:2]
    s = W / 1280
    lab, names = labels(idi, info["ids"])
    # Pflasterfugen gehören zur Pflasterfläche (sie werden später nur angedeutet)
    joint = names.index("Quay/StoneDark") if "Quay/StoneDark" in names else -1
    stone = names.index("Quay/Stone") if "Quay/Stone" in names else -1
    is_joint = lab == joint
    lab[is_joint] = stone
    # Randverwerfung: alle Ebenen mit demselben Feld verschieben
    wx = (wc.value_noise(H, W, 26 * s, 21, 3) - 0.5) * 6 * s
    wy = (wc.value_noise(H, W, 26 * s, 22, 3) - 0.5) * 6 * s
    lab = wc.warp(lab, wx, wy, order=0)
    is_joint = wc.warp(is_joint.astype(float), wx, wy) > 0.5
    rgb = wc.warp(col[..., :3], wx, wy)
    dep = wc.warp(dep, wx, wy, order=0)

    horizon = info["points"]["horizon_far"][1] * s
    D = sky(H, W, horizon)
    Dsky_full = D.copy()
    paper_l = wc.s2l(wc.PAPER)
    lin = wc.s2l(rgb)
    pig = wc.value_noise(H, W, 70 * s, 23, 4)
    gran = wc.value_noise(H, W, 4 * s, 24, 2)
    pig2 = wc.value_noise(H, W, 120 * s, 27, 3)
    haze = wc.density(wc.hexc("#d9c3cc"))
    streak = wc.value_noise(H, W, 30 * s, 25, 3, aniso=(8.0, 0.25))
    for i, nm in enumerate(names):
        m_full = lab == i
        if not m_full.any():
            continue
        ys, xs = np.where(m_full)
        pad = int(45 * s)
        y0, y1 = max(0, ys.min() - pad), min(H, ys.max() + pad + 1)
        x0, x1 = max(0, xs.min() - pad), min(W, xs.max() + pad + 1)
        sl = (slice(y0, y1), slice(x0, x1))
        m = m_full[sl]
        mf = m.astype(np.float64)
        L = lin[sl]
        # Vereinfachung: Mittelwert der Fläche + weicher lokaler Verlauf (normierte Faltung innerhalb der Fläche)
        num = wc.blur(L * mf[..., None], 14 * s)
        den = wc.blur(mf, 14 * s)[..., None]
        loc = num / np.maximum(den, 1e-4)
        mean = (L * mf[..., None]).sum((0, 1)) / mf.sum()
        c = 0.45 * mean + 0.55 * loc
        mat = nm.split("/")[1]
        if mat in PALETTE and nm != "Sea/Water":
            # Malerpalette statt Renderfarbe; das Licht (Helligkeit relativ zum Flächenmittel) bleibt erhalten
            lum = (c * [0.2126, 0.7152, 0.0722]).sum(-1, keepdims=True)
            mlum = float((mean * [0.2126, 0.7152, 0.0722]).sum())
            shade = np.clip(lum / max(mlum, 1e-4), 0.55, 1.35)
            pc = wc.s2l(wc.hexc(PALETTE[mat]))
            cool = wc.s2l(wc.hexc("#8d86b0"))
            sh = np.clip((0.95 - shade) / 0.4, 0, 1)
            c = pc * shade * (1 - 0.35 * sh) + cool * pc * 0.35 * sh * shade
        if nm.endswith("/Glass"):
            c = np.broadcast_to(wc.s2l(wc.hexc("#fbe7a6")), c.shape)
        Dr = -np.log(np.clip(c / paper_l, 1e-4, 1.0))
        # Luftperspektive: in der Ferne dünner und zum Dunst hin
        k = (1 - np.exp(-np.maximum(dep[sl] - 12, 0) / 45.0))[..., None]
        Dr = Dr * (1 - 0.65 * k) + haze * 0.5 * k
        mod = 0.85 + 0.3 * pig[sl]
        mod = mod * (1 + 0.5 * wc.inner_edge(mf, 3.5 * s))
        mod = mod * (1 + 0.08 * (gran[sl] - 0.5) * 2)
        if nm == "Sea/Water":
            # Wasser spiegelt den Himmel: gespiegelter Himmelsverlauf, etwas dunkler und kühler, mit Schlieren
            yy_ = np.arange(y0, y1)
            src = np.clip((2 * horizon - yy_).astype(int), 0, H - 1)
            Dsky = Dsky_full[src][:, x0:x1]
            Dr = Dsky * 1.15 + wc.density(wc.hexc("#c9c9e0")) * 0.6
            mod = (0.8 + 0.4 * streak[sl]) * (1 + 0.5 * wc.inner_edge(mf, 3.5 * s))
        if nm == "Quay/Stone":
            # Pflaster: nass in nass zwei Töne (Ocker und Violett), nach vorn heller und lockerer
            yy = (np.arange(y0, y1) / H)[:, None]
            v = pig2[sl][..., None]
            Dr = Dr * 0.7 + (wc.density(wc.hexc("#c9b49a")) * v + wc.density(wc.hexc("#a99fba")) * (1 - v)) * 0.55
            mod = mod * (1.0 - 0.45 * wc.smoothstep(0.66, 0.85, yy)) * (0.8 + 0.4 * pig2[sl])
        Dsl = D[sl]
        Dsl[m] = (Dr * mod[..., None])[m]
    # Pflasterfugen als vereinzelte trockene Pinselstriche
    jn = wc.value_noise(H, W, 18 * s, 26, 2)
    yy = np.arange(H)[:, None] / H
    jm = is_joint & (jn > 0.6) & (yy < 0.8)
    D = D + (wc.blur(jm.astype(float), 0.8 * s) * 0.3)[..., None] * wc.density(wc.hexc("#9f96a6"))
    # erste Sterne: ein paar Spritzer Abdecklack, nach dem Malen abgerieben (Papierweiß)
    rng = np.random.default_rng(31)
    yy, xx = np.mgrid[0:H, 0:W]
    for _ in range(14):
        cx, cy = rng.uniform(0.05, 0.95) * W, rng.uniform(0.04, 0.26) * H
        if lab[int(cy), int(cx)] >= 0:
            continue
        r = rng.uniform(1.2, 2.6) * s
        d = np.hypot(xx[int(cy - 8 * s):int(cy + 8 * s), int(cx - 8 * s):int(cx + 8 * s)] - cx,
                     yy[int(cy - 8 * s):int(cy + 8 * s), int(cx - 8 * s):int(cx + 8 * s)] - cy)
        sub = D[int(cy - 8 * s):int(cy + 8 * s), int(cx - 8 * s):int(cx + 8 * s)]
        sub *= (1 - 0.85 * wc.smoothstep(r + 0.8 * s, r - 0.8 * s, d))[..., None]
    out = paper_l * np.exp(-D)
    img = wc.to_srgb_image(out).resize((1280, 720), Image.LANCZOS)
    img.save(a.out)
    # Masken für Godot (1280x720): Himmel und Wasser
    labs = Image.fromarray((lab + 1).astype(np.int32)).resize((1280, 720), Image.NEAREST)
    lab_s = np.asarray(labs) - 1
    sky_m = (lab_s < 0).astype(np.uint8) * 255
    water = names.index("Sea/Water")
    wat_m = (lab_s == water).astype(np.uint8) * 255
    Image.fromarray(sky_m).save(ROOT / "assets/sky_mask_3d.png")
    Image.fromarray(wat_m).save(ROOT / "assets/water_mask_3d.png")
    print("ok", a.out)


if __name__ == "__main__":
    main()
