#!/usr/bin/env python3
"""Bereitet das KI-Foto für die Shader-Animation vor (Hintergrund des Eintrags fotoreal-standbild).

    .venv/bin/python styles/fotoreal-standbild/tools/prep_scene.py [--debug <Ordner>]

Eingaben: assets/raw/bg.png (KI-Foto, agy, 1264x848), assets/raw/mask.png (KI-Farbcode-Maske derselben Komposition),
Einstellungen in tools/scene.json (Ausschnitt, Retusche, Lichter, Boote, Strahl, Rauch).
Ausgaben nach assets/ und demo/art/ (alle 1280x720):
  photo.png   retuschiertes Foto (Bootsnamen entfernt), 16:9-Ausschnitt
  plate.png   saubere Platte: Himmel hinter Häuschen, Laterne, Leuchtturm und Landzunge fortgesetzt, Wasser unter
              den Booten je Spalte senkrecht gespiegelt (oben Wasser, unten Spiegelung; für Wolkenzug, Wellen und
              Schaukeln)
  mask_a.png  R Wasser, G Himmel, B Sterne
  mask_b.png  R Fenster, G Laterne (Glas + Lichtschein auf Pfosten, Wand, Kai), B Leuchtfeuer
  mask_c.png  R Boot 1, G Boot 2, B Sichtbarkeit des Leuchtturmstrahls (nur vor Himmel)
  photo_blur.png  weichgezeichnetes Foto (Lichtsaum um die Figur, Milchglas des Textfelds)
  noise.png   drei kachelbare Rauschkanäle 256x256
  scene.json  Lagen für main.gd
"""
import argparse, json, pathlib, shutil, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import aimask  # noqa: E402
import imgops as K  # noqa: E402

BASE = HERE.parent
W, H = 1280, 720


def retouch(img, rects):
    """Kleine Flächen (Bootsnamen) zeilenweise aus den Pixeln links und rechts daneben überblenden; die waagerechte
    Plankenstruktur bleibt, die Buchstaben verschwinden. Etwas Struktur aus der Zeile darüber/darunter dazu."""
    out = img.copy()
    for x0, y0, x1, y1 in rects:
        left = img[y0:y1, x0 - 2:x0].mean(1)
        right = img[y0:y1, x1:x1 + 2].mean(1)
        t = np.linspace(0, 1, x1 - x0)[None, :, None]
        base = left[:, None] * (1 - t) + right[:, None] * t
        # feine Struktur aus dem Bereich direkt über dem Rechteck (dieselbe Planke weiter oben)
        tex = img[y0 - (y1 - y0):y0, x0:x1]
        tex = tex - tex.mean((0, 1), keepdims=True)
        out[y0:y1, x0:x1] = np.clip(base + tex * 0.5, 0, 1)
        # weicher Übergang am Rand
        m = np.zeros(img.shape[:2], np.float32)
        m[y0:y1, x0:x1] = 1
        m = K.blur(m, 1)[..., None]
        out = img * (1 - m) + out * m
        img = out
    return out


def vertical_fill(plate, hole):
    """Loch unter einem Boot je Spalte senkrecht gespiegelt füllen: obere Hälfte aus dem Wasser darüber, untere aus der
    Spiegelung darunter. Schaukelt das Boot, wird nur ein schmaler Rand des Lochs sichtbar (bis etwa 4 px); dort muss
    die Platte dem Wasser direkt daneben gleichen. Pull-Push und waagerechtes Spiegeln mischten Wasser und dunkle
    Spiegelung zu einem dunklen Fleck, der beim Schaukeln als Schatten über und als heller Streifen unter dem Rumpf
    auftauchte. hole: bool (H, W)."""
    out = plate.copy()
    h, w = hole.shape
    for x in range(w):
        col = hole[:, x]
        ys = np.nonzero(col)[0]
        if len(ys) == 0:
            continue
        # Läufe [a, b) des Lochs in dieser Spalte
        cuts = np.nonzero(np.diff(ys) > 1)[0]
        starts = np.r_[ys[0], ys[cuts + 1]]
        ends = np.r_[ys[cuts] + 1, ys[-1] + 1]
        for a, b in zip(starts, ends):
            yy = np.arange(a, b)
            up = (yy - a) < (b - a) / 2
            if a == 0:
                up[:] = False
            if b >= h:
                up[:] = True
            src = np.where(up, 2 * a - 1 - yy, 2 * b - 1 - yy)
            # Quelle außerhalb des Bildes oder in einem anderen Loch: Randpixel des eigenen Laufs
            edge = np.where(up, a - 1, b)
            bad = (src < 0) | (src >= h)
            src = np.clip(src, 0, h - 1)
            bad |= col[src]
            src = np.where(bad, np.clip(edge, 0, h - 1), src)
            out[yy, x] = plate[src, x]
    return out


