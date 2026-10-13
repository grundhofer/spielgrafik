#!/usr/bin/env python3
"""Rohe Blender-Renderings -> 256-Farben-Assets für die Godot-Demo (iso-vorgerendert).

  .venv/bin/python styles/iso-vorgerendert/scripts/bake.py --raw <renderordner>

<renderordner> enthält bg/ (render_bg.py: beauty/f_XXXX, depth.npy, emit.png, beam_XXXX, bg_meta.json) und
badger/ (render_badger.py). Ablauf:
  1. Verkleinern in linearem Licht (Karte 2×2, Dachs 4×4 Box-Filter), Dachs: Deckung 1 Bit, Tiefe, Schatten.
  2. Eine gemeinsame Palette mit 256 Farben (k-Mittel in Oklab) aus Karte, Wasserfolge, Dachs, Porträt und
     Bedienleiste, jeweils auch in den Lichtstufen, die die Demo zeigt.
  3. Lichttabelle (16 Stufen × 256 Einträge, jede Zelle wieder eine Palettenfarbe) wie in 8-Bit-Rollenspielen:
     Stufe 10 = wie gerendert, darunter dunkler und blauer (Nacht), darüber wärmer und heller (Laterne).
  4. Alles mit leichtem geordnetem Dithering (Bayer 8×8) auf Palettenindizes setzen.
Ausgaben in demo/art/ und demo/data/bake.json; Messwerte in assets/bake_report.json.
"""
import argparse
import json
import pathlib

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
ART = STYLE / "demo" / "art"
DATA = STYLE / "demo" / "data"
SCENE = json.load(open(STYLE / "assets" / "scene.json"))

LEVELS = [0.20, 0.28, 0.36, 0.44, 0.52, 0.60, 0.68, 0.76, 0.84, 0.92, 1.0, 1.1, 1.22, 1.36, 1.52, 1.72]
LEVEL_ONE = 10
NIGHT = np.array([0.50, 0.56, 1.0])
EXPOSURE = 1.3          # Belichtung der Renderings für Stufe 10 (wie gerendert, etwas heller)
WARM_MUL = np.array([1.0, 0.80, 0.52])
WARM_ADD = np.array([0.20, 0.12, 0.035])
DITHER = 0.032            # Amplitude des geordneten Ditherings (sRGB, 0..1)
DEPTH_D0, DEPTH_D1 = 95.0, 140.0
RING = (0.24, 0.80, 0.30)  # Auswahlring unter der Figur (feste Palettenfarbe)

BAYER8 = np.array([[0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26],
                   [12, 44, 4, 36, 14, 46, 6, 38], [60, 28, 52, 20, 62, 30, 54, 22],
                   [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25],
                   [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21]]) / 64.0 - 0.5 + 1 / 128


# ------------------------------------------------------------------------------------------------
def s2l(c):
    c = np.asarray(c, np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def l2s(c):
    c = np.clip(np.asarray(c, np.float64), 0, None)
    return np.clip(np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055), 0, 1)


def oklab(lin):
    lin = np.asarray(lin, np.float64)
    M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    lms = np.cbrt(np.clip(lin @ M1.T, 0, None))
    return lms @ M2.T


def load_rgb(p):
    return np.asarray(Image.open(p).convert("RGB"), np.float64) / 255.0


