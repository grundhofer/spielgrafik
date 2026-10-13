#!/usr/bin/env python3
"""Schreibt assets/image_jobs.json (Format von tools/genimg.py --jobs) aus den Vorlagen in assets/prompts/.

    .venv/bin/python styles/kinemagramm/tools/make_jobs.py [--check]

Die Vorlagen enthalten Platzhalter, die hier wörtlich aus data/motif.json gefüllt werden, damit Motiv-,
Figuren- und Schutzblock nie von Hand abgeschrieben werden:
  {MOTIF} scene.block_en   {BACKGROUND_ONLY} scene.background_only_en   {CHARACTER} character.block_en
  {GUARDS} guards_en
Reihenfolge = Priorität (das wichtigste Bild zuerst). Pfade relativ zum Projektordner.
--check vergleicht nur mit der vorhandenen Datei (Exit 1 bei Abweichung).
"""
import argparse, json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
ROOT = ENTRY.parents[1]
REL = ENTRY.relative_to(ROOT).as_posix()

# (Vorlage, Ziel, Größe, Referenzen) – Reihenfolge ist die Priorität
JOBS = [
    ("bg.txt", "bg.png", "1536x1024", []),
    ("badger.txt", "badger.png", "1024x1536", [f"{REL}/assets/ref/badger_front.png", f"{REL}/assets/raw/bg.png"]),
    ("mask.txt", "mask.png", "1536x1024", [f"{REL}/assets/raw/bg.png"]),
]
FORBIDDEN = re.compile(r"in the style of|\bstudio\b|ghibli|disney|pixar|lucasarts|sierra", re.I)


def build():
    motif = json.loads((ROOT / "data" / "motif.json").read_text())
    fill = {"{MOTIF}": motif["scene"]["block_en"], "{BACKGROUND_ONLY}": motif["scene"]["background_only_en"],
            "{CHARACTER}": motif["character"]["block_en"], "{GUARDS}": motif["guards_en"]}
    jobs = []
    for tpl, out, size, refs in JOBS:
        text = (ENTRY / "assets" / "prompts" / tpl).read_text().strip()
        for k, v in fill.items():
            text = text.replace(k, v)
        left = re.findall(r"\{[A-Z_]+\}", text)
        if left:
            sys.exit(f"{tpl}: Platzhalter nicht gefüllt: {left}")
        if FORBIDDEN.search(text):
            sys.exit(f"{tpl}: verbotene Formulierung: {FORBIDDEN.search(text).group(0)!r}")
        for r in refs:
            if not r.startswith(f"{REL}/assets/raw/") and not (ROOT / r).exists():
                sys.exit(f"{tpl}: Referenz fehlt: {r}")
        job = {"out": f"{REL}/assets/raw/{out}", "size": size, "prompt": text}
        if refs:
            job["refs"] = refs
        jobs.append(job)
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    jobs = build()
    text = json.dumps(jobs, ensure_ascii=False, indent=1) + "\n"
    dst = ENTRY / "assets" / "image_jobs.json"
    if a.check:
        same = dst.exists() and dst.read_text() == text
        print("image_jobs.json aktuell" if same else "image_jobs.json weicht von den Vorlagen ab")
        return 0 if same else 1
    dst.write_text(text)
    for j in jobs:
        print(f"{j['out']}  {j['size']}  {len(j['prompt'])} Zeichen  refs={j.get('refs', [])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
