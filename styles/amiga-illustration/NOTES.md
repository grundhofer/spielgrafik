# amiga-illustration – Stand

Stand 11.10.2026, fertig (Phase 3 nach PIPELINE.md → „Bildaufträge“). `style.json` steht auf `done`.

## Was in der Demo steckt

- Hafenbild: `assets/raw/bg.png` (gpt-image über Codex, Auftrag 1 der Warteschlange, 1 Versuch) → 320×144, 32 Register.
- Nahaufnahme: `assets/raw/closeup.png` (gpt-image über Codex, Auftrag 2, Referenzen Hafenbild + Referenzblatt,
  1 Versuch) → eigene 32 Register, zieht sich ab 3,85 s über das Hafenbild (Palettenwechsel an der Kante).
- Dachs in der Totale: Blender-BOBs (`blender/render_badger.py`, Renderings in `assets/raw/badger3d/`), in der
  Hafenpalette, Haltepunkt x 108 neben der Laterne. Seit der Nachbesserung (11.10. mittags, nach der Prüfung)
  `scripts/badger_paint.py`: festes Kopfteil je Ansicht mit von Hand gesetztem Gesicht (`SIDE_FACE`, `FRONT_FACE`),
  Tonleitern aus Figuren- und Bildregistern mit Bayer-Dithering, Paket mit Schnur, Kontur nur rechts/unten,
  Kontaktschatten als eigenes Blitter-Objekt (`demo/scripts/shadow.gd`, Breite je Bild in `badger.json` → `feet`).
- Nachbesserung außerdem: Palette aus 10 k-means-Starts (kleinster Fehler), Grün der Kostüme mit festem Farbton
  (`HUE` in `build_assets.py`, Nahaufnahme über `green_poly`), rotes Turmband per `paint` in `ai_layout.json`,
  Boote als Polygone in `water_exclude`, Unschärfemaske der Nahaufnahme 0,3, Leuchtfeuer-Versatz 1,6 s
  (`LAMP_OFFSET` in `main.gd`, Blitz bei 4,6 und 5,2 s in der Nahaufnahme).
- Ablauf in 6 s: Bild wird herabgezogen (0,1–0,95 s), Dachs läuft ein und bleibt stehen (bis 3,2 s), Eingabe
  „nimm paket“ (ab 2,25 s), Eingabetaste bei 3,6 s, Nahaufnahme ab 3,85 s (fertig bei 4,6 s). Poster bei 5,1 s
  (`--poster-at 0.85`).
- Geprüft: 14–29 Farben je Bildstück, Textschirm 4 Farben, 0 Pixel außerhalb des 12-Bit-Rasters; Fußzeile des Dachses
  in allen Bildern nach dem Herabziehen gleich, Standfuß je Schritt über 3 Zeichnungen ortsfest; Forward+ zweimal
  bitgleich, Mobile und Compatibility 0 abweichende Pixel.

## Abweichungen vom Plan aus Phase 1

- Die Bilder kamen von Codex (gpt-image), nicht von agy: 1536×1024 exakt, RGB. Die Skripte messen Größe und Format
  selbst; Annahmen über agy (Freistellen, `*.keyed-src.png`) gibt es in den Skripten nicht.
- Ausschnitt: Der Schornstein liegt bei 10 % der Höhe (Prompt: 22 %), deshalb `crop_y` 16 statt 34 (Pflaster nur
  14 Zeilen, Rauch mit wenig Platz: `smoke.gd` steigt langsamer und treibt nach rechts). Nahaufnahme `crop_y` 22,
  damit die Mütze ganz im Bild ist.
- Die automatische Erkennung fand Leuchtfeuer (1 px), Laterne (2 px) und Wasser (nur oben links) nicht ausreichend;
  Lichter und Wasser stehen jetzt von Hand in `assets/ai_layout.json` und `assets/closeup_layout.json`.
- Rauchregister heller gewählt (`smoke_regs`: +0,22/+0,12 statt +0,17/+0,09 in Oklab L), sonst rosa vor dem
  tiefblauen Himmel.
- Aufgeräumt: Blender-Rückfallbild `assets/raw/bg3d/`, `assets/raw/layout_ref.png`, `prompts/badger.txt`,
  `prompts/jobs1.json`, `prompts/jobs1.log` (erster, abgebrochener Versuch). `blender/render_bg.py` und
  `build_assets.py --source blender` bleiben als Rückfallweg; vor Gebrauch `render_bg.py` neu ausführen.

## Neues Bild einbauen (z. B. weiterer Ort)

1. Prompt nach dem Muster in `prompts/make_jobs.py` (Lagen in Prozent, keine Pixel-Art, keine Effekte mitmalen).
2. `.venv/bin/python styles/amiga-illustration/scripts/grid_preview.py <tmp>/grid.png --full --zoom 3` ansehen,
   `crop_y` festlegen (Band 144 von 213 Zeilen), dann mit `--crop-y N --zoom 4` Koordinaten ablesen.
3. Layout-Datei schreiben (Schlüssel im Kopf von `scripts/load_ai.py`): `crop_y`, `lamp`/`lantern`/`window` als
   Rechtecke mit `*_lmin` 0,7, `water_poly` und `water_exclude` (Boote, Pfähle als Polygone entlang der Umrisse),
   `feet_y`/`stop_x`, bei Bedarf `paint` (kleine Farbflächen, die die Quantisierung verliert) und `green_poly`.
4. `.venv/bin/python styles/amiga-illustration/scripts/finish.py <tmp>/check` – Prüfbilder
   `assets/raw/*_preview_x3.png`, `*_masks_x3.png` und `<tmp>/check/probe_*.png` ansehen; mit `--capture` aufnehmen.
5. `scripts/compare_renderers.py`, `tools/collect_prompts.py`, `python3 build.py`.

## Dateien

- `scripts/amiga.py` – 12-Bit-Raster, Oklab, k-means, Muster-Dithering mit Farbpaaren
- `scripts/load_ai.py` – KI-Bild verkleinern, ausschneiden, Masken und Lagen (Korrektur per Layout-Datei)
- `scripts/build_assets.py` – Palette, Dithering, Wellenstriche, Lichter, Dachs-Blatt; `--picture closeup`
- `scripts/badger_cells.py` – materialtreue Verkleinerung der Dachs-Renderings
- `scripts/badger_paint.py` – Dachs in der Malweise des Bildes (Kopfteil, Gesicht, Dithering, Paket, Kontur)
- `scripts/finish.py` – alles bauen, importieren, prüfen, optional aufnehmen
- `scripts/probe.py` – Farben je Bildstück, 12-Bit-Raster, Fußzeilen; `scripts/compare_renderers.py`
- `scripts/grid_preview.py` – Raster-Hilfsbild zum Ablesen von Koordinaten für die Layout-Dateien
- `scripts/ai_badger.py` – Zerlegung eines KI-Sprite-Blatts (nur Vergleich, nicht in der Demo)
- `demo/scripts/main.gd` (Ablauf, Paletten), `text_screen.gd`, `smoke.gd`, `gull.gd`, `shadow.gd`,
  `demo/shaders/indexed.gdshader`
