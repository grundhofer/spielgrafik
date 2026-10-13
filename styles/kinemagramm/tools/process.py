#!/usr/bin/env python3
"""Verarbeitet alle vorhandenen Rohbilder aus assets/raw/ zu den Daten der Godot-Demo (ein Aufruf).

    .venv/bin/python styles/kinemagramm/tools/process.py [--work DIR] [--no-godot]

Ablauf (jeder Schritt nur, wenn sein Rohbild da ist):
  1. Szene   assets/raw/bg.png (+ assets/raw/mask.png)
             mit Maske:  auto_scene.py richtet die KI-Maske aus und rechnet alle Positionen aus
             ohne Maske: tools/scene.hand.json (Polygone von Hand); fehlt sie, wird ein Entwurf samt
                         Rasterbild in den Arbeitsordner geschrieben und mit Exit 3 abgebrochen
             danach tools/scene.override.json (Korrekturen von Hand) darübergelegt
             -> assets/scene_config.json -> prep.py -> assets/still.png, plate.png, mask_a/b/c.png, noise.png,
                scene.json (+ assets/mask_ai.png, die ausgerichtete KI-Maske)
  2. Dachs   assets/raw/badger.png -> auto_badger.py (+ tools/badger.override.json)
             -> assets/badger_config.json -> prep_badger.py -> assets/badger_body/scarf/lids.png, badger.json
             fehlt das Bild: Abbruch mit Exit 4
  3. Kopie der Demo-Daten nach demo/art/
  4. Godot: Import und 30 Bilder Probelauf (render.py), Fehlerzeilen werden gemeldet; ein Probebild und die
     Kontrollbilder (scene_overlay.png, badger_overlay.png, prep/masks_overlay.png) liegen im Arbeitsordner.
Arbeitsordner (Standard): <TMPDIR>/kinemagramm/process. Für Tests lassen sich --raw, --assets und --demo umlenken.
"""
import argparse, json, os, pathlib, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
sys.path.insert(0, str(HERE))
import auto_badger  # noqa: E402
import auto_scene  # noqa: E402

DEMO_FILES = ["still.png", "plate.png", "mask_a.png", "mask_b.png", "mask_c.png", "noise.png", "scene.json",
              "badger_body.png", "badger_scarf.png", "badger_lids.png", "badger.json"]
PY = sys.executable


