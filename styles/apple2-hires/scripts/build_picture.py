"""Strichvorlage + Linienzüge -> Zeichenprogramm für die Hi-Res-Seite (demo/data/picture.json) und Vorschauen.

    .venv/bin/python styles/apple2-hires/scripts/build_picture.py

Ablauf wie bei einem Bild-Interpreter der frühen 80er: erst alle Linien (weiß, Bresenham, Byte für Byte),
dann Flächen (zeilenweise Spannen mit einem Füllmuster). Jede Schreiboperation setzt wie die echte Routine
das ganze Byte: die 7 Bildpunkte und Bit 7 (Farbgruppe) des Musters. Treffen sich zwei Flächen mit
verschiedener Farbgruppe in einem Byte, gewinnt die zuletzt gefüllte; die Bildpunkte der anderen wechseln
die Farbe (Violett <-> Blau, Grün <-> Orange). Das ist gewollt und wird gezählt.

Ausgaben:
  demo/data/picture.json   Schreibfolge (Adresse, Wert), Phasengrenzen, Animationsplätze
  assets/picture_preview.png       Endbild nach dem Farbmodell der Demo ("crisp", ×3)
  assets/picture_fringe.png        dasselbe mit allen Säumen (auch dunklen), assets/picture_ideal.png ohne Säume
  assets/picture_regions.png       Flächen in Klassenfarben (Prüfbild)
  assets/HARBOUR.BIN               8192 Bytes im Format einer Hi-Res-Seite ($2000)
"""
import base64, json, pathlib
import numpy as np
from PIL import Image
from a2lib import render, to_bin
from bres import line_pixels
from patterns import PATTERNS

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
TW, TH = 280, 160

# Farbklassen der Vorlage: Name, Mittelfarbe in der KI-Vorlage, Füllmuster (oder Liste (ab Zeile, Muster))
CLASSES = [
    ("himmel", "#3a4c94", [(0, "blau_k2"), (14, "blau_k"), (26, "dunkelblau")]),
    ("wolke", "#5c55a5", "violett"),
    ("abendrot", "#886196", "rot"),
    ("horizont", "#f38f44", "orange"),
    ("meer", "#3d7cb1", "meer"),
    ("kai", "#9c8f89", "schwarz*"),
    ("stein", "#897e78", "schwarz*"),
    ("dach", "#c1542b", "orange"),
    ("holz", "#926842", "orange"),
    ("holzdunkel", "#796250", "braun"),
    ("weiss", "#ededed", "weiss*"),
    ("gras", "#4d8137", "gruen"),
    ("fels", "#736a63", "dunkelviolett"),
    ("gelb", "#ffda4e", "gelb"),
]
LUMA_LINE = 52

# Einzelne Flächen umfärben: (x, y) im 280×160-Raster -> Muster
OVERRIDES = []
# Linienfilter: Anteil der Stichproben, an denen links und rechts verschiedene Farbklassen liegen
SEP_MIN = 0.35
CLEANUP = HERE / "cleanup.txt"


def read_cleanup():
    """Handbearbeitung (scripts/cleanup.txt): drop, poly, area, line, dark – siehe Kopf der Datei."""
    drops, polys, lines_, darks = [], [], [], []
    for raw in CLEANUP.read_text().splitlines():
        t = raw.split("#")[0].split()
        if not t:
            continue
        cmd = t[0]
        def pts(items):
            return [tuple(int(v) for v in it.split(",")) for it in items]
        if cmd == "drop":
            drops.append(tuple(int(v) for v in t[1:5]))
        elif cmd in ("poly", "area"):
            polys.append((cmd, t[1], pts(t[2:])))
        elif cmd == "line":
            lines_.append(pts(t[1:]))
        elif cmd == "dark":
            darks.append(pts(t[1:]))
        elif cmd == "recolor":
            polys.append((cmd, (t[1], t[2]), tuple(int(v) for v in t[3:7])))
        else:
            raise SystemExit(f"cleanup.txt: unbekannt: {raw}")
    return drops, polys, lines_, darks


