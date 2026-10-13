#!/usr/bin/env python3
"""Macht aus den Blender-Renderings (blender/render_sprites.py) Sprites in der 256er-Palette.

Je Zielpixel (Block von SUPER x SUPER Renderpixeln) entscheidet die Mehrheit der Materialien aus dem
ID-Durchgang; ist mehr als die Hälfte Hintergrund, bleibt das Pixel durchsichtig (Index 255, 1-Bit-Alpha).
Die Farbe ist der Mittelwert der Pixel dieses Materials im beleuchteten Durchgang, eingerastet nur in die
Rampe(n) des Materials (Weste bleibt grün, Schal rot; kein Farbrauschen an Materialgrenzen).

Ausgabe (8-Bit-Graustufen = Palettenindex):
  assets/sprites/badger_atlas.png   8 Spalten (Blickwinkel 0–7, 0 = von vorn, gegen den Uhrzeigersinn)
                                    x 7 Zeilen (walk0–3, idle0, wave0, wave1), Zelle 40 x 46, Fuß bei (20, 43)
  assets/sprites/<prop>.png         Fass, Taurolle, Poller, Laternenpfahl, Laternenglas (4 Bilder),
                                    Paket, Rauch (4 Bilder), Möwe (2 Bilder)
  assets/sprites/sprites.json       Größen und Fußpunkte

    python3 scripts/build_sprites.py --render <ordner mit den Renderings>
"""
import argparse
import json
import pathlib
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import rc_palette as P  # noqa: E402

ENTRY = pathlib.Path(__file__).resolve().parent.parent
OUT = ENTRY / "assets" / "sprites"
DEMO = ENTRY / "demo" / "sprites"

ID_COLORS = {
    "FurDark": (40, 40, 40), "FurLight": (255, 255, 255), "Cap": (0, 160, 0), "Brass": (255, 200, 0),
    "Vest": (0, 90, 40), "Shirt": (255, 230, 170), "Scarf": (230, 0, 0), "Satchel": (140, 70, 0),
    "Parcel": (220, 150, 80), "Nose": (0, 0, 0), "Eye": (0, 0, 255),
    "Wood": (160, 100, 50), "WoodDark": (90, 50, 20), "Metal": (60, 60, 90), "Rope": (200, 180, 120),
    "StoneDark": (100, 100, 100), "Glass": (255, 255, 0), "String": (250, 240, 200),
}
# Material -> erlaubte Rampen und Helligkeitsfaktor vor dem Einrasten
RAMPS = {
    "FurDark": (["grau", "nacht"], 1.0), "FurLight": (["creme", "granit"], 1.0), "Cap": (["gruen"], 1.05),
    "Brass": (["gelb", "orange"], 1.0), "Vest": (["gruen"], 1.1), "Shirt": (["creme"], 1.0),
    "Scarf": (["rot"], 1.0), "Satchel": (["rostbraun", "holz"], 1.0), "Parcel": (["holz"], 1.05),
    "Nose": (["nacht", "grau"], 1.0), "Eye": (["nacht", "grau"], 1.0),
    "Wood": (["holz"], 1.0), "WoodDark": (["holz", "rostbraun"], 1.0), "Metal": (["schiefer", "grau"], 1.0),
    "Rope": (["holz", "oliv"], 1.0), "StoneDark": (["grau", "granit"], 1.0), "Glass": (["gelb"], 1.0),
    "String": (["creme"], 1.0),
}
NAMES = list(ID_COLORS)
IDS = np.array([ID_COLORS[n] for n in NAMES], float)


def classify(id_img):
    a = np.asarray(id_img.convert("RGBA"), float)
    rgb, alpha = a[..., :3], a[..., 3]
    d = ((rgb[:, :, None, :] - IDS[None, None]) ** 2).sum(-1)
    m = d.argmin(-1)
    m[alpha < 128] = -1
    return m


def downsample(shade, id_img, cw, ch, K, keep=None):
    """-> Indexbild (ch, cw) mit 255 = durchsichtig, Materialkarte (ch, cw)."""
    mat = classify(id_img)
    sh = np.asarray(shade.convert("RGBA"), float)[..., :3]
    out = np.full((ch, cw), P.TRANSPARENT, np.uint8)
    mats = np.full((ch, cw), -1, int)
    for y in range(ch):
        for x in range(cw):
            blk = mat[y * K:(y + 1) * K, x * K:(x + 1) * K]
            if keep is not None:
                blk = np.where(np.isin(blk, keep), blk, -1)
            vals, cnt = np.unique(blk, return_counts=True)
            bg = cnt[vals == -1].sum() if (vals == -1).any() else 0
            if bg * 2 > K * K:
                continue
            sel = vals != -1
            m = vals[sel][cnt[sel].argmax()]
            px = sh[y * K:(y + 1) * K, x * K:(x + 1) * K][blk == m]
            name = NAMES[m]
            ramps, gain = RAMPS[name]
            col = np.clip(px.mean(0) * gain, 0, 255)
            out[y, x] = P.nearest_index(col[None], P.ramp_mask(ramps))[0]
            mats[y, x] = m
    return out, mats


