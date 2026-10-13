"""Prüflauf für den Eintrag mode7: nimmt die Demo verlustfrei in 256×224 auf und misst die Hardware-Regeln.

Aufruf:
  .venv/bin/python styles/mode7/scripts/probe.py --out <tmp>/fwd
  .venv/bin/python styles/mode7/scripts/probe.py --out <tmp>/gl --rendering-method gl_compatibility --compare <tmp>/fwd
  .venv/bin/python styles/mode7/scripts/probe.py --out <tmp>/late --t0 30 --frames 60

Geprüft je Bild:
  - Mode 7: Godots HDMA-Tabelle gleich m7lib.hdma_table(camera(t)); jedes Ebenenpixel, das kein Sprite verdeckt,
    gleich der ganzzahligen Python-Nachrechnung (m7lib.render_plane + CGRAM + Farbaddition je Zeile)
  - jede Ausgabefarbe auf dem 5-Bit-Raster (32 Stufen je Kanal); Farben je Bild
  - Sprites: 16×16-Zellen je Zeile (wie Hardware-Sprites der Größen 16/32) und 8-px-Streifen je Zeile
    (Grenzen 32 bzw. 34), OAM-Einträge je Bild (128), OBJ-Kacheln je Bild in Byte (4bpp, 16 KB OBJ-VRAM)
  - Textfenster (BG3): je 8×8-Kachel auf dem um (4, 4) verschobenen Raster höchstens 3 Farben
Ergebnis: assets/probe<suffix>.json und eine Kurzfassung auf der Konsole.
"""
import argparse
import json
import math
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m7lib import H, PLANE_END, STYLE, W, Y_H, camera, hdma_table, render_plane   # noqa: E402

HAZE_LINES = 20
LEVELS = np.array([round(k * 255 / 31) for k in range(32)])


