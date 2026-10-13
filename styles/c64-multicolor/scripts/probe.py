#!/usr/bin/env python3
"""Prüfungen am gerenderten Bild der Demo (384x240, Ausgabe von Godot --write-movie).

  1. Dachs allein (--only=badger, Hintergrund Hellblau): Kopf- und Fußzeile je Bild, Standfuß beim Laufen
     (eine Fußsohle bleibt über jeden Posenwechsel auf ±1 px an derselben Stelle), Vorschub je Posenwechsel,
     Unterschied der Posen (abweichende Pixel je Paar im 24x42-Ausschnitt).
  2. Hintergrund allein (--only=bg): Zellregel (je 4x8-Zelle höchstens 3 Farben neben der Zeilen-Hintergrundfarbe),
     Doppelpixel (Spaltenpaare gleich), nur Palettenfarben; Textzeilen: je 8x8-Zeichen höchstens 2 Farben.
  3. Ganzes Bild 0-6 s: nur Palettenfarben, Sprites je Zeile (aus --probe), Dauerlauf ab t0=30 s.
  4. Renderer: Mobile und Compatibility gegen Forward+ (je 30 Bilder).
Ergebnis: media/probe.json
"""
import json, pathlib, subprocess, sys, tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from c64lib import *  # noqa

DEMO = ROOT / "demo"


def render(td, n, *user, method=None, t0=0.0):
    d = pathlib.Path(td) / (("_".join(user) or "all").replace("=", "-").replace("/", "") + (method or "") + f"{t0}")
    d.mkdir(parents=True, exist_ok=True)
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--write-movie", str(d / "f.png"),
           "--fixed-fps", "30", "--quit-after", str(n)]
    if method:
        cmd += ["--rendering-method", method]
    cmd += ["--", f"--t0={t0}", *user]
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    hw = [l for l in r.stdout.splitlines() if l.startswith("HWSTAT")]
    frames = [np.asarray(Image.open(p).convert("RGB")) for p in sorted(d.glob("f*.png"))]
    return frames, errs, hw


def pal_index(img):
    flat = img.reshape(-1, 3).astype(int)
    key = flat[:, 0] * 65536 + flat[:, 1] * 256 + flat[:, 2]
    pk = PAL[:, 0].astype(int) * 65536 + PAL[:, 1].astype(int) * 256 + PAL[:, 2].astype(int)
    lut = {int(k): i for i, k in enumerate(pk)}
    idx = np.array([lut.get(int(k), -1) for k in key])
    return idx.reshape(img.shape[:2])


def runs(mask):
    xs = np.flatnonzero(mask)
    if not len(xs):
        return []
    out, s, p = [], xs[0], xs[0]
    for x in xs[1:]:
        if x != p + 1:
            out.append((int(s), int(p)))
            s = x
        p = x
    out.append((int(s), int(p)))
    return out


