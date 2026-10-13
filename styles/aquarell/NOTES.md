# Aquarell – Stand und Fertigstellen

## Stand (11.10.2026, nach Prüfung 1: fertig)

- Prüfung 1 (score 3, „fix“): Figur deckende Gouache statt Lasur (major), Papierrand wackelt in den Wasserzeilen,
  Standfuß rutscht bei walk_1 → walk_2, Zwinkern statt Blinzeln (auch in wave_in), Hintergrund zu bunt ohne
  Papierweiß, Füße auf der Unterkante, style.json ungenau. Behoben wie folgt:
  - **Figur:** `tools/reglaze.py` lasiert beide Bögen in Quellauflösung neu (Kostümteile über Farbgruppen, flache
    Lasur + harte Schattenlasur, Papierweiß, Trockenränder, Granulation; Augen/Nase/Mund/Knöpfe aus dem KI-Bild).
    `prep_badger_ai.py` ruft es auf (`--no-reglaze` = alter Stand).
  - **Nachbesserung per genimg.py:** Der abgebrochene Korrekturlauf hat `assets/raw/walk_v2.png` erzeugt (Codex,
    Stilreferenz `assets/ref/wash_style.png` aus `tools/make_style_ref.py`, Auftrag in `assets/fix_jobs.json` von
    `prompts/make_jobs.py`). Kaum flacher, nicht verwendet. Der zweite Auftrag dort (`front_v2`) wurde nicht erzeugt.
    Damit 4 Bilderzeugungen, eine der zwei erlaubten Nachbesserungen verbraucht.
  - **Augen:** `fix_eyes()` in `prep_badger_ai.py`: Blinzeln = Bild „front“ mit den geschlossenen Augen aus dem
    KI-Blinzelbild, Winkbilder mit den offenen Augen aus „front“ (Gesichtsausschnitt per Vorlagenvergleich).
  - **Vorschub:** gemessen in `assets/badger_ai_override.json` (`walk_dx`, Begründung im Kommentar);
    `measure_badger.py` meldet jetzt den Schlupf je Bildwechsel (gleicher Fuß: 0–1 px).
  - **Papierrand:** `demo/shaders/painting.gdshader` tastet Alpha unverschoben ab und verschiebt am Rand nicht
    (Spanne des rechten Rands über die Zeit jetzt ≤ 1 px).
  - **Hintergrund:** `grade()` in `prep_bg_ai.py` (Sättigung 0,78, hellste 3 % als Papierweiß);
    Laufzeile Bildschirm 550 (`feet_y`), Rohbild 770, Figurenhöhe fest 150 px (alles in `bg_ai_override.json`).
- Geprüft: `build_ai.py` ohne Godot-Fehler; Fußlinie in allen 180 Bildern y 549; Renderer mobile bitgleich,
  gl_compatibility mittlere Abweichung 0,23; Aufnahme mit `--poster-at 0.72` (Winken, Vorderansicht);
  `python3 build.py` ohne Meldung für den Eintrag.
- Offen (in `style.json` → `pitfalls`): Hintergrund bleibt detailreich; Schattenformen der Figur wechseln leicht
  von Laufbild zu Laufbild; Kopf rückt an den Doppelstand-Wechseln nur 4 px vor; Halt in Schrittstellung.
- **Nicht aufgeräumt (Löschen wurde in der Sitzung nicht erlaubt):** die Ausgaben des 3D-Rückfallwegs, die die Demo
  nicht mehr nutzt: `assets/bg_3d.png`, `assets/sky_mask_3d.png`, `assets/water_mask_3d.png`,
  `assets/badger_{idle,stop,turn,walk,wave}.png`, `assets/badger_meta.json`, `assets/raw/badger_passes/` (50 MB),
  `assets/raw/bg_passes/`. Sie lassen sich mit `blender/bg_passes.py`, `blender/badger_passes.py`,
  `tools/paint_bg.py` und `tools/paint_badger.py` jederzeit neu erzeugen und können gelöscht werden; die Skripte
  bleiben (`stage.py --bg 3d --badger 3d` braucht dann einen neuen Lauf dieser vier Skripte).

## Welche Datei aus welchem Auftrag entsteht

Aufträge erzeugt `prompts/make_jobs.py` (Motivblock wörtlich aus `data/motif.json`). Alle 1536×1024 angefragt;
Codex lieferte genau das (agy liefert erfahrungsgemäß etwa 1264×848) – die Skripte messen die Größe selbst.

