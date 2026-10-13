# hintergrund-serie: Stand und Nachbau

Stand 11.10.2026, Phase 3 abgeschlossen. `style.json` steht auf `done`; Ergebnisse, Messwerte und Grenzen stehen
dort (`pipeline`, `pitfalls`, `ratings_note`). Diese Datei sagt nur, wie man den Eintrag nachbaut oder ändert.

## Bilder

Fünf Aufträge aus `assets/image_jobs.json`, zentral von `tools/imagequeue.py` erzeugt, alle über **Codex**
(gpt-image), je ein Versuch, alle 1536×1024 (`assets/raw/<name>.json` → `backend`, `actual_size`). Keine
Nachbesserung mit `genimg.py`. Der Laufzyklus kam mit echtem Alphakanal, ohne Magenta.

| Rohbild | Referenzen | wird zu |
|---|---|---|
| `hafen.png` | keine (Stilanker) | `bg_hafen.png`, Ankerpalette, Identitäts-LUT |
| `leuchtturm.png` | `raw/hafen.png` | `bg_leuchtturm.png`, `lut/lut_leuchtturm.png` |
| `stube.png` | `raw/hafen.png` | `bg_stube.png`, `lut/lut_stube.png` |
| `klippe.png` | `raw/hafen.png` | `bg_klippe.png`, `lut/lut_klippe.png` |
| `walk.png` | `raw/walk_layout_ref.png`, `raw/hafen.png`, `shared/badger/master_sheet.png` | `walk.png`, `walk.json` |

## Nachbau (aus dem Projektordner, Python mit `-I`)

1. `.venv/bin/python -I styles/hintergrund-serie/tools/prep.py all` – Effekte, Textbox, Schnitt, LUTs, Berichte
   (`drift.json`, `lut_compare.png`, `series_sheet.png`, `palette_anchor.png`), Laufzyklus. Endet mit
   „keine Platzhalter in demo/art“. Zwei Läufe ergeben bitgleiche Dateien.
2. `godot --headless --path styles/hintergrund-serie/demo --import`
3. `.venv/bin/python -I styles/hintergrund-serie/tools/measure_walk.py` → `assets/walk_measure.json`
4. `.venv/bin/python -I styles/hintergrund-serie/tools/render_check.py` → `assets/render_check.*`
5. `.venv/bin/python tools/capture.py styles/hintergrund-serie --poster-at 0.3` (Poster bei 1,8 s: Dachs steht
   im Hafen)
6. `python3 tools/collect_prompts.py hintergrund-serie`, dann `python3 build.py`

Temporäre Ausgaben der Skripte landen in `$TMPDIR/hintergrund-serie/`.

## Stellschrauben (nach Sichtung der Codex-Bilder gesetzt)

- `tools/prep.py` `CROP_TOP`: Schnitt je Ort, sodass der Horizont überall auf Bildschirmzeile 256 liegt
  (gemessene Horizonte im Rohbild: Hafen 39,6 %, Klippe 37,3 %, Leuchtturmfenster 40,5 %, Stubenfenster 35,8 %).
- `tools/prep.py` `LUT_PARAMS`: unverändert aus Phase 1 (L 50 %, a/b 60 %, Palettenzug 50 %).
- `tools/prep.py` `BADGER_H = 140`, `WALK_ORDER = [0, 1, 2, 3]` (Kontakt, Abheben, Durchgang, Ausholen; mit
  Bild 4 oder 5 rutscht der Körper zurück), `WALK_STAND` (Stehbild aus Bild 2: erhobenes Bein ab, Standbein
  versetzt als fernes Bein). Der Magenta-Saumabzug läuft nur bei Schlüsselfarben-Bildern (agy).
- `demo/locations.gd`: Lagen aller Effekte in Bildschirmpixeln, Dachs auf der Kaimauer (`feet_y` 492,
  `stop_x` 520, `walk_time` 1,7 s, Dämmerungstönung). Im Hafen kein Rauch (Schornsteinkrone über dem Bildrand),
  Flammen in der Stube additiv.
- Vergleich ohne Farbabgleich: `.venv/bin/python -I styles/hintergrund-serie/tools/peek.py <tmp>/nolut.png 1.0 2.8 4.3 5.6 -- --no-lut`.
- `tools/lights.py` schlägt Lichtquellen vor; Laterne und Fenster im Hafen findet es nicht (Laterne verschmilzt
  mit dem Horizontband, Fenster zu dunkel), dort von Hand messen.
