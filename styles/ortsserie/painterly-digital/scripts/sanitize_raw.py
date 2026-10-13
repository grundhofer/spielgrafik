#!/usr/bin/env python3
"""Entfernt Sitzungs- und Kontodaten aus den genimg-Begleitdateien in assets/raw/ (werden veröffentlicht).

    .venv/bin/python -I styles/ortsserie/painterly-digital/scripts/sanitize_raw.py

Hintergrund: Das .gitignore-Muster styles/*/assets/raw/* deckt styles/ortsserie/<stil>/assets/raw/ nicht ab;
die .json neben den Rohbildern würden mit conversation_id, agy_account und absoluten Pfaden (ImagePaths in
actual_calls) eingecheckt. Entfernt conversation_id und agy_account, macht absolute Pfade projektrelativ.
Alles andere (Prompt, Größe, Sekunden, Backend, verbatim, backend_choice) bleibt. Mehrfach ausführbar.
"""
import json, pathlib

HERE = pathlib.Path(__file__).resolve().parent
E = HERE.parent
ROOT = E.parents[2]
DROP = ("conversation_id", "agy_account")


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items() if k not in DROP}
    if isinstance(x, list):
        return [clean(v) for v in x]
    if isinstance(x, str) and x.startswith("/"):
        p = pathlib.Path(x)
        try:
            return p.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return "<außerhalb des Projekts>/" + p.name
    return x


def main():
    for f in sorted((E / "assets" / "raw").glob("*.json")):
        d = json.loads(f.read_text())
        c = clean(d)
        if c != d:
            f.write_text(json.dumps(c, ensure_ascii=False, indent=1) + "\n")
            print("bereinigt:", f.relative_to(ROOT))


if __name__ == "__main__":
    main()
