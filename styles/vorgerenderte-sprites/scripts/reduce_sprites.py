#!/usr/bin/env python3
"""Vorgerenderte Einzelbilder zu Sprite-Bögen nach der Regel der 16-Bit-Konsolen.

    .venv/bin/python styles/vorgerenderte-sprites/scripts/reduce_sprites.py RENDERDIR [gruppe …]

Je Sprite (eine Gruppe von Animationen mit derselben Palette):
  1. 4×4-Mittel mit Alpha-Gewichtung (Render ist 4× überabgetastet)
  2. Alpha hart: deckend ab 50 %, sonst durchsichtig (1 Bit, keine Kantenglättung)
  3. Palette: 15 Farben aus allen deckenden Pixeln aller Bilder der Gruppe, gewichtetes k-means in Oklab
     über die 15-Bit-Farben, Zentren auf vorkommende Farben gezogen, auf BGR555 gerundet
  4. Jeder Pixel auf die nächste Palettenfarbe (ohne Dithering)
Schreibt nach assets/ und demo/sprites/: <name>.png (RGBA-Bogen), <name>_idx.png (indiziert, Index 0 =
durchsichtig), <name>.json (Zellen, Animationen, Palette, Ursprung).
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import vs_color as C  # noqa: E402

STYLE = pathlib.Path(__file__).resolve().parent.parent
SS = 4


def load_small(path):
    """4×-Render verkleinern: nach Materialmehrheit, wenn ein Kennungsbild daneben liegt."""
    img = C.load_rgba(path)
    idp = path.with_name(path.stem + "_id.png")
    if idp.exists():
        s, _ = C.downsample_majority(img, C.decode_ids(C.load_rgba(idp)), SS)
    else:
        s = C.downsample(img, SS)
    s[..., :3] = C.grade(s[..., :3])
    return s


def reduce_set(files, ncolors=15, weight_pow=0.7, dither=0.0, fixed=None, alpha_cut=0.5):
    """files: 4×-Einzelbilder. Rückgabe: Palette, Liste (idx, mask), verkleinerte Bilder."""
    small = [load_small(p) for p in files]
    masks = [s[..., 3] >= alpha_cut for s in small]
    allpx = np.concatenate([s[..., :3][m] for s, m in zip(small, masks)])
    pal = C.kmeans_palette(allpx, ncolors, weight_pow=weight_pow, fixed=fixed)
    out = [(C.map_to_palette(s[..., :3], pal, dither), m) for s, m in zip(small, masks)]
    return pal, out, small


def sheet_from(cells, cell_w, cell_h, cols):
    rows = (len(cells) + cols - 1) // cols
    sheet = np.zeros((rows * cell_h, cols * cell_w, 4), np.uint8)
    for i, c in enumerate(cells):
        r, k = divmod(i, cols)
        sheet[r * cell_h:(r + 1) * cell_h, k * cell_w:(k + 1) * cell_w] = c
    return sheet


def write(name, rgba_cells, idx_cells, pal, cell_w, cell_h, cols, meta):
    for d in (STYLE / "assets", STYLE / "demo" / "sprites"):
        d.mkdir(parents=True, exist_ok=True)
    sheet = sheet_from(rgba_cells, cell_w, cell_h, cols)
    Image.fromarray(sheet, "RGBA").save(STYLE / "assets" / f"{name}.png")
    Image.fromarray(sheet, "RGBA").save(STYLE / "demo" / "sprites" / f"{name}.png")
    # indizierte Fassung als Nachweis der 15+1-Farben
    idx_sheet = np.zeros(sheet.shape[:2], np.int32)
    msk_sheet = np.zeros(sheet.shape[:2], bool)
    for i, (ix, m) in enumerate(idx_cells):
        r, k = divmod(i, cols)
        idx_sheet[r * cell_h:(r + 1) * cell_h, k * cell_w:(k + 1) * cell_w] = ix
        msk_sheet[r * cell_h:(r + 1) * cell_h, k * cell_w:(k + 1) * cell_w] = m
    C.save_indexed(STYLE / "assets" / f"{name}_idx.png", idx_sheet, pal, msk_sheet)
    used = np.unique(sheet[sheet[..., 3] > 0][:, :3], axis=0)
    meta = dict(meta, cell=[cell_w, cell_h], columns=cols, palette=["%02x%02x%02x" % tuple(p) for p in pal],
                colors_used=int(len(used)), all_555=bool(C.is555(used).all()))
    (STYLE / "assets" / f"{name}.json").write_text(json.dumps(meta, indent=1))
    (STYLE / "demo" / "sprites" / f"{name}.json").write_text(json.dumps(meta, indent=1))
    print(f"{name}: {len(rgba_cells)} Bilder, Palette {len(pal)}, benutzt {len(used)}, 15 Bit: {meta['all_555']}")


def group_badger(rd, opts):
    g = rd / "badger"
    m = json.loads((g / "meta.json").read_text())
    order = ["walk", "stand", "turn", "wave", "idle"]
    files, anims, i = [], {}, 0
    for a in order:
        n = m["anims"][a]["frames"]
        anims[a] = dict(m["anims"][a], first=i)
        anims[a].pop("detail", None)
        files += [g / f"{a}_{k:02d}.png" for k in range(n)]
        i += n
    pal, out, small = reduce_set(files, weight_pow=opts.get("pow", 0.7), dither=opts.get("dither", 0.0))
    cells = [C.to_rgba8(ix, pal, mk) for ix, mk in out]
    cw, ch = m["cell"]
    write("badger", cells, out, pal, cw, ch, 10, {"origin": m["origin"], "anims": anims,
                                                  "advance_px": m["anims"]["walk"]["advance_px"]})
    # Schatten: eigene Bilder, nur Maske (Abdunkeln über Farbrechnung in Godot)
    sh = [g / f"{a}_{k:02d}_shadow.png" for a in order for k in range(m["anims"][a]["frames"])]
    if all(p.exists() for p in sh):
        cells = []
        for p in sh:
            s = C.downsample(C.load_rgba(p), SS)
            mk = (s[..., 3] >= 0.25)
            cells.append(np.dstack([np.zeros(mk.shape + (3,), np.uint8), np.where(mk, 255, 0).astype(np.uint8)]))
        shm = json.loads((g / "meta.json").read_text()).get("shadow", {})
        scw, sch = shm.get("cell", m["cell"])
        sheet = sheet_from(cells, scw, sch, 10)
        for d in (STYLE / "assets", STYLE / "demo" / "sprites"):
            Image.fromarray(sheet, "RGBA").save(d / "badger_shadow.png")
        print("badger_shadow:", len(cells), "Bilder")


def group_dirs(rd, opts):
    g = rd / "dirs"
    m = json.loads((g / "meta.json").read_text())
    pal_src = json.loads((STYLE / "assets" / "badger.json").read_text())["palette"]
    pal = np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in pal_src])
    files = [g / f"{d}_{k:02d}.png" for d in m["dirs"] for k in range(m["frames"])]
    small = [load_small(f) for f in files]
    out = [(C.map_to_palette(s[..., :3], pal), s[..., 3] >= 0.5) for s in small]
    cells = [C.to_rgba8(ix, pal, mk) for ix, mk in out]
    cw, ch = m["cell"]
    write("badger_8dir", cells, out, pal, cw, ch, m["frames"], {"origin": m["origin"], "dirs": m["dirs"],
                                                               "palette_from": "badger"})


def group_boxed(rd, group, name, prefix, opts, ncolors=15):
    g = rd / group
    m = json.loads((g / "meta.json").read_text())
    files = sorted(p for p in g.glob(f"{prefix}_*.png") if not p.stem.endswith(("_id", "_shadow")))
    pal, out, small = reduce_set(files, ncolors=ncolors, weight_pow=opts.get("pow", 0.7))
    cells = [C.to_rgba8(ix, pal, mk) for ix, mk in out]
    h, w = cells[0].shape[:2]
    box = m["box"] if "box" in m else m[prefix]["box"]
    write(name, cells, out, pal, w, h, min(len(cells), 10), {"box": box, "frames": len(cells),
                                                              "fps": m.get("fps", 0)})


def group_ui(rd, opts):
    g = rd / "ui"
    m = json.loads((g / "meta.json").read_text())
    # Rahmen und Schild teilen sich eine Palette (wie eine Hintergrundebene), der Zeiger hat eine eigene
    files = [g / "frame_00.png", g / "plaque_00.png"]
    pal, out, small = reduce_set(files, weight_pow=0.6)
    for (ix, mk), name in zip(out, ("ui_frame", "ui_plaque")):
        cell = C.to_rgba8(ix, pal, mk)
        write(name, [cell], [(ix, mk)], pal, cell.shape[1], cell.shape[0], 1, {"palette_shared": "ui"})
    files = [g / f"cursor_{k:02d}.png" for k in range(m["cursor"]["frames"])]
    pal, out, small = reduce_set(files, weight_pow=0.6)
    cells = [C.to_rgba8(ix, pal, mk) for ix, mk in out]
    write("ui_cursor", cells, out, pal, cells[0].shape[1], cells[0].shape[0], len(cells),
          {"frames": len(cells), "fps": m["cursor"]["fps"]})


def group_beam(rd, opts, group="beam", prefix="beam", name="beam", meta_key=None):
    """Lichtkegel, Lichthof: additiv (Farbrechnung), Schwarz = keine Wirkung; 15 Farben + Schwarz."""
    g = rd / group
    m = json.loads((g / "meta.json").read_text())
    if meta_key:
        m = m[meta_key]
    files = sorted(p for p in g.glob(f"{prefix}_*.png"))
    small = []
    for p in files:
        # Emission über durchsichtigem Grund: Blender schreibt die Farbe mit Alpha 0 → RGB ist direkt
        # der additive Beitrag (einfaches 4×4-Mittel)
        a = C.load_rgba(p)[..., :3]
        h, w = a.shape[0] // SS, a.shape[1] // SS
        small.append(a[:h * SS, :w * SS].reshape(h, SS, w, SS, 3).mean((1, 3)))
    allpx = np.concatenate([s.reshape(-1, 3) for s in small])
    lit = allpx[allpx.max(1) > 0.02]
    pal = C.kmeans_palette(lit, 15, weight_pow=0.5)
    pal = np.concatenate([[[0, 0, 0]], pal])
    cells, out = [], []
    for s in small:
        ix = C.map_to_palette(s, pal)
        ix[s.max(-1) <= 0.02] = 0
        cells.append(C.to_rgba8(ix, pal))
        out.append((ix, np.ones(ix.shape, bool)))
    h, w = cells[0].shape[:2]
    write(name, cells, out, pal, w, h, min(6, len(cells)), {"box": m["box"], "frames": len(cells),
                                                             "fps": m.get("fps", 0), "blend": "add"})


def main():
    rd = pathlib.Path(sys.argv[1])
    groups = sys.argv[2:] or ["badger", "dirs", "boat", "lantern", "props", "beam", "ui"]
    for gname in groups:
        if gname == "badger":
            group_badger(rd, {})
        elif gname == "dirs":
            group_dirs(rd, {})
        elif gname == "boat":
            group_boxed(rd, "boat", "boat", "boat", {})
        elif gname == "lantern":
            group_boxed(rd, "lantern", "lantern", "lantern", {})
            group_beam(rd, {}, "lantern", "halo", "lantern_halo", "halo")
        elif gname == "ui":
            group_ui(rd, {})
        elif gname == "beam":
            group_beam(rd, {})
        elif gname == "props":
            group_boxed(rd, "props", "barrels", "barrels", {})
            if (rd / "props" / "crates_00.png").exists():
                group_boxed(rd, "props", "crates", "crates", {})


if __name__ == "__main__":
    main()
