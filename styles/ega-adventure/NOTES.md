# ega-adventure – Stand

Stand 11.10.2026, Phase 3 von 3 abgeschlossen, danach Nachbesserung nach der unabhängigen Prüfung (Fässer, Pfahl,
Prioritätsebene, Streupixel). Status in `style.json`: `done`.

## Was die Demo zeigt

Das Hafenbild ist ein **KI-Bild mit Nacharbeit** (`demo/art/harbor_ai.pic.json`, aktiv über `demo/art/scene.json`).
Das von Hand geschriebene Bild aus Phase 1 (`demo/art/harbor.pic.json`) bleibt als Vergleich und Rückfall;
`{"picture": "harbor.pic.json"}` in `scene.json` schaltet zurück. Vergleich aller Fassungen: `assets/ai_compare.png`.

| Fassung | Datei | Befehle | Urteil |
|---|---|---|---|
| Handbild | `assets/harbor.pic.json` | 370 | sauber, aber karg |
| nur Farbbild | `assets/ai_bg_flat.pic.json` | 975 | Masten, Fugen, Sterne fehlen |
| Flächen aus der Strichvorlage | `assets/ai_bg_flat_lines.pic.json` | 1244 | Boote, Steg, Fässer werden Klumpen (verworfen) |
| Strichvorlage als Detailhinweis | `assets/ai_bg_flat_detail.pic.json` | 1609 | gut bis auf Steg, Boote, Kisten, Fässer, Pfahl |
| dasselbe + Handnacharbeit | `assets/ai_bg_flat_touchup.pic.json` | 1486 | **in der Demo** |

## Bilder

Beide Bilder kamen über die zentrale Warteschlange von **Codex** (gpt-image), nicht über agy; je ein Versuch,
`image_generations: 2`. Es gibt daher keine `*.keyed-src.png` und kein `verbatim`-Feld.

- `assets/raw/bg_flat.png`: Hafen in flachen EGA-Farben (mittlerer Oklab-Abstand zur Palette 0,064).
- `assets/raw/bg_lines.png`: dieselbe Komposition als Strichvorlage (74 % Deckung mit den Farbkanten).

## Neu bauen

```
.venv/bin/python styles/ega-adventure/scripts/process_raw.py [--capture]
.venv/bin/python styles/ega-adventure/scripts/check_pic.py styles/ega-adventure/demo/art/harbor_ai.pic.json
.venv/bin/python styles/ega-adventure/scripts/probe_badger.py
.venv/bin/python tools/capture.py styles/ega-adventure --poster-at 0.82
```

`process_raw.py` liest `scripts/ai_settings.json` (Schlüssel unter `_doc` erklärt):

- Ausschnitt ab 6 % der Höhe, 24 Farbgruppen, `min_area` 5, zwei Brauntöne über die Mittelfarbe auf Schwarz
  (`cluster_map` mit `#rrggbb`; Gruppennummern ändern sich mit dem Ausschnitt).
- Strichvorlage als Detailhinweis (`ai_convert.detail_from_lines`, Schwelle 25 %).
- Handnacharbeit `scripts/ai_touchup.py` (139 Zeichenoperationen: Steg, Boote, Pfosten, Taue, Kisten, Tauring,
  Poller, Spiegelungen, Wellenstriche; seit der Prüfung auch Laternenpfahl und beide Fässer über die
  Zeichenfunktionen `lamp_pole` und `barrel`, Lage in `POLE`/`BARRELS`, sowie Weiß/Hellcyan auf dem Kai ->
  Pflaster). Sie arbeitet auf dem Indexbild vor dem Vektorisieren und wird bei jedem Lauf neu angewendet.
- Lage von Hand für `ai_bg_flat_detail` und `ai_bg_flat_touchup`: Fußlinie 152, Laternenglas
  [116, 83, 120, 93], Schornstein [12, 21], bei der Demo-Fassung Start x=132 (ganz hinter dem linken Fass).
  Leuchtfeuer, Kaikante, Wasser, Glitzer, Möwenhöhe und Prioritätsflächen kommen automatisch
  (`ai_layout.priority`: über der Kaikante zählen nur Wasser und Himmel ohne Schwarz/Dunkelgrau als Hintergrund,
  bis 4 Zeilen über die Mütze; nebeneinanderliegende Teile nur bei gleichem Band zusammengefasst).

## Messwerte (11.10.2026)

- Godot-Wiedergabe bitgleich zur Python-Wiedergabe (KI-Bild und Handbild), Bild steht nach 47 Bildern.
- Dachs: Standfuß 24× gehalten, 0× gesprungen, 6× verdeckt (Fass, Pfahl); Fußzeile 152, Kopfzeile 123/122.
- Verdeckung (`probe_badger.py`): Silhouetten von Pfahl und Fässern 958 Pixel, 0 ohne Band 14, 0 Band-14-Pixel
  außerhalb; 0 Dachspixel in einer Silhouette; Bild 53–61 ganz hinter dem linken Fass, sichtbar nur Zeilen 122–129.
- Forward+ zweimal bitgleich; Mobile und gl_compatibility in RGB bitgleich (0 von 180 Bildern).
- Rechenzeit 0,43 ms je Bild beim Aufbau (höchstens 0,61 ms), 0,11 ms danach (Fenster; headless 0,38–0,41/0,07–0,08).
- capture.py: 0 Godot-Fehler, 0 Warnungen (`godot_warnings` in `media/capture.json`).
- Änderungen an `main.gd` in Phase 3 (Laterne flackert nur auf gelben Glaspixeln, Möwenhöhe aus `layout.gull_y`):
  Das Handbild läuft damit bitgleich wie vorher (0 von 180 Bildern abweichend).

## Offen

- Takelage, Steg, Fässer und Pfahl ließen sich nicht automatisch umwandeln; für weitere Räume ist mit ähnlicher
  Nacharbeit an allen dichten Vordergrundgegenständen zu rechnen.
- Die KI-Bilder haben schwarze Konturen um jeden Gegenstand. Ein Prompt ohne Konturen („no black outlines, shapes
  separated only by colour“) könnte die Umwandlung verbessern; nicht getestet.
