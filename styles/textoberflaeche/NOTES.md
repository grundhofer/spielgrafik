# textoberflaeche – Arbeitsnotizen

## Stand (11.10.2026)

Fertig, `style.json` → `status: "done"`. **Keine Bildaufträge:** `assets/image_jobs.json` ist eine leere Liste.

Warum keine eigenen Bilder:

- **Hintergrund:** Das KI-Hauptbild von painterly-digital (`styles/painterly-digital/assets/raw/master.png`,
  agy) wird nur lesend verwendet. Es ist ruhig, enthält weder gemalten Rauch noch einen Leuchtturmkegel, und
  unten liegt eine Kaimauer ohne Wichtiges, über die das Textpanel passt. Ein eigenes Gemälde würde für diesen
  Technik-Eintrag nichts zeigen, was dieses nicht zeigt.
- **Dachs:** Schnittfigur aus `shared/badger/walk_painted.png` (Bild 3), Gang aus Code. Das Blatt taugt nicht
  als Bildfolge (Standfuß springt zwischen Bild 3 und 4 um 121 px Quellmaß, Bild 1 und 5 sind fast gleich).
- **Icons:** aus Code (`scripts/draw_icons.py`), bei 30 px gut lesbar.

Der erste Bau (abgebrochen) hatte drei Bilder angefordert. Alle sieben agy-Aufrufe scheiterten am Kontingent,
es entstand kein Bild (`image_generations: 0`). Die Prompts von damals liegen in `prompts/` (siehe unten).

## Welche Datei woraus entsteht

| Datei (assets/ und Kopie in demo/art/) | Quelle | Skript |
|---|---|---|
| bg_640.png | painterly-digital raw/master.png (nur lesen), Lanczos auf 640×429 | prep.py |
| badger_body.png, badger_leg.png | shared/badger/walk_painted.png, Bild 3, 56 px | badger_rig.py (über prep.py) |
| badger_preview.png (nur assets/) | Rumpf + Beine in Ruhe, 6-fach | badger_rig.py |
| icons/*.png (64 px) | Code | draw_icons.py (über prep.py) |
| beam.png, glint.png, smoke.png, paper.png | Code, feste Seeds | prep.py |
| demo/art/scene.json | Lagen, Ausschnitte, Laufplan, Rig-Maße | prep.py |

Lagen im 640er-Gemälde (ANCHORS, GLINTS, GULLS, Fußlinie 322) wurden in einem 2-fach vergrößerten Rasterbild
mit 20-px-Gitter von Hand abgelesen. Wer das Gemälde tauscht, muss sie neu messen.

## Neu bauen

```
.venv/bin/python styles/textoberflaeche/scripts/prep.py          # zwei Läufe ergeben bitgleiche Dateien
godot --headless --path styles/textoberflaeche/demo --import
godot --headless --path styles/textoberflaeche/demo --quit-after 5   # keine ERROR-Zeilen
.venv/bin/python tools/capture.py styles/textoberflaeche              # endet mit "ok:"
# Laufen messen (Ausgabeordner im eigenen Temp-Unterordner):
.venv/bin/python styles/textoberflaeche/scripts/grab.py <tmp>/textoberflaeche/mask --mask
.venv/bin/python styles/textoberflaeche/scripts/measure_walk.py <tmp>/textoberflaeche/mask   # Rückgabe 0
# Renderer-Vergleich:
.venv/bin/python styles/textoberflaeche/scripts/grab.py <tmp>/textoberflaeche/mobile --method mobile
.venv/bin/python styles/textoberflaeche/scripts/grab.py <tmp>/textoberflaeche/compat --method gl_compatibility
```

Letzte Messung: Standfuß 149/149 Bildwechsel je Bein auf ±1 px, Sohle stehend konstant (Zeile 229 im Band),
gehend 228/229. mobile bitgleich zu Forward+, gl_compatibility höchstens 2 von 255 Abweichung.

## Optional, falls später Kontingent frei ist (nicht angefordert)

Beides würde den Eintrag verbessern, ist aber nicht nötig. Für jedes wäre Code in `prep.py` nachzurüsten
(die alte Verarbeitung für KI-Blätter wurde entfernt, weil sie ungenutzt war).

1. **Gemaltes Icon-Blatt** (`prompts/icons.txt`, 1024×1024, 3 × 2 Gegenstände, transparenter Grund; bei agy
   Magenta-Freistellung). Verarbeitung: Zusammenhangskomponenten den 6 Zellen zuordnen, Saum entfernen,
   quadratisch zentrieren, vormultipliziert auf 64 px. Ansehen: alle sechs getrennt (keine Schatten, keine
   Kästen), gleicher Maßstab, vor dunkler und heller Fläche keine Magenta-Säume, keine Buchstaben auf Brief,
   Kompass und Karte. Damit die Icons zum Gemälde passen, das Gemälde als Stilreferenz mitgeben und den
   Stilblock auf „weiche digitale Malerei ohne Konturen“ umstellen (der alte Prompt verlangt Tuschekonturen).
2. **Neu gemaltes Laufblatt** (`prompts/walk.txt`, Referenzen `assets/raw/walk_layout_ref.png` aus
   `blender/walk_layout.py`, `shared/badger/walk_painted.png`, `shared/badger/master_sheet.png`). 8 Phasen in
   2 × 4. Ansehen: Beinstellungen müssen der Lagevorlage folgen (sonst wieder Sprünge), Füße auf einer Linie,
   gleicher Maßstab. Danach nach Beinstellung sortieren, Vorschub je Bild aus dem gemessenen Standfuß
   (`raw/walk3d/walk3d.json` hat die Fußpunkte des 3D-Modells je Phase) und mit `measure_walk.py` prüfen.

`prompts/bg.txt` ist der Prompt des nie erzeugten eigenen Gemäldes; er wird nicht mehr gebraucht.
