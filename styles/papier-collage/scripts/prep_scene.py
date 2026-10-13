#!/usr/bin/env python3
"""Szenenteile für die Godot-Demo aus den KI-Bildern (back, quay, props) plus Wellenstreifen aus Code.

Bildschirmraum 1280x720. back.png und quay.png wurden aus derselben Lagevorlage erzeugt (Leinwand 1536x1024,
geliefert 1264x848): Bildschirm = (x, y - 65.83) * 1280/1264. Das Häuschen wird als eigenes Teil um DX nach links
gerückt (das Modell malte es größer als vorgesehen, dadurch war zu wenig Meer zu sehen); der freiwerdende
Kaistreifen wird mit ganzen Pflastersteinen von daneben belegt (fill_pavement).

Freigestellt wird nicht mit genimgs Ergebnis, sondern aus dem Original (<name>.keyed-src.png) mit
pc_util.key_green: genimgs Randentfärbung machte den gemalten Magenta-Schatten zu deckendem Schwarz.

Ausgabe: assets/scene/*.png (Teile + Schatten), assets/scene/layout.json, assets/check/pflaster_fuellung.png.

    .venv/bin/python styles/papier-collage/scripts/prep_scene.py
"""
import json, pathlib, sys
import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pc_util import (_shift, dilate, erode, key_green, neutralize, shadow_from_alpha,  # noqa: E402
                     resize_premult, save_rgba)
from prep_puppet import components, comp_mask  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent.parent
RAW = HERE / "assets" / "raw"
OUT = HERE / "assets" / "scene"
CHECK = HERE / "assets" / "check"
K = 1280 / 1264
OY = 80 * 0.8229          # Leinwand-Oberkante des 16:9-Ausschnitts in Bildpixeln
DX = 100                  # Häuschen nach links (Bildschirm-px)
SEED = 11


def to_screen_affine(img, size=(1280, 720)):
    """Ganzes Bild in den Bildschirmraum (bikubisch). img: PIL."""
    inv = (1 / K, 0, 0, 0, 1 / K, OY)
    return img.transform(size, Image.AFFINE, inv, resample=Image.BICUBIC)


def scr(x, y):
    return [round(x * K, 1), round((y - OY) * K, 1)]


def load_src(name):
    """Original von agy vor genimgs Freistellung (Magenta-Grund mit gemaltem Schatten)."""
    return np.asarray(Image.open(RAW / f"{name}.keyed-src.png").convert("RGB")).astype(np.float64)


def paper_grain():
    """Papierkorn aus dem (verdeckten) unteren Meer des KI-Hintergrunds, gespiegelt: 108 x 2528."""
    b = np.asarray(Image.open(RAW / "back.png").convert("RGB")).astype(np.float64)
    patch = b[692:746, :, :].mean(-1)
    grain = patch / patch.mean()
    grain = np.concatenate([grain, grain[:, ::-1]], 1)
    return np.concatenate([grain, grain[::-1]], 0)


def stone_labels(rgb, A, yy):
    """Pflastersteine des Kais als Etiketten (samt gemaltem Schatten), Fugen = 0.

    Fuge: helles Beige (193/185/172) mit G - B um 13; Steine weichen deutlich ab. Steine, die sich an engen
    Fugen berühren, werden über einen um 2 px eingerückten Kern getrennt und danach zurückgeweitet."""
    mortar = np.array([193, 185, 172.])
    d = np.abs(rgb - mortar).sum(-1) + 2 * np.abs((rgb[..., 1] - rgb[..., 2]) - 13)
    st = (A > 0.5) & (d > 40) & (yy >= 578) & (yy <= 726)
    st = dilate(erode(st, 1), 1) & st
    lab = np.zeros(A.shape, np.int32)
    for i, c in enumerate(components(erode(st, 2))):
        if len(c) > 15:
            lab[c[:, 0], c[:, 1]] = i + 1
    for _ in range(3):
        m = lab.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                m = np.maximum(m, _shift(lab, dy, dx))
        lab = np.where((lab == 0) & st, m, lab)
    return lab, d


