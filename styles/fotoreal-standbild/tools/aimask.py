"""KI-Farbcode-Maske lesen: Farbcodes einordnen, an das Gemälde ausrichten, Bereiche zerlegen (nur NumPy/Pillow).

Codes wie in assets/prompts/mask.txt. Das Bildmodell liefert keine exakten Flächen (JPEG, Kantensäume, leichte
Verschiebung oder Skalierung gegenüber dem Gemälde); deshalb: nächster Code je Pixel, Mehrheitsfilter, dann
Ausrichtung über die Übereinstimmung der Codegrenzen mit Kanten im Gemälde.
"""
import numpy as np
from PIL import Image

import imgops as K

CODES = {  # Name -> RGB
    "other": (0, 0, 0),
    "sky": (0, 0, 255),
    "water": (0, 255, 255),
    "boats": (255, 0, 255),
    "window": (255, 255, 0),
    "lantern": (255, 128, 0),
    "lamp": (255, 0, 0),
    "chimney": (0, 255, 0),
}
NAMES = list(CODES)
IDX = {n: i for i, n in enumerate(NAMES)}
PALETTE = np.array([CODES[n] for n in NAMES], np.float32) / 255.0


def classify(rgb, max_dist=0.5, mode_r=2):
    """rgb (H,W,3) 0..1 -> Index je Pixel (nächster Code). Weiter entfernte Pixel (Säume) entscheidet die
    Mehrheit der Nachbarn im (2r+1)^2-Fenster; dieselbe Mehrheit glättet JPEG-Rauschen."""
    d = np.linalg.norm(rgb[..., None, :] - PALETTE[None, None], axis=-1)
    lab = d.argmin(-1)
    sure = d.min(-1) <= max_dist
    votes = np.stack([K.box(((lab == k) & sure).astype(np.float32), mode_r) for k in range(len(NAMES))], -1)
    out = votes.argmax(-1)
    return np.where(votes.max(-1) > 0, out, lab).astype(np.uint8)


def to_rgb(lab):
    return (PALETTE[lab] * 255 + 0.5).astype(np.uint8)


def from_rgb(arr):
    """Exakte Codefarben (z. B. eine gespeicherte, ausgerichtete Maske) -> Index."""
    rgb = np.asarray(arr, np.float32) / 255.0
    return np.linalg.norm(rgb[..., None, :] - PALETTE[None, None], axis=-1).argmin(-1).astype(np.uint8)


def resize_lab(lab, size):
    return np.asarray(Image.fromarray(lab).resize(size, Image.NEAREST))


def warp_lab(lab, T, size):
    """Bildet die Indexkarte mit T = (sx, sy, dx, dy) ab: x' = cx + sx (x - cx) + dx (Mitte als Zentrum)."""
    sx, sy, dx, dy = T
    w, h = size
    cx, cy = w / 2.0, h / 2.0
    # Ränder fortsetzen (Randpixel wiederholen), damit beim Verkleinern oder Verschieben kein Streifen "other"
    # am Bildrand entsteht
    pad = int(np.ceil(max(abs(dx), abs(dy)) + max(abs(1 - sx) * w, abs(1 - sy) * h))) + 2
    src = np.pad(lab, pad, mode="edge")
    # inverse Abbildung für Image.transform: Quelle = (x' - cx - dx) / sx + cx (+ pad im gepolsterten Bild)
    coeffs = (1 / sx, 0, cx - (cx + dx) / sx + pad, 0, 1 / sy, cy - (cy + dy) / sy + pad)
    return np.asarray(Image.fromarray(src).transform(size, Image.AFFINE, coeffs, Image.NEAREST))


def boundary(lab):
    e = np.zeros(lab.shape, bool)
    e[:, 1:] |= lab[:, 1:] != lab[:, :-1]
    e[1:] |= lab[1:] != lab[:-1]
    return e


def edge_map(img):
    L = K.luma(img)
    gx = np.zeros_like(L)
    gy = np.zeros_like(L)
    gx[:, 1:-1] = L[:, 2:] - L[:, :-2]
    gy[1:-1] = L[2:] - L[:-2]
    g = np.hypot(gx, gy)
    g = K.blur(g, 1)
    return g / (np.percentile(g, 99) + 1e-6)