def box_lin(img_srgb, k):
    h, w = img_srgb.shape[:2]
    lin = s2l(img_srgb)
    return lin.reshape(h // k, k, w // k, k, -1).mean((1, 3))


def grade(lin, lv):
    """Lichtstufe auf lineare Farbe anwenden (Nacht kühl, Laternenlicht warm)."""
    if lv <= 1.0:
        tint = NIGHT + (1 - NIGHT) * lv ** 0.8
        return lin * lv * tint
    e = lv - 1.0
    return lin * (1 + e * WARM_MUL) + e * WARM_ADD


class Palette:
    def __init__(self, rgb_srgb):
        self.srgb = np.asarray(rgb_srgb, np.float64)
        self.lab = oklab(s2l(self.srgb))

    def nearest(self, lab, chunk=60000):
        out = np.empty(len(lab), np.int32)
        for i in range(0, len(lab), chunk):
            d = ((lab[i:i + chunk, None, :] - self.lab[None]) ** 2).sum(-1)
            out[i:i + chunk] = d.argmin(1)
        return out


def kmeans_palette(samples_lin, k=256, iters=14, seed=7, fixed=()):
    lab = oklab(samples_lin)
    rng = np.random.default_rng(seed)
    nfix = len(fixed)
    centers = lab[rng.choice(len(lab), k - nfix, replace=False)]
    fixed_lab = oklab(s2l(np.array(fixed, np.float64))) if nfix else np.zeros((0, 3))
    for it in range(iters):
        allc = np.concatenate([fixed_lab, centers])
        assign = np.empty(len(lab), np.int32)
        for i in range(0, len(lab), 40000):
            d = ((lab[i:i + 40000, None, :] - allc[None]) ** 2).sum(-1)
            assign[i:i + 40000] = d.argmin(1)
        for j in range(k - nfix):
            m = assign == j + nfix
            if m.any():
                centers[j] = lab[m].mean(0)
            else:
                centers[j] = lab[rng.integers(len(lab))]
    allc = np.concatenate([fixed_lab, centers])
    # Oklab -> linear sRGB
    M2i = np.linalg.inv(np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                                  [1.9779984951, -2.4285922050, 0.4505937099],
                                  [0.0259040371, 0.7827717662, -0.8086757660]]))
    M1i = np.linalg.inv(np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                                  [0.2119034982, 0.6806995451, 0.1073969566],
                                  [0.0883024619, 0.2817188376, 0.6299787005]]))
    lms = (allc @ M2i.T) ** 3
    lin = np.clip(lms @ M1i.T, 0, 1)
    srgb = np.round(l2s(lin) * 255) / 255
    # nach Helligkeit sortieren (nur für die Ansicht der Palette)
    order = np.argsort(oklab(s2l(srgb))[:, 0], kind="stable")
    return srgb[order]


def quantize(img_srgb, pal, dither=DITHER, origin=(0, 0)):
    h, w = img_srgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    b = BAYER8[(yy + origin[1]) % 8, (xx + origin[0]) % 8][..., None]
    d = np.clip(img_srgb + b * dither, 0, 1)
    idx = pal.nearest(oklab(s2l(d.reshape(-1, 3))))
    return idx.reshape(h, w)


def save_rgb(path, arr):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.asarray(arr, np.uint8), "RGB").save(path, optimize=True)


