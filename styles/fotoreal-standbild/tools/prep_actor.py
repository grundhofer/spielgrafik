#!/usr/bin/env python3
"""Bereitet den freigestellten KI-Dachs für das Einsetzen ins Foto vor (wie ein vor Bluescreen gefilmter Darsteller).

    .venv/bin/python styles/fotoreal-standbild/tools/prep_actor.py [--debug <Ordner>]

Eingabe: assets/raw/badger.png (Codex, echter Alphakanal), Einstellungen tools/actor.json.
Schritte (alle Zahlen in actor.json):
  1. Alpha säubern (Codex liefert innen 252-253 statt 255), Randfarben aus dem Inneren fortsetzen (keine Säume)
  2. Licht angleichen, in linearem Licht:
     a) das helle Studio-Führungslicht von links abschwächen (Rampe über die Figurenbreite),
     b) Weißabgleich und Belichtung über ein bekanntes Weiß: das weiße Bauchfell soll so hell und so blau sein wie
        die weiße Wand des Leuchtturms im Foto (gleiches Himmelslicht),
     c) Gesicht und Brust (oben, zur Kamera gewandt) dämpfen: die Szene ist Gegenlicht (top_gain),
     d) Sättigung senken, Bodenverschattung an den Füßen
  1b. Kopfdrehung: Kopf der zweiten KI-Fassung (assets/raw/badger_look.png) oberhalb des Schals auf den Körper der
     ersten setzen, Belichtung je Kanal über das Bauchfell angleichen -> actor_look.png (gleich groß, deckungsgleich)
  3. vormultipliziert verkleinern, Schärfe angleichen (Nachschärfen wie im KI-Foto; gemessen mit measure_match.py).
     Die Farbtexturen (actor, actor_look, actor_raw) entstehen in tex_scale-facher Auflösung (2x: 370x514); der Shader
     verkleinert sie mit 3x3 Abtastpunkten. So bleibt die Schärfe gleich, wenn Atmen und Gewichtsverlagerung die Figur um
     Bruchteile eines Pixels verschieben (bei 1x pumpte sie mit der linearen Filterung, gemessen mit measure_sharp.py).
     Hilfskarten und Schatten sind weich und bleiben in 1x.
  4. Hilfskarten für den Shader: actor_aux.png R/G Randnormale (x, y), B Randband (für Kantenlicht aus beliebiger
     Richtung); actor_aux2.png R Lichtsaum-Band, G Gewicht des wehenden Schalendes
  5. Schatten: Kontaktschatten unter den Füßen + weicher Schlagschatten von der Laterne weg (nach rechts vorn)
Immer dabei: actor_raw.png, nur freigestellt und verkleinert, ohne Angleichung (für den Schalter --raw der Demo).
Ausgaben nach demo/art/ und assets/: actor.png, actor_look.png, actor_aux.png, actor_aux2.png, actor_shadow.png,
actor.json (Lagen für main.gd); nur demo/art/: actor_raw.png.
"""
import argparse, json, pathlib, shutil, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import imgops as K  # noqa: E402

BASE = HERE.parent


def to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def resize_premul(rgb, al, size):
    """Vormultipliziert verkleinern (keine dunklen oder farbigen Säume), dann wieder teilen."""
    pm = np.dstack([rgb * al[..., None], al])
    chans = [np.asarray(Image.fromarray(pm[..., k].astype(np.float32), "F").resize(size, Image.LANCZOS))
             for k in range(4)]
    pm = np.clip(np.stack(chans, -1), 0, None)
    a = np.clip(pm[..., 3], 0, 1)
    rgb = pm[..., :3] / np.maximum(a, 1e-4)[..., None]
    return np.clip(rgb, 0, 1), a