def hex2rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def oklab(rgb):
    c = np.asarray(rgb, np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                   [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    lms = np.cbrt(c @ M1.T)
    M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                   [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return lms @ M2.T


def label4(mask, cls):
    """4er-Nachbarschaft: Komponenten gleicher Klasse innerhalb mask. Rückgabe Labelbild (-1 = keine)."""
    H, W = mask.shape
    lab = -np.ones((H, W), np.int32)
    n = 0
    for y in range(H):
        for x in range(W):
            if not mask[y, x] or lab[y, x] >= 0:
                continue
            c = cls[y, x]
            stack = [(y, x)]
            lab[y, x] = n
            while stack:
                cy, cx = stack.pop()
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and lab[ny, nx] < 0 and cls[ny, nx] == c:
                        lab[ny, nx] = n
                        stack.append((ny, nx))
            n += 1
    return lab, n


def pattern_for(spec, y):
    if isinstance(spec, str):
        return spec
    cur = spec[0][1]
    for y0, name in spec:
        if y >= y0:
            cur = name
    return cur


def main():
    lines = json.loads((ENTRY / "assets" / "lines.json").read_text())
    src = np.asarray(Image.open(ENTRY / lines["source"]).convert("RGB"))
    cy0, ch = lines["crop_y"], lines["crop_h"]
    src = src[cy0:cy0 + ch].astype(np.float64)
    H0, W0 = src.shape[:2]
    luma = src @ np.array([0.299, 0.587, 0.114])
    srcline = luma < LUMA_LINE

    # 2. Klassen je Quellpixel (Oklab, nächste Mittelfarbe)
    names = [c[0] for c in CLASSES]
    cen = oklab([hex2rgb(c[1]) for c in CLASSES])
    lab_src = oklab(src.reshape(-1, 3))
    d = np.stack([((lab_src - c) ** 2).sum(1) for c in cen], 1)
    cls_src = d.argmin(1).reshape(H0, W0)
    cls_src[srcline] = -1

    # 1. Linien filtern: nur Züge behalten, die zwei verschiedene Farbflächen der Vorlage trennen
    #    (Planken, Steinfugen, Fensterkreuze, Pflaster liegen innerhalb einer Fläche und fallen weg)
    def side_class(X, Y, nx, ny, sign):
        for r in range(3, 16):
            xi, yi = int(round(X + sign * nx * r)), int(round(Y + sign * ny * r))
            if not (0 <= xi < W0 and 0 <= yi < H0):
                return -2
            c = cls_src[yi, xi]
            if c >= 0:
                return int(c)
        return -1

    def separation(src_pts):
        sep = same = 0
        for (x0, y0), (x1, y1) in zip(src_pts, src_pts[1:]):
            L_ = np.hypot(x1 - x0, y1 - y0)
            if L_ < 1e-6:
                continue
            nx, ny = -(y1 - y0) / L_, (x1 - x0) / L_
            for t in np.arange(2.0, L_ - 1.0, 4.0) if L_ > 4 else [L_ / 2]:
                X, Y = x0 + (x1 - x0) * t / L_, y0 + (y1 - y0) * t / L_
                a, b = side_class(X, Y, nx, ny, 1), side_class(X, Y, nx, ny, -1)
                if a < 0 or b < 0:
                    continue
                if a != b:
                    sep += 1
                else:
                    same += 1
        return sep / max(1, sep + same), sep + same

    DROP_BOXES, POLYS, EXTRA_LINES, DARK_LINES = read_cleanup()
    EXTRA_STROKES = [list(p) + [p[0]] for c, _, p in POLYS if c == "poly"] + EXTRA_LINES
    all_strokes = lines["strokes"]
    strokes, dropped = [], 0
    for st in all_strokes:
        score, nsamp = separation(st["src"])
        box_drop = any(all(bx0 <= x <= bx1 and by0 <= y <= by1 for x, y in st["pts"])
                       for bx0, by0, bx1, by1 in DROP_BOXES)
        if (score >= SEP_MIN or nsamp == 0) and not box_drop:
            strokes.append(st["pts"])
        else:
            dropped += 1
    strokes += EXTRA_STROKES

    L = np.zeros((TH, TW), bool)
    stroke_px = []
    for pts in strokes:
        px = []
        if len(pts) == 1:
            px = [tuple(pts[0])]
        for a, b in zip(pts, pts[1:]):
            seg = line_pixels(tuple(a), tuple(b))
            if px and seg[0] == px[-1]:
                seg = seg[1:]
            px += seg
        stroke_px.append(px)
        for x, y in px:
            L[y, x] = True

    # 3. Klasse je Zielpixel: Mehrheit im Quellblock (ohne Umrisspixel)
    K = len(CLASSES)
    cls = -np.ones((TH, TW), np.int32)
    xs = (np.arange(TW + 1) * W0 / TW).round().astype(int)
    ys = (np.arange(TH + 1) * H0 / TH).round().astype(int)
    for y in range(TH):
        for x in range(TW):
            blk = cls_src[ys[y]:ys[y + 1], xs[x]:xs[x + 1]].ravel()
            blk = blk[blk >= 0]
            if blk.size:
                cls[y, x] = np.bincount(blk, minlength=K).argmax()
    # Löcher (Block nur aus Umriss) von Nachbarn füllen
    for _ in range(6):
        miss = (cls < 0) & ~L
        if not miss.any():
            break
        for y, x in zip(*np.nonzero(miss)):
            nb = [cls[yy, xx] for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1))
                  if 0 <= yy < TH and 0 <= xx < TW and cls[yy, xx] >= 0]
            if nb:
                cls[y, x] = max(set(nb), key=nb.count)
    # Handbearbeitung: Flächen übermalen (in Dateireihenfolge)
    from PIL import ImageDraw
    for kind, cname, p in POLYS:
        if kind == "recolor":
            a, b = names.index(cname[0]), names.index(cname[1])
            x0, y0, x1, y1 = p
            sub = cls[y0:y1 + 1, x0:x1 + 1]
            sub[sub == a] = b
            continue
        m = Image.new("L", (TW, TH), 0)
        ImageDraw.Draw(m).polygon(p, fill=1, outline=1)
        cls[np.asarray(m, bool)] = names.index(cname)
    fillmask = ~L & (cls >= 0)

    # 4. Komponenten; Splitter (< 5 Punkte) der häufigsten Nachbarklasse zuschlagen
    for _ in range(3):
        lab, n = label4(fillmask, cls)
        sizes = np.bincount(lab[lab >= 0], minlength=n)
        small = np.nonzero(sizes < 5)[0]
        if not len(small):
            break
        changed = 0
        for s in small:
            ys_, xs_ = np.nonzero(lab == s)
            nb = []
            for y, x in zip(ys_, xs_):
                for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= yy < TH and 0 <= xx < TW and lab[yy, xx] >= 0 and lab[yy, xx] != s:
                        nb.append(cls[yy, xx])
            if nb:
                c = max(set(nb), key=nb.count)
                if c != cls[ys_[0], xs_[0]]:
                    cls[ys_, xs_] = c
                    changed += 1
        if not changed:
            break
    lab, n = label4(fillmask, cls)
    sizes = np.bincount(lab[lab >= 0], minlength=n)

    # 5. Muster je Komponente
    comp_cls = np.zeros(n, np.int32)
    for i in range(n):
        y, x = np.argwhere(lab == i)[0]
        comp_cls[i] = cls[y, x]
    comp_spec = [CLASSES[c][2] for c in comp_cls]
    for (x, y, pat) in OVERRIDES:
        if lab[y, x] >= 0:
            comp_spec[lab[y, x]] = pat
    # Schwarz und Weiß gibt es in beiden Farbgruppen (HCOLOR 0/4, 3/7). Wie ein Grafiker die passende wählen:
    # die Gruppe, die die farbigen Nachbarflächen in den gemeinsamen Bytes haben (sonst kippen deren Farben).
    auto = {"schwarz*": ("schwarz0", "schwarz"), "weiss*": ("weiss0", "weiss")}
    for i in range(n):
        if not (isinstance(comp_spec[i], str) and comp_spec[i] in auto):
            continue
        ys_, xs_ = np.nonzero(lab == i)
        votes = [0, 0]
        for y, b in set(zip(ys_.tolist(), (xs_ // 7).tolist())):
            for x in range(7 * b, 7 * b + 7):
                j = lab[y, x]
                if j < 0 or j == i or (isinstance(comp_spec[j], str) and comp_spec[j] in auto):
                    continue
                nm = pattern_for(comp_spec[j], y)
                bits, h = PATTERNS[nm][y % len(PATTERNS[nm])]
                if bits[x % len(bits)] == "1":
                    votes[h] += 1
        comp_spec[i] = auto[comp_spec[i]][0 if votes[0] > votes[1] else 1]

    # 6. Füllreihenfolge: große Flächen zuerst
    order = sorted(range(n), key=lambda i: -sizes[i])

    def fill_ops():
        """Liste (Komponente, y, x0, x1) in Füllreihenfolge."""
        ops = []
        for i in order:
            ys_, xs_ = np.nonzero(lab == i)
            for y in np.unique(ys_):
                row = np.sort(xs_[ys_ == y])
                start = row[0]
                prev = row[0]
                for x in row[1:]:
                    if x != prev + 1:
                        ops.append((i, int(y), int(start), int(prev)))
                        start = x
                    prev = x
                ops.append((i, int(y), int(start), int(prev)))
        return ops

    fops = fill_ops()

    def span_writes(mem, i, y, x0, x1):
        name = pattern_for(comp_spec[i], y)
        rows = PATTERNS[name]
        bits, h = rows[y % len(rows)]
        out = []
        for b in range(x0 // 7, x1 // 7 + 1):
            m = 0
            v = 0
            for k in range(7):
                x = 7 * b + k
                if x0 <= x <= x1:
                    m |= 1 << k
                    if bits[x % len(bits)] == "1":
                        v |= 1 << k
            old = int(mem[y, b])
            new = (old & 0x7F & ~m) | v | (h << 7)
            out.append((y, b, new))
            mem[y, b] = new
        return out

    # Vorlauf: Endgruppe je Byte nur aus den Flächen
    pre = np.zeros((TH, 40), np.uint8)
    for op in fops:
        span_writes(pre, *op)
    final_h = pre >> 7

    # Linien-Reihenfolge: zusammenhängende Liniennetze, größte zuerst, darin in Zugreihenfolge
    netlab, nn = label4(L, np.zeros((TH, TW), np.int32))
    net_of = [int(netlab[px[0][1], px[0][0]]) if px else 0 for px in stroke_px]
    net_size = np.bincount(netlab[netlab >= 0], minlength=nn)
    sorder = sorted(range(len(stroke_px)), key=lambda s: (-net_size[net_of[s]], net_of[s], s))

    mem = np.zeros((TH, 40), np.uint8)
    writes = []
    stroke_h = []
    for s in sorder:
        px = stroke_px[s]
        if not px:
            continue
        hs = [int(final_h[y, x // 7]) for x, y in px]
        h = 1 if sum(hs) * 2 >= len(hs) else 0
        stroke_h.append(h)
        for x, y in px:
            b = x // 7
            new = ((int(mem[y, b]) | (1 << (x % 7))) & 0x7F) | (h << 7)
            if new != mem[y, b]:
                mem[y, b] = new
                writes.append((y * 40 + b, new))
    n_line_writes = len(writes)
    line_px = int(L.sum())
    for op in fops:
        for y, b, new in span_writes(mem, *op):
            writes.append((y * 40 + b, new))
    # schwarze Detaillinien nach den Flächen (Bits löschen, Farbgruppe bleibt)
    for p in DARK_LINES:
        for a, b in zip(p, p[1:]):
            for x, y in line_pixels(a, b):
                bb = x // 7
                new = int(mem[y, bb]) & ~(1 << (x % 7))
                if new != mem[y, bb]:
                    mem[y, bb] = new
                    writes.append((y * 40 + bb, new))
    n_fill_writes = len(writes) - n_line_writes

    # Prüfen: Flächenpunkte, deren Byte am Ende eine andere Farbgruppe hat als ihr Muster (Farbe gekippt)
    clash = 0
    clash_bytes = set()
    for y in range(TH):
        for x in range(TW):
            i = lab[y, x]
            if i < 0:
                continue
            nm = pattern_for(comp_spec[i], y)
            bits, h = PATTERNS[nm][y % len(PATTERNS[nm])]
            if bits[x % len(bits)] == "1" and (int(mem[y, x // 7]) >> 7) != h:
                clash += 1
                clash_bytes.add((y, x // 7))
    clash = f"{clash} Punkte in {len(clash_bytes)} Bytes"

    full = np.zeros((192, 40), np.uint8)
    full[:TH] = mem
    S = 3
    for model, fn in (("crisp", "picture_preview.png"), ("fringe", "picture_fringe.png"),
                      ("ideal", "picture_ideal.png")):
        img = render(full[:TH], model)
        Image.fromarray(np.repeat(np.repeat(img, S, 0), S, 1)).save(ENTRY / "assets" / fn)
    cols = np.array([hex2rgb(c[1]) for c in CLASSES] + [(255, 255, 255)], np.uint8)
    reg = cols[np.where(L, K, np.maximum(cls, 0))]
    Image.fromarray(np.repeat(np.repeat(reg, S, 0), S, 1)).save(ENTRY / "assets" / "picture_regions.png")
    (ENTRY / "assets" / "HARBOUR.BIN").write_bytes(to_bin(full))

    # Animationsplätze: Komponenten nach Klasse und Lage
    def comps_of(cname, box=None):
        ci = names.index(cname)
        res = []
        for i in range(n):
            if comp_cls[i] != ci:
                continue
            ys_, xs_ = np.nonzero(lab == i)
            cx, cyy = xs_.mean(), ys_.mean()
            if box and not (box[0] <= cx <= box[2] and box[1] <= cyy <= box[3]):
                continue
            res.append({"id": int(i), "px": [[int(x), int(y)] for y, x in zip(ys_, xs_)],
                        "center": [round(float(cx), 1), round(float(cyy), 1)]})
        return res

    data = {
        "size": [TW, TH],
        "writes": base64.b64encode(np.array(
            [[a & 0xFF, a >> 8, v] for a, v in writes], np.uint8).tobytes()).decode(),
        "n_line_writes": n_line_writes,
        "n_fill_writes": n_fill_writes,
    }
    # Animationsplätze für die Demo
    yel = comps_of("gelb")
    def nearest(cx, cy):
        return min(yel, key=lambda c: (c["center"][0] - cx) ** 2 + (c["center"][1] - cy) ** 2)
    lamp = nearest(239, 22)
    lantern = nearest(109, 93)
    rng = np.random.default_rng(1980)
    skyid, seaid = names.index("himmel"), names.index("meer")
    sky = (cls == skyid) & ~L
    stars = []
    tries = 0
    while len(stars) < 16 and tries < 5000:
        tries += 1
        x, y = int(rng.integers(4, 274)), int(rng.integers(1, 14))
        if y % 2 == 0 or 222 <= x <= 256:
            continue
        if not sky[max(0, y - 1):y + 2, x - 3:x + 4].all():
            continue
        if any(abs(x - sx) < 14 and abs(y - sy) < 5 for sx, sy, _ in stars):
            continue
        stars.append((x - 1, y, 3))
    sea = (cls == seaid) & ~L
    glints = []
    tries = 0
    while len(glints) < 12 and tries < 5000:
        tries += 1
        x, y = int(rng.integers(64, 270)), int(rng.integers(74, 126))
        if y % 4 == 3:
            continue
        if not sea[y - 2:y + 3, x - 3:x + 6].all():
            continue
        if any(abs(x - gx) < 16 and abs(y - gy) < 6 for gx, gy in glints):
            continue
        glints.append((x, y))
    # Leuchtfeuer: zwei Strahlkanten nach links und rechts (Bresenham), nur während des Blitzes
    lx, ly = lamp["center"]
    lx0, lx1 = int(min(p_[0] for p_ in lamp["px"])), int(max(p_[0] for p_ in lamp["px"]))
    beam = []
    okcls = (names.index("himmel"), names.index("wolke"))
    def beam_ok(x, y):
        return 0 <= y < TH and 0 <= x < TW and cls[y, x] in okcls and not L[y, x]
    # Strahl als Keil: nahe der Lampe volle Zeilen (weiß), weiter außen nur jeder zweite Punkt (farbig, verblasst)
    for side, length in ((-1, 80), (1, 34)):
        xs0 = (lx0 - 3) if side < 0 else (lx1 + 3)
        for i in range(length):
            x = xs0 + side * i
            tt = i / length
            hh = 0.5 + tt * 2.5
            for y in range(int(np.floor(ly - hh)), int(np.ceil(ly + hh)) + 1):
                if tt < 0.55 or (x + y) % 2 == 0:
                    if beam_ok(x, y):
                        beam.append([x, y])
    data["anim"] = {
        "beam": beam,
        "lamp": lamp["px"], "lamp_center": lamp["center"],
        "lantern": lantern["px"], "lantern_center": lantern["center"],
        "stars": [list(s_) for s_ in stars],
        "glints": [list(g) for g in glints],
    }
    (ENTRY / "demo" / "data").mkdir(parents=True, exist_ok=True)
    (ENTRY / "demo" / "data" / "picture.json").write_text(json.dumps(data))
    np.savez_compressed(ENTRY / "assets" / "picture_build.npz", mem=full, cls=cls, lab=lab, L=L)
    print(f"Animation: Lampe {len(lamp['px'])} Punkte bei {lamp['center']}, Laterne {len(lantern['px'])} Punkte bei "
          f"{lantern['center']}, {len(stars)} Sterne, {len(glints)} Glitzerstellen")
    print(f"Linienfilter: {len(all_strokes)} Züge aus der Vorlage, {dropped} innerhalb einer Fläche verworfen")
    print(f"Linien: {len(stroke_px)} Züge, {line_px} Punkte, {n_line_writes} Schreibvorgänge; "
          f"Flächen: {n} ({len(fops)} Spannen), {n_fill_writes} Schreibvorgänge; "
          f"Farbe durch Gruppenbit gekippt: {clash}")
    for c in range(K):
        print(f"  {names[c]:13s} {int((cls == c).sum()):6d} px")


if __name__ == "__main__":
    main()
