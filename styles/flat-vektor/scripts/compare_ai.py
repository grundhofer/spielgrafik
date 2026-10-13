#!/usr/bin/env python3
"""Vergleich der beiden Wege: KI-Bild (Raster), KI-Bild -> vtracer -> Polygon2D, Code-SVG -> Polygon2D.

    # zuerst im eigenen venv mit vtracer:
    <venv>/bin/python -I styles/flat-vektor/scripts/vectorize_ai.py styles/flat-vektor/assets/raw/bg_ai.png <tmp>/bg_ai_vec.svg --fit 1280x720
    <venv>/bin/python -I styles/flat-vektor/scripts/vectorize_ai.py styles/flat-vektor/assets/raw/badger_ai.png <tmp>/badger_ai_vec.svg --scale 0.2
    # dann:
    .venv/bin/python styles/flat-vektor/scripts/compare_ai.py <tmp>

Rendert alles mit Godot (gleicher Renderer, 4x-MSAA) und schreibt assets/compare_ai_vs_code.jpg und
assets/compare_ai_vs_code.json (Formen, Punkte, Dateigrößen). Zwischenstände bleiben in <tmp>.
"""
import json, pathlib, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[3]
STYLE = ROOT / "styles" / "flat-vektor"
DEMO = STYLE / "demo"
PY = sys.executable
FOOT = (517, 574)          # Standplatz des Code-Dachses im Bild (Mitte unten der Pfoten)
BADGER_H = 181             # gemessene Höhe des Code-Dachses (badger_measure.json: oberste Zeile 393 bei Fußlinie 573)
CROP = (322, 372, 713, 592)  # 16:9-Ausschnitt um den stehenden Dachs


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    bad = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    if r.returncode or bad:
        sys.exit(f"Fehler in {cmd[:3]}: {(bad or [r.stderr[-400:]])[0]}")
    return r


