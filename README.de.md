[Read in English → README.md](README.md)

# Spielgrafik

**Eine Szene, viele Spielgrafiken.**

Ein Katalog mit 84 Spielgrafik-Stilen und Techniken (66 Stile, 18 Techniken), von 1-Bit-Pixel-Art über
Heimcomputer-Grafik, Aquarell und Holzschnitt bis zum PS1-Look und Cel-Shading. Jeder Eintrag zeigt dieselbe
Szene: den Hafen von Lornholm in der Abenddämmerung, über den der Dachs-Kurier läuft. Alles ist selbst erzeugt,
mit KI-Bildern, Code, Blender und Godot, und jeder Eintrag läuft als kurze Godot-Demo, mit Aufnahme, Bewertungen,
den Prompts seiner KI-Bilder und einer ehrlichen Beschreibung, was funktioniert hat und was nicht.

**[Katalog öffnen](https://grundhofer.github.io/spielgrafik/)**

## Worum es geht

Der Katalog dient der Stilwahl für unser Spielprojekt; das erste Spiel wird ein Textadventure. Weil jeder Eintrag
dieselbe Szene zeigt, lassen sich Stile direkt vergleichen. Jeder Eintrag fragt: Können wir diesen Stil selbst und
wiederholbar erzeugen, aus KI-Bildern, Skripten und einer Spiel-Engine?

- **Katalog:** alle Einträge mit Demo-Video, filterbar nach Familie und Art.
- **Vergleich:** fünf Bewertungen je Eintrag (Eignung fürs Textadventure, KI-Beitrag, Konsistenz, Aufwand,
  geschätzte Mobiltauglichkeit), sortierbar.
- **Techniken:** Bausteine wie Animation, Licht, Kacheln und Oberflächen und welche Stile sie verwenden.
- **Textadventure:** die Einträge als Rangliste nach ihrer Eignung für unser erstes Spiel.
- **Werkzeuge:** Werkzeugkette, gemeinsame Szene und Figur, Ehrlichkeitsregeln und Lizenzhinweise.

## Projektaufbau

| Pfad | Inhalt |
| --- | --- |
| `styles/<slug>/` | Ein Eintrag: `style.json` (Steckbrief), `assets/` (verarbeitete Assets), `demo/` (eigenständiges Godot-4.7-Projekt), `scripts/` und `blender/` (Bauskripte), `media/` (Aufnahme), `prompts.json` (Prompts der KI-Bilder) |
| `styles/<slug>/assets/raw/` | Rohbilder der Bilderzeugung; eingecheckt sind nur die, die ein Eintrag zeigt |
| `shared/badger/` | Referenzblatt des Dachs-Kuriers |
| `shared/3d/` | Gemeinsame 3D-Grundlage: Hafenszene und geriggter Dachs als glTF, gebaut von Blender-Skripten, dazu eine Godot-Probeszene ([README](shared/3d/README.md)) |
| `data/catalog.json` | Familien und alle Einträge mit ihrem Auftrag |
| `data/motif.json` | Die gemeinsame Szene und Figur, mit den englischen Prompt-Blöcken |
| `data/legal.json` | Angaben für das Impressum, nur dort gespeichert |
| `tools/` | Bilderzeugung (`genimg.py`, `imagequeue.py`), Sprite-Verarbeitung (`sprites.py`), Aufnahme (`capture.py`), Prompts sammeln (`collect_prompts.py`) |
| [`PIPELINE.md`](PIPELINE.md) | Bauanleitung für einen Eintrag: Verzeichnis, Werkzeuge, Bilderzeugung, Godot, Blender, Selbstprüfung, Schema von `style.json` |
| `site/`, `build.py` | Seitenstil, Seitenskript, Schriften und statischer Generator |
| `tests/` | Tests für `build.py` und `tools/collect_prompts.py` mit kleinen Testdaten |
| `docs/` | Erzeugte Website; nicht eingecheckt |

## Bauen und testen

Der Seitengenerator braucht Python 3.12+ und nur die Standardbibliothek. Ist `cwebp` (oder unter macOS `sips`)
installiert, bekommen große Bilder eine kleinere WebP-Fassung.

```sh
python3 build.py
python3 -m http.server 8000 --directory docs
python3 -m unittest discover -s tests -v      # oder: python3 -m pytest -q
```

GitHub Actions baut die Website aus dem Repository, führt die Tests aus und veröffentlicht `main` auf GitHub Pages.

## Einen Eintrag bauen

[PIPELINE.md](PIPELINE.md) ist der Vertrag für jeden Eintrag. Die Werkzeuge brauchen mehr als der Seitengenerator:

- `tools/sprites.py` und `tools/capture.py`: Python mit Pillow und NumPy; `capture.py` zusätzlich Godot 4.7 und
  ffmpeg. `genimg.py` ruft `sprites.py` auf, wenn es einen Hintergrund freistellen muss.
- `tools/genimg.py`: ein angemeldetes [Codex CLI](https://github.com/openai/codex) (gpt-image) oder Antigravity CLI
  (Gemini-Bildmodell). Neben jedes Bild schreibt es eine JSON-Datei mit dem Prompt; `tools/collect_prompts.py`
  macht daraus das eingecheckte `prompts.json`.
- 3D-Einträge: Blender 5.2 LTS, ohne Oberfläche per Skript.

```sh
python3 tools/genimg.py --out styles/<slug>/assets/raw/bg.png --size 1536x1024 \
  --prompt-file p.txt --ref shared/badger/master_sheet.png
python3 tools/sprites.py pixelize in.png out.png --width 320 --palette ega
godot --headless --path styles/<slug>/demo --import
python3 tools/capture.py styles/<slug>
python3 tools/collect_prompts.py && python3 build.py
```

## Kennzeichnung und Lizenz

Die KI-Bilder entstehen mit gpt-image (OpenAI) über Codex CLI oder mit dem Gemini-Bildmodell (Google) über
Antigravity CLI und sind auf der Website als solche gekennzeichnet.
Code: [MIT](LICENSE). Texte: [CC BY 4.0](LICENSE-CONTENT.md). Bilder, Videos und 3D-Modelle:
[CC0](LICENSE-CONTENT.md). Prompts: frei verwendbar.
Code und Daten Dritter: [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) und die Lizenzliste des jeweiligen
Eintrags. Schriften: Inter und IBM Plex Mono auf der Website, die Schriften der Demos im Ordner `fonts/` des
Eintrags, alle unter ihrer eigenen Lizenz (SIL Open Font License 1.1 oder CC0); die Website liefert ihre Schriften
selbst aus und lädt nichts von Google Fonts.
Die Angaben des Impressums in `data/legal.json` stehen unter keiner dieser Lizenzen.
Namen von Spielen, Konsolen und Studios beschreiben einen historischen Stil; sie gehören ihren Inhabern, und
dieses Projekt steht in keiner Verbindung zu ihnen.

Schwesterprojekt: [Bildsprache](https://github.com/grundhofer/bildsprache), Bildstile für KI-Bilder nach Anwendung.

© Sebastian Grundhöfer
