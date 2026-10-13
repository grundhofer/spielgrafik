#!/usr/bin/env python3
"""Setzt die Bild-Prompts aus den Bausteinen in assets/prompts/ und data/motif.json (wörtlich) zusammen.

    .venv/bin/python styles/lebendes-portraet/tools/make_jobs.py            # schreibt assets/prompts/*.prompt.txt
                                                                             # und assets/jobs_*.json
Reihenfolge: portrait (Grundlage), danach faces (Bearbeitung von portrait) und bg (Stilreferenz portrait).
"""
import json, pathlib

HERE = pathlib.Path(__file__).resolve().parent.parent
ROOT = HERE.parent.parent
P = HERE / "assets" / "prompts"
motif = json.loads((ROOT / "data" / "motif.json").read_text())
REL = HERE.relative_to(ROOT).as_posix()


def part(name):
    return (P / name).read_text().strip()


char, scene, guards = motif["character"]["block_en"], motif["scene"]["block_en"], motif["guards_en"]
bg_only = motif["scene"]["background_only_en"]

prompts = {
    "portrait": "\n".join([part("style_portrait.txt"), part("portrait_body.txt"), char, part("portrait_ref.txt"),
                           guards, "Image format: square 1:1."]),
    "faces": "\n".join([part("faces_edit.txt"), part("style_portrait.txt"), char,
                        "The character stays isolated on a fully transparent background (alpha channel).",
                        guards, "Image format: square 1:1."]),
    "bg": "\n".join([part("bg_body.txt"), scene, bg_only, guards, "Image format: landscape 3:2."]),
}
for k, v in prompts.items():
    (P / f"{k}.prompt.txt").write_text(v + "\n")

raw = f"{REL}/assets/raw"
jobs1 = [{"out": f"{raw}/portrait.png", "size": "1024x1024", "prompt": prompts["portrait"],
          "refs": [f"{REL}/assets/ref/badger_bust.png", "shared/badger/master_sheet.png"]}]
jobs2 = [{"out": f"{raw}/faces.png", "size": "1024x1024", "prompt": prompts["faces"],
          "refs": [f"{raw}/portrait.png", "shared/badger/master_sheet.png"], "ref_note": ""},
         {"out": f"{raw}/bg.png", "size": "1536x1024", "prompt": prompts["bg"],
          "refs": [f"{raw}/portrait.png"], "ref_note": ""}]
(HERE / "assets" / "jobs_1.json").write_text(json.dumps(jobs1, indent=1, ensure_ascii=False))
(HERE / "assets" / "jobs_2.json").write_text(json.dumps(jobs2, indent=1, ensure_ascii=False))
for k, v in prompts.items():
    print(f"--- {k} ({len(v)} Zeichen)")