def wood_detail(idx, mats, shade, idimg, cw, ch, K, name):
    """Holzteile mit dem Maserungsmuster der KI-Textur "tarboard" (senkrechte Bretter) überziehen:
    Helligkeit des Renderings x Muster, wieder in die Holzrampe eingerastet. Gibt Fass und Pfahl die
    Dauben- bzw. Brettstruktur, die in den Sprites der Zeit gemalt war."""
    tex = np.asarray(Image.open(ENTRY / "assets" / "textures" / "tarboard.png"))
    lumt = P.PALETTE[tex].astype(float).mean(-1)
    pat = (lumt - lumt.mean()) / (lumt.std() + 1e-6)
    sh = np.asarray(shade.convert("RGBA"), float)[..., :3]
    out = idx.copy()
    wood = [NAMES.index("Wood"), NAMES.index("WoodDark")]
    for y in range(ch):
        for x in range(cw):
            m = mats[y, x]
            if m not in wood:
                continue
            blk_ids = classify_cache(idimg)[y * K:(y + 1) * K, x * K:(x + 1) * K]
            px = sh[y * K:(y + 1) * K, x * K:(x + 1) * K][blk_ids == m]
            # Fass: Dauben laufen senkrecht -> Muster nach x (2 Texel je Brett-Texel), Pfahl: schmal
            u = (x * (2 if name == "barrel" else 1)) % 64
            v = (y * 2) % 64
            g = 1.0 + 0.22 * np.clip(pat[v, u], -2, 2)
            col = np.clip(px.mean(0) * g, 0, 255)
            out[y, x] = P.nearest_index(col[None], P.ramp_mask(RAMPS[NAMES[m]][0]))[0]
    return out


_CLS = {}


def classify_cache(id_img):
    k = id(id_img)
    if k not in _CLS:
        _CLS[k] = classify(id_img)
    return _CLS[k]


def to_rgb(idx):
    rgb = P.PALETTE[idx].copy()
    a = np.where(idx == P.TRANSPARENT, 0, 255).astype(np.uint8)
    return np.dstack([rgb, a])