def gauss(a, sigma):
    """Separables Gauß-Filter (NumPy), Ränder fortgesetzt."""
    r = max(1, int(np.ceil(sigma * 3)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    p = np.pad(a, [(r, r), (r, r)] + [(0, 0)] * (a.ndim - 2), mode="edge")
    out = sum(k[i] * p[:, i:i + a.shape[1]] for i in range(2 * r + 1))
    out = sum(k[i] * out[i:i + a.shape[0]] for i in range(2 * r + 1))
    return out.astype(np.float32)


def gauss_premul(rgb, al, sigma):
    if sigma <= 0:
        return rgb, al
    pm = gauss(np.dstack([rgb * al[..., None], al]), sigma)
    a = np.clip(pm[..., 3], 0, 1)
    return np.clip(pm[..., :3] / np.maximum(a, 1e-4)[..., None], 0, 1), a


def sharpen(rgb, sh):
    """Unscharf maskieren wie die Kamera-Nachschärfung im KI-Foto (sh = [sigma, Stärke]); nur Farbe, Alpha bleibt.
    Die Randfarben sind aus dem Inneren fortgesetzt, deshalb entsteht am Umriss kein Saum."""
    if not sh:
        return rgb
    return np.clip(rgb + (rgb - gauss(rgb, sh[0])) * sh[1], 0, 1)


def load_clean(path, cfg):
    """Alpha säubern (Codex liefert innen 252-253 statt 255) und Randfarben aus dem Inneren fortsetzen: halbtransparente
    Pixel bekommen die Farbe des nächsten deckenden Inneren (Pull-Push), gemischt mit ihrer eigenen nach Deckung; so
    trägt der Rand keine Reste des Erzeugungshintergrunds."""
    src = np.asarray(Image.open(path).convert("RGBA"), np.float32) / 255.0
    rgb, al = src[..., :3], src[..., 3]
    lo, hi = cfg.get("alpha_floor", 0.02), cfg.get("alpha_full", 0.985)
    al = np.clip((al - lo) / (hi - lo), 0, 1)
    ext = K.pushpull(rgb, (al > 0.97).astype(np.float32))
    t = K.smoothstep(0.4, 0.97, al)[..., None]
    return ext * (1 - t) + rgb * t, al


def grade(rgb, cfg, bbox, gains=None):
    """Licht angleichen in linearem Licht: Führungslicht links abschwächen, Weißabgleich + Belichtung über das weiße
    Bauchfell (Ziel: Weiß des Leuchtturms im Foto), Sättigung, Bodenverschattung. gains: von der ersten Fassung."""
    x0, x1, y0, y1 = bbox
    lin = to_lin(rgb)
    yy, xx = np.mgrid[0:rgb.shape[0], 0:rgb.shape[1]].astype(np.float32)
    u = (xx - x0) / (x1 - x0)
    v = (yy - y0) / (y1 - y0)
    kr = cfg["key_ramp"]
    key = kr["gain_left"] + (1 - kr["gain_left"]) * K.smoothstep(kr["u0"], kr["u1"], u)
    lin = lin * key[..., None]
    # Gegenlicht-Szene: zur Kamera gewandte Flächen oben (Gesicht, Brust) bekamen im KI-Bild das meiste Licht
    tg = cfg.get("top_gain")
    if tg:
        lin = lin * (tg[0] + (1 - tg[0]) * K.smoothstep(tg[1], tg[2], v))[..., None]
    bx = cfg["ref_white_box"]
    ref = lin[bx[1]:bx[3], bx[0]:bx[2]].reshape(-1, 3)
    ref = ref[np.argsort(ref.sum(1))[len(ref) // 4: len(ref) * 3 // 4]].mean(0)   # mittlere Hälfte
    if gains is None:
        target = to_lin(np.array(cfg["target_white_srgb"], np.float32) / 255.0)
        gains = target / np.maximum(ref, 1e-4)
    lin = lin * gains
    Y = (lin * np.array([0.2126, 0.7152, 0.0722])).sum(-1, keepdims=True)
    lin = Y + (lin - Y) * cfg.get("saturation", 0.85)
    ao = cfg.get("foot_ao", [0.86, 0.6])
    lin = lin * (ao[0] + (1 - ao[0]) * (1 - K.smoothstep(1 - ao[1] * 0.25, 1.0, v)))[..., None]
    return to_srgb(lin), gains, ref


def scarf_top(rgb, al, hc):
    """Je Spalte die oberste Zeile des roten Schals (unterhalb search_y0), geglättet; ohne Schal y_max."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    red = (r > 0.25) & (r > 2.2 * g) & (r > 1.8 * b) & (al > 0.5)
    red[:hc["search_y0"]] = False
    red[hc["y_max"] + 60:] = False
    # einzelne Ausreißer weg: mindestens 6 rote Pixel in den 9 Zeilen darunter
    top = np.full(rgb.shape[1], float(hc["y_max"]))
    for x in range(rgb.shape[1]):
        rows = np.nonzero(red[:, x])[0]
        for r0 in rows:
            if red[r0:r0 + 9, x].sum() >= 6:
                top[x] = min(float(r0), hc["y_max"])
                break
    k = 15
    pad = np.pad(top, k, mode="edge")
    return np.array([np.median(pad[i:i + 2 * k + 1]) for i in range(len(top))])


def head_mask(shape, top, overlap, feather):
    yy = np.arange(shape[0], dtype=np.float32)[:, None]
    return (1 - K.smoothstep(-feather, feather, yy - (top[None, :] + overlap))).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HERE / "actor.json"))
    ap.add_argument("--debug")
    a = ap.parse_args()
    cfg = json.loads(pathlib.Path(a.config).read_text())
    art = BASE / "demo" / "art"
    art.mkdir(parents=True, exist_ok=True)
    dbg = pathlib.Path(a.debug) if a.debug else None
    if dbg:
        dbg.mkdir(parents=True, exist_ok=True)

    rgb, al = load_clean(BASE / "assets/raw/badger.png", cfg)
    ys, xs = np.nonzero(al > 0.5)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    raw_rgb, raw_al = rgb.copy(), al.copy()

    # --- Kopfdrehung: Kopf aus der zweiten KI-Fassung (gleiche Figur, Kopf nach rechts) auf den Körper der ersten
    look = None
    lp = BASE / "assets/raw/badger_look.png"
    if lp.exists() and cfg.get("head"):
        rgbB, alB = load_clean(lp, cfg)
        # Belichtung der zweiten Fassung an die erste angleichen (gleiches Bauchfell, je Kanal in linearem Licht)
        bx = cfg["ref_white_box"]
        mA = to_lin(rgb[bx[1]:bx[3], bx[0]:bx[2]]).reshape(-1, 3).mean(0)
        mB = to_lin(rgbB[bx[1]:bx[3], bx[0]:bx[2]]).reshape(-1, 3).mean(0)
        print("Bauchfell (linear) Fassung 1 / 2:", np.round(mA, 4), np.round(mB, 4))
        rgbB = to_srgb(to_lin(rgbB) * (mA / mB))
        hc = cfg["head"]
        topA, topB = scarf_top(rgb, al, hc), scarf_top(rgbB, alB, hc)
        headA = head_mask(al.shape, topA, 0, hc["feather"])
        headB = head_mask(al.shape, topB, hc["overlap_b"], hc["feather"])
        covB = alB * headB
        # Kopfpixel der ersten Fassung, die der gedrehte Kopf nicht verdeckt, verschwinden (sonst Doppelkopf)
        alA_clean = al * (1 - headA * (1 - np.clip(K.blur(covB, 2) * 1.5, 0, 1)))
        pm = rgbB * covB[..., None] + rgb * (alA_clean * (1 - covB))[..., None]
        al_l = covB + alA_clean * (1 - covB)
        look = (np.clip(pm / np.maximum(al_l, 1e-4)[..., None], 0, 1), al_l)
        if dbg:
            K.save_gray(headA, dbg / "headA.png")
            K.save_gray(headB, dbg / "headB.png")

    # --- 2. Licht angleichen ------------------------------------------------------------------------------
    graded, gains, ref = grade(rgb, cfg, (x0, x1, y0, y1))
    if look is not None:
        look = (grade(look[0], cfg, (x0, x1, y0, y1), gains)[0], look[1])

    # --- 3. verkleinern, Schärfe angleichen ---------------------------------------------------------------------
    H_px = cfg["height_px"]
    s = H_px / (y1 - y0)
    pad = 6
    bx0, by0 = max(0, x0 - int(pad / s)), max(0, y0 - int(pad / s))
    bx1, by1 = min(rgb.shape[1], x1 + int(pad / s)), min(rgb.shape[0], y1 + int(pad / s))
    size = (round((bx1 - bx0) * s), round((by1 - by0) * s))

    ts = int(cfg.get("tex_scale", 1))
    size_hi = (size[0] * ts, size[1] * ts)

    def shrink(c, aa, sz=size):
        return resize_premul(c[by0:by1, bx0:bx1], aa[by0:by1, bx0:bx1], sz)

    def finish(c, aa, k):
        # Weichzeichnen und Nachschärfen in Bildschirmpixeln (sigma mal k Texel)
        c, aa = gauss_premul(c, aa, cfg.get("soften_sigma", 0.0) * k)
        shp = cfg.get("sharpen")
        return sharpen(c, [shp[0] * k, shp[1]] if shp else None), aa

    # 1x: Grundlage der Hilfskarten (Randnormale, Schal, Schatten) und der Lagen in actor.json
    g_rgb, g_al = finish(*shrink(graded, al), 1)
    # tex_scale x: die Farbtexturen, die der Shader abtastet
    h_rgb, h_al = finish(*shrink(graded, al, size_hi), ts)
    if look is not None:
        l_rgb, l_al = finish(*shrink(*look, size_hi), ts)
    r_rgb, r_al = shrink(raw_rgb, raw_al, size_hi)

    # --- 4. Hilfskarten ---------------------------------------------------------------------------------
    A = g_al
    # Randnormale aus dem weichgezeichneten Alpha (nach außen = -grad), selbst noch einmal geglättet: der Shader
    # rechnet daraus Kantenlicht für beliebige Lichtrichtungen (Laterne links oben, Himmel hinten oben)
    Ab = K.blur(A, cfg["rim"].get("normal_r", 3))
    gy, gx = np.gradient(Ab)
    gx, gy = K.blur(gx, 2), K.blur(gy, 2)
    gl = np.hypot(gx, gy) + 1e-6
    nx, ny = -gx / gl, -gy / gl
    band = A * (1 - K.blur(A, cfg["rim"]["width"]))   # innen am Rand hoch
    band = np.clip(band / (np.percentile(band[A > 0.5], 99) + 1e-6), 0, 1)
    wrap = np.clip(A * (1 - K.blur(A, cfg["wrap_width"])) * 3.0, 0, 1)
    # Schalende: rote Pixel rechts der Wurzel, Gewicht wächst entlang der Schalachse
    sc = cfg["scarf"]
    sr, sg_, sb = g_rgb[..., 0], g_rgb[..., 1], g_rgb[..., 2]
    red = ((sr > 1.6 * sg_) & (sr > 1.4 * sb) & (A > 0.1)).astype(np.float32)
    root = (np.array(sc["root"], np.float32) - [bx0, by0]) * s
    tip = (np.array(sc["tip"], np.float32) - [bx0, by0]) * s
    axis = tip - root
    alen = float(np.linalg.norm(axis))
    yy2, xx2 = np.mgrid[0:A.shape[0], 0:A.shape[1]].astype(np.float32)
    along = ((xx2 - root[0]) * axis[0] + (yy2 - root[1]) * axis[1]) / (alen * alen)
    reg = K.blur(red, sc.get("dilate", 3)) > 0.02
    if sc.get("clip_below"):
        # Ärmel unter dem Schal nicht mitbewegen: unterhalb der Linie (Quellkoordinaten) nichts
        (ax_, ay_), (bx_, by_) = [((np.array(p, np.float32) - [bx0, by0]) * s) for p in sc["clip_below"]]
        side = (xx2 - ax_) * (by_ - ay_) - (yy2 - ay_) * (bx_ - ax_)
        reg &= side > 0
    scarf_w = K.blur(reg.astype(np.float32), 2) * K.smoothstep(0.0, 0.75, along)
    scarf_w = np.clip(scarf_w, 0, 1)

    # --- 5. Schatten ------------------------------------------------------------------------------------
    sh = cfg["shadow"]
    Hs, Ws = A.shape
    feet_y = int(np.nonzero(A.max(1) > 0.5)[0].max())
    # Kontaktschatten: Fußabdruck (unterste Zeilen der Silhouette), flach gedrückt, weich
    foot = A[max(0, feet_y - int(Hs * 0.06)):feet_y + 1].max(0)
    canvas_w, canvas_h = Ws + 2 * sh["margin_x"], sh["canvas_h"]
    S = np.zeros((canvas_h, canvas_w), np.float32)
    cy = sh["contact_y"]
    for dy in range(-3, 4):
        S[cy + dy, sh["margin_x"]:sh["margin_x"] + Ws] = np.maximum(S[cy + dy, sh["margin_x"]:sh["margin_x"] + Ws],
                                                                foot * (1 - abs(dy) / 4))
    contact = np.clip(K.blur(S, sh["contact_blur"]) * sh["contact_k"], 0, 1)
    # Schlagschatten: Silhouette auf den Boden geklappt (gestaucht, nach rechts geschert), sehr weich
    cast = np.zeros_like(S)
    flat = np.asarray(Image.fromarray((A * 255).astype(np.uint8)).resize((Ws, max(2, int(Hs * sh["cast_squash"]))),
                                                                          Image.BILINEAR), np.float32)[::-1] / 255.0
    fh = flat.shape[0]
    for r in range(fh):
        off = int(round(r * sh["cast_shear"]))
        y = cy + r
        if y >= canvas_h:
            break
        xs0 = sh["margin_x"] + off
        seg = flat[r][: max(0, min(Ws, canvas_w - xs0))]
        cast[y, xs0:xs0 + len(seg)] = np.maximum(cast[y, xs0:xs0 + len(seg)], seg * (1 - r / fh) ** 0.7)
    cast = np.clip(K.blur(cast, sh["cast_blur"]) * sh["cast_k"], 0, 1)

    def save_rgba(rgb_, a_, p):
        Image.fromarray(np.dstack([np.clip(rgb_ * 255 + 0.5, 0, 255), np.clip(a_ * 255 + 0.5, 0, 255)])
                        .astype(np.uint8), "RGBA").save(p)

    save_rgba(h_rgb, h_al, art / "actor.png")
    if look is not None:
        save_rgba(l_rgb, l_al, art / "actor_look.png")
        shutil.copy(art / "actor_look.png", BASE / "assets" / "actor_look.png")
    save_rgba(r_rgb, r_al, art / "actor_raw.png")
    K.save_rgb(np.stack([nx * 0.5 + 0.5, ny * 0.5 + 0.5, band], -1), art / "actor_aux.png")
    K.save_rgb(np.stack([wrap, scarf_w, np.zeros_like(wrap)], -1), art / "actor_aux2.png")
    # Schatten als Graustufen: R Kontakt, G Schlagschatten (der Shader mischt nach Laternenstärke)
    K.save_rgb(np.stack([contact, cast, np.zeros_like(cast)], -1), art / "actor_shadow.png")
    for n in ("actor.png", "actor_aux.png", "actor_aux2.png", "actor_shadow.png"):
        shutil.copy(art / n, BASE / "assets" / n)

    rows = A[max(0, feet_y - int(Hs * 0.04)):feet_y + 1]
    cols = np.nonzero(rows.max(0) > 0.5)[0]
    feet_x = float((cols.min() + cols.max() + 1) / 2)
    info = {
        "size": list(size), "tex_scale": ts, "tex_size": list(size_hi), "scale": round(s, 5), "feet_row": feet_y,
        "feet_col": round(feet_x, 1),
        "feet_screen": cfg["feet_screen"], "shadow_origin": [sh["margin_x"], cy],
        "shadow_size": [canvas_w, canvas_h],
        "scarf_root": [round(float(root[0]), 1), round(float(root[1]), 1)],
        "scarf_tip": [round(float(tip[0]), 1), round(float(tip[1]), 1)],
        "gains": [round(float(g), 4) for g in gains], "ref_white_lin": [round(float(r), 4) for r in ref],
    }
    (art / "actor.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info))
    if dbg:
        K.save_gray(scarf_w, dbg / "scarf_w.png")
        K.save_gray(band, dbg / "band.png")
        K.save_gray(wrap, dbg / "wrap.png")
        K.save_gray(np.maximum(contact, cast), dbg / "shadow.png")


if __name__ == "__main__":
    main()
