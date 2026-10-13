#!/usr/bin/env python3
"""Füllt die Prompt-Vorlagen aus assets/prompts/ und schreibt Auftragsdateien für tools/genimg.py --jobs.

    .venv/bin/python styles/tageszeit-wetter/tools/make_jobs.py bg            # nur das Grundbild
    .venv/bin/python styles/tageszeit-wetter/tools/make_jobs.py mask depth    # Folgeaufträge mit bg als Referenz

Platzhalter werden wörtlich aus data/motif.json gefüllt:
  {MOTIF} scene.block_en   {BACKGROUND_ONLY} scene.background_only_en   {CHARACTER} character.block_en
  {GUARDS} guards_en
Ausgabe: $TW_TMP oder <System-Temp>/tageszeit-wetter/jobs_<namen>.json (Pfad wird ausgegeben).
"""
import json, os, pathlib, re, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
ROOT = ENTRY.parents[1]
REL = ENTRY.relative_to(ROOT).as_posix()
TMP = pathlib.Path(os.environ.get("TW_TMP", pathlib.Path(tempfile.gettempdir()) / "tageszeit-wetter"))

BG = f"{REL}/assets/raw/bg.png"
# Name: (Vorlage, Größe, Referenzen, ref_note)
JOBS = {
    "bg": ("bg.txt", "1536x1024", [], None),
    "mask": ("mask.txt", "1536x1024", [BG], ""),
    "depth": ("depth.txt", "1536x1024", [BG], ""),
    "snow": ("snow.txt", "1536x1024", [BG], None),
    "night": ("night.txt", "1536x1024", [BG], None),
}
FORBIDDEN = re.compile(r"in the style of|\bstudio\b|ghibli|disney|pixar|lucasarts|sierra", re.I)


def build(name):
    tpl, size, refs, note = JOBS[name]
    motif = json.loads((ROOT / "data" / "motif.json").read_text())
    fill = {"{MOTIF}": motif["scene"]["block_en"], "{BACKGROUND_ONLY}": motif["scene"]["background_only_en"],
            "{CHARACTER}": motif["character"]["block_en"], "{GUARDS}": motif["guards_en"]}
    text = (ENTRY / "assets" / "prompts" / tpl).read_text().strip()
    for k, v in fill.items():
        text = text.replace(k, v)
    left = re.findall(r"\{[A-Z_]+\}", text)
    if left:
        sys.exit(f"{tpl}: Platzhalter nicht gefüllt: {left}")
    if FORBIDDEN.search(text):
        sys.exit(f"{tpl}: verbotene Formulierung: {FORBIDDEN.search(text).group(0)!r}")
    for r in refs:
        if not (ROOT / r).exists():
            sys.exit(f"{tpl}: Referenz fehlt: {r}")
    job = {"out": f"{REL}/assets/raw/{name}.png", "size": size, "prompt": text}
    if refs:
        job["refs"] = refs
    if note is not None:
        job["ref_note"] = note
    return job


def main():
    names = sys.argv[1:] or ["bg"]
    jobs = [build(n) for n in names]
    TMP.mkdir(parents=True, exist_ok=True)
    dst = TMP / f"jobs_{'_'.join(names)}.json"
    dst.write_text(json.dumps(jobs, ensure_ascii=False, indent=1) + "\n")
    for j in jobs:
        print(j["out"], len(j["prompt"]), "Zeichen")
    print(dst)


if __name__ == "__main__":
    main()