def fill_pavement(rgb, A, E, yy, xx, hidden=None, gap=4):
    """Freigewordenen Kaistreifen E mit ganzen Steinen belegen statt ein Rechteck einzukopieren.

    1. Steine, die E rechts berühren (vom alten Häuschen halb verdeckt, gerade abgeschnitten), kommen weg.
    2. Fläche F0 = E + diese Steine bekommt Fugenpapier (Farbe der Fugen daneben, KI-Papierkorn).
    3. Ganze Steine des Kais (x <= 875, also ohne Laterne, Felsen und Fässer, nicht angeschnitten, mindestens
       170 px vom Loch entfernt, damit kein Doppel daneben steht) werden gierig eingesetzt:
       größter passender Stein zuerst, mit mindestens `gap` px Fuge zu allem, möglichst eng an Nachbarn.
    `hidden` (unter dem verrückten Häuschen) bekommt nur Fugenpapier, damit durch Lücken am Mauerfuß nichts
    durchscheint. Rückgabe: rgb, A, F0, Liste der Einsetzungen."""
    lab, d = stone_labels(rgb, A, yy)
    H, W = A.shape
    touch = np.unique(lab[dilate(E, 2) & (xx >= 505)])
    touch = touch[touch > 0]
    F0 = E | np.isin(lab, touch)
    free = (lab > 0) & ~np.isin(lab, touch)
    hole = dilate(A < 0.5, 2)                    # an Häuschen-Loch oder Bildrand angeschnittene Steine nicht
    hole[:, :2] = hole[:, -2:] = True
    fy, fx = np.nonzero(F0)
    fc = np.array([fx.mean(), fy.mean()])
    cands = []
    for l in np.unique(lab[free]):
        m = lab == l
        ys, xs = np.nonzero(m)
        if xs.max() > 875 or (m & hole).any():   # rechts davon Laterne, Felsen, Fässer, Kisten, Tau
            continue
        if np.hypot(xs.mean() - fc[0], ys.mean() - fc[1]) < 170:   # sonst steht das Doppel direkt daneben
            continue
        cands.append((int(l), ys.min(), xs.min(), m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]))
    cands.sort(key=lambda c: -c[3].sum())
    ys0, xs0 = np.nonzero(F0)
    by0, by1, bx0, bx1 = ys0.min(), ys0.max(), xs0.min(), xs0.max()
    inner = erode(F0, gap)
    placed = np.zeros((H, W), bool)
    placements, used = [], set()
    while True:
        ok_area = inner & ~dilate(placed, gap)
        best = None
        for l, y0, x0, m in cands:
            if l in used:
                continue
            h, w = m.shape
            mys, mxs = np.nonzero(m)
            for oy in range(by0, by1 - h + 2, 2):
                for ox in range(bx0, bx1 - w + 2, 2):
                    if not ok_area[mys + oy, mxs + ox].all():
                        continue
                    env = (~F0 | placed)[max(oy - 7, 0):oy + h + 7, max(ox - 7, 0):ox + w + 7].sum()
                    score = m.sum() * 10 + env
                    if best is None or score > best[0]:
                        best = (score, l, oy, ox, m, y0, x0)
        if best is None:
            break
        _, l, oy, ox, m, y0, x0 = best
        mys, mxs = np.nonzero(m)
        placed[mys + oy, mxs + ox] = True
        used.add(l)
        placements.append({"stone": l, "from": [int(x0), int(y0)], "to": [int(ox), int(oy)], "size": list(m.shape)})
    near = dilate(F0, 25) & ~F0 & (A > 0.5) & (lab == 0) & (d < 25)
    mcol = np.median(rgb[near], 0)
    grain = paper_grain()
    g = grain[yy % grain.shape[0], xx % grain.shape[1]]
    out, oA = rgb.copy(), A.copy()
    base = mcol[None, None] * (1 + (g[..., None] - 1) * 0.6)
    out[F0], oA[F0] = base[F0], 1.0
    if hidden is not None:
        out[hidden & ~F0], oA[hidden & ~F0] = base[hidden & ~F0], 1.0
    # Oberkante des Kais (weicher, dunkler Schnittrand) aus dem Zeilenmittel des freien Stücks übernehmen
    for y in range(by0, by0 + 3):
        a_med = np.median(A[y, 560:860])
        if a_med < 0.99:
            row = F0[y]
            out[y, row] = np.median(rgb[y, 560:860], 0)
            oA[y, row] = a_med
    for p in placements:
        ys, xs = np.nonzero(dilate(lab == p["stone"], 1))
        ty, tx = ys - p["from"][1] + p["to"][1], xs - p["from"][0] + p["to"][0]
        out[ty, tx] = rgb[ys, xs]
        oA[ty, tx] = 1.0
    return out, oA, F0, placements