def code_sprites():
    """Paket, Rauch, Möwe als kleine Pixelbilder per Code (Indexbilder)."""
    res = {}
    T = P.TRANSPARENT
    # Paket 12 x 10, Fußpunkt unten Mitte: braunes Papier mit Schnur, oben heller
    pk = np.full((10, 12), T, np.uint8)
    paper_top = P.nearest_index(np.array([[214, 172, 116]]), P.ramp_mask(["holz"]))[0]
    paper = P.nearest_index(np.array([[176, 128, 80]]), P.ramp_mask(["holz"]))[0]
    paper_dk = P.nearest_index(np.array([[120, 84, 52]]), P.ramp_mask(["holz"]))[0]
    string = P.nearest_index(np.array([[236, 226, 196]]), P.ramp_mask(["creme"]))[0]
    pk[1:4, 1:11] = paper_top
    pk[4:10, 1:11] = paper
    pk[4:10, 9:11] = paper_dk
    pk[0, 2:10] = paper_top
    pk[:, 5] = np.where(pk[:, 5] != T, string, T)
    pk[2, 1:11] = string
    pk[6, 1:11] = np.where(pk[6, 1:11] != T, string, T)
    pk[0, 4:7] = string
    res["parcel"] = (pk, (6, 10))
    # Rauch: 4 Bilder 24 x 24, wachsende ausgefranste Wolke; oben heller (Abendhimmel), unten dunkler;
    # das letzte Bild löst sich im Schachbrettmuster auf (keine Halbtransparenz in den Engines der Zeit)
    rng = np.random.default_rng(5)
    shades = [P.nearest_index(np.array([c]), P.ramp_mask(["grau", "schiefer", "violett"]))[0]
              for c in ((196, 190, 200), (164, 160, 174), (132, 130, 146), (104, 102, 120), (80, 78, 96))]
    yy, xx = np.mgrid[0:24, 0:24].astype(float)
    for f in range(4):
        im = np.full((24, 24), T, np.uint8)
        r = 3.6 + 1.6 * f
        cx, cy = 11.5, 11.5
        # vier überlappende Kreise mit Rauschrand
        blobs = [(cx, cy, r), (cx - r * 0.55, cy + r * 0.2, r * 0.7), (cx + r * 0.5, cy + r * 0.05, r * 0.75),
                 (cx + r * 0.1, cy - r * 0.45, r * 0.62)]
        n = rng.normal(0, 0.55, (24, 24))
        body = np.zeros((24, 24), bool)
        for bx, by, br in blobs:
            body |= np.hypot(xx - bx, yy - by) + n < br
        # Kugelschattierung je Teilwolke (Licht von links oben vorn), die vorderste Teilwolke gewinnt
        bright = np.full((24, 24), -1.0)
        L = np.array([-0.5, -0.6, 0.62])
        for bx, by, br in blobs:
            dx, dy = (xx - bx) / br, (yy - by) / br
            d2 = dx * dx + dy * dy
            nz = np.sqrt(np.clip(1 - d2, 0, 1))
            v = np.where(d2 < 1.0, dx * L[0] + dy * L[1] + nz * L[2], -1.0)
            bright = np.maximum(bright, v)
        lev = np.clip((4.4 - (bright + 0.35) * 3.6).astype(int) + (1 if f >= 2 else 0), 0, 4)
        im[body] = np.array(shades)[lev[body]]
        inner = np.zeros_like(body)
        for bx, by, br in blobs:
            inner |= np.hypot(xx - bx, yy - by) + n < br - 1.3
        edge = body & ~inner
        chk = (xx + yy) % 2 == 0
        if f >= 1:
            im[edge & chk] = T
        if f == 3:
            im[body & chk] = T
        res[f"smoke{f}"] = (im, (12, 12))
    # Möwe: 2 Bilder 24 x 10 (Flügel oben / unten), Spannweite 0,75 m
    w = P.nearest_index(np.array([[238, 236, 232]]), P.ramp_mask(["grau", "creme"]))[0]
    g = P.nearest_index(np.array([[150, 150, 160]]), P.ramp_mask(["grau", "schiefer"]))[0]
    k_ = P.nearest_index(np.array([[40, 40, 46]]), P.ramp_mask(["grau", "nacht"]))[0]
    y_ = P.nearest_index(np.array([[250, 196, 70]]), P.ramp_mask(["gelb", "orange"]))[0]
    up = ["k......................k",
          "gk....................kg",
          ".gg..................gg.",
          "..ggw..............wgg..",
          "...gww............wwg...",
          ".....www........www.....",
          ".......wwwwwwwwwwy......",
          "..........wwww..........",
          "........................",
          "........................"]
    dn = ["........................",
          "........................",
          "........................",
          "..........wwww..........",
          ".......wwwwwwwwwwy......",
          ".....www........www.....",
          "...gww............wwg...",
          "..ggw..............wgg..",
          ".gg..................gg.",
          "kk....................kk"]
    for k, rows in enumerate((up, dn)):
        im = np.full((10, 24), T, np.uint8)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch != ".":
                    im[y, x] = {"w": w, "g": g, "k": k_, "y": y_}[ch]
        res[f"gull{k}"] = (im, (12, 6))
    # Leuchtfeuer-Blitz: waagrechter Lichtschein 128 x 24 Texel (4 m x 0,75 m), Mitte = Lampe, vollhell
    fl = np.full((24, 128), T, np.uint8)
    cols = [P.nearest_index(np.array([c]), P.ramp_mask(["gelb", "orange"]))[0]
            for c in ((255, 255, 236), (255, 244, 170), (255, 220, 110), (250, 186, 70))]
    for y in range(24):
        for x in range(128):
            dx, dy = abs(x - 63.5) / 64.0, abs(y - 11.5) / 12.0
            v = 1.0 - (dx ** 0.8 + dy * (0.6 + 1.6 * dx))
            if v > 0.0:
                fl[y, x] = cols[3 if v < 0.25 else (2 if v < 0.45 else (1 if v < 0.7 else 0))]
    res["flare"] = (fl, (64, 12))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", required=True)
    a = ap.parse_args()
    R = pathlib.Path(a.render)
    OUT.mkdir(parents=True, exist_ok=True)
    info = {}

    # Dachs-Atlas
    meta = json.loads((R / "badger_meta.json").read_text())
    cw, ch = meta["canvas"]
    K = meta["super"]
    poses = [p["name"] for p in meta["poses"]]
    atlas = np.full((ch * len(poses), cw * 8), P.TRANSPARENT, np.uint8)
    for j, pose in enumerate(poses):
        for rot in range(8):
            base = R / f"badger_{pose}_r{rot}"
            idx, _ = downsample(Image.open(f"{base}_shade.png"), Image.open(f"{base}_id.png"), cw, ch, K)
            atlas[j * ch:(j + 1) * ch, rot * cw:(rot + 1) * cw] = idx
    P.save_index_png(atlas, OUT / "badger_atlas.png")
    Image.fromarray(to_rgb(atlas), "RGBA").save(OUT / "badger_atlas_rgb.png")
    info["badger"] = {"cell": [cw, ch], "origin": meta["origin"], "poses": poses, "rotations": 8,
                      "scale": meta["scale"]}

    # Requisiten
    for name in ("barrel", "rope", "bollard", "lanternpost"):
        pm = json.loads((R / f"prop_{name}_meta.json").read_text())
        pcw, pch = pm["canvas"]
        shade, idimg = Image.open(R / f"prop_{name}_shade.png"), Image.open(R / f"prop_{name}_id.png")
        idx, mats = downsample(shade, idimg, pcw, pch, pm["super"])
        if name in ("barrel", "lanternpost"):
            idx = wood_detail(idx, mats, shade, idimg, pcw, pch, pm["super"], name)
        P.save_index_png(idx, OUT / f"{name}.png")
        info[name] = {"size": [pcw, pch], "origin": pm["origin"]}
        if name == "lanternpost":
            # Glas als eigenes Vollhell-Sprite mit 4 Flackerstufen; im Pfahl-Sprite bleibt das Glas dunkel
            glass = mats == NAMES.index("Glass")
            dark = P.nearest_index(np.array([[150, 96, 40]]), P.ramp_mask(["orange"]))[0]
            post = idx.copy()
            post[glass] = dark
            P.save_index_png(post, OUT / "lanternpost.png")
            levels = [(255, 250, 200), (255, 226, 130), (255, 204, 96), (250, 176, 70)]
            for f, col in enumerate(levels):
                g = np.full_like(idx, P.TRANSPARENT)
                ys, xs = np.nonzero(glass)
                # Glas mit leichtem Verlauf: oben heller
                for y, x in zip(ys, xs):
                    t = (y - ys.min()) / max(1, ys.max() - ys.min())
                    c = np.array(col, float) * (1.0 - 0.18 * t)
                    g[y, x] = P.nearest_index(c[None], P.ramp_mask(["gelb", "orange"]))[0]
                P.save_index_png(g, OUT / f"lanternglow{f}.png")
            info["lanternglow"] = {"size": [pcw, pch], "origin": pm["origin"], "frames": 4}

    for name, (im, origin) in code_sprites().items():
        P.save_index_png(im, OUT / f"{name}.png")
        info[name] = {"size": [im.shape[1], im.shape[0]], "origin": list(origin)}

    (OUT / "sprites.json").write_text(json.dumps(info, indent=1))
    # Vorschau aller Requisiten (RGB) und Kopie in die Demo
    DEMO.mkdir(parents=True, exist_ok=True)
    for p in OUT.glob("*.png"):
        if p.name.endswith("_rgb.png") or p.name.startswith("preview"):
            continue
        shutil.copy2(p, DEMO / p.name)
    shutil.copy2(OUT / "sprites.json", DEMO / "sprites.json")
    names = [p.stem for p in sorted(OUT.glob("*.png")) if not p.name.endswith("_rgb.png")
             and p.stem not in ("badger_atlas",) and not p.stem.startswith("preview")]
    ims = [np.asarray(Image.open(OUT / f"{n}.png")) for n in names]
    W = sum(i.shape[1] + 3 for i in ims)
    H = max(i.shape[0] for i in ims)
    sheet = np.zeros((H, W, 4), np.uint8)
    sheet[..., :3] = (60, 70, 90)
    sheet[..., 3] = 255
    x = 0
    for i in ims:
        rgba = to_rgb(i)
        m = rgba[..., 3] > 0
        sheet[:i.shape[0], x:x + i.shape[1]][m] = rgba[m]
        x += i.shape[1] + 3
    Image.fromarray(sheet).save(OUT / "preview_props.png")
    print("Sprites:", ", ".join(sorted(info)))


if __name__ == "__main__":
    main()
