#!/usr/bin/env python3
"""Schreibt styles/ortsserie/prompts.json aus den Begleitdateien der drei Teilordner.

    .venv/bin/python -I styles/ortsserie/scripts/collect_prompts_serie.py

tools/collect_prompts.py liest nur styles/<slug>/assets/raw/. Die Ortsserie hat ihre Rohbilder je Stil in
styles/ortsserie/<stil>/assets/raw/ (drei Agenten, je eigene Skripte); styles/ortsserie/assets/raw/ gibt es nicht, also
lässt tools/collect_prompts.py den Eintrag unverändert. Dieses Skript nutzt dieselbe Funktion collect() je Teilordner
und setzt den Teilordner vor den Dateinamen ("bilderbuch-gouache/assets/raw/stube.png"), damit die Prompt-Verweise in
style.json → assets[].prompt passen. Sortiert wie das Werkzeug nach Erzeugungszeit. Ohne Begleitdateien (frischer
Klon) bleibt prompts.json unverändert.
"""
import importlib.util, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
E = HERE.parent
ROOT = E.parents[1]
PARTS = ["bilderbuch-gouache", "painterly-digital", "pc98-adventure"]

spec = importlib.util.spec_from_file_location("collect_prompts_tool", ROOT / "tools" / "collect_prompts.py")
CP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CP)


def main():
    timed = []
    for part in PARTS:
        raw = E / part / "assets" / "raw"
        items = CP.collect(E / part, ROOT)
        if not items:
            print(f"  {part}: keine Begleitdateien", file=sys.stderr)
            continue
        # collect() sortiert schon; für die gemeinsame Reihenfolge die Erzeugungszeit erneut lesen
        for it in items:
            side = (E / part / it["file"]).with_suffix(".json")
            at = str(json.loads(side.read_text(encoding="utf-8")).get("generated_at") or "") if side.exists() else ""
            it["file"] = f"{part}/{it['file']}"
            timed.append((at, it["file"], it))
        print(f"  {part}: {len(items)} Prompts aus {raw.relative_to(ROOT)}")
    if not timed:
        print("keine Begleitdateien gefunden – prompts.json bleibt unverändert")
        return 0
    timed.sort(key=lambda x: (x[0], x[1]))
    text = json.dumps([it for _, _, it in timed], ensure_ascii=False, indent=1) + "\n"
    target = E / "prompts.json"
    old = target.read_text(encoding="utf-8") if target.exists() else None
    if old == text:
        print("unverändert")
        return 0
    target.write_text(text, encoding="utf-8")
    print(f"{len(timed)} Prompts -> {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
