#!/usr/bin/env python3
"""Bereitet ein gemaltes Standbild für die Shader-Animation vor (Kinemagramm).

    .venv/bin/python styles/kinemagramm/tools/prep.py styles/kinemagramm/tools/scene.json [--out styles/kinemagramm/demo/art]

Eingaben (Pfade in der Konfiguration relativ zum Eintragsordner):
  src        gemaltes KI-Bild (3:2), wird auf 16:9 beschnitten und auf 1280x720 verkleinert
  sky/water  grobe Polygone (Bildschirmpixel 1280x720) ODER ai_labels: ausgerichtete KI-Farbcode-Maske
             (1280x720, von auto_scene.py); Boote dann ohne poly aus den Codeflächen
  lights     Lichtquellen mit Lage und Kanal (window, lantern, lamp)
  boats      Polygone + Drehpunkt je Boot (Schaukeln)
Ausgaben (alle 1280x720):
  still.png  das Standbild
  plate.png  "saubere Platte": Himmel und Wasser über Objekte und Boote hinweg fortgesetzt (Pull-Push),
             damit Verzerrungen keine Objektfarben ins Wasser ziehen und Boote beim Schaukeln nichts aufreißen
  mask_a.png R Wasser, G Himmel, B Sterne
  mask_b.png R Fenster, G Laterne, B Leuchtfeuer (Leuchtfläche + gemalter Lichtschein, für Flackern)
  mask_c.png R Boot 1, G Boot 2, B Sichtbarkeit des Strahls
  noise.png  drei kachelbare Rauschkanäle 256x256
  scene.json Lage von Lichtern, Schornstein, Horizont, Drehpunkten für main.gd
"""
import argparse, json, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import imgops as K  # noqa: E402

W, H = 1280, 720


def load_still(src, crop_y):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    ch = round(w * 9 / 16)
    if ch > h:
        cw = round(h * 16 / 9)
        x0 = (w - cw) // 2
        box = (x0, 0, x0 + cw, h)
    else:
        y0 = round((h - ch) * crop_y)
        box = (0, y0, w, y0 + ch)
    return im.crop(box).resize((W, H), Image.LANCZOS), box


def ai_regions(path):
    """Liest die ausgerichtete KI-Farbcode-Maske (1280x720, von auto_scene.py geschrieben) als 0/1-Masken
    je Code (aimask.CODES), dazu boat1/boat2 als getrennte Boote."""
    import aimask
    im = Image.open(path).convert("RGB")
    if im.size != (W, H):
        sys.exit(f"{path}: erwartet {W}x{H}, ist {im.size[0]}x{im.size[1]} (auto_scene.py schreibt sie ausgerichtet)")
    return aimask.regions(aimask.from_rgb(im))


def box_x(a, r):
    """Mittelwert nur waagerecht über 2r+1 Pixel."""
    c = np.pad(np.cumsum(a.astype(np.float64), 1), ((0, 0), (1, 0)))
    n = a.shape[1]
    hi = np.minimum(np.arange(n) + r + 1, n)
    lo = np.maximum(np.arange(n) - r, 0)
    return ((c[:, hi] - c[:, lo]) / (hi - lo)).astype(np.float32)


