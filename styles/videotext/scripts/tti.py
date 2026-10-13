#!/usr/bin/env python3
"""Seite als TTI-Datei (Textformat der Videotext-Einspeiser und -Editoren) schreiben und zurücklesen.

    .venv/bin/python styles/videotext/scripts/tti.py        # schreibt assets/hafen.tti aus demo/data/stream.json

Zeilen: DE (Beschreibung), PN (Magazin+Seite+Unterseite), SC, PS, OL,<zeile>,<inhalt>, FL (Fastext-Links:
rot, grün, gelb, cyan, Index). Steuerzeichen 0x00–0x1F stehen als ESC (0x1B) + (Code + 0x40), wie im MRG-Format
üblich. Zeile 0 (Kopfzeile) schreibt der Einspeiser selbst und fehlt deshalb.
Nur mit dem eigenen Leser geprüft, nicht in einem externen Editor.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ttxlib as T  # noqa: E402

ESC = "\x1b"


def write(page, path, page_no="100", links=("201", "202", "203", "100", "8FF", "100")):
    lines = ["DE,Hafen von Lornholm (Spielgrafik-Katalog, Eintrag videotext)",
             f"PN,{page_no}00", "SC,0000", "PS,8000"]
    for r in range(1, T.ROWS):
        s = "".join(ESC + chr(b + 0x40) if b < 0x20 else chr(b) for b in page[r])
        lines.append(f"OL,{r},{s}")
    lines.append("FL," + ",".join(links))
    pathlib.Path(path).write_bytes(("\r\n".join(lines) + "\r\n").encode("latin-1"))


def read(path):
    page = T.blank_page()
    for line in pathlib.Path(path).read_bytes().decode("latin-1").split("\r\n"):
        if not line.startswith("OL,"):
            continue
        _, r, s = line.split(",", 2)
        row, i = [], 0
        while i < len(s):
            if s[i] == ESC:
                row.append(ord(s[i + 1]) - 0x40)
                i += 2
            else:
                row.append(ord(s[i]))
                i += 1
        page[int(r)] = (row + [0x20] * 40)[:40]
    return page


def main():
    st = json.load(open(T.HERE / "demo" / "data" / "stream.json"))
    page = T.page_from_hex(st["base"])
    out = T.HERE / "assets" / "hafen.tti"
    write(page, out)
    back = read(out)
    same = all(back[r] == page[r] for r in range(1, T.ROWS))
    print(f"{out.name}: {out.stat().st_size} Bytes, Zeilen 1–24 zurückgelesen {'gleich' if same else 'VERSCHIEDEN'}")
    if not same:
        sys.exit(1)


if __name__ == "__main__":
    main()