| Auftrag | Rohbild | Referenzen | verarbeitet von | ergibt |
|---|---|---|---|---|
| 1 Hintergrund | `assets/raw/bg.png` | – | `prep_bg_ai.py` | `assets/bg_ai_painted.png`, `sky_mask_ai.png`, `water_mask_ai.png`, `scene_ai.json` → `stage.py`/`finish_bg.py` → `assets/bg.png` → `demo/art/bg.png`, `sky_mask.png`, `water_mask.png` |
| 2 Laufbogen 2×5 | `assets/raw/walk.png` | `assets/ref/walk_layout.png`, Master-Sheet, `raw/bg.png` | `prep_badger_ai.py` | Bilder 1–8 → `assets/badger_ai_walk.png` → `demo/art/badger_walk.png`; Bild 9 (Stehen) und 10 (Dreiviertel) → Anfang von `assets/badger_ai_stand.png` |
| 3 Vorderbogen 2×3 | `assets/raw/front.png` | `assets/ref/front_layout.png`, `raw/walk.png`, Master-Sheet | `prep_badger_ai.py` | Vorderansicht, 3 Winkbilder, Blinzeln, Sprechen → Rest von `assets/badger_ai_stand.png` → `demo/art/badger_stand.png` |

Abhängigkeiten: Auftrag 2 braucht `raw/bg.png`, Auftrag 3 braucht `raw/walk.png` (sonst `ref-missing`, kostet kein
Kontingent). Fehlt ein Teil, nimmt `stage.py` automatisch den Rückfallweg dafür:
- kein `bg.png` → gerechneter Hafen; kein `walk.png` → gerechneter Dachs (auch auf dem KI-Hintergrund, skaliert);
- `walk.png` ohne `front.png` → Dachs läuft, bleibt stehen, dreht sich zu drei Vierteln und atmet (kein Winken).

Ablauf der KI-Figur in der Demo (15 Bilder/s, `stage.py: badger_ai`): 48 Laufbilder (6 Zyklen, endet auf
walk_7) bis 3,2 s, Stehen, Dreiviertel, Vorderansicht, Winken 3,67–4,87 s, Blinzeln bei 5,13 s, dann Sprechen.
Das Poster daher bei 0,72 (4,3 s, mitten im Winken).

## Fertigstellen (Phase 3, so durchgeführt; für neue Bilder wiederholen)

1. Ergebnis der Warteschlange ansehen: `assets/image_jobs.status.json`, je Bild `assets/raw/<name>.json`
   (`backend`, `actual_size`, `verbatim`, `key_transparent_share`) und ggf. `<name>.fail.json`.
2. Alles verarbeiten (ruft kein Bildmodell auf):
   ```
   .venv/bin/python styles/aquarell/tools/build_ai.py
   ```
3. Prüfbilder in `assets/check/` **ansehen** (Hinweise unten):
   `bg_ai_check.png` (Masken: Himmel magenta, Wasser grün; Punkte mit Quelle „automatisch/Korrektur/GERATEN“;
   rote Linie = Laufzeile y 572, blaue = Horizont, roter Kasten = Dachsgröße am Haltepunkt),
   `bg_ai_grid.png` (Rohbild mit Gitter in Rohbild-Pixeln), `badger_ai_frames.png` (alle Bilder auf Papier und
   dunkel, rote Linie = Fußlinie, blaue = Anker), `badger_ai_feet.png` (Laufbilder mit Vorschub übereinander:
   der stehende Fuß muss jeweils deckungsgleich bleiben).
4. Bei Fehlern `assets/bg_ai_override.json` anlegen (alle Felder optional, Koordinaten in Rohbild-Pixeln aus
   `bg_ai_grid.png`) und Schritt 2 wiederholen:
   ```json
   {"lamp": [x, y], "lantern": [x, y], "window": [x, y], "chimney": [x, y], "horizon": y,
    "walk_y": y, "top_y": y, "water_seed": [[x, y]], "water_y": [y0, y1],
    "inpaint": [[[x, y], [x, y], [x, y]]], "sky_exclude": [[[x, y], [x, y], [x, y]]],
    "badger_height": 150, "stop_x": 560, "window_glow_scale": 0.7, "lantern_glow_scale": 0.5}
   ```
   `walk_y` = Fußzeile des Dachses im Rohbild (Standard 88,5 % der Höhe), `top_y` = oberste Zeile, die sichtbar
   bleiben muss (Standard: Lampe minus 7,5 %), `badger_height`/`stop_x` in Bildschirm-px (Standard: Höhe aus der
   Perspektive 0,69 × (Fußzeile − Horizont), begrenzt auf 120–200; Halt bei x 560). `inpaint` übermalt Polygone mit
   der Umgebung (z. B. mitgemalter Rauch oder Lichtstrahl); das Polygon über dem Schornstein enden lassen.
   Für die Figur: `prep_badger_ai.py --whole` nimmt die Vorderbilder ganz statt aus Teilen (wenn die Teilmasken
   Nähte zeigen); `--rim 0` schaltet den zusätzlichen Trockenrand ab.
5. Aufnahme und Sichtprüfung nach PIPELINE.md:
   ```
   .venv/bin/python tools/capture.py styles/aquarell --poster-at 0.72
   ```
   `media/frames.jpg` und `media/poster.png` ansehen. `measure_badger.py` lief in Schritt 2 mit (Ausgabe dort,
   Daten in `assets/check/badger_measure.json`): Fußlinie konstant, Ferse in Standphasen ±1–2 px.