def crop_resize(arr_img, c, resample):
    w = arr_img.width
    ch = round(w * 9 / 16)
    return arr_img.crop((0, c, w, c + ch)).resize((W, H), resample)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HERE / "scene.json"))
    ap.add_argument("--debug")
    a = ap.parse_args()
    cfg = json.loads(pathlib.Path(a.config).read_text())
    dbg = pathlib.Path(a.debug) if a.debug else None
    if dbg:
        dbg.mkdir(parents=True, exist_ok=True)
    art = BASE / "demo" / "art"
    art.mkdir(parents=True, exist_ok=True)
    assets = BASE / "assets"

    raw = K.load_rgb(BASE / "assets/raw/bg.png")
    raw = retouch(raw, cfg["retouch"])
    rh, rw = raw.shape[:2]

    # --- KI-Maske einordnen und auf das Foto ausrichten (beide aus agy, gleiche Größe) ------------------------
    mraw = Image.open(BASE / "assets/raw/mask.png").convert("RGB")
    if mraw.size != (rw, rh):
        mraw = mraw.resize((rw, rh), Image.BILINEAR)
    lab = aimask.classify(np.asarray(mraw, np.float32) / 255.0)
    T = aimask.align(raw, lab)
    print("Ausrichtung Maske -> Foto:", T)
    lab = aimask.warp_lab(lab, (T["sx"], T["sy"], T["dx"], T["dy"]), (rw, rh))

    c = cfg["crop_y"]
    photo_im = crop_resize(Image.fromarray((raw * 255 + 0.5).astype(np.uint8)), c, Image.LANCZOS)
    img = np.asarray(photo_im, np.float32) / 255.0
    lab = np.asarray(crop_resize(Image.fromarray(lab), c, Image.NEAREST))
    reg = aimask.regions(lab)
    L = K.luma(img)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    size = (W, H)

    # --- Himmel und Wasser kantentreu ---------------------------------------------------------------------
    sky0, water0 = reg["sky"], reg["water"]
    sky = K.smoothstep(0.25, 0.75, K.guided(img, sky0, 6, 2e-3))
    # dünne dunkle Teile vor dem Himmel (Laternenhaken, Wetterfahne, Dachkante): nahe an "nicht Himmel" und
    # deutlich dunkler als die Umgebung -> fest, sonst ziehen sie mit den Wolken
    near_obj = K.blur(1 - sky0, 6) > 0.02
    thin = K.smoothstep(0.03, 0.07, -(K.luma(img) - K.blur(K.luma(img), 3))) * near_obj
    thin = np.clip(K.blur(thin, 1) * 2.5, 0, 1)
    sky = sky * (1 - thin)
    water = K.smoothstep(0.25, 0.75, K.guided(img, water0, 6, 2e-3))
    water = np.minimum(water, 1 - sky)
    # Festmacherleinen und Pfähle im Wasser: dünne dunkle Linien bleiben stehen (sonst wabern sie mit den Wellen)
    hp = L - K.blur(L, 3)
    ropes = K.smoothstep(cfg.get("rope_lo", 0.035), cfg.get("rope_hi", 0.08), -hp) * (water0 > 0.5)
    ropes = np.clip(K.blur(ropes, 1) * 1.8, 0, 1)
    if cfg.get("rope_zone"):
        ropes *= K.poly_mask(size, cfg["rope_zone"])
    water = water * (1 - ropes)

    # --- Boote: KI-Fläche, an die Bildkanten gelegt -------------------------------------------------------------
    boats = []
    for i, b in enumerate(cfg["boats"]):
        m0 = reg.get(f"boat{i + 1}", np.zeros((H, W), np.float32))
        m0 = np.clip(K.blur(m0, 2) * 2.5, 0, 1)  # etwas größer: Bojen und Bordwand ganz drin
        hole = np.clip(K.blur(m0, 4) * 3, 0, 1)
        env = K.pushpull(img, (1 - hole) ** 4)
        diff = np.abs(K.blur(img, 1) - K.blur(env, 1)).max(-1)
        m1 = np.maximum(K.smoothstep(0.04, 0.10, diff) * m0, (K.blur(m0, 4) > 0.97).astype(np.float32))
        m = K.smoothstep(0.3, 0.7, K.guided(img, m1, 2, 2e-3)) * (K.blur(m0, 3) > 0.02)
        boats.append(m.astype(np.float32))
    boat_any = np.maximum(boats[0], boats[1])
    water = water * (1 - boat_any)

    # --- Sterne: kleine helle, fast farblose Punkte im Himmel --------------------------------------------------
    sat = img.max(-1) - img.min(-1)
    # Wolkenränder sind auch hell und fein: nur dort, wo der Himmel ringsum ruhig ist (wenig Struktur)
    calm = K.blur(np.abs(L - K.blur(L, 4)), 8)
    stars = (K.smoothstep(0.018, 0.045, L - K.blur(L, 3)) * (sky > 0.95) * (sat < 0.2)
             * (yy < cfg["horizon_y"] - 60) * (calm < cfg.get("star_calm", 0.012)))
    stars = np.clip(K.blur(stars, 1) * 2.0, 0, 1) * (sky > 0.9)

    # --- Lichter --------------------------------------------------------------------------------------------
    warm = np.clip((img[..., 0] - img[..., 2]) * 2.0, 0, 1)
    chan = {}
    lights = {}
    for li in cfg["lights"]:
        m = reg[li["code"]]
        if m.sum() > 0:
            pos = [float((xx * m).sum() / m.sum()), float((yy * m).sum() / m.sum())]
        else:
            pos = li["pos"]
        if li.get("pos"):
            pos = li["pos"]  # von Hand gesetzt (KI-Fläche zu grob)
        lights[li["name"]] = [round(pos[0], 1), round(pos[1], 1)]
        d = np.hypot(xx - pos[0], yy - pos[1])
        core = K.smoothstep(0.35, 0.75, L * (0.5 + warm)) * np.clip(K.blur(m, 2) * 3, 0, 1)
        ch = core
        if li.get("pool_r"):
            fall = np.clip(1 - d / li["pool_r"], 0, 1) ** li.get("pool_gamma", 1.5)
            pool = fall * K.smoothstep(0.03, 0.35, warm * (0.3 + L)) * li.get("pool_k", 0.7) * (1 - sky)
            ch = np.maximum(ch, pool)
        for fp in li.get("floor_pools", []):
            cx_, cy_ = fp["center"]
            r_ell = np.hypot((xx - cx_) / fp["rx"], (yy - cy_) / fp["ry"])
            fall = np.clip(1 - r_ell, 0, 1) ** fp.get("gamma", 0.8)
            ch = np.maximum(ch, fall * K.smoothstep(0.02, 0.3, warm * (0.3 + L)) * fp.get("k", 0.6)
                            * (1 - sky) * (1 - water))
        chan[li["channel"]] = np.maximum(chan.get(li["channel"], 0), ch)
    zero = np.zeros((H, W), np.float32)

    # --- Strahl nur vor Himmel ----------------------------------------------------------------------------------
    beam_vis = K.blur(sky, 2)

    # --- saubere Platte ---------------------------------------------------------------------------------------
    grow = lambda m, r: np.clip(K.blur(m, r) * 4, 0, 1)  # noqa: E731
    boat_hole = grow(boat_any, 3)
    plate1 = K.pushpull(img, (1 - boat_hole) ** 4)
    known = np.clip(np.maximum(sky, water), 0, 1)
    known = np.where(boat_hole > 0.05, 0.0, known) * (1 - grow(stars, 2))
    core = (K.box((known > 0.5).astype(np.float32), 3) > 0.999).astype(np.float32)
    known = np.minimum(known, core)
    plate_pp = K.pushpull(plate1, known ** 2)
    plate = K.mirror_fill(plate1, known > 0.5, plate_pp, reach=48)
    plate = vertical_fill(plate, boat_hole > 0.05)

    photo_blur = K.blur(K.blur(img, 6), 6)

    n = 256
    noise = np.stack([K.tile_noise(n, 1.0, 11), K.tile_noise(n, 1.6, 23), K.tile_noise(n, 0.7, 37)], -1)

    outs = {
        "photo.png": img, "plate.png": plate,
        "mask_a.png": np.stack([water, sky, stars], -1),
        "mask_b.png": np.stack([chan.get("window", zero), chan.get("lantern", zero), chan.get("lamp", zero)], -1),
        "mask_c.png": np.stack([boats[0], boats[1], beam_vis], -1),
        "photo_blur.png": photo_blur,
    }
    for name, arr in outs.items():
        K.save_rgb(arr, art / name)
    K.save_rgb(noise, art / "noise.png")
    for name in ("photo.png", "plate.png", "mask_a.png", "mask_b.png", "mask_c.png"):
        shutil.copy(art / name, assets / name)

    def to_out(p):
        return [round(p[0] * W / rw, 1), round((p[1] - c) * H / (rw * 9 / 16), 1)]

    scene = {k: cfg[k] for k in ("horizon_y", "quay_y", "beam", "smoke", "ui", "badger") if k in cfg}
    scene["lights"] = lights
    scene["chimney"] = cfg["chimney"]
    scene["boats"] = cfg["boats"]
    scene["mask_align"] = T
    (art / "scene.json").write_text(json.dumps(scene, indent=1))

    stats = {"sky": round(float((sky > 0.5).mean()), 3), "water": round(float((water > 0.5).mean()), 3),
             "stars_px": int((stars > 0.5).sum()), "boat_px": [int((m > 0.5).sum()) for m in boats],
             "rope_px": int((ropes > 0.5).sum()), "lights": lights,
             "light_px": {k: int((v > 0.5).sum()) for k, v in chan.items()}}
    print(json.dumps(stats))
    if dbg:
        ov = img * 0.45
        ov[..., 2] += sky * 0.5
        ov[..., 1] += water * 0.45
        ov[..., 0] += boat_any * 0.6
        ov += stars[..., None] * 0.8
        ov[..., 0] += sum(chan.values()) * 0.6
        ov[..., 1] += ropes * 0.6
        K.save_rgb(np.clip(ov, 0, 1), dbg / "masks_overlay.png")
        K.save_rgb(plate, dbg / "plate.png")
        K.save_rgb(aimask.to_rgb(lab) / 255.0, dbg / "labels.png")


if __name__ == "__main__":
    main()