def godot_still(project, out, t0=None, extra=()):
    out.mkdir(parents=True, exist_ok=True)
    args = ["godot", "--path", str(project), "--position", "20000,20000", "--resolution", "1280x720",
            "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "2", "--"]
    if t0 is not None:
        args.append(f"--t0={t0}")
    sh(args + list(extra))
    return Image.open(sorted(out.glob("f*.png"))[-1]).convert("RGB")


COMPARE_GD = '''extends Node2D
func _ready() -> void:
	var a := {}
	for s in OS.get_cmdline_user_args():
		if s.contains("="):
			a[s.get_slice("=", 0)] = s.get_slice("=", 1)
	if a.has("--bg"):
		var img := Image.load_from_file(a["--bg"])
		var spr := Sprite2D.new()
		spr.texture = ImageTexture.create_from_image(img)
		spr.centered = false
		add_child(spr)
	var sc: Node2D = load("res://" + a["--scene"] + ".tscn").instantiate()
	if a.has("--pos"):
		sc.position = Vector2(float(a["--pos"].get_slice(",", 0)), float(a["--pos"].get_slice(",", 1)))
	if a.has("--scale"):
		sc.scale = Vector2.ONE * float(a["--scale"])
	add_child(sc)
'''


def main():
    tmp = pathlib.Path(sys.argv[1]).resolve()
    proj = tmp / "cmpproj"
    proj.mkdir(exist_ok=True)
    stats = {}
    for n in ("bg_ai_vec", "badger_ai_vec"):
        sh([PY, str(STYLE / "scripts" / "svg2godot.py"), str(tmp / f"{n}.svg"), str(proj / f"{n}.tscn"),
            "--tol", "0.35", "--stats", str(tmp / f"{n}.stats.json")])
        stats[n] = json.loads((tmp / f"{n}.stats.json").read_text())
        stats[n]["svg_bytes"] = (tmp / f"{n}.svg").stat().st_size
        stats[n]["tscn_bytes"] = (proj / f"{n}.tscn").stat().st_size
    for n in ("harbor", "badger"):
        stats[f"code_{n}"] = json.loads((STYLE / "assets" / f"{n}_stats.json").read_text())
        stats[f"code_{n}"]["svg_bytes"] = (STYLE / "assets" / f"{n}.svg").stat().st_size
        stats[f"code_{n}"]["tscn_bytes"] = (DEMO / "art" / f"{n}.tscn").stat().st_size
    (proj / "project.godot").write_text('config_version=5\n[application]\nrun/main_scene="res://main.tscn"\n'
                                        'config/features=PackedStringArray("4.7", "Forward Plus")\n[display]\n'
                                        'window/size/viewport_width=1280\nwindow/size/viewport_height=720\n'
                                        '[rendering]\nenvironment/defaults/default_clear_color=Color(0.16, 0.13, 0.31, 1)\n'
                                        'anti_aliasing/quality/msaa_2d=2\n')
    (proj / "compare.gd").write_text(COMPARE_GD)
    (proj / "main.tscn").write_text('[gd_scene format=3]\n[ext_resource type="Script" path="res://compare.gd" id="1"]\n'
                                    '[node name="Main" type="Node2D"]\nscript = ExtResource("1")\n')
    sh(["godot", "--headless", "--path", str(proj), "--import"])
    sh(["godot", "--headless", "--path", str(DEMO), "--import"])

    # Code-Weg aus der Demo: Hintergrund ohne Figur, Figur im Stand (t = 5,5 s)
    code_bg = godot_still(DEMO, tmp / "r_code_bg", 5.5, ["--probe-no-badger", "--probe-no-ui"])
    code_bd = godot_still(DEMO, tmp / "r_code_bd", 5.5, ["--probe-no-ui"])
    code_bg.save(tmp / "code_bg.png")
    # KI-Weg, Raster: Bild auf volle Breite, unten bündig (wie --fit in vectorize_ai.py)
    ai = Image.open(STYLE / "assets" / "raw" / "bg_ai.png").convert("RGB")
    s = 1280 / ai.width
    ai_s = ai.resize((1280, round(ai.height * s)), Image.LANCZOS)
    ai_bg = ai_s.crop((0, ai_s.height - 720, 1280, ai_s.height))
    # KI-Weg, vektorisiert
    vec_bg = godot_still(proj, tmp / "r_vec_bg", None, ["--scene=bg_ai_vec"])
    # KI-Figur: auf denselben Hintergrund und dieselbe Höhe wie der Code-Dachs
    bd = Image.open(STYLE / "assets" / "raw" / "badger_ai.png").convert("RGBA")
    box = Image.fromarray((np.asarray(bd)[:, :, 3] > 128).astype(np.uint8) * 255).getbbox()
    k = BADGER_H / (box[3] - box[1])
    cx = (box[0] + box[2]) / 2
    ai_bd_img = bd.resize((round(bd.width * k), round(bd.height * k)), Image.LANCZOS)
    ai_bd = code_bg.copy().convert("RGBA")
    ai_bd.alpha_composite(ai_bd_img, (round(FOOT[0] - cx * k), round(FOOT[1] - box[3] * k)))
    ai_bd = ai_bd.convert("RGB")
    kv = k / 0.2   # vectorize_ai.py --scale 0.2
    pos = f"{FOOT[0] - cx * 0.2 * kv:.2f},{FOOT[1] - box[3] * 0.2 * kv:.2f}"
    vec_bd = godot_still(proj, tmp / "r_vec_bd", None, ["--scene=badger_ai_vec", f"--bg={tmp / 'code_bg.png'}",
                                                        f"--pos={pos}", f"--scale={kv:.5f}"])

    # Tafel: 3 Spalten (KI-Raster, KI -> vtracer, Code-SVG), 3 Reihen (Szene, Figur, Ausschnitt 1:1)
    PW, PH = 640, 360
    font = ImageFont.truetype(str(DEMO / "fonts" / "Montserrat-wght.ttf"), 17)
    small = ImageFont.truetype(str(DEMO / "fonts" / "Montserrat-wght.ttf"), 14)
    sheet = Image.new("RGB", (PW * 3, PH * 3 + 3 * 34), (24, 22, 48))
    d = ImageDraw.Draw(sheet)
    sb, sv, ch, cb = stats["bg_ai_vec"], stats["badger_ai_vec"], stats["code_harbor"], stats["code_badger"]
    cols = [
        ("KI-Bild (agy / Codex), Raster", [ai_bg, ai_bd], "Raster, keine Teile animierbar"),
        ("KI-Bild -> vtracer -> Polygon2D", [vec_bg, vec_bd], f"Szene {sb['polygons']} / Figur {sv['polygons']} Formen"),
        ("Code -> SVG -> Polygon2D (Demo)", [code_bg, code_bd], f"Szene {ch['polygons']} / Figur {cb['polygons']} Formen"),
    ]
    for c, (title, ims, note) in enumerate(cols):
        x = c * PW
        for r, im in enumerate(ims):
            y = r * (PH + 34) + 34
            panel = im.resize((PW, PH), Image.LANCZOS) if r == 0 else im.crop(CROP).resize((PW, PH), Image.LANCZOS)
            sheet.paste(panel, (x, y))
        y = 2 * (PH + 34) + 34
        z = ims[0].crop((900, 70, 1220, 250)).resize((PW, PH), Image.LANCZOS)
        sheet.paste(z, (x, y))
        d.text((x + 12, 8), title, font=font, fill=(246, 236, 220))
        d.text((x + 12, PH + 34 + 9), note, font=small, fill=(255, 216, 143))
        d.text((x + 12, 2 * (PH + 34) + 9), "Ausschnitt Leuchtturm, 2-fach", font=small, fill=(200, 190, 210))
    out = STYLE / "assets" / "compare_ai_vs_code.jpg"
    sheet.save(out, quality=88)
    summary = {k: {kk: v.get(kk) for kk in ("polygons", "points", "groups", "gradients", "svg_bytes", "tscn_bytes", "self_intersecting")}
               for k, v in stats.items()}
    (STYLE / "assets" / "compare_ai_vs_code.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps(summary, ensure_ascii=False))
    print(out)


if __name__ == "__main__":
    main()
