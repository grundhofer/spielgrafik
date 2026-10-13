#!/usr/bin/env python3
"""Macht aus den fünf KI-Rohbildern die Daten der Demo (alles automatisch, keine Handpolygone).

    .venv/bin/python styles/tageszeit-wetter/tools/prep.py [--debug DIR]

Eingang assets/raw/: bg.png (Tag, neutrales Licht), mask.png (Farbcodes), depth.png (Graustufen-Tiefe),
snow.png (dieselbe Szene verschneit), night.png (dieselbe Szene nachts) – alle mit bg.png als Referenz.
Ausgang assets/ (und Kopie nach demo/art/), 1280×720 aus dem 16:9-Schnitt CROP:
  bg.png          Grundbild
  sky_plate.png   Himmel unter Objekten fortgesetzt (für ziehende Wolken)
  data_a.png      R Himmel, G Wasser, B Tiefe (nah = 1)
  data_b.png      R/G/B Anteil Fenster / Laterne / Leuchtfeuer am Lichtbild
  data_c.png      R Wolkendeckung, G Boote, B Schneedeckung (Alpha der Schneeschicht)
  snow_rgb.png    Farbe der Schneeschicht (aus snow.png)
  light.png       Lichtbild: Nachtschlüssel minus Nacht-LUT(Grundbild), nur positiv
  lut.png         6 LUTs übereinander (Tag, Dämmerung, Nacht, Regen, Nebel, Schnee), je 1024×32
  noise.png       drei kachelbare Rauschkanäle 256×256
  scene.json      Lagen (Lichter, Schornstein, Horizont, Dachsplatz) und Himmelsfarben je Zustand
"""
import argparse, json, pathlib, shutil, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import imgops as io  # noqa: E402
import lut as L      # noqa: E402

ENTRY = pathlib.Path(__file__).resolve().parent.parent
RAW, OUT, ART = ENTRY / "assets" / "raw", ENTRY / "assets", ENTRY / "demo" / "art"
W, H = 1280, 720
SRC_W = 1536
Y0 = 48                       # 16:9-Schnitt: Zeilen 48..912 des 1536×1024-Bildes
S = W / SRC_W                 # 0,8333

CODES = {"sky": (0, 0, 1), "water": (0, 1, 1), "boat": (1, 0, 1), "window": (1, 1, 0),
         "lantern": (1, .5, 0), "lamp": (1, 0, 0), "chimney": (0, 1, 0), "other": (0, 0, 0)}
STATES = ["tag", "daemmerung", "nacht", "regen", "nebel", "schnee"]


def crop(a):
    return a[Y0:Y0 + int(round(H / S))]


def out_size(a, resample=Image.LANCZOS):
    return io.resize(crop(a), (W, H), resample)


def to720(x, y):
    return [round(x * S, 1), round((y - Y0) * S, 1)]


def labels_from_mask(m):
    names = list(CODES)
    cols = np.array([CODES[n] for n in names], np.float32)
    d = ((m[..., None, :] - cols[None, None]) ** 2).sum(-1)
    lab = d.argmin(-1)
    onehot = np.stack([(lab == i).astype(np.float32) for i in range(len(names))], -1)
    lab = io.box(onehot, 2).argmax(-1)                     # Mehrheitsfilter 5×5
    return {n: (lab == i) for i, n in enumerate(names)}