def run(out, method, t0, frames):
    demo = STYLE / "demo"
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("f*.png"):
        p.unlink()
    subprocess.run(["godot", "--headless", "--path", str(demo), "--import"], capture_output=True)
    cmd = ["godot", "--path", str(demo), "--position", "20000,20000", "--write-movie", str(out / "f.png"),
           "--fixed-fps", "30", "--quit-after", str(frames)]
    if method:
        cmd += ["--rendering-method", method]
    cmd += ["--", f"--dump={out / 'dump.jsonl'}"]
    if t0:
        cmd.append(f"--t0={t0}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    (out / "godot.log").write_text(log)
    return [l for l in log.splitlines() if "ERROR" in l or "SCRIPT ERROR" in l], \
           [l for l in log.splitlines() if "WARNING" in l]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--rendering-method", default="")
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--compare", default="")
    ap.add_argument("--suffix", default="")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    errors, warnings = run(out, a.rendering_method, a.t0, a.frames)
    dump = [json.loads(l) for l in (out / "dump.jsonl").read_text().splitlines()]
    pngs = sorted(out.glob("f*.png"))
    atlas = np.asarray(Image.open(STYLE / "demo/art/obj_atlas.png"))
    tiles = np.load(STYLE / "assets/m7_tiles.npy")
    tmap = np.asarray(Image.open(STYLE / "demo/art/m7_map.png"))
    cg = json.loads((STYLE / "demo/data/cgram.json").read_text())
    base = np.array(cg["base"])
    seq = cg["glint_seq"]

    res = dict(frames=len(pngs), godot_errors=errors[:5], godot_warnings=warnings[:5], hdma_rows_diff=0,
               plane_pixels_checked=0, plane_pixels_diff=0, off_grid_pixels=0, colors_per_frame_max=0,
               sprites_per_line_max=0, slivers_per_line_max=0, oam_entries_max=0, obj_bytes_max=0,
               math_sprites_in_haze=0, window_tiles_checked=0, window_tile_colors_max=0)
    cmp_diff = []
    for k, p in enumerate(pngs):
        d = dump[k + 1]
        tt = d["t"]
        img = np.asarray(Image.open(p).convert("RGB")).astype(int)
        # 5-Bit-Raster und Farben
        off = ~np.isin(img, LEVELS)
        res["off_grid_pixels"] += int(off.any(axis=2).sum())
        ncol = len(np.unique(img.reshape(-1, 3), axis=0))
        res["colors_per_frame_max"] = max(res["colors_per_frame_max"], ncol)
        # HDMA-Tabelle: Godot gegen Python
        tab, regs = hdma_table(*camera(tt))
        gtab = np.array(d["hdma"])
        res["hdma_rows_diff"] += int((np.abs(gtab - tab[Y_H + 1:PLANE_END]).max(axis=1) > 0).sum())
        if list(regs) != d["regs"]:
            res["hdma_rows_diff"] += 1000
        # Sprite-Maske, Zellen je Zeile
        mask = np.zeros((H, W), bool)
        cells_line = np.zeros(H, int)
        cells_total = 0
        tiles_line = np.zeros(H, int)
        tiles_total = 0
        mix_spr = np.zeros(H, int)      # gemischt 8×8/16×16 (OBSEL Größe 0): Sprites je Zeile
        mix_sliv = np.zeros(H, int)     # 8-px-Streifen je Zeile
        mix_total = 0
        oam_tiles = set()
        for (sheet, step, x, y, rect, math_, flip) in d["oam"]:
            rx, ry, rw, rh = (int(v) for v in rect)
            x, y = int(x), int(y)
            spr = atlas[ry:ry + rh, rx:rx + rw]
            if flip:
                spr = spr[:, ::-1]
            op = spr > 0
            if math_ and y < Y_H + 1 + HAZE_LINES and y + rh > Y_H + 1:
                res["math_sprites_in_haze"] += 1
            ys0, ys1 = max(0, y), min(H, y + rh)
            xs0, xs1 = max(0, x), min(W, x + rw)
            if ys1 > ys0 and xs1 > xs0:
                mask[ys0:ys1, xs0:xs1] |= op[ys0 - y:ys1 - y, xs0 - x:xs1 - x]
            for cy0 in range(0, rh, 16):
                for cx0 in range(0, rw, 16):
                    cell = op[cy0:cy0 + 16, cx0:cx0 + 16]
                    if not cell.any():
                        continue
                    sx = x + cx0
                    if sx + 16 <= 0 or sx >= W or y + cy0 + 16 <= 0 or y + cy0 >= H:
                        continue
                    cells_total += 1
                    quads = [(qy, qx) for qy in (0, 8) for qx in (0, 8)
                             if op[cy0 + qy:cy0 + qy + 8, cx0 + qx:cx0 + qx + 8].any()]
                    if len(quads) >= 3:
                        ya, yb = max(0, y + cy0), min(H, y + cy0 + 16)
                        mix_spr[ya:yb] += 1
                        mix_sliv[ya:yb] += 2
                        mix_total += 1
                    else:
                        for qy, qx in quads:
                            if x + cx0 + qx + 8 <= 0 or x + cx0 + qx >= W:
                                continue
                            ya, yb = max(0, y + cy0 + qy), min(H, y + cy0 + qy + 8)
                            mix_spr[ya:yb] += 1
                            mix_sliv[ya:yb] += 1
                            mix_total += 1
                    for yy in range(y + cy0, y + cy0 + 16):
                        if 0 <= yy < H:
                            cells_line[yy] += 1
            for cy0 in range(0, rh, 8):
                for cx0 in range(0, rw, 8):
                    if op[cy0:cy0 + 8, cx0:cx0 + 8].any():
                        oam_tiles.add((rx + cx0, ry + cy0))
                        sx, sy = x + cx0, y + cy0
                        if sx + 8 <= 0 or sx >= W or sy + 8 <= 0 or sy >= H:
                            continue
                        tiles_total += 1
                        tiles_line[max(0, sy):min(H, sy + 8)] += 1
        res["sprites_per_line_max"] = max(res["sprites_per_line_max"], int(cells_line.max()))
        res["slivers_per_line_max"] = max(res["slivers_per_line_max"], int(2 * cells_line.max()))
        res["oam_entries_max"] = max(res["oam_entries_max"], cells_total)
        res["sprites8_per_line_max"] = max(res.get("sprites8_per_line_max", 0), int(tiles_line.max()))
        res["oam8_entries_max"] = max(res.get("oam8_entries_max", 0), tiles_total)
        res["mix_sprites_per_line_max"] = max(res.get("mix_sprites_per_line_max", 0), int(mix_spr.max()))
        res["mix_slivers_per_line_max"] = max(res.get("mix_slivers_per_line_max", 0), int(mix_sliv.max()))
        res["mix_oam_entries_max"] = max(res.get("mix_oam_entries_max", 0), mix_total)
        if int(mix_sliv.max()) > 34 or int(mix_spr.max()) > 32 or mix_total > 128:
            res.setdefault("frames_over_limits_mix", []).append(k)
        res["obj_bytes_max"] = max(res["obj_bytes_max"], 32 * len(oam_tiles))
        # Mode-7-Ebene nachrechnen
        idx = render_plane(np.vstack([np.zeros((Y_H + 1, 4), int), gtab]), d["regs"], tmap, tiles)
        pal = base.copy()
        step = int(math.floor(tt * 10.0))
        for q in range(4):
            pal[cg["names"][f"glint{q}"]] = seq[(step + q * 3) % len(seq)]
        c5 = pal[idx].astype(int)
        for y in range(Y_H + 1, PLANE_END):
            kk = y - Y_H
            s = min(max(1 - (kk - 1) / HAZE_LINES, 0), 1) ** 2
            c5[y] = np.minimum(c5[y] + np.array([round(15 * s + 1e-9), round(7 * s + 1e-9), round(6 * s + 1e-9)]), 31)
        ref = np.round(c5 * 255 / 31).astype(int)
        sel = np.zeros((H, W), bool)
        sel[Y_H + 1:PLANE_END] = True
        sel &= ~mask
        diff = (np.abs(ref - img).max(axis=2) > 0) & sel
        res["plane_pixels_checked"] += int(sel.sum())
        res["plane_pixels_diff"] += int(diff.sum())
        # Textfenster: 8×8-Kacheln auf dem (4,4)-Raster, nur ganz geöffnet
        if tt >= 0.5:
            for ty in range(4, 52, 8):
                for tx in range(4, 252, 8):
                    if (ty in (4, 44)) and (tx in (4, 244)):
                        continue        # Ecken mit durchsichtigen Pixeln
                    t8 = img[ty:ty + 8, tx:tx + 8].reshape(-1, 3)
                    n = len(np.unique(t8, axis=0))
                    res["window_tiles_checked"] += 1
                    res["window_tile_colors_max"] = max(res["window_tile_colors_max"], n)
        if a.compare:
            q = pathlib.Path(a.compare) / p.name
            if q.exists():
                o = np.asarray(Image.open(q).convert("RGB")).astype(int)
                dd = np.abs(o - img).max(axis=2)
                cmp_diff.append((int((dd > 0).sum()), int(dd.max())))
    if a.compare:
        res["compare_frames"] = len(cmp_diff)
        res["compare_pixels_diff_total"] = sum(c[0] for c in cmp_diff)
        res["compare_pixels_diff_max_frame"] = max((c[0] for c in cmp_diff), default=0)
        res["compare_value_diff_max"] = max((c[1] for c in cmp_diff), default=0)
    print(json.dumps(res, indent=1, ensure_ascii=False))
    (STYLE / f"assets/probe{a.suffix}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