def convex_hull_mask(m):
    """Konvexe Hülle einer 0/1-Maske als 0/1-Maske (monotone Kette über die Randpunkte je Zeile)."""
    ys, xs = np.where(m)
    if len(ys) < 3:
        return m.astype(np.float32)
    pts = set()
    for y in np.unique(ys):
        row = xs[ys == y]
        pts.add((int(row.min()), int(y)))
        pts.add((int(row.max()), int(y)))
    pts = sorted(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    return K.poly_mask((m.shape[1], m.shape[0]), [hull])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--out")
    ap.add_argument("--debug")
    a = ap.parse_args()
    cfgp = pathlib.Path(a.config).resolve()
    cfg = json.loads(cfgp.read_text())
    base = cfgp.parent.parent if cfg.get("base") is None else (cfgp.parent / cfg["base"]).resolve()
    out = pathlib.Path(a.out or base / "demo" / "art")
    out.mkdir(parents=True, exist_ok=True)
    dbg = pathlib.Path(a.debug) if a.debug else None
    if dbg:
        dbg.mkdir(parents=True, exist_ok=True)

    still_im, still_box = load_still(base / cfg["src"], cfg.get("crop_y", 0.5))
    still_im.save(out / "still.png")
    img = np.asarray(still_im, np.float32) / 255.0
    L = K.luma(img)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

    # --- grobe Masken: Polygone oder KI-Maske ---------------------------------------------------
    size = (W, H)
    if cfg.get("ai_labels"):
        reg = ai_regions(base / cfg["ai_labels"])
        sky0, water0 = reg["sky"], reg["water"]
    else:
        reg = {}
        sky0 = K.poly_mask(size, cfg["sky"])
        water0 = K.poly_mask(size, cfg["water"])
    if cfg.get("sky_exclude"):
        sky0 *= 1 - K.poly_mask(size, cfg["sky_exclude"])
    if cfg.get("water_exclude"):
        water0 *= 1 - K.poly_mask(size, cfg["water_exclude"])
    if cfg.get("sky_add"):
        sky0 = np.maximum(sky0, K.poly_mask(size, cfg["sky_add"]))
    if cfg.get("water_add"):
        water0 = np.maximum(water0, K.poly_mask(size, cfg["water_add"]))

    # Kanten an das Bild anlegen (Guided Filter), dann leicht weich
    gr, ge = cfg.get("guided_r", 6), cfg.get("guided_eps", 2e-3)
    sky = K.smoothstep(0.25, 0.75, K.guided(img, sky0, gr, ge))
    water = K.smoothstep(0.25, 0.75, K.guided(img, water0, gr, ge))
    water = np.minimum(water, 1 - sky)

    # Boote: Polygone (+ Masten als Linien), kantentreu verfeinert
    # Boote: grobes Polygon (oder KI-Maske), darin "was sich von der Umgebung unterscheidet":
    # Umgebung von außen in das Polygon hineinfüllen (Pull-Push) und den Farbabstand messen.
    boats = []
    for i, b in enumerate(cfg.get("boats", [])):
        if b.get("poly"):
            m0 = K.poly_mask(size, [b["poly"]])
        else:
            m0 = reg.get(f"boat{i + 1}", reg.get("boats", np.zeros((H, W), np.float32)))
            if b.get("clip"):
                m0 = m0 * K.poly_mask(size, [b["clip"]])
        if b.get("masts"):
            m0 = np.maximum(m0, K.poly_mask(size, b["masts"], width=b.get("mast_w", 5)))
        if b.get("segment", True):
            hole = np.clip(K.blur(m0, 4) * 3, 0, 1)
            env = K.pushpull(img, (1 - hole) ** 4)
            diff = np.abs(K.blur(img, 1) - K.blur(env, 1)).max(-1)
            lo, hi = b.get("diff", [0.05, 0.12])
            m1 = K.smoothstep(lo, hi, diff) * np.clip(K.blur(m0, 2) * 2, 0, 1)
            core = (K.blur(m0, b.get("core_r", 4)) > 0.97).astype(np.float32)  # Inneres des Polygons immer Boot
            m1 = np.maximum(m1, core)
        else:
            m1 = m0
        m = K.smoothstep(0.3, 0.7, K.guided(img, m1, 2, 2e-3)) * (K.blur(m0, 3) > 0.02)
        if b.get("rigging", True):
            # Takelage: dünne dunkle, nicht waagerechte Linien innerhalb der konvexen Hülle des Boots (Mast bis
            # Rumpf) gehören zum Boot. Sonst liegen sie im Wasser, wabern mit der Verzerrung und reißen beim
            # Schaukeln vom Mast ab. Waagerechter Hochpass: waagerechte Wellenstriche bleiben draußen.
            hull = K.blur(convex_hull_mask(m > 0.5), 2) > 0.02
            hp_x = L - box_x(L, b.get("rig_r", 3))
            near_water = K.blur(water0, 2) > 0.5   # Steg, Pfähle und Kai bleiben draußen
            rig = K.smoothstep(b.get("rig_lo", 0.025), b.get("rig_hi", 0.06), -hp_x) * hull * near_water
            rig = np.clip(K.blur(rig, 1) * 1.6, 0, 1) * hull
            m = np.maximum(m, rig)
        boats.append(m)
        if dbg:
            K.save_gray(m, dbg / f"boat{i + 1}.png")
    boat_any = np.zeros((H, W), np.float32)
    for m in boats:
        boat_any = np.maximum(boat_any, m)

    # Sterne: kleine helle Punkte im Himmel (Hochpass)
    # Sterne: kleine, helle, fast farblose Punkte im Himmel, die deutlich heller als ihr Umfeld sind
    hp = L - K.blur(L, 4)
    sat = img.max(-1) - img.min(-1)
    stars = K.smoothstep(cfg.get("star_lo", 0.10), cfg.get("star_hi", 0.22), hp) * (sky > 0.95)
    stars *= (L > cfg.get("star_min_luma", 0.5)) * (sat < cfg.get("star_max_sat", 0.25))
    if cfg.get("star_zone"):
        stars *= K.poly_mask(size, cfg["star_zone"])
    stars = np.clip(K.blur(stars, 1) * 2.2, 0, 1) * (sky > 0.9)

    # Lichter: Leuchtfläche (hell und warm) und gemalter Lichtschein (warm, mit Abstand abfallend)
    warm = np.clip((img[..., 0] - img[..., 2]) * 2.0, 0, 1)
    chan = {"window": np.zeros((H, W), np.float32), "lantern": np.zeros((H, W), np.float32),
            "lamp": np.zeros((H, W), np.float32)}
    for li in cfg.get("lights", []):
        if li.get("from_ai"):
            # Lage aus der KI-Maske: Schwerpunkt der Farbfläche (optional auf ein Suchfeld begrenzt)
            m = reg[li["from_ai"]]
            if li.get("search"):
                m = m * K.poly_mask(size, [li["search"]])
            if m.sum() > 0:
                li["pos"] = [round(float((xx * m).sum() / m.sum()), 1), round(float((yy * m).sum() / m.sum()), 1)]
                li["ai_px"] = int(m.sum())
            print("Licht", li["name"], "aus KI-Maske:", li.get("pos"), li.get("ai_px"))
        px, py = li["pos"]
        d = np.hypot(xx - px, yy - py)
        core = K.smoothstep(li.get("core_lo", 0.45), li.get("core_hi", 0.8), L * (0.5 + warm)) * (d < li["r"])
        pool = np.zeros_like(core)
        if li.get("pool_r"):
            fall = np.clip(1 - d / li["pool_r"], 0, 1) ** 2
            pool = fall * K.smoothstep(0.05, 0.5, warm * L * 2) * li.get("pool_k", 0.7)
            if li.get("pool_clip"):
                pool *= K.poly_mask(size, li["pool_clip"])
        chan[li["channel"]] = np.maximum(chan[li["channel"]], np.maximum(core, pool))
    # Lichtschein auf dem Boden (Kai, Steg): warme Pixel in einer flachen Ellipse unter der Lampe, linear abfallend;
    # der kreisförmige pool oben fällt quadratisch ab und erreicht den Kai unter der Laterne kaum
    for fp in cfg.get("floor_pools", []):
        cx_, cy_ = fp["center"]
        r_ell = np.hypot((xx - cx_) / fp["rx"], (yy - cy_) / fp["ry"])
        fall = np.clip(1 - r_ell, 0, 1) ** fp.get("gamma", 0.8)
        fpool = fall * K.smoothstep(0.05, 0.5, warm * L * 2) * fp.get("k", 0.6) * (1 - sky) * (1 - water)
        chan[fp["channel"]] = np.maximum(chan[fp["channel"]], fpool)

    # Sichtbarkeit des Leuchtturmstrahls: nur vor Himmel (alles davor verdeckt ihn), am Rand weich
    beam_vis = K.blur(sky, 2) * (1 - boat_any)
    if cfg.get("beam_add"):
        beam_vis = np.maximum(beam_vis, K.blur(K.poly_mask(size, cfg["beam_add"]), 6) * 0.6)

    # --- saubere Platte -----------------------------------------------------------------------
    grow = lambda m, r: np.clip(K.blur(m, r) * 4, 0, 1)  # noqa: E731
    boat_hole = grow(boat_any, 3)
    plate1 = K.pushpull(img, (1 - boat_hole) ** 4)
    known2 = np.clip(np.maximum(sky, water) * 1.0, 0, 1)
    # Unter dem Horizont wird das Bootsloch aus dem Wasser daneben gefüllt (gespiegelte Wellenstruktur), nicht aus
    # plate1: dessen Pull-Push-Füllung ist ein grauer Schmierfleck, den die Wasserverzerrung als Saum ums Boot zieht.
    # Darüber (Mastspitzen vor Bergen) bleibt plate1, dort gibt es kein Wasser zum Spiegeln.
    hole_above = (boat_hole > 0.05) & (yy < cfg.get("horizon_y", 0))
    known2 = np.where(hole_above, 1.0, np.where(boat_hole > 0.05, 0.0, known2)) * (1 - grow(stars, 2))
    er = cfg.get("plate_erode", 3)
    if er:
        # Saum an Objektkanten (dunkle Kontur, Kantenglättung) nicht in die Platte übernehmen: Beim Ziehen des
        # Himmels wandert er sonst als Geisterlinie neben dem Objekt mit (gesehen am Schornstein)
        core = (K.box((known2 > 0.5).astype(np.float32), er) > 0.999).astype(np.float32)
        known2 = np.minimum(known2, core)
    plate_pp = K.pushpull(plate1, known2 ** 2)
    # Nahe den Rändern gespiegelte Pinselstruktur statt Weichzeichnung (die Verzerrung tastet dort ab)
    plate = K.mirror_fill(plate1, known2 > 0.5, plate_pp, reach=cfg.get("mirror_reach", 48))
    if cfg.get("plate_patch"):
        # Stellen, die im Standbild übermalt werden müssen (z. B. mitgemalter Rauch): aus der Umgebung füllen
        patch = K.blur(K.poly_mask(size, cfg["plate_patch"]), 4)
        fill = K.pushpull(img, 1 - np.clip(patch * 3, 0, 1))
        img = img * (1 - patch[..., None]) + fill * patch[..., None]
        plate = plate * (1 - patch[..., None]) + fill * patch[..., None]
        K.save_rgb(img, out / "still.png")

    K.save_rgb(plate, out / "plate.png")
    K.save_rgb(np.stack([water, sky, stars], -1), out / "mask_a.png")
    K.save_rgb(np.stack([chan["window"], chan["lantern"], chan["lamp"]], -1), out / "mask_b.png")
    b1 = boats[0] if len(boats) > 0 else np.zeros((H, W), np.float32)
    b2 = boats[1] if len(boats) > 1 else np.zeros((H, W), np.float32)
    K.save_rgb(np.stack([b1, b2, beam_vis], -1), out / "mask_c.png")

    n = 256
    noise = np.stack([K.tile_noise(n, 1.0, 11), K.tile_noise(n, 1.6, 23), K.tile_noise(n, 0.7, 37)], -1)
    K.save_rgb(noise, out / "noise.png")

    for li in cfg.get("lights", []):
        if li["channel"] == "lamp" and li.get("from_ai"):
            cfg["lamp"] = li["pos"]
    scene = {k: cfg[k] for k in ("lamp", "chimney", "horizon_y", "quay_y", "beam_len", "ui", "gulls") if k in cfg}
    scene["lights"] = [{"name": li["name"], "pos": li["pos"], "channel": li["channel"],
                        "glow": li.get("glow", 60), "glow_k": li.get("glow_k", 0.16)} for li in cfg.get("lights", [])]
    scene["boats"] = [{"pivot": b["pivot"], "amp_deg": b.get("amp_deg", 1.0), "period": b.get("period", 4.0),
                       "phase": b.get("phase", 0.0), "bob": b.get("bob", 1.0)} for b in cfg.get("boats", [])]
    scene["badger"] = cfg.get("badger", {})
    (out / "scene.json").write_text(json.dumps(scene, indent=1))

    stats = {"sky_share": float((sky > 0.5).mean()), "water_share": float((water > 0.5).mean()),
             "stars_px": int((stars > 0.5).sum()), "boat_px": [int((m > 0.5).sum()) for m in boats],
             "window_px": int((chan["window"] > 0.5).sum()), "lantern_px": int((chan["lantern"] > 0.5).sum()),
             "lamp_px": int((chan["lamp"] > 0.5).sum())}
    print(json.dumps(stats))
    if dbg:
        # Kontrollbild: Masken farbig über dem Standbild
        ov = img * 0.45
        ov[..., 2] += sky * 0.5
        ov[..., 1] += water * 0.45
        ov[..., 0] += boat_any * 0.6
        ov += stars[..., None] * 0.8
        ov[..., 0] += (chan["window"] + chan["lantern"] + chan["lamp"]) * 0.5
        K.save_rgb(np.clip(ov, 0, 1), dbg / "masks_overlay.png")
        K.save_rgb(plate, dbg / "plate.png")
        K.save_gray(sky0, dbg / "sky_coarse.png")
        K.save_gray(water0, dbg / "water_coarse.png")
        for name, m in reg.items():
            K.save_gray(m, dbg / f"ai_{name}.png")


if __name__ == "__main__":
    main()