def premult_affine(rgb, A, size, inv):
    pm = np.dstack([rgb * A[..., None], A * 255])
    ch = [Image.fromarray(pm[..., i].astype(np.float32), "F").transform(size, Image.AFFINE, inv,
                                                                      resample=Image.BICUBIC) for i in range(4)]
    arr = np.stack([np.asarray(c) for c in ch], -1)
    A2 = np.clip(arr[..., 3] / 255, 0, 1)
    rgb2 = np.where(A2[..., None] > 1e-3, arr[..., :3] / np.maximum(A2[..., None], 1e-3), 0)
    return np.clip(rgb2, 0, 255), A2


def save_piece(name, rgb, A, shadow_blur=4.0, pad=14):
    save_rgba(OUT / f"{name}.png", rgb, A)
    shadow_from_alpha(A, shadow_blur, pad).save(OUT / f"{name}_shadow.png")
    return {"file": f"{name}.png", "shadow": f"{name}_shadow.png", "size": [A.shape[1], A.shape[0]],
            "shadow_pad": pad}


def crop_piece(rgb, A, mask, scale, pad=8):
    ys, xs = np.nonzero(mask)
    x0, y0, x1, y1 = xs.min() - pad, ys.min() - pad, xs.max() + pad + 1, ys.max() + pad + 1
    sub_rgb = rgb[y0:y1, x0:x1]
    sub_A = A[y0:y1, x0:x1] * mask[y0:y1, x0:x1]
    w, h = round((x1 - x0) * scale), round((y1 - y0) * scale)
    r2, a2 = resize_premult(sub_rgb, sub_A, (w, h))
    return r2, a2, (x0, y0)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    L = {"screen": [1280, 720], "k": K, "oy": OY, "dx_cottage": DX}

    # --- Hintergrund (Himmel, fernes Meer, Landzunge mit Leuchtturm)
    back = to_screen_affine(Image.open(RAW / "back.png").convert("RGB"))
    back.save(OUT / "back.png")
    L["lamp"] = scr(1108, 187)
    L["horizon"] = round((413 - OY) * K, 1)

    # --- Kai-Ebene
    rgb, A = key_green(load_src("quay"))
    H, W = A.shape
    yy, xx = np.mgrid[0:H, 0:W]
    # Häuschen: alles über der Kaioberkante (Zeile 577) links von x 540 (Dach ragt bis 530), dazu die unterste
    # Mauerreihe bis zur Mauerkante (x <= 509, y <= 626) samt dunkelgrauem gemaltem Schattenstrich darunter (bis 631).
    # Pflaster bleibt am Kai.
    wall = (yy <= 626) | ((yy <= 631) & (rgb.mean(-1) < 110) & (rgb.max(-1) - rgb.min(-1) < 25))   # grauer Strich
    cott = (A > 0.02) & (xx < 540) & ((yy < 577) | (wall & (xx > 28) & (xx <= 509)))
    # Unter dem Häuschen liegt kein Pflaster; nach dem Verrücken würde dort ein Loch aufgehen. Belegt wird es mit
    # ganzen Steinen aus dem freien Kaistück rechts daneben (fill_pavement). Links von x 404 bleibt es vom
    # verrückten Häuschen verdeckt.
    quay_rgb, quay_A = rgb.copy(), A.copy()
    quay_rgb[cott], quay_A[cott] = 0, 0
    # freiwerdend: alter Mauerfuß samt gemaltem Schatten an der rechten Mauerkante (bis x 514) und unter der
    # Mauer (bis Zeile 631); links von x 404 bleibt alles vom verrückten Häuschen verdeckt
    E = (cott | ((yy <= 631) & (xx <= 514))) & (yy >= 577) & (xx >= 509 - round(DX / K) - 6)
    quay_rgb, quay_A, F0, placements = fill_pavement(quay_rgb, quay_A, E, yy, xx, hidden=cott & (yy >= 578))
    L["pavement_fill"] = placements
    CHECK.mkdir(parents=True, exist_ok=True)
    vis = np.dstack([quay_rgb, np.ones_like(quay_A) * 255])[540:760, 300:900].copy()
    vis[..., :3] = vis[..., :3] * quay_A[540:760, 300:900, None] + 30 * (1 - quay_A[540:760, 300:900, None])
    edge = (F0 & ~erode(F0, 1))[540:760, 300:900]
    vis[edge, :3] = (255, 0, 0)
    vis[:, 509 - round(DX / K) - 300, :3] = (0, 90, 255)
    Image.fromarray(vis.clip(0, 255).astype(np.uint8), "RGBA").resize((1200, 440), Image.NEAREST).save(
        CHECK / "pflaster_fuellung.png")
    inv = (1 / K, 0, 0, 0, 1 / K, OY)
    qr, qa = premult_affine(quay_rgb, quay_A, (1280, 720), inv)
    L["quay"] = save_piece("quay", qr, qa, 7.0, 20)
    cr, ca = premult_affine(rgb * cott[..., None], A * cott, (1280, 720), (1 / K, 0, DX / K, 0, 1 / K, OY))
    ys, xs = np.nonzero(ca > 0.01)
    cy0 = ys.min() - 4
    L["cottage"] = save_piece("cottage", cr[cy0:], ca[cy0:], 7.0, 20)
    L["cottage"]["pos"] = [0, int(cy0)]
    L["window"] = [scr(355, 432)[0] - DX, scr(355, 432)[1], scr(456, 531)[0] - DX, scr(456, 531)[1]]
    L["lantern_glass"] = scr(825, 423) + scr(862, 463)
    L["chimney_top"] = [scr(440, 154)[0] - DX, scr(440, 154)[1]]
    L["quay_top"] = scr(0, 578)[1]

    # --- Requisitenbogen (eigene Freistellung: Papier ohne Magentastich; Wolken behalten ihr Violett;
    # Rauch ist graues Seidenpapier, durch das das Modell Magenta scheinen ließ -> überall entfärbt)
    src = load_src("props")
    rgbK, AK = key_green(src)
    rgbH, AH = key_green(src, keep_hue=True)
    H, W = AK.shape
    yy, xx = np.mgrid[0:H, 0:W]
    strong = AK > 0.5
    m = strong & (yy < 470)
    comps = [c for c in components(m) if len(c) > 300]

    def find(x0, y0, x1, y1):
        for c in comps:
            cy, cx = c.mean(0)
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                return comp_mask(AK.shape, c)
        raise SystemExit(f"Teil nicht gefunden {x0, y0, x1, y1}")

    # Ohne den gemalten Schatten hängen Steg und rechtes Boot nicht mehr zusammen: Das Boot ist eine eigene
    # Komponente, die Pfostenenden des Stegs darüber gehören nicht dazu, die Mastspitze bleibt ganz.
    jetty = find(60, 60, 690, 240)
    boat_r = find(330, 300, 620, 470)
    boat_l = find(50, 250, 280, 470)
    pieces = {
        "jetty": (jetty, 0.62, "paper"), "boat_l": (boat_l, 0.74, "paper"), "boat_r": (boat_r, 0.84, "paper"),
        "cloud_a": (find(730, 60, 1020, 150), 0.9, "hue"), "cloud_b": (find(1040, 70, 1230, 150), 0.9, "hue"),
        "gull_body": (find(715, 230, 865, 325), 0.26, "paper"),
        "gull_wing": (find(895, 225, 1185, 330), 0.26, "paper"),
        "smoke": (find(730, 385, 815, 470), 0.5, "tissue"),
    }
    for name, (mask, sc, kind) in pieces.items():
        # weicher Rand bis 2 px um die Komponente, aber nichts von Nachbarteilen (Pfostenenden über dem Mast)
        mask2 = dilate(mask, 2) & ~dilate(strong & ~mask, 1)
        r_src, a_src = {"paper": (rgbK, AK), "hue": (rgbH, AH), "tissue": (neutralize(rgbH), AH)}[kind]
        a_use = a_src * mask2
        r2, a2, org = crop_piece(r_src, a_use, mask2, sc)
        meta = save_piece(name, r2, a2, 3.0 if sc < 0.5 else 4.0, 12)
        meta["scale"] = sc
        meta["origin_img"] = [int(org[0]), int(org[1])]
        L[name] = meta
    # Drehpunkte (Bildpixel des Bogens -> Teilpixel)
    def piv(name, x, y):
        o, s = L[name]["origin_img"], L[name]["scale"]
        return [round((x - o[0]) * s, 1), round((y - o[1]) * s, 1)]
    L["boat_l"]["pivot"] = piv("boat_l", 165, 445)        # Mitte des Rumpfs auf Höhe der Wasserlinie
    L["boat_r"]["pivot"] = piv("boat_r", 470, 445)
    L["gull_wing"]["pivot"] = piv("gull_wing", 912, 290)
    L["gull_body"]["pivot"] = piv("gull_body", 790, 280)
    L["gull_body"]["wing_at"] = piv("gull_body", 800, 268)

    # --- Wellenstreifen aus Code, Papierkorn aus dem (verdeckten) unteren Meer des KI-Hintergrunds
    b = np.asarray(Image.open(RAW / "back.png").convert("RGB")).astype(np.float64)
    patch = b[692:746, :, :].mean(-1)
    grain = patch / patch.mean()
    grain = np.concatenate([grain, grain[:, ::-1]], 1)            # spiegeln: 2528 px breit
    grain = np.concatenate([grain, grain[::-1]], 0)               # 108 px hoch
    rng = np.random.default_rng(SEED)
    strips = [  # Oberkante (Bildschirm), Farbe, Wellenlänge, Amplitude
        (402, (92, 114, 136), 260, 3.0), (432, (78, 118, 132), 220, 3.5),
        (468, (62, 106, 120), 300, 4.0), (497, (50, 88, 104), 240, 4.5)]
    L["strips"] = []
    Wd, Hd = 1440, 150
    for i, (top, col, lam, amp) in enumerate(strips):
        x = np.arange(Wd)
        phase = rng.uniform(0, 2 * np.pi)
        noise = np.zeros(Wd)
        for octave, (f, a) in enumerate([(1 / 90, 2.2), (1 / 31, 1.2), (1 / 9, 0.6), (1 / 3, 0.35)]):
            ph = rng.uniform(0, 2 * np.pi, 3)
            noise += a * (np.sin(2 * np.pi * f * x + ph[0]) * 0.6 + np.sin(2 * np.pi * f * 1.37 * x + ph[1]) * 0.4)
        edge = 14 + amp * np.sin(2 * np.pi * x / lam + phase) + noise          # Rissoberkante (weißer Rand)
        rim = 2.6 + 1.4 * np.sin(2 * np.pi * x / 57 + phase * 2) + rng.uniform(0, 1.6, Wd)
        fib = rng.uniform(0, 1, Wd) < 0.18                                       # einzelne Fasern
        edge_o = edge - np.where(fib, rng.uniform(0.6, 2.2, Wd), 0)
        yy2 = np.arange(Hd)[:, None]
        # Kantenglättung: Abdeckung je Pixel aus Abstand zur Kante
        cov = np.clip(yy2 - edge_o[None, :] + 0.5, 0, 1)
        colz = np.clip(yy2 - (edge[None, :] + rim[None, :]) + 0.5, 0, 1)    # 0 = weißer Rand, 1 = Farbe
        g = grain[(np.arange(Hd) + 23 * i) % grain.shape[0]][:, (x + 377 * i) % grain.shape[1]]
        paper = np.array(col, float)[None, None, :] * g[..., None]
        white = np.array([236, 233, 224], float)[None, None, :] * (0.94 + 0.06 * g[..., None])
        rgbS = white * (1 - colz[..., None]) + paper * colz[..., None]
        # dunkle Kante unter dem weißen Rand (Farbschicht reißt tiefer)
        dark = np.clip(1 - np.abs(yy2 - (edge[None, :] + rim[None, :] + 0.6)) / 1.2, 0, 1) * 0.25
        rgbS *= (1 - dark[..., None])
        name = f"strip{i}"
        save_rgba(OUT / f"{name}.png", rgbS, cov)
        shadow_from_alpha(cov, 3.0, 10).save(OUT / f"{name}_shadow.png")
        L["strips"].append({"file": f"{name}.png", "shadow": f"{name}_shadow.png", "top": top, "size": [Wd, Hd],
                            "edge_offset": 14, "shadow_pad": 10, "color": col})

    (OUT / "layout.json").write_text(json.dumps(L, indent=1))
    print("ok", {k: v.get("size") for k, v in L.items() if isinstance(v, dict) and "size" in v})


if __name__ == "__main__":
    main()