def centroid(b):
    ys, xs = np.nonzero(b)
    return float(xs.mean()), float(ys.mean()), (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", default="")
    a = ap.parse_args()
    dbg = pathlib.Path(a.debug) if a.debug else None
    if dbg:
        dbg.mkdir(parents=True, exist_ok=True)

    bg = io.load(RAW / "bg.png")
    mask = io.load(RAW / "mask.png")
    depth_raw = io.load(RAW / "depth.png", "L")
    snow = io.load(RAW / "snow.png")
    night = io.load(RAW / "night.png")
    for n, im in (("mask", mask), ("depth", depth_raw), ("snow", snow), ("night", night)):
        if im.shape[:2] != bg.shape[:2]:
            sys.exit(f"{n}.png hat {im.shape[1]}×{im.shape[0]}, erwartet {bg.shape[1]}×{bg.shape[0]}")

    # ---- Masken aus der Farbcode-Karte ------------------------------------------------------
    lab = labels_from_mask(mask)
    sky = np.clip(io.guided(bg, lab["sky"].astype(np.float32), 5, 2e-3), 0, 1)
    water = np.clip(io.guided(bg, lab["water"].astype(np.float32), 5, 2e-3), 0, 1)
    boat = np.clip(io.guided(bg, lab["boat"].astype(np.float32), 3, 2e-3), 0, 1)
    pos = {}
    for n in ("window", "lantern", "lamp", "chimney"):
        if lab[n].sum() < 20:
            sys.exit(f"Farbcode {n} fehlt in mask.png")
        pos[n] = centroid(lab[n])
    # Horizont: unterste Zeile, in der in der Bildmitte noch Himmel ist
    mid = lab["sky"][:, 600:1000].mean(1)
    horizon = int(np.nonzero(mid > 0.5)[0].max())

    # ---- Tiefe --------------------------------------------------------------------------------
    d = io.box(depth_raw, 2)
    d = np.clip(io.guided(bg, d, 4, 1e-3), 0, 1)
    d = d * (1 - sky)                                   # Himmel = fern
    lo, hi = np.percentile(d[sky < 0.5], [1, 99.5])
    depth = np.clip((d - 0.0) / max(hi, 1e-3), 0, 1)

    # ---- Schneeschicht ------------------------------------------------------------------------
    kb, ks = io.box(bg, 1), io.box(snow, 1)
    lb, lk = io.lum(kb), io.lum(ks)
    satk = ks.max(-1) - ks.min(-1)
    white = np.clip((lk - 0.55) / 0.25, 0, 1) * np.clip(1 - satk / 0.35, 0, 1)
    a_bright = np.clip((lk - lb) / np.maximum(0.92 - lb, 0.10), 0, 1) * white
    core = io.box((a_bright > 0.5).astype(np.float32), 3) > 0.02         # um Schnee herum
    a_any = np.clip(np.abs(ks - kb).max(-1) / 0.18, 0, 1) * core
    snow_a = np.maximum(a_bright, a_any)
    snow_a *= np.clip(1 - 1.5 * sky, 0, 1) * np.clip(1 - 1.5 * water, 0, 1)
    snow_a = io.box(snow_a, 1)

    # ---- Nacht: LUT anpassen und Lichtbild ----------------------------------------------------
    valid = (sky < 0.2).reshape(-1)
    src, dst = bg.reshape(-1, 3), night.reshape(-1, 3)
    use = valid.copy()
    for it in range(3):
        nlut, M = L.fit(src[use], dst[use])
        pred = L.apply(nlut, bg)
        res = night - pred
        lit = io.box((io.lum(res) > 0.035).astype(np.float32), 6) > 0.01   # Lichthöfe + Rand
        use = valid & ~lit.reshape(-1)
        print(f"LUT-Durchgang {it + 1}: {use.sum()} Pixel, Lichtfläche {lit.mean() * 100:.1f} %")
    res = night - L.apply(nlut, bg)
    resid_err = np.abs(res)[use.reshape(bg.shape[:2])].mean()
    print(f"Nacht-LUT: mittlerer Restfehler außerhalb der Lichter {resid_err:.4f}")
    light = np.clip(res, 0, None)
    light = np.minimum(light, io.box(light, 1) * 1.6)            # Ausreißer (Versatz) dämpfen
    gate = np.clip((io.lum(io.box(light, 2)) - 0.012) / 0.03, 0, 1)
    light = light * gate[..., None] * np.clip(1 - 1.2 * sky, 0, 1)[..., None]

    # Anteil je Lichtquelle (anisotrop: Lichtpfützen liegen senkrecht unter der Quelle)
    yy, xx = np.mgrid[0:bg.shape[0], 0:bg.shape[1]].astype(np.float32)
    ky = np.where(water > 0.5, 0.25, 0.45)
    wts = []
    for n, r0 in (("window", 40.0), ("lantern", 40.0), ("lamp", 25.0)):
        cx, cy, _ = pos[n]
        dist2 = (xx - cx) ** 2 + ((yy - cy) * ky) ** 2
        wts.append(1.0 / (dist2 + r0 * r0) ** 1.5)
    wts = np.stack(wts, -1)
    frac = wts / wts.sum(-1, keepdims=True)

    # Licht am Dachsplatz (für die Figur): Bestrahlung = Rest / Albedo auf dem Boden um die Füße
    badger_feet = (515.0, 890.0)            # in Rohpixeln (720p: ~429/701)
    fx, fy = badger_feet
    win = (slice(int(fy) - 40, int(fy) + 10), slice(int(fx) - 70, int(fx) + 70))
    irr = (light[win] / np.maximum(bg[win], 0.08)).reshape(-1, 3)
    irr_feet = np.median(irr, 0)
    # Richtung: Anteil der Laterne
    print("Licht am Dachsplatz (Bestrahlung, linear):", irr_feet.round(3))

    # ---- Himmel: Platte und Wolkendeckung -----------------------------------------------------
    sure_sky = (sky > 0.97) & (io.box(lab["sky"].astype(np.float32), 3) > 0.99)
    plate = io.pull_push(bg, sure_sky.astype(np.float32))
    plate = np.where(sure_sky[..., None], bg, plate)
    rows = []
    for y in range(bg.shape[0]):
        rr = bg[y, sure_sky[y], 0]
        rows.append(np.percentile(rr, 8) if len(rr) > 40 else np.nan)
    rows = np.array(rows)
    good = ~np.isnan(rows)
    r_clear = np.interp(np.arange(len(rows)), np.nonzero(good)[0], rows[good])
    r_clear = np.convolve(np.pad(r_clear, 15, mode="edge"), np.ones(31) / 31, mode="valid")
    cloud = np.clip((plate[..., 0] - r_clear[:, None] - 0.02) / (0.93 - r_clear[:, None]), 0, 1)

    # Himmelsfarben des Nachtschlüssels (für den Nachtzustand)
    nsky = night[sure_sky & (cloud < 0.15)]
    nsky_top = night[:200][sure_sky[:200] & (cloud[:200] < 0.15)].mean(0)
    nsky_hor = night[horizon - 60:horizon][sure_sky[horizon - 60:horizon] & (cloud[horizon - 60:horizon] < 0.15)].mean(0)
    ncloud = night[sure_sky & (cloud > 0.6)].mean(0)
    print("Nachthimmel oben", nsky_top.round(3), "Horizont", nsky_hor.round(3), "Wolken", ncloud.round(3), len(nsky))

    # ---- LUTs ---------------------------------------------------------------------------------
    g = L.grid()
    day = L.contrast(L.sat(g, 1.06), 1.04) * np.array([1.02, 1.0, 0.97])
    n_l = nlut
    dusk = L.split_tone(L.sat(g, 0.85) * 0.70, (0.78, 0.66, 1.02), (1.16, 0.86, 0.66))
    dusk = 0.75 * dusk + 0.25 * n_l
    rain = L.sat(n_l, 0.70) * np.array([0.90, 0.96, 1.0]) * 0.92
    rain = L.contrast(rain, 0.92, 0.2)
    fog = L.contrast(L.sat(g, 0.55), 0.78, 0.5) * np.array([0.92, 0.96, 1.0]) * 0.88 + 0.03
    snowl = L.contrast(L.sat(g, 0.72), 0.86, 0.55) * np.array([0.90, 0.95, 1.04]) * 0.92 + 0.02
    luts = [day, dusk, n_l, rain, fog, snowl]
    strip = np.concatenate([L.to_strip(np.clip(t, 0, 1)) for t in luts], 0)

    # ---- Rauschen (kachelbar, 1/f) -------------------------------------------------------------
    rng = np.random.default_rng(20261011)
    fy_, fx_ = np.meshgrid(np.fft.fftfreq(256), np.fft.fftfreq(256), indexing="ij")
    f = np.hypot(fx_, fy_)
    f[0, 0] = 1
    chans = []
    for beta, lowcut in ((2.0, 0.0), (2.6, 0.0), (1.2, 0.02)):
        spec = np.fft.fft2(rng.standard_normal((256, 256))) / f ** (beta / 2)
        spec[f < lowcut] = 0
        spec[0, 0] = 0
        n = np.fft.ifft2(spec).real
        n = (n - n.mean()) / (n.std() * 4) + 0.5
        chans.append(np.clip(n, 0, 1))
    noise = np.stack(chans, -1)

    # ---- Ausgabe ------------------------------------------------------------------------------
    OUT.mkdir(exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    files = {
        "bg.png": out_size(bg),
        "sky_plate.png": out_size(plate),
        "data_a.png": np.stack([out_size(sky, Image.BOX), out_size(water, Image.BOX), out_size(depth, Image.BOX)], -1),
        "data_b.png": out_size(frac, Image.BOX),
        "data_c.png": np.stack([out_size(cloud, Image.BOX), out_size(boat, Image.BOX), out_size(snow_a, Image.BOX)], -1),
        "snow_rgb.png": out_size(snow),
        "light.png": out_size(light, Image.BOX),
    }
    for name, arr in files.items():
        io.save(OUT / name, arr)
    io.save(OUT / "lut.png", strip)
    io.save(OUT / "noise.png", noise)
    sx = lambda n: to720(pos[n][0], pos[n][1])
    bx = pos["chimney"][2]
    scene = {
        "size": [W, H], "crop_y0": Y0, "scale": S,
        "horizon_y": round((horizon - Y0) * S, 1),
        "window": sx("window"), "lantern": sx("lantern"), "lamp": sx("lamp"),
        "chimney": [round((bx[0] + bx[2]) / 2 * S, 1), round((bx[1] - Y0) * S, 1)],
        "chimney_width": round((bx[2] - bx[0]) * S, 1),
        "badger_feet": to720(*badger_feet),
        "badger_irradiance": [round(float(v), 4) for v in irr_feet],
        "night_sky": {"top": nsky_top.round(4).tolist(), "horizon": nsky_hor.round(4).tolist(),
                      "cloud": ncloud.round(4).tolist()},
        "states": STATES,
        "night_lut_affine": M.round(4).tolist(),
    }
    (OUT / "scene.json").write_text(json.dumps(scene, indent=1))
    for name in list(files) + ["lut.png", "noise.png", "scene.json"]:
        shutil.copy2(OUT / name, ART / name)
    print(json.dumps({k: scene[k] for k in ("horizon_y", "window", "lantern", "lamp", "chimney", "badger_feet")}))

    if dbg:
        io.save(dbg / "sky.png", sky); io.save(dbg / "water.png", water); io.save(dbg / "depth.png", depth)
        io.save(dbg / "snow_a.png", snow_a); io.save(dbg / "cloud.png", cloud); io.save(dbg / "plate.png", plate)
        io.save(dbg / "light.png", np.clip(light * 2, 0, 1)); io.save(dbg / "frac.png", frac)
        io.save(dbg / "night_pred.png", L.apply(nlut, bg))
        for i, (nm, t) in enumerate(zip(STATES, luts)):
            io.save(dbg / f"lut_{i}_{nm}.png", L.apply(np.clip(t, 0, 1), bg))


if __name__ == "__main__":
    main()