def merge(a, b):
    """b über a legen: Objekte rekursiv, Listen von Objekten je Index, sonst ersetzen; null löscht."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            if k.startswith("_"):
                continue
            if v is None:
                out.pop(k, None)
            else:
                out[k] = merge(a.get(k), v) if k in a else v
        return out
    if isinstance(a, list) and isinstance(b, list) and b and all(isinstance(x, dict) for x in a + b):
        return [merge(a[i], b[i]) if i < len(a) else b[i] for i in range(len(b))] + a[len(b):]
    return b


def rebase(cfg, old_base, new_cfg_dir, keys):
    """Pfade in cfg (relativ zu old_base) auf einen neuen Speicherort umrechnen (base = ENTRY)."""
    cfg = dict(cfg)
    for k in keys:
        if isinstance(cfg.get(k), str):
            p = (old_base / cfg[k]).resolve()
            cfg[k] = os.path.relpath(p, ENTRY) if ENTRY in p.parents else str(p)
    cfg["base"] = os.path.relpath(ENTRY, new_cfg_dir)
    return cfg


def run(cmd, what):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        print(p.stdout[-2000:], p.stderr[-3000:])
        sys.exit(f"{what} fehlgeschlagen (Exit {p.returncode})")
    return p.stdout


def load_override(name):
    p = HERE / name
    if p.exists():
        print(f"  Korrekturen aus tools/{name}")
        return json.loads(p.read_text())
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ENTRY / "assets" / "raw"))
    ap.add_argument("--assets", default=str(ENTRY / "assets"))
    ap.add_argument("--demo", default=str(ENTRY / "demo"))
    ap.add_argument("--work", default=str(pathlib.Path(tempfile.gettempdir()) / "kinemagramm" / "process"))
    ap.add_argument("--scene", choices=["auto", "hand"], default=None,
                    help="Masken aus der KI-Maske (auto) oder aus tools/scene.hand.json (hand); Standard: auto, wenn mask.png da ist")
    ap.add_argument("--hand", default=str(HERE / "scene.hand.json"), help="Szene von Hand (Polygone)")
    ap.add_argument("--no-godot", action="store_true")
    a = ap.parse_args()
    raw, assets, demo, work = (pathlib.Path(x).resolve() for x in (a.raw, a.assets, a.demo, a.work))
    work.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    report = {}

    # 1. Szene ----------------------------------------------------------------------------------
    bg, mask, hand = raw / "bg.png", raw / "mask.png", pathlib.Path(a.hand).resolve()
    if not bg.exists():
        print(f"fehlt: {bg} (Bildauftrag 1). Nichts zu tun.")
        return 2
    mode = a.scene or ("auto" if mask.exists() else "hand")
    print(f"Szene: {bg.name}, Masken {'aus KI-Maske ' + mask.name if mode == 'auto' else 'von Hand (' + hand.name + ')'}")
    override = load_override("scene.override.json")
    if mode == "auto":
        if not mask.exists():
            sys.exit(f"fehlt: {mask} (Bildauftrag 3)")
        # crop_y aus den Korrekturen schon beim Ausrichten anwenden (alle Positionen hängen am Ausschnitt)
        cfg, _ = auto_scene.build(bg, mask, assets / "mask_ai.png", ENTRY, work, crop_y=override.get("crop_y"))
        cfg = rebase(cfg, ENTRY, assets, ["src", "ai_labels"])
    elif hand.exists():
        cfg = json.loads(hand.read_text())
        cfg = rebase(cfg, (hand.parent / cfg.get("base", "..")).resolve(), assets, ["src"])
    else:
        draft, _ = auto_scene.build(bg, None, None, ENTRY, work, crop_y=override.get("crop_y"))
        draft = rebase(draft, ENTRY, HERE, ["src"])
        (work / "scene.hand.draft.json").write_text(json.dumps(draft, ensure_ascii=False, indent=1))
        print(f"Keine KI-Maske und keine {hand}.\n"
              f"  Entwurf: {work / 'scene.hand.draft.json'}\n  Raster:  {work / 'scene_overlay.png'}\n"
              f"  sky/water als Polygone [[x, y], ...] in 1280x720, boats als [{{poly, masts, pivot}}] und chimney "
              f"[x, y] nach dem Raster setzen (Felder siehe prep.py) und als "
              f"tools/scene.hand.json speichern, dann erneut aufrufen.")
        return 3
    cfg = merge(cfg, override)
    report["scene_auto"] = cfg.get("_auto", {})
    (assets / "scene_config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1))
    out = run([PY, str(HERE / "prep.py"), str(assets / "scene_config.json"), "--out", str(assets),
               "--debug", str(work / "prep")], "prep.py")
    report["prep"] = json.loads(out.strip().splitlines()[-1])
    print("  prep:", out.strip().splitlines()[-1])

    # 2. Dachs ----------------------------------------------------------------------------------
    braw = raw / "badger.png"
    if braw.exists():
        bcfg = auto_badger.build(braw, ENTRY, work)
        bcfg = rebase(bcfg, ENTRY, assets, ["src"])
        report["badger_auto"] = bcfg.get("_auto", {})
    else:
        print(f"fehlt: {braw} (Bildauftrag 2). Szene ist verarbeitet; Dachs nicht.")
        return 4
    bcfg = merge(bcfg, load_override("badger.override.json"))
    (assets / "badger_config.json").write_text(json.dumps(bcfg, ensure_ascii=False, indent=1))
    out = run([PY, str(HERE / "prep_badger.py"), str(assets / "badger_config.json"), "--out", str(assets),
               "--debug", str(work / "badger")], "prep_badger.py")
    print("  prep_badger:", out.strip().splitlines()[-1])
    report["badger"] = json.loads(out.strip().splitlines()[-1])

    # 3. In die Demo kopieren -------------------------------------------------------------------
    art = demo / "art"
    art.mkdir(parents=True, exist_ok=True)
    for f in DEMO_FILES:
        shutil.copy2(assets / f, art / f)
    print(f"  {len(DEMO_FILES)} Dateien nach {art}")

    # 4. Godot-Probelauf -------------------------------------------------------------------------
    if not a.no_godot:
        imp = subprocess.run(["godot", "--headless", "--path", str(demo), "--import"], capture_output=True, text=True)
        bad = [l for l in (imp.stdout + imp.stderr).splitlines() if "ERROR" in l]
        chk = work / "render_check"
        p = subprocess.run([PY, str(HERE / "render.py"), str(chk), "--frames", "30", "--demo", str(demo)],
                           capture_output=True, text=True)
        print("  Godot:", p.stdout.strip().splitlines()[0] if p.stdout.strip() else p.stderr[-300:])
        bad += [l for l in p.stdout.splitlines()[1:]]
        frames = sorted(chk.glob("f*.png"))
        if frames:
            shutil.copy2(frames[-1], work / "check_frame.png")
        report["godot_errors"] = bad
        if bad or p.returncode:
            print("\n".join(bad[:10]))
            sys.exit("Godot meldet Fehler")
    (work / "process_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print("Ansehen:", ", ".join(str(work / n) for n in ("scene_overlay.png", "badger_overlay.png",
                                                       "prep/masks_overlay.png", "check_frame.png")
                                if (work / n).exists()))
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
