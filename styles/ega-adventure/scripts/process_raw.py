#!/usr/bin/env python3
"""Verarbeitet jedes KI-Bild aus assets/raw/ automatisch zu einer Befehlsliste für die Demo.

    .venv/bin/python styles/ega-adventure/scripts/process_raw.py              # alles verarbeiten + Godot-Prüfung
    .venv/bin/python styles/ega-adventure/scripts/process_raw.py --capture    # zusätzlich Probeaufnahme (Kontaktbogen)
    .venv/bin/python styles/ega-adventure/scripts/process_raw.py --activate   # Demo zeigt danach das KI-Bild
    .venv/bin/python styles/ega-adventure/scripts/process_raw.py --deactivate # Demo zeigt wieder das Handbild
Zum Testen mit Platzhaltern: --raw-dir <Ordner> --out-dir <Ordner> (dann bleiben assets/ und demo/ unberührt).

Eingaben (Namen aus assets/image_jobs.json; weitere PNGs in raw/ werden wie Farbbilder behandelt):
  bg_flat.png   Farbbild  -> Variante ai_bg_flat         (Farben über Gruppen den EGA-Farben zugeordnet)
  bg_lines.png  Strichvorlage, vom Farbbild abgepaust
                -> Variante ai_bg_flat_lines             (Flächen aus der Vorlage, Farben aus dem Farbbild)
                -> Variante ai_bg_flat_detail            (Flächen aus dem Farbbild, Vorlage nur für dünne Details)
                -> Variante ai_bg_flat_touchup           (ai_bg_flat_detail + Handnacharbeit aus scripts/ai_touchup.py)
                -> Variante ai_bg_lines (nur mit Handfarben aus ai_settings.json -> region_colors)
Je Variante in --out-dir (Standard assets/): <v>.pic.json (Befehle + Lage + Tempo), <v>_visual.png,
<v>_priority.png, <v>_cga.png, <v>_layout.png (Markierungen zum Prüfen), dazu <bild>_clusters.png
(Farbzuordnung), bg_lines_mask.png (Linienraster), ai_compare.png (Handbild und alle Varianten) und
ai_report.json. Die gewählte Variante (ai_settings.json -> use, sonst automatisch) geht als
demo/art/harbor_ai.pic.json in die Demo; Godot spielt sie ab und muss bitgleich zur Python-Wiedergabe sein.

Einstellungen: scripts/ai_settings.json (Erklärung der Schlüssel dort unter "_doc").
"""
import argparse, json, math, pathlib, re, shutil, subprocess, sys, tempfile

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
SD = HERE.parent
sys.path.insert(0, str(HERE))
import ai_convert as ac  # noqa: E402
import ai_layout as al  # noqa: E402
import ai_touchup as at  # noqa: E402
from agipic import EGA_RGB, W, H, replay, to_rgb  # noqa: E402
from vectorize import vectorize  # noqa: E402

BUILD_RATE, LINE_COST, BUILD_FRAMES = 560, 8, 48     # wie main.gd; Bild soll nach ≤ 50 Aufnahmebildern stehen
CGA = np.array([[0, 0, 0], [85, 255, 255], [255, 85, 255], [255, 255, 255]], np.uint8)
PAIR = [0, 1, 5, 5, 10, 2, 6, 7, 3, 5, 5, 5, 11, 10, 15, 15]   # wie demo/shaders/ega.gdshader