def main():
    res = {}
    rom = json.loads((DEMO / "rom/c64.json").read_text())
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    with tempfile.TemporaryDirectory() as td:
        # 1. Dachs
        probe_file = pathlib.Path(td) / "probe.jsonl"
        frames, errs, hw = render(td, 180, "--only=badger", f"--probe={probe_file}")
        poses = [json.loads(l) for l in probe_file.read_text().splitlines()]
        heads, feet, soles = [], [], []
        for fr in frames:
            idx = pal_index(fr)
            scr = idx[20:220, 32:352]
            m = (scr != LBLUE) & (scr >= 0)
            ys = np.flatnonzero(m.any(1))
            if not len(ys):
                heads.append(None); feet.append(None); soles.append([])
                continue
            heads.append(int(ys[0])); feet.append(int(ys[-1]))
            soles.append(runs(m[ys[-1]]))
        walk = []
        drift = []
        for i in range(1, len(frames)):
            a, b = poses[i - 1], poses[i]
            if a["pose"] == b["pose"] and a["x"] == b["x"]:
                continue
            if not soles[i - 1] or not soles[i]:
                continue
            # Standfuß: die Sohle, die in beiden Bildern am nächsten beieinander liegt (Ferse links)
            if min(s0 for s0, _ in soles[i - 1] + soles[i]) <= 0:
                continue          # Fuß noch im linken Rahmen verdeckt: Sohle abgeschnitten
            best = min(abs(sa[0] - sb[0]) for sa in soles[i - 1] for sb in soles[i])
            if b["x"] - a["x"] > 0 or a["pose"] != b["pose"]:
                drift.append(best)
                walk.append({"f": b["f"], "von": a["pose"], "nach": b["pose"], "dx": b["x"] - a["x"],
                             "sohlen_vorher": soles[i - 1], "sohlen_nachher": soles[i], "standfuss_abweichung": best})
        visible = [i for i, h in enumerate(heads) if h is not None and poses[i]["x"] >= 0]
        # Posen unterscheidbar? Je Pose das erste ganz sichtbare Bild, Ausschnitt 24x42 über der Fußzeile
        foot = max(feet[i] for i in visible)
        crops = {}
        for i in visible:
            name, x = poses[i]["pose"], poses[i]["x"]
            if name not in crops and x + 24 <= 320:
                crops[name] = pal_index(frames[i])[20:220, 32:352][foot - 41:foot + 1, x:x + 24]
        names = sorted(crops)
        pose_diff = {f"{a}/{b}": int((crops[a] != crops[b]).sum()) for k, a in enumerate(names) for b in names[k + 1:]}
        res["badger"] = {
            "fusszeile": sorted({feet[i] for i in visible}),
            "kopfzeile_laufen": sorted({heads[i] for i in visible if poses[i]["pose"].startswith("walk")}),
            "kopfzeile_stehen": sorted({heads[i] for i in visible if not poses[i]["pose"].startswith("walk")}),
            "posenwechsel": len(drift),
            "standfuss_max_abweichung_px": max(drift) if drift else None,
            "standfuss_abweichungen": drift,
            "posen_abweichende_pixel": pose_diff,
            "beispiele": walk[:6],
            "godot_fehler": errs,
        }
        # 2. Hintergrund
        frames, errs, hw = render(td, 3, "--only=bg", t0=2.0)
        idx = pal_index(frames[-1])
        scr = idx[20:220, 32:352]
        foreign = int((idx < 0).sum())
        pairs_bad = int((scr[:144, 0::2] != scr[:144, 1::2]).sum())
        line_bg = [r[0] for r in rom["raster"][20:220]]
        cell_bad, worst = 0, 0
        for cy in range(18):
            for cx in range(40):
                cols = set()
                for r in range(8):
                    y = cy * 8 + r
                    for v in scr[y, cx * 8:cx * 8 + 8]:
                        if v != line_bg[y]:
                            cols.add(int(v))
                worst = max(worst, len(cols))
                cell_bad += len(cols) > 3
        text_bad = 0
        for cy in range(18, 25):
            for cx in range(40):
                fg = set()
                for r in range(8):
                    y = cy * 8 + r
                    fg |= {int(v) for v in scr[y, cx * 8:cx * 8 + 8] if v != line_bg[y]}
                text_bad += len(fg) > 1
        res["background"] = {"fremde_farben": foreign, "doppelpixel_verstoesse": pairs_bad,
                             "zellen_ueber_3_farben": cell_bad, "max_farben_je_zelle_ohne_zeilenhintergrund": worst,
                             "textzellen_mit_mehr_als_1_zeichenfarbe": text_bad, "farben_im_bild": sorted(set(np.unique(scr).tolist())),
                             "rasterzeilen_mit_farbwechsel": int(sum(1 for a, b in zip(line_bg, line_bg[1:]) if a != b)),
                             "godot_fehler": errs}
        # 3. Ganzes Bild
        probe_file = pathlib.Path(td) / "probe_all.jsonl"
        frames, errs, hw = render(td, 180, f"--probe={probe_file}")
        fc = sum(int((pal_index(f) < 0).sum()) for f in frames[::6])
        pl = [json.loads(l) for l in probe_file.read_text().splitlines()]
        res["full"] = {"fremde_farben_in_30_bildern": fc, "max_sprites_je_zeile": max(p["max_line"] for p in pl),
                       "max_sprites_gleichzeitig": max(p["sprites"] for p in pl), "hwstat": hw, "godot_fehler": errs}
        base = frames
        frames30, errs30, hw30 = render(td, 60, t0=30.0)
        Image.fromarray(frames30[-1]).resize((1152, 720), Image.NEAREST).save(ROOT / "media/probe_t30.png")
        res["dauerlauf_t30"] = {"bilder": len(frames30), "fremde_farben": int((pal_index(frames30[-1]) < 0).sum()),
                                "godot_fehler": errs30}
        # 4. Renderer
        res["renderer"] = {}
        for m in ("mobile", "gl_compatibility"):
            fr, e, _ = render(td, 30, method=m)
            same = sum(1 for a, b in zip(fr, base[:30]) if a.shape == b.shape and np.array_equal(a, b))
            diff = max((float(np.abs(a.astype(int) - b.astype(int)).max()) for a, b in zip(fr, base[:30])),
                       default=None)
            res["renderer"][m] = {"pixelgleich": f"{same}/{min(len(fr), 30)}", "max_abweichung": diff,
                                  "godot_fehler": e[:3]}
    (ROOT / "media/probe.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("beispiele", "standfuss_abweichungen")}
                      if isinstance(v, dict) else v for k, v in res.items()}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