def align(img, lab, search=0.03, scales=0.05, seed=7, r=2):
    """Sucht T = (sx, sy, dx, dy) in Bildpixeln, unter dem die Codegrenzen am besten auf Farbgrenzen des
    Gemäldes fallen. Maß: mittlerer Farbunterschied quer zur Codegrenze (je Grenzpunkt r px davor und dahinter,
    senkrecht zur Grenze). Anders als reine Kantenstärke zählt das nur Kanten in der richtigen Richtung,
    Pinselstruktur im Inneren der Flächen stört kaum. img (H,W,3), lab (H,W) gleich groß; ~640 px Breite,
    grob nach fein."""
    H, W = lab.shape
    f = 640.0 / W
    w2, h2 = 640, max(1, round(H * f))
    small = np.asarray(Image.fromarray((img * 255).astype(np.uint8)).resize((w2, h2), Image.BILINEAR),
                       np.float32) / 255.0
    I = K.blur(small, 1)
    ls = resize_lab(lab, (w2, h2))
    ya, xa = np.nonzero(ls[:, :-1] != ls[:, 1:])
    yb, xb = np.nonzero(ls[:-1] != ls[1:])
    px = np.concatenate([xa + 0.5, xb.astype(np.float64)])
    py = np.concatenate([ya.astype(np.float64), yb + 0.5])
    nx = np.concatenate([np.ones(len(xa)), np.zeros(len(xb))])
    ny = 1.0 - nx
    rng = np.random.default_rng(seed)
    if len(px) > 10000:
        pick = rng.choice(len(px), 10000, replace=False)
        px, py, nx, ny = px[pick], py[pick], nx[pick], ny[pick]
    cx, cy = w2 / 2.0, h2 / 2.0

    def score(sx, sy, dx, dy):
        qx = cx + sx * (px - cx) + dx
        qy = cy + sy * (py - cy) + dy
        ax, ay = np.rint(qx - r * nx).astype(int), np.rint(qy - r * ny).astype(int)
        bx, by = np.rint(qx + r * nx).astype(int), np.rint(qy + r * ny).astype(int)
        ok = (ax >= 0) & (bx < w2) & (ay >= 0) & (by < h2) & (bx >= 0) & (by >= 0) & (ax < w2) & (ay < h2)
        if not ok.any():
            return 0.0
        return float(np.abs(I[ay[ok], ax[ok]] - I[by[ok], bx[ok]]).sum(-1).sum() / len(px))

    base = score(1, 1, 0, 0)
    R = max(2, round(search * w2))
    best = max(((score(1, 1, dx, dy), 1.0, 1.0, dx, dy) for dx in range(-R, R + 1) for dy in range(-R, R + 1)))
    # gleiche Skalierung in x und y (beide Bilder kommen aus demselben Modell im selben Format) ...
    steps = np.round(np.arange(-scales, scales + 1e-9, 0.01), 3)
    for _ in range(2):
        _, bsx, bsy, bdx, bdy = best
        cands = [(score(1 + ds, 1 + ds, dx, dy), 1 + ds, 1 + ds, dx, dy) for ds in steps
                 for dx in range(bdx - 3, bdx + 4) for dy in range(bdy - 3, bdy + 4)]
        best = max(cands + [best])
    # ... dann nur eine kleine Abweichung zwischen x und y zulassen (frei gesucht wandert sy gegen dy)
    _, bsx, bsy, bdx, bdy = best
    cands = [(score(bsx, bsy * (1 + an), dx, dy), bsx, bsy * (1 + an), dx, dy)
             for an in (-0.012, -0.008, -0.004, 0.004, 0.008, 0.012)
             for dx in range(bdx - 2, bdx + 3) for dy in range(bdy - 2, bdy + 3)]
    best = max(cands + [best])
    # Feinsuche in halben Pixeln der kleinen Fassung
    _, bsx, bsy, bdx, bdy = best
    fine = [(score(bsx * (1 + ds), bsy * (1 + ds), bdx + ex, bdy + ey), bsx * (1 + ds), bsy * (1 + ds), bdx + ex, bdy + ey)
            for ds in (-0.004, 0, 0.004) for ex in (-0.5, 0, 0.5) for ey in (-0.5, 0, 0.5)]
    best = max(fine + [best])
    sc, sx, sy, dx, dy = best
    return {"sx": round(float(sx), 4), "sy": round(float(sy), 4), "dx": round(float(dx / f), 1),
            "dy": round(float(dy / f), 1), "score": round(sc, 4), "score_identity": round(base, 4),
            "edge_points": int(len(px))}


def components(mask, min_px=1):
    """Zusammenhängende Bereiche (8er-Nachbarschaft) über Lauflängen und Union-Find.
    Gibt eine Liste von Indexarrays (ys, xs) zurück, nach Größe absteigend."""
    h, w = mask.shape
    runs = []  # (y, x0, x1)
    row_runs = []
    for y in range(h):
        r = mask[y]
        if not r.any():
            row_runs.append([])
            continue
        d = np.diff(np.concatenate([[0], r.astype(np.int8), [0]]))
        starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        ids = []
        for s, e in zip(starts, ends):
            ids.append(len(runs))
            runs.append((y, int(s), int(e)))
        row_runs.append(ids)
    parent = list(range(len(runs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for y in range(1, h):
        prev, cur = row_runs[y - 1], row_runs[y]
        for i in cur:
            _, s, e = runs[i]
            for k in prev:
                _, ps, pe = runs[k]
                if ps <= e and pe >= s:  # 8er-Nachbarschaft: Lauf [s, e) berührt [ps, pe) auch diagonal
                    a, b = find(i), find(k)
                    if a != b:
                        parent[a] = b
    groups = {}
    for i, (y, s, e) in enumerate(runs):
        groups.setdefault(find(i), []).append((y, s, e))
    out = []
    for g in groups.values():
        ys = np.concatenate([np.full(e - s, y) for y, s, e in g])
        xs = np.concatenate([np.arange(s, e) for y, s, e in g])
        if len(ys) >= min_px:
            out.append((ys, xs))
    out.sort(key=lambda c: -len(c[0]))
    return out


def boat_components(lab, n=2, min_px=300):
    """Die n größten Bootsflächen (Code boats), von links nach rechts sortiert: Boot 1, Boot 2."""
    comps = components(lab == IDX["boats"], min_px=min_px)[:n]
    comps.sort(key=lambda c: c[1].mean())
    return comps


def regions(lab):
    """Indexkarte -> {Name: 0/1-Maske}, dazu boat1/boat2 als getrennte Boote."""
    out = {n: (lab == i).astype(np.float32) for n, i in IDX.items()}
    for k, (ys, xs) in enumerate(boat_components(lab)):
        m = np.zeros(lab.shape, np.float32)
        m[ys, xs] = 1
        out[f"boat{k + 1}"] = m
    return out
