#!/usr/bin/env python3
"""Prüft, ob die automatische Verarbeitung eine verschobene, verkleinerte JPEG-Maske (wie von agy) wiederfindet.

    .venv/bin/python styles/kinemagramm/tools/selftest.py [--work DIR]

Voraussetzung: process.py ist mit den eigenen Bildern gelaufen (assets/mask_ai.png, mask_a/c.png, scene.json).
1. Bezug: die Ergebnisse aus assets/ (Masken aus der echten, bereits passenden KI-Maske von Codex)
2. Künstliche KI-Maske daraus: assets/mask_ai.png ins 3:2-Quellformat zurückgerechnet, absichtlich verschoben
   und skaliert (sx 1,02, sy 1,015, dx +9, dy -6 px), auf 1264x848 verkleinert (wie agy) und als JPEG
   (Qualität 70) gespeichert -> WORK/raw/mask.png; dazu WORK/raw/bg.png und WORK/raw/badger.png (eigene Rohbilder)
3. process.py mit umgelenkten Ordnern (WORK/raw, WORK/assets, Kopie der Demo in WORK/demo)
4. Vergleich mit dem Bezug: IoU Himmel/Wasser/Boote, Lage der Lichter, Schornstein, Drehpunkte,
   Augen und Schalende gefunden, Godot ohne Fehler. Exit 1, wenn eine Grenze verfehlt wird.
Schreibt nichts in den Eintragsordner.
"""
import argparse, io, json, pathlib, shutil, subprocess, sys, tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
sys.path.insert(0, str(HERE))
import aimask as A  # noqa: E402

PY = sys.executable
W, H = 1280, 720


