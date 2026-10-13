#!/usr/bin/env python3
"""Entfernt Sitzungs- und Kontodaten aus den Begleitdateien von genimg.py in assets/raw/.

    .venv/bin/python -B styles/ortsserie/bilderbuch-gouache/scripts/sanitize_raw.py

Warum: Die .gitignore des Projekts schließt nur styles/*/assets/raw/* aus, nicht styles/ortsserie/*/assets/raw/.
Die Begleitdateien hier würden also mit veröffentlicht. genimg.py schreibt hinein: conversation_id (Sitzungs-ID),
agy_account (Kontoname) und in actual_calls[].ImagePaths absolute Pfade mit Benutzernamen.
Das Skript löscht die beiden Felder, macht absolute Pfade relativ zum Projektordner und prüft danach, dass kein
Heimatverzeichnis mehr vorkommt. Prompt, Größe, Backend, Dauer und verbatim bleiben unverändert.
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
RAW = pathlib.Path(__file__).resolve().parents[1] / "assets/raw"
HOME = str(pathlib.Path.home())
DROP = ("conversation_id", "agy_account")


def clean(v):
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items() if k not in DROP}
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, str):
        v = v.replace(str(ROOT) + "/", "")
        return v.replace(HOME, "~")
    return v


def main():
    n = 0
    for p in sorted(RAW.glob("*.json")):
        d = json.loads(p.read_text())
        c = clean(d)
        if c != d:
            p.write_text(json.dumps(c, ensure_ascii=False, indent=1))
            n += 1
        txt = p.read_text()
        if HOME in txt or any(f'"{k}"' in txt for k in DROP):
            sys.exit(f"noch sensibel: {p.name}")
    print(f"ok {n} Dateien bereinigt in {RAW.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