def cga_image(vis):
    pairs = np.array(PAIR)[vis]
    out = np.zeros((H, W * 2, 3), np.uint8)
    out[:, 0::2] = CGA[pairs // 4]
    out[:, 1::2] = CGA[pairs % 4]
    return Image.fromarray(out)


def build_rate(cmds):
    """Tempo des Bildaufbaus so, dass das Bild wie das Handbild nach etwa 50 Bildern (1,7 s) steht.
    Kosten wie in main.gd: jedes gesetzte Pixel 1, je Linien-/Punktbefehl LINE_COST."""
    from agipic import Pic
    p = Pic()
    for op, arg in cmds:
        if op == "c":
            p.color(arg)
        elif op == "p":
            p.prio(arg)
        elif op == "l":
            p.line(*arg)
        elif op == "s":
            p.dots(*arg)
        elif op == "f":
            p.fill(*arg)
    n_ls = sum(1 for c in cmds if c[0] in "ls")
    cost = p.work + LINE_COST * n_ls
    return max(BUILD_RATE, math.ceil(cost / BUILD_FRAMES)), cost


def godot_check(pic_path, td):
    """Spielt die Befehlsliste in Godot ab (--pic) und vergleicht beide Ebenen mit der Python-Wiedergabe."""
    data = json.loads(pathlib.Path(pic_path).read_text())
    vis, pri = replay(data["commands"])
    dump = pathlib.Path(td) / "pic.bin"
    r = subprocess.run(["godot", "--headless", "--path", str(SD / "demo"), "--quit-after", "150", "--",
                        f"--pic={pathlib.Path(pic_path).resolve()}", f"--dump-pic={dump}"],
                       capture_output=True, text=True, timeout=600)
    log = r.stdout + r.stderr
    errs = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
    m = re.search(r"Bild fertig nach [\d.]+ s \(Bild (\d+)\)", log)
    if not dump.exists():
        return {"ok": False, "errors": errs[:5] or ["kein Bild-Dump (Bild nicht fertig?)"]}
    raw = np.frombuffer(dump.read_bytes(), np.uint8)
    gv, gp = raw[:W * H].reshape(H, W), raw[W * H:].reshape(H, W)
    dv, dp = int((gv != vis).sum()), int((gp != pri).sum())
    return {"ok": not errs and dv == 0 and dp == 0, "diff_visual": dv, "diff_priority": dp,
            "built_at_frame": int(m.group(1)) if m else None, "errors": errs[:5]}


def capture_sheet(pic_path, out_jpg, td):
    """Probeaufnahme (6 s, 30 fps) mit --pic und Kontaktbogen wie tools/capture.py (8 Zeitpunkte)."""
    fr = pathlib.Path(td) / "frames"
    fr.mkdir()
    r = subprocess.run(["godot", "--path", str(SD / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(fr / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--",
                        f"--pic={pathlib.Path(pic_path).resolve()}"], capture_output=True, text=True, timeout=900)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
    pngs = sorted(fr.glob("f*.png"))
    if not pngs:
        return {"ok": False, "errors": errs[:5] or ["keine Bilder"]}
    idx = [int(i * (len(pngs) - 1) / 7) for i in range(8)]
    first = Image.open(pngs[0])
    k2 = max(1, 640 // first.width)                     # Basisauflösung 320×200 -> ganzzahlig ×2
    tw, th = first.width * k2, first.height * k2
    sheet = Image.new("RGB", ((tw + 8) * 4, (th + 20) * 2), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for k, i in enumerate(idx):
        im = Image.open(pngs[i]).convert("RGB").resize((tw, th), Image.NEAREST)
        x, y = (k % 4) * (tw + 8), (k // 4) * (th + 20)
        sheet.paste(im, (x, y + 18))
        d.text((x + 4, y + 3), f"t={i / 30:4.1f}s", fill="white")
    sheet.save(out_jpg, quality=88)
    return {"ok": not errs, "frames": len(pngs), "errors": errs[:5]}


def make_variant(name, idx, settings, out, report):
    """Indexbild -> Befehle (sichtbar + Priorität), Lage, Ansichten. Gibt den Pfad der .pic.json zurück."""
    lay_over = (settings.get("layout") or {}).get(name, {})
    cmds, nreg = vectorize(idx, layered=True)
    layout, lrep = al.detect(idx, lay_over)
    pri_target, objs = al.priority(idx, layout, lrep, lay_over.get("priority_objects"))
    pcmds = al.priority_commands(pri_target)
    allc = cmds + pcmds
    vis, pri = replay(allc)
    dv, dp = int((vis != idx).sum()), int((pri != pri_target).sum())
    rate, cost = build_rate(allc)
    data = {"w": W, "h": H, "build_rate": rate, "commands": allc, "layout": layout,
            "source": name, "notes": [[0, "automatisch umgewandelt (scripts/process_raw.py)"]]}
    pic = out / f"{name}.pic.json"
    pic.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    to_rgb(vis).save(out / f"{name}_visual.png")
    to_rgb(pri).save(out / f"{name}_priority.png")
    cga_image(vis).save(out / f"{name}_cga.png")
    al.overlay(to_rgb(vis), layout, objs, out / f"{name}_layout.png")
    n_l = sum(1 for c in allc if c[0] == "l")
    n_f = sum(len(c[1]) // 2 for c in allc if c[0] == "f")
    front = [o for o in objs if o.get("front_of_badger")]
    path_x = (layout["start_x"] - al.WALK_SPAN, layout["start_x"] + al.BADGER_W - 1)
    occl = [o for o in front if o["box"][2] >= path_x[0] and o["box"][0] <= path_x[1]]
    rep = {"regions": nreg, "commands": len(allc), "visual_commands": len(cmds), "lines": n_l, "fill_seeds": n_f,
           "json_bytes": len(json.dumps(allc, separators=(",", ":"))), "colours": int(len(np.unique(vis))),
           "replay_diff_visual": dv, "replay_diff_priority": dp, "build_cost": cost, "build_rate": rate,
           "layout": {k: v for k, v in lrep.items()}, "priority_objects": objs,
           "occluders_on_walk_path": len(occl)}
    warn = []
    if dv or dp:
        warn.append(f"Wiedergabe weicht ab ({dv}/{dp} Pixel)")
    for k in ("lamp", "lantern", "chimney_top"):
        if layout.get(k) is None:
            warn.append(f"{k} nicht erkannt (Animation fällt weg; in ai_settings.json -> layout.{name}.{k} setzen)")
    if len(layout.get("glints") or []) < 6:
        warn.append("weniger als 6 Glitzerstellen (Wasserfarbe prüfen)")
    if not occl:
        warn.append("kein Gegenstand vor dem Laufweg: Prioritätsbänder nicht sichtbar (walk_y/start_x oder "
                    "priority_objects setzen)")
    if not 90 <= layout["quay_edge"] <= 140:
        warn.append(f"Kaikante bei y={layout['quay_edge']} unplausibel")
    rep["warnings"] = warn
    report["variants"][name] = rep
    print(f"  {name}: {nreg} Flächen, {len(allc)} Befehle ({n_l} Linienzüge, {n_f} Füllpunkte), "
          f"{rep['json_bytes']} Byte, {rep['colours']} Farben, Tempo {rate} px/Bild; Kai {layout['quay_edge']}, "
          f"Fußlinie {layout['walk_y']}, Lampe {layout['lamp']}, Laterne {layout['lantern']}, "
          f"Schornstein {layout['chimney_top']}, {len(layout['glints'])} Glitzer, {len(objs)} Prioritätsflächen, "
          f"{len(occl)} vor dem Laufweg")
    for w_ in warn:
        print("    WARNUNG:", w_)
    return pic


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=str(SD / "assets/raw"))
    ap.add_argument("--out-dir", default=str(SD / "assets"))
    ap.add_argument("--settings", default=str(HERE / "ai_settings.json"))
    ap.add_argument("--no-godot", action="store_true")
    ap.add_argument("--capture", action="store_true", help="Probeaufnahme der gewählten Variante -> <v>_frames.jpg")
    ap.add_argument("--activate", action="store_true", help="demo/art/scene.json auf harbor_ai.pic.json stellen")
    ap.add_argument("--deactivate", action="store_true", help="demo/art/scene.json auf harbor.pic.json stellen")
    a = ap.parse_args()
    scene = SD / "demo/art/scene.json"
    if a.deactivate:
        scene.write_text(json.dumps({"picture": "harbor.pic.json"}) + "\n")
        print("Demo zeigt das Handbild (demo/art/scene.json)")
        return 0
    raw, out = pathlib.Path(a.raw_dir), pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    settings = json.loads(pathlib.Path(a.settings).read_text()) if pathlib.Path(a.settings).exists() else {}
    pngs = sorted(p for p in raw.glob("*.png") if not re.search(r"\.(keyed-src|keyfail)\.png$", p.name))
    line_imgs = [p for p in pngs if "lines" in p.stem]
    colour_imgs = [p for p in pngs if p not in line_imgs]
    if not pngs:
        print(f"keine Rohbilder in {raw} – nichts zu tun (Aufträge: assets/image_jobs.json)")
        return 2
    report = {"inputs": {}, "variants": {}}
    crops, idxs, infos = {}, {}, {}
    for p in colour_imgs:
        s = (settings.get("images") or {}).get(p.stem, {})
        im = Image.open(p).convert("RGB")
        crop, topf = ac.crop_band(im, s.get("crop_top"))
        dist = ac.ega_distance(crop)
        mode = s.get("mapping", "auto")
        if mode == "auto":
            mode = "nearest" if dist < 0.035 else "clusters"
        if mode == "nearest":
            idx, info = ac.nearest_index(crop, s), None
        else:
            idx, info = ac.colour_to_index(crop, s)
            ac.cluster_sheet(crop, info, out / f"{p.stem}_clusters.png")
        meta = p.with_suffix(".json")
        mj = json.loads(meta.read_text()) if meta.exists() else {}
        report["inputs"][p.name] = {"kind": "Farbbild", "size": list(im.size), "crop_top": round(topf, 3),
                                    "ega_distance": round(dist, 4), "mapping": mode, "backend": mj.get("backend"),
                                    "verbatim": mj.get("verbatim"),
                                    **({k: info[k] for k in ("light_scale", "chroma_gain", "groups")} if info else {})}
        print(f"{p.name}: {im.width}×{im.height}, Ausschnitt ab {topf:.0%}, mittlerer EGA-Abstand {dist:.3f} "
              f"-> Zuordnung {mode}")
        crops[p.stem], idxs[p.stem], infos[p.stem] = crop, idx, info
        make_variant(f"ai_{p.stem}", idx, settings, out, report)
    pairs = settings.get("pairs", {"bg_lines": "bg_flat"})
    for p in line_imgs:
        s = (settings.get("images") or {}).get(p.stem, {})
        im = Image.open(p).convert("RGB")
        partner = pairs.get(p.stem)
        top = s.get("crop_top")
        if top is None and partner in idxs:
            top = report["inputs"][f"{partner}.png"]["crop_top"]
        crop, topf = ac.crop_band(im, top)
        lines, linfo = ac.lines_to_mask(crop, s)
        Image.fromarray(np.repeat(np.where(lines, 0, 255).astype(np.uint8), 2, axis=1)).resize(
            (W * 4, H * 2), Image.NEAREST).save(out / f"{p.stem}_mask.png")
        meta = p.with_suffix(".json")
        mj = json.loads(meta.read_text()) if meta.exists() else {}
        rin = {"kind": "Strichvorlage", "size": list(im.size), "crop_top": round(topf, 3), **linfo,
               "line_pixels": int(lines.sum()), "backend": mj.get("backend"), "verbatim": mj.get("verbatim")}
        report["inputs"][p.name] = rin
        print(f"{p.name}: {im.width}×{im.height}, Linienpixel {int(lines.sum())}, Tintenschwelle {linfo['ink_threshold']}")
        if partner in idxs:
            al_score = ac.alignment(lines, idxs[partner])
            rin["alignment"] = round(al_score, 3)
            print(f"  Deckung mit {partner}.png: {al_score:.0%} der Linien auf Farbkanten")
            idx, cinfo = ac.combine(idxs[partner], lines, s)
            rin.update(cinfo)
            make_variant(f"ai_{partner}_lines", idx, settings, out, report)
            # zweite Kombination: Flächen aus dem Farbbild, Strichvorlage nur als Hinweis auf dünne Details
            if infos.get(partner) is not None and s.get("detail", True):
                idx, dinfo = ac.detail_from_lines(idxs[partner], infos[partner]["votes"], lines, s)
                rin["detail"] = dinfo
                print(f"  Details aus der Strichvorlage: {dinfo['detail_pixels']} Pixel gesetzt, "
                      f"{dinfo['detail_undone']} Einzelpixel zurückgenommen")
                make_variant(f"ai_{partner}_detail", idx, settings, out, report)
                # Handnacharbeit (scripts/ai_touchup.py, nur für dieses Bild geschrieben): Steg, Boote, Kisten
                fn = getattr(at, f"touchup_{partner}", None) if partner == "bg_flat" and settings.get("touchup", True) else None
                if fn:
                    idx, ops = fn(idx)
                    rin["touchup_ops"] = ops
                    print(f"  Handnacharbeit (scripts/ai_touchup.py): {ops} Zeichenoperationen")
                    make_variant(f"ai_{partner}_touchup", idx, settings, out, report)
        rc = s.get("region_colors")
        if rc:
            idx, cinfo = ac.combine(None, lines, s, rc)
            rin["lines_only"] = cinfo
            make_variant(f"ai_{p.stem}", idx, settings, out, report)

    # Wahl der Variante für die Demo
    names = list(report["variants"])
    use = settings.get("use")
    if use not in names:
        # Kombination nur, wenn die Strichvorlage gut auf dem Farbbild liegt und das Bild nicht unruhiger macht
        # (mehr Befehle = mehr Krümel und Detaillinien); sonst das Farbbild allein
        # Flächen-Kombination: im ersten echten Lauf (11.10.) trotz 77 % Deckung unbrauchbar (Boote und Steg
        # wurden zu Klumpen), die Befehlszahl merkte das nicht. Deshalb hat die Detail-Variante Vorrang.
        flat = report["variants"].get("ai_bg_flat")
        combo = report["variants"].get("ai_bg_flat_lines")
        align = report["inputs"].get("bg_lines.png", {}).get("alignment", 0)
        if "ai_bg_flat_detail" in names and align >= 0.6:
            use = "ai_bg_flat_detail"
        elif combo and (not flat or (align >= 0.6 and combo["commands"] <= 1.1 * flat["commands"])):
            use = "ai_bg_flat_lines"
        else:
            use = "ai_bg_flat" if flat else names[0]
    report["use"] = use
    print(f"gewählt für die Demo: {use}")

    # Vergleichsbogen: Handbild + Varianten (×2)
    tiles = [("Handbild (scripts/pic_harbor.py)", Image.open(SD / "assets/harbor_visual.png"))]
    tiles += [(n, Image.open(out / f"{n}_visual.png")) for n in names]
    tw, th = W * 2 * 2, H * 2
    sheet = Image.new("RGB", (tw * 2 + 10, (th + 22) * math.ceil(len(tiles) / 2)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(tiles):
        x, y = (i % 2) * (tw + 10), (i // 2) * (th + 22)
        sheet.paste(im.convert("RGB").resize((tw, th), Image.NEAREST), (x, y + 20))
        d.text((x + 4, y + 4), label + (" <- Demo" if label == use else ""), fill=(230, 230, 230))
    sheet.save(out / "ai_compare.png")

    default_out = out.resolve() == (SD / "assets").resolve()
    pic = out / f"{use}.pic.json"
    if default_out:
        shutil.copy2(pic, SD / "demo/art/harbor_ai.pic.json")
        pic = SD / "demo/art/harbor_ai.pic.json"
    with tempfile.TemporaryDirectory(prefix="ega-adventure-") as td:
        if not a.no_godot:
            g = godot_check(pic, td)
            report["godot"] = g
            print(f"Godot: {'bitgleich' if g['ok'] else 'FEHLER'} {g}")
        if a.capture:
            c = capture_sheet(pic, out / f"{use}_frames.jpg", td)
            report["capture"] = c
            print(f"Probeaufnahme: {out / f'{use}_frames.jpg'} {c}")
    (out / "ai_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    if a.activate:
        if not default_out:
            sys.exit("--activate nur mit Standard-Ausgabeordner")
        scene.write_text(json.dumps({"picture": "harbor_ai.pic.json"}) + "\n")
        print("Demo zeigt jetzt das KI-Bild (demo/art/scene.json); zurück mit --deactivate")
    bad = report.get("godot", {}).get("ok") is False or any(
        v["replay_diff_visual"] or v["replay_diff_priority"] for v in report["variants"].values())
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