def iou(a, b):
    return float((a & b).sum() / max((a | b).sum(), 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=str(pathlib.Path(tempfile.gettempdir()) / "kinemagramm" / "selftest"))
    a = ap.parse_args()
    work = pathlib.Path(a.work).resolve()
    if work.exists():
        shutil.rmtree(work)
    (work / "raw").mkdir(parents=True)
    src = ENTRY / "assets" / "raw" / "bg.png"
    stand = json.loads((ENTRY / "assets" / "scene_config.json").read_text())

    # 1. Bezug
    ma = np.asarray(Image.open(ENTRY / "assets" / "mask_a.png").convert("RGB")) > 127
    mc = np.asarray(Image.open(ENTRY / "assets" / "mask_c.png").convert("RGB")) > 127
    hscene = json.loads((ENTRY / "assets" / "scene.json").read_text())
    cx, cy = hscene["chimney"]

    # 2. Künstliche KI-Maske aus der ausgerichteten echten Maske
    lab_still = A.from_rgb(Image.open(ENTRY / "assets" / "mask_ai.png").convert("RGB"))
    sw, sh = Image.open(src).size
    ch = round(sw * 9 / 16)
    y0 = round((sh - ch) * stand.get("crop_y", 0.5))
    big = A.resize_lab(lab_still, (sw, ch))
    full = np.concatenate([np.repeat(big[:1], y0, 0), big, np.repeat(big[-1:], sh - ch - y0, 0)], 0)
    T_true = (1.02, 1.015, 9.0, -6.0)
    undist = full
    full = A.warp_lab(full, T_true, (sw, sh))
    rgb = Image.fromarray(A.to_rgb(full)).resize((1264, 848), Image.BILINEAR)
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=70)
    Image.open(io.BytesIO(buf.getvalue())).convert("RGB").save(work / "raw" / "mask.png")
    shutil.copy2(src, work / "raw" / "bg.png")
    shutil.copy2(ENTRY / "assets" / "raw" / "badger.png", work / "raw" / "badger.png")

    # 3. process.py in eine Kopie der Demo
    shutil.copytree(ENTRY / "demo", work / "demo", ignore=shutil.ignore_patterns(".godot"))
    p = subprocess.run([PY, str(HERE / "process.py"), "--raw", str(work / "raw"), "--assets", str(work / "assets"),
                        "--demo", str(work / "demo"), "--work", str(work / "process")], capture_output=True, text=True)
    print(p.stdout[-3000:], p.stderr[-2000:])
    if p.returncode:
        print("FAIL: process.py Exit", p.returncode)
        return 1

    # 4. Vergleich
    res, fails = {}, []
    aa = np.asarray(Image.open(work / "assets" / "mask_a.png").convert("RGB")) > 127
    ac = np.asarray(Image.open(work / "assets" / "mask_c.png").convert("RGB")) > 127
    res["iou_sky"] = round(iou(aa[..., 1], ma[..., 1]), 3)
    res["iou_water"] = round(iou(aa[..., 0], ma[..., 0]), 3)
    res["iou_boat1"] = round(iou(ac[..., 0], mc[..., 0]), 3)
    res["iou_boat2"] = round(iou(ac[..., 1], mc[..., 1]), 3)
    for k, lim in (("iou_sky", 0.95), ("iou_water", 0.9), ("iou_boat1", 0.75), ("iou_boat2", 0.75)):
        if res[k] < lim:
            fails.append(f"{k} {res[k]} < {lim}")
    ascene = json.loads((work / "assets" / "scene.json").read_text())
    for ch_ in ("window", "lantern", "lamp"):
        hp = next(li["pos"] for li in hscene["lights"] if li["channel"] == ch_)
        ap_ = [li["pos"] for li in ascene["lights"] if li["channel"] == ch_]
        dist = min(float(np.hypot(p_[0] - hp[0], p_[1] - hp[1])) for p_ in ap_) if ap_ else 999
        res[f"light_{ch_}_px"] = round(dist, 1)
        if dist > 12:
            fails.append(f"Licht {ch_} {dist:.1f} px daneben")
    dch = float(np.hypot(ascene["chimney"][0] - cx, ascene["chimney"][1] - cy))
    res["chimney_px"] = round(dch, 1)
    if dch > 8:
        fails.append(f"Schornstein {dch:.1f} px daneben")
    for i, (hb, ab) in enumerate(zip(hscene["boats"], ascene["boats"])):
        dp = float(np.hypot(hb["pivot"][0] - ab["pivot"][0], hb["pivot"][1] - ab["pivot"][1]))
        res[f"pivot{i + 1}_px"] = round(dp, 1)
        if dp > 25:
            fails.append(f"Drehpunkt Boot {i + 1} {dp:.1f} px vom Bezug")
    if len(ascene["boats"]) != 2:
        fails.append(f"{len(ascene['boats'])} Boote statt 2")
    rep = json.loads((work / "process" / "process_report.json").read_text())
    res["align"] = T = rep["scene_auto"].get("align")
    # Ausrichtung: dieselben Punkte müssen dort landen, wo die unverzerrte Maske ausgerichtet landet
    # (verglichen wird nur die Wiederfindung, nicht die absolute Lage)
    src_img = np.asarray(Image.open(src).convert("RGB"), np.float32) / 255.0
    Ti = A.align(src_img, undist)
    ccx, ccy = sw / 2.0, sh / 2.0
    errs = []
    for x, y in [(x, y) for x in (150, 768, 1390) for y in (250, 400, 600, 850)]:
        x1, y1 = ccx + T_true[0] * (x - ccx) + T_true[2], ccy + T_true[1] * (y - ccy) + T_true[3]
        x2, y2 = ccx + T["sx"] * (x1 - ccx) + T["dx"], ccy + T["sy"] * (y1 - ccy) + T["dy"]
        x3, y3 = ccx + Ti["sx"] * (x - ccx) + Ti["dx"], ccy + Ti["sy"] * (y - ccy) + Ti["dy"]
        errs.append(float(np.hypot(x2 - x3, y2 - y3)))
    res["align_undistorted"] = Ti
    res["align_error_px_max"] = round(max(errs), 1)
    if max(errs) > 4.5:
        fails.append(f"Ausrichtung weicht bis {max(errs):.1f} px ab (Quellpixel)")
    bj = json.loads((work / "assets" / "badger.json").read_text())
    bc = json.loads((work / "assets" / "badger_config.json").read_text())
    res["eyes"] = bc.get("eyes")
    res["tail"] = bc.get("tail")
    if len(bc.get("eyes", [])) != 2:
        fails.append("Augen nicht gefunden")
    if not bc.get("tail") or bj["tail_end_v"] <= bj["anchor_v"]:
        fails.append("Schalende nicht gefunden")
    if rep.get("godot_errors"):
        fails.append("Godot-Fehler")
    print(json.dumps(res, indent=1))
    (work / "selftest.json").write_text(json.dumps({"result": res, "fails": fails}, indent=1))
    print("FAIL:\n  " + "\n  ".join(fails) if fails else "PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