# ------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    a = ap.parse_args()
    raw = pathlib.Path(a.raw)
    bgdir, bdir = raw / "bg", raw / "badger"
    meta = json.load(open(bgdir / "bg_meta.json"))
    W, H = meta["map"]
    report = {}

    # --- Karte -----------------------------------------------------------------------------
    frames = sorted(bgdir.glob("f_*.png"))
    base_src = frames[0] if frames else bgdir / "beauty.png"
    base_lin = np.clip(box_lin(load_rgb(base_src), 2) * EXPOSURE, 0, 1)
    frame_lin = [np.clip(box_lin(load_rgb(p), 2) * EXPOSURE, 0, 1) for p in frames]
    emit = box_lin(load_rgb(bgdir / "emit.png"), 2).max(-1)
    depth = np.load(bgdir / "depth.npy")
    assert depth.shape == (H, W), depth.shape
    beams = sorted(bgdir.glob("beam_*.png"))

    # Animierter Bereich: wo sich die Quelle über die Schleife spürbar ändert (Wasser, Boote)
    if frame_lin:
        diff = np.zeros((H, W))
        for f in frame_lin[1:]:
            diff = np.maximum(diff, np.abs(f - base_lin).max(-1))
        anim = diff > 0.012
        # Lücken schließen, 1 px erweitern
        from PIL import ImageFilter
        m = Image.fromarray((anim * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
        anim = np.asarray(m.filter(ImageFilter.MaxFilter(3))) > 0
        report["anim_area_px"] = int(anim.sum())
    else:
        anim = np.zeros((H, W), bool)

    # --- Dachs ------------------------------------------------------------------------------
    bmeta = json.load(open(bdir / "badger.json"))
    cw, ch = bmeta["cell"]
    sprites = {}
    for fr in bmeta["frames"]:
        n = fr["name"]
        im = np.asarray(Image.open(bdir / f"{n}.png").convert("RGBA"), np.float64) / 255
        k = 4
        a_ = im[..., 3:4]
        lin = s2l(im[..., :3]) * a_
        cov = a_.reshape(ch, k, cw, k, 1).mean((1, 3))[..., 0]
        col = np.clip(lin.reshape(ch, k, cw, k, 3).mean((1, 3)) / np.maximum(cov[..., None], 1e-6) * EXPOSURE, 0, 1)
        zi = np.asarray(Image.open(bdir / f"{n}_z.png").convert("RGBA"), np.float64) / 255
        za = (zi[..., 3] > 0.5).astype(np.float64)
        zs = (zi[..., 0] * za).reshape(ch, k, cw, k).sum((1, 3))
        zc = za.reshape(ch, k, cw, k).sum((1, 3))
        zrel = np.where(zc > 0, zs / np.maximum(zc, 1), 0.5)
        sh = s2l(np.asarray(Image.open(bdir / f"{n}_sh.png").convert("RGB"), np.float64) / 255).mean(-1)
        sh = sh.reshape(ch, k, cw, k).mean((1, 3))
        lit = np.percentile(sh, 75)
        shadow = np.clip(1 - sh / max(lit, 1e-6), 0, 1)
        sprites[n] = {"cov": cov >= 0.5, "col": col, "z": zrel, "shadow": shadow}

    # --- Porträt und Leiste --------------------------------------------------------------------
    por = Image.open(STYLE / "assets" / "raw" / "portrait.png").convert("RGB")
    pw, phh = por.size
    lay = json.load(open(STYLE / "assets" / "ui" / "ui_layout.json"))
    px0, py0, px1, py1 = lay["portrait"]
    tw, th = px1 - px0, py1 - py0
    crop_w = int(pw * 0.86)
    crop_h = int(crop_w * th / tw)
    cx0 = int(pw * 0.06)
    cy0 = int(phh * 0.125)
    por_c = por.crop((cx0, cy0, cx0 + crop_w, cy0 + crop_h))
    por_lin = box_lin(np.asarray(por_c.resize((tw * 4, th * 4), Image.LANCZOS), np.float64) / 255, 4)
    bar_lin = s2l(load_rgb(STYLE / "assets" / "ui" / "bar.png"))

    # --- Palette ----------------------------------------------------------------------------
    rng = np.random.default_rng(3)

    def pick(arr, n, mask=None):
        flat = arr.reshape(-1, 3) if mask is None else arr[mask]
        if len(flat) == 0:
            return np.zeros((0, 3))
        return flat[rng.choice(len(flat), min(n, len(flat)), replace=False)]

    samples = []
    view = np.zeros((H, W), bool)
    vr = SCENE["map"]["view_row"]
    view[vr:vr + SCENE["map"]["view_size"][1] - SCENE["map"]["bar_height"]] = True
    for lv, n in ((1.0, 22000), (0.36, 34000), (0.44, 14000), (0.28, 12000), (0.20, 6000), (0.60, 12000),
                  (0.84, 10000), (1.22, 9000), (1.52, 5000)):
        samples.append(grade(pick(base_lin, n, view), lv))
    if frame_lin:
        allw = np.concatenate([f[anim & view] for f in frame_lin[::3]])
        samples.append(grade(pick(allw.reshape(-1, 1, 3), 8000), 0.36))
        samples.append(grade(pick(allw.reshape(-1, 1, 3), 4000), 1.0))
    bcols = np.concatenate([s["col"][s["cov"]] for s in sprites.values()])
    for lv, n in ((1.0, 14000), (0.84, 6000), (1.1, 6000)):
        samples.append(grade(pick(bcols.reshape(-1, 1, 3), n), lv))
    samples.append(pick(por_lin, 9000))
    samples.append(pick(bar_lin, 7000))
    samples = np.concatenate([s.reshape(-1, 3) for s in samples])
    fixed = [(0, 0, 0), (1, 1, 1), RING]
    pal_rgb = kmeans_palette(np.clip(samples, 0, 1), 256, fixed=fixed)
    pal = Palette(pal_rgb)
    report["palette_colors"] = int(len(np.unique((pal_rgb * 255).round(), axis=0)))

    # --- Lichttabelle --------------------------------------------------------------------------
    lut_idx = np.zeros((len(LEVELS), 256), np.int32)
    pal_lin = s2l(pal_rgb)
    for r, lv in enumerate(LEVELS):
        lut_idx[r] = pal.nearest(oklab(np.clip(grade(pal_lin, lv), 0, 1)))
    lut_idx[LEVEL_ONE] = np.arange(256)
    lut_rgb = (pal_rgb[lut_idx] * 255).round().astype(np.uint8)
    save_rgb(ART / "lut.png", lut_rgb)
    save_rgb(STYLE / "assets" / "palette.png",
             np.repeat(np.repeat((pal_rgb.reshape(16, 16, 3) * 255).round().astype(np.uint8), 8, 0), 8, 1))

    # --- Karte quantisieren --------------------------------------------------------------------
    base_idx = quantize(l2s(base_lin), pal)
    emis_level = np.zeros((H, W), np.uint8)
    e = np.clip(emit / 0.6, 0, 1)
    emis_level[e > 0.08] = np.clip(np.round(LEVEL_ONE + e[e > 0.08] * 4), LEVEL_ONE, len(LEVELS) - 1)
    bg_rgb = np.dstack([base_idx, emis_level, np.zeros_like(emis_level)]).astype(np.uint8)
    save_rgb(ART / "bg.png", bg_rgb)
    dq = np.clip((depth - DEPTH_D0) / (DEPTH_D1 - DEPTH_D0), 0, 1)
    d16 = np.round(dq * 65535).astype(np.int64)
    save_rgb(ART / "depth.png", np.dstack([d16 >> 8, d16 & 255, np.zeros_like(d16)]).astype(np.uint8))
    report["depth_range"] = [float(depth.min()), float(depth.max())]

    # Wasserfolge als Überlagerung: nur Palettenindex (L8), auf das Rechteck des animierten Bereichs beschnitten;
    # die feste Maske (wo die Folge gilt) liegt einmal in water_mask.png
    water_dir = ART / "water"
    for p in water_dir.glob("w_*.png") if water_dir.exists() else []:
        p.unlink()
    water_dir.mkdir(parents=True, exist_ok=True)
    ys, xs = np.nonzero(anim) if anim.any() else (np.array([0]), np.array([0]))
    wx0, wy0, wx1, wy1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    Image.fromarray((anim[wy0:wy1, wx0:wx1] * 255).astype(np.uint8), "L").save(ART / "water_mask.png", optimize=True)
    changed = []
    for i, f in enumerate(frame_lin):
        idx = quantize(l2s(f), pal)
        Image.fromarray(np.where(anim, idx, 0)[wy0:wy1, wx0:wx1].astype(np.uint8), "L").save(
            water_dir / f"w_{i:02d}.png", optimize=True)
        changed.append(int(((idx != base_idx) & anim).sum()))
    report["water_frames"] = len(frame_lin)
    report["water_rect"] = [wx0, wy0, wx1, wy1]
    report["water_changed_px"] = changed

    # Strahl: Helligkeit je Bild als L8 in halber Auflösung (weicher Lichtschein, spart Grafikspeicher)
    beam_dir = ART / "beam"
    for p in beam_dir.glob("b_*.png") if beam_dir.exists() else []:
        p.unlink()
    beam_dir.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(beams):
        bl = load_rgb(p).max(-1)
        bl = bl.reshape(H // 2, 2, W // 2, 2).mean((1, 3))
        v = np.clip(bl, 0, 1) ** 1.6
        Image.fromarray(np.round(v * 255).astype(np.uint8), "L").save(beam_dir / f"b_{i:02d}.png", optimize=True)
    report["beam_frames"] = len(beams)

    # --- Dachs-Blatt ---------------------------------------------------------------------------
    order = []
    rows = []
    for d in bmeta["dirs"]:
        rows.append([f"walk_{d}_{i}" for i in range(8)])
    rows.append([f"stand_{d}" for d in bmeta["dirs"]])
    rows.append([f"idle_S_{i:02d}" for i in range(12)])
    rows.append([f"wave_S_{i:02d}" for i in range(15)])
    ncol = max(len(r) for r in rows)
    sheet = np.zeros((ch * len(rows), cw * ncol, 3), np.uint8)
    preview = np.zeros((ch * len(rows), cw * ncol, 3), np.uint8)
    frame_pos = {}
    for r, names in enumerate(rows):
        for c, n in enumerate(names):
            if n not in sprites:
                continue
            s = sprites[n]
            idx = quantize(l2s(s["col"]), pal, origin=(0, 0))
            cov = s["cov"]
            zq = np.clip(np.round(s["z"] * 255), 1, 255).astype(np.uint8)
            yy, xx = np.mgrid[0:ch, 0:cw]
            shbit = (s["shadow"] > 0.5 + BAYER8[yy % 8, xx % 8] * 0.5) & ~cov
            cell = np.dstack([np.where(cov, idx, 0), np.where(cov, zq, 0), shbit * 255]).astype(np.uint8)
            sheet[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = cell
            pv = np.where(cov[..., None], (pal_rgb[idx] * 255).round(), np.where(shbit[..., None], 40, 90))
            preview[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = pv
            frame_pos[n] = [c * cw, r * ch]
            # Kontrolle: Zelle darf nicht abgeschnitten sein
            if cov[0].any() or cov[-1].any() or cov[:, 0].any() or cov[:, -1].any():
                report.setdefault("cell_clipped", []).append(n)
            if shbit[0].any() or shbit[:, -1].any() or shbit[-1].any() or shbit[:, 0].any():
                report.setdefault("shadow_clipped", []).append(n)
    save_rgb(ART / "badger.png", sheet)
    save_rgb(STYLE / "assets" / "badger_sheet_preview.png", preview)

    # --- Porträt und Leiste in Palettenfarben ----------------------------------------------------
    por_idx = quantize(l2s(por_lin), pal)
    save_rgb(ART / "portrait.png", (pal_rgb[por_idx] * 255).round())
    bar_idx = quantize(l2s(bar_lin), pal, dither=DITHER * 0.6)
    save_rgb(ART / "bar.png", (pal_rgb[bar_idx] * 255).round())

    # --- Daten für Godot --------------------------------------------------------------------------
    DATA.mkdir(parents=True, exist_ok=True)
    out = {
        "map_size": [W, H], "px_per_m": meta["px_per_m"], "cam_location": meta["cam_location"],
        "R": meta["R"], "U": meta["U"], "D": meta["D"], "depth_d0": DEPTH_D0, "depth_d1": DEPTH_D1,
        "levels": LEVELS, "level_one": LEVEL_ONE,
        "ring_idx": int(pal.nearest(oklab(s2l(np.array([RING]))))[0]),
        "lantern": meta["lantern"], "lighthouse_light": meta["lighthouse_light"], "window": meta["window"],
        "water_fps": meta["fps"], "water_frames": len(frame_lin), "water_rect": report.get("water_rect", [0, 0, 1, 1]),
        "beam_fps": meta["beam_fps"],
        "beam_frames": len(beams),
        "badger": {"cell": [cw, ch], "anchor": bmeta["anchor"], "depth_range_m": bmeta["depth_range_m"],
                   "cycle_px": bmeta["cycle_px"], "stride_m": bmeta["stride_m"], "frames": frame_pos},
        "scene": SCENE,
        "ui": lay,
    }
    json.dump(out, open(DATA / "bake.json", "w"), indent=1)
    report["sprites"] = len(sprites)
    json.dump(report, open(STYLE / "assets" / "bake_report.json", "w"), indent=1)
    print(json.dumps(report, indent=1)[:1500])


if __name__ == "__main__":
    main()