6. Renderer-Probe wiederholen (nur wenn Shader geändert wurden; sonst gilt die Prüfung oben):
   `godot --path styles/aquarell/demo --rendering-method mobile --write-movie <tmp>/f.png --fixed-fps 30 --quit-after 136`
   (ebenso `gl_compatibility` und `forward_plus`), Bilder 30/90/135 vergleichen.
7. `.venv/bin/python tools/collect_prompts.py aquarell`, dann `style.json` ergänzen: `status` (done/partial),
   `ratings.ai_fit` und `consistency` mit Begründung, `pipeline` (Backend, `verbatim`, gelieferte Größe,
   Korrekturen), `assets` (KI-Dateien mit `prompt`: `assets/raw/bg.json` usw.), `image_generations`, `pitfalls`
   und `verdict` nach dem, was die Bilder zeigen; Merkmale in `traits` gegen das Poster prüfen. Danach
   `python3 build.py`.
8. Höchstens zwei Nachbesserungen direkt mit genimg.py (endet sofort, wenn agy gesperrt ist), z. B.:
   ```
   .venv/bin/python styles/aquarell/prompts/make_jobs.py      # Prompts ggf. vorher dort ändern
   .venv/bin/python tools/genimg.py --jobs <tmp>/one_job.json  # einzelner Auftrag mit neuem out-Namen
   ```
   Neues Rohbild unter neuem Namen ablegen und mit `--raw`/`--walk`/`--front` an die Skripte geben oder das alte
   ersetzen. Jede Erzeugung zählt (Kontingent höchstens 10 je Eintrag).

## Worauf beim Ansehen der Bilder achten

Hintergrund (`raw/bg.png`):
- Echtes Aquarell (Lasuren, Trockenränder, Papierweiß, Körnung) statt 3D-Render, Foto oder Postkarten-Kitsch?
  Das ist die eigentliche Frage des Eintrags (`ai_fit`).
- Trotz Verbot mitgemalt: Rauch über dem Schornstein (bei ligne-claire und vga-adventure passiert),
  Lichtstrahl oder großer Schein an der Lampe, große Wolken, Möwen → mit `inpaint` übermalen bzw. hinnehmen und in
  `pitfalls` nennen (Rauch wird animiert, Wolken ziehen zusätzlich).
- Komposition: Hütte links, Leuchtturm bei etwa drei Vierteln, Laterne etwas rechts der Mitte, unteres Fünftel
  freies Pflaster. Wenn nicht: Punkte und `walk_y` per Korrekturdatei setzen. Liegt der Kai nur als schmale Kante
  vor einer Mauer (wie bei painterly-digital), läuft der Dachs auf der Kante – dann `walk_y` dorthin.
- Lampe samt Dach im Bild? Sonst `top_y` setzen (der Maßstab sinkt dann bis 80 %, seitlich bleibt Papier).
- Der Lichtschein der Laterne ist ein heller Fleck (`lift.gdshader`); auf dunklen Stellen kann er wie ein gelber
  Klecks wirken. Dann `lantern_glow_scale` (bzw. `window_glow_scale`) in der Korrekturdatei kleiner setzen oder die
  Deckkraft in `main.gd` senken.

Laufbogen (`raw/walk.png`):
- Zehn Figuren, Posen wie im Layout (Bild 1–8 Laufzyklus, 9 Stehen, 10 Dreiviertel), gleicher Maßstab,
  Füße auf einer Linie. `badger_ai_frames.png`: Fußlinie bei allen Bildern auf der roten Linie.
- Freistellung: kein Magenta-Saum (dunkle und helle Fläche im Prüfbild), keine Löcher, kein Magenta in hellem
  Fell oder Hemd (transparente Lasur über Magenta wäre ein Fehler des Bildmodells). `key_transparent_share` in
  der .json; bei `key-failed` liegt der Versuch als `walk.keyfail.png` daneben.
- Farben: Mütze und Weste klar dunkelgrün (nicht oliv), Schal rot, Gesichtsstreifen lesbar.
- Stil passt zum Hintergrund (gleiche Lasurtechnik, keine Konturlinien)? Sonst `consistency` niedriger.
- `prep_badger_ai.py` meldet „Vorschub weicht stark vom Layout ab“, „Figurenhöhen schwanken“ oder „berührende
  Figuren geteilt“ → Bogen und `badger_ai_feet.png` genau ansehen.

Vorderbogen (`raw/front.png`):
- Sechs Figuren; Körper, Gesicht und Kostüm in allen gleich; Bild 5 mit geschlossenen Augen, Bild 6 mit offenem
  Mund. Die Ausgabe meldet je Teil den übertragenen Anteil: Winken etwa 25–35 %, Blinzeln/Sprechen unter 2 %.
  „keine Änderung gefunden“ heißt: das Modell hat Augen/Mund nicht geändert, das Bild wird übersprungen.
- Nähte an den Teilmasken (Armansatz, Kopf)? Dann `--whole` probieren und das Flimmern des Körpers vergleichen.
- Gleicher Maßstab wie der Laufbogen? (Beide Bögen werden getrennt auf die Zielhöhe gebracht; ein anders
  proportioniertes Modell fällt beim Übergang Dreiviertel → Vorderansicht auf.)
