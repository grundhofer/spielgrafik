#!/usr/bin/env python3
"""Entfernt Sitzungs- und Kontodaten aus den Begleit-JSON der Rohbilder (assets/raw/*.json).

genimg.py schreibt neben jedes agy-Bild conversation_id, agy_account und in actual_calls die absoluten Pfade der
Referenzbilder. Die .gitignore-Regel styles/*/assets/raw/* deckt den verschachtelten Ordner
styles/ortsserie/pc98-adventure/assets/raw/ nicht ab; damit nichts davon veröffentlicht wird, werden diese Felder
gelöscht und absolute Projektpfade durch projektrelative ersetzt. Prompt, Größe, Backend, Dauer, verbatim und
der tatsächlich gesendete Prompt bleiben erhalten.

    .venv/bin/python styles/ortsserie/pc98-adventure/scripts/sanitize_raw.py
"""
import json, pathlib, re

SD = pathlib.Path(__file__).resolve().parent.parent
ROOT = SD.parents[2]
DROP = ("conversation_id", "agy_account")
HOME = re.compile(r"/(Users|home)/[^/\s'\"]+/")


def clean(v):
    if isinstance(v, str):
        return HOME.sub("~/", v.replace(str(ROOT) + "/", ""))
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items() if k not in DROP}
    return v


def main():
    for f in sorted((SD / "assets" / "raw").glob("*.json")):
        d = json.loads(f.read_text())
        c = clean(d)
        if c != d:
            f.write_text(json.dumps(c, ensure_ascii=False, indent=1) + "\n")
            print("bereinigt:", f.name)


if __name__ == "__main__":
    main()
