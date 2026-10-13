"""Setzt die Bild-Prompts aus assets/prompts/*.txt zusammen: Platzhalter werden wörtlich aus data/motif.json gefüllt.

    .venv/bin/python styles/fotoreal-standbild/tools/make_prompts.py <Zielordner>

Schreibt <Zielordner>/<name>.prompt.txt für jede Vorlage (Eingabe für genimg.py --prompt-file).
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent
ROOT = HERE.parent.parent


def fill(text, motif):
    sc, ch = motif["scene"], motif["character"]
    return (text.replace("{MOTIF}", sc["block_en"]).replace("{BGONLY}", sc["background_only_en"])
            .replace("{CHARACTER}", ch["block_en"]).replace("{GUARDS}", motif["guards_en"]))


def main():
    out = pathlib.Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    motif = json.loads((ROOT / "data" / "motif.json").read_text())
    for p in sorted((HERE / "assets" / "prompts").glob("*.txt")):
        txt = fill(p.read_text(), motif).strip() + "\n"
        assert "{" not in txt, f"Platzhalter übrig in {p.name}"
        (out / f"{p.stem}.prompt.txt").write_text(txt)
        print(out / f"{p.stem}.prompt.txt", len(txt), "Zeichen")


if __name__ == "__main__":
    main()
