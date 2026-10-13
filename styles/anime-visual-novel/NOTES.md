# anime-visual-novel – Arbeitsstand

Stand 11.10.2026, Phase 3 abgeschlossen, danach Mängel aus der unabhängigen Prüfung behoben (nahe Möwe, Kantenlicht,
Lippen-Haltezeiten, harte Mimikwechsel, Pseudo-Schrift auf dem Boot, Alpha 0/255, Lage von Auswahl/Ortskarte/Rauch,
Poster). `style.json` steht auf `done`.

## Was fertig ist

- **Bilder:** alle drei Aufträge aus `assets/image_jobs.json` über `tools/imagequeue.py` erzeugt, alle über
  **Codex (gpt-image)**, nicht über agy wie in Phase 1 erwartet: 1536×1024, echter Alphakanal, keine
  `*.keyed-src.png`. Je ein Versuch, keine Nachbesserung mit genimg.py (image_generations = 3).
- **Verarbeitung:** `tools/prep.py` (ohne `--test`) hat `assets/badger_*.png` (6 Fassungen), `assets/bg.png`,
  `assets/sprite_report.json` und `demo/art/` geschrieben; `demo/art/TESTBILDER.txt` ist entfernt, `sprite.json`
  und `layout.json` haben `"test_images": false`.
- **Abweichungen von den Messungen** stehen in `tools/prep_config.json` (auf diese Bilder abgestimmt):
  - `sprite.regions`: Rechtecke für Augen und Mund (A0-Koordinaten). Die automatische Trennzeile fand die
    Mützenkante, weil die Codex-Bearbeitung alle Konturen leicht neu zeichnet; die Ellipsen schnitten die offenen
    Münder ab. Mit `regions` gilt für jede Quelle die Differenzmaske nur in diesen Rechtecken (neu in prep.py,
    `region_parts`), Flecken unter `min_part` fallen weg. sprite.json bekommt die Bereiche als `regions`, und
    `tools/measure.py` erlaubt Änderungen in Kopf + Bereichen.
  - `bg.lights` (Fenster, Laterne, Schornstein), `bg.window_r` und `bg.stars` (Liste statt Anzahl, neu in
    prep.py): die Messung landete auf hellen Wolkenrändern bzw. Dach und Wolken.
  - `bg.choices`: Auswahlfelder rechts neben der Figur (x 884, y 338, w 352, h 46, Abstand 44).
  - `bg.retouch`: Rechtecke im Rohbild, die senkrecht überblendet werden (Namensschild mit Pseudo-Schrift auf dem
    blauen Boot).
- **Alpha:** prep.py setzt geliefertes Alpha ≥ 250 auf 255 und ≤ 2 auf 0 (Codex liefert den Körper mit 250–254).
- **Geprüft:** `measure.py` Rückgabe 0 (151 Ruhebilder ohne Abweichung, alle Mimikwechsel in
  [508, 170, 703, 327], nichts außerhalb von Kopf + Bereichen mit 3 px Rand; 25 Haltezeiten der Gesichtszustände,
  keine unter 3 Bildern); `capture.py --poster-at 0.85` endet mit `ok:` ohne Warnungen;
  `renderers.py --at 3.2`: Mobile pixelgleich, Compatibility mittlere Abweichung 0,09 (max 2);
  `collect_prompts.py` → `prompts.json`; `python3 build.py` ohne Datenfehler.
- **Probelauf mit Testbildern** (siehe unten) braucht jetzt eine eigene, leere Konfiguration, weil
  `tools/prep_config.json` auf die echten Bilder abgestimmt ist: `--config <Temp>/leer.json` mit `{}`.

## Welche Datei aus welchem Auftrag

| Auftrag | Ziel (`assets/raw/`) | Inhalt | daraus |
|---|---|---|---|
| 1 | `sheet.png` | Dachs zweimal, gleiche Pose; links neutral (A0), rechts freudig (A1) | A0 = Körper aller Fassungen und `badger_neutral.png`; A1-Gesicht → `badger_happy.png`; A1-Augen + A0-Mund → `badger_happy_closed.png` |
| 2 | `bg.png` | Anime-Hintergrund 3:2 | `assets/bg.png`, `demo/art/bg.png`, `demo/art/layout.json` |
| 3 | `faces.png` | Bearbeitung von Auftrag 1, gleiches Layout; links Augen zu + Mund offen (B0), rechts überrascht (B1) | B0-Augen → `badger_blink.png`, B0-Mund → `badger_talk.png`, B1-Gesicht → `badger_surprised.png` |

Auftrag 3 nahm `sheet.png` als Vorlage (ursprünglich `sheet.keyed-src.png`, die es nur auf dem agy-Weg gibt;
`tools/make_jobs.py` ist angepasst und erzeugt wieder genau die gelaufene `image_jobs.json`).

## Fertigstellen (Phase 3) – so wurde es gemacht, für neue Bilder wiederholen

Alle Befehle aus dem Projektordner.

1. `assets/image_jobs.status.json` und die Begleitdateien `assets/raw/*.json` lesen: `backend`,
   `actual_size` (agy liefert meist 1264×848), `verbatim`, `key_transparent_share` (Blatt ≈ 0,4–0,6).
   `*.fail.json` / `*.keyfail.png` beachten.
2. Rohbilder ansehen (bei agy `*.keyed-src.png`, bei Codex `sheet.png`/`faces.png` vor grauer Fläche, dazu `bg.png`),
   siehe „Worauf achten“.
3. `.venv/bin/python styles/anime-visual-novel/tools/prep.py` (ohne `--test`). Schreibt `assets/badger_*.png`,
   `assets/bg.png`, `assets/sprite_report.json`, Kopien nach `demo/art/`, `sprite.json`, `layout.json`,
   entfernt `TESTBILDER.txt` und veraltete Fassungen.
4. Prüfbilder in `assets/raw/debug/` ansehen:
   - `sprite_debug.png`: Köpfe A0/A1/B0/B1, alle Fassungen, Masken rot, Gesichtsfeld türkis, Trennlinie
     Augen/Mund gelb. Masken „B0 eyes“ und „B0 mouth“ müssen eng um Augen bzw. Mund liegen.
   - `sprite_full.jpg`: neutrale Figur vor hell/dunkel und Kopfkante doppelt vergrößert (Magenta-Saum?).
   - `bg_marks.jpg`: Lampe, Fenster, Laterne, Schornstein (nur geschätzt!), Horizont (gelb), Glitzerstellen
     (weiße Kreise, nur auf Wasser), Sterne (rosa), Figur (rotes Rechteck), Textfenster-Oberkante.
5. Abweichungen in `tools/prep_config.json` eintragen (gleiche Struktur wie `DEFAULTS` in prep.py, nur die
   geänderten Werte) und Schritt 3 wiederholen, z. B.:
   ```json
   {"bg": {"lights": {"chimney": [96, 210], "lantern": [262, 330]}, "crop_y": 30},
    "sprite": {"split_y": 410, "center_x": 600, "top_y": 72, "display_h": 760}}
   ```
   - Figur zu klein/groß oder Kopf von der Ortskarte verdeckt: `display_h`, `center_x`, `top_y`. Über
     `max_upscale` (1,05) wird nicht vergrößert; liegt die Figurenhöhe im Blatt unter `display_h`, wird sie
     kleiner gezeigt (Warnung in der Ausgabe).
   - Gesichtsfeld oder Trennlinie falsch gemessen: `face_box` bzw. `split_y` (Koordinaten im Prüfbild + Rand;
     Werte stehen in `assets/sprite_report.json` → `geometry`).
   - Freudig/überrascht passen nicht auf den neutralen Körper (Nähte am Ellipsenrand, verschobene Augen,
     anderer Kopfwinkel): Fassungen mit eigenem Körper, z. B.
     `"variants": {"neutral": {"body": "A0", "layers": []}, "blink": {"body": "A0", "layers": [["B0", "eyes"]]},
     "talk": {"body": "A0", "layers": [["B0", "mouth"]]}, "happy": {"body": "A1", "layers": []},
     "happy_closed": {"body": "A1", "layers": [["A0", "mouth"]]}, "surprised": {"body": "A1", "layers": [["B1", "face"]]}}`
     (getestet). Dann wechselt beim Mimikwechsel der Körper mit; measure.py meldet das als Abweichung, und
     das gehört in `pitfalls`.
6. `godot --headless --path styles/anime-visual-novel/demo --import`, dann
   `.venv/bin/python styles/anime-visual-novel/tools/measure.py` (muss mit Rückgabe 0 enden; schreibt
   `media/measure.json`).
7. `.venv/bin/python tools/capture.py styles/anime-visual-novel --poster-at 0.85` (t ≈ 5,1 s: neutrale offene
   Augen, drei Auswahlfelder, Strahl nach rechts, vor dem Blinzeln bei 5,22 s). `media/frames.jpg` und
   `poster.png` ansehen, dazu die Einzelbilder 88–105 aus `demo.mp4` (Möwe über dem Kopf, Gesicht frei).
8. `.venv/bin/python styles/anime-visual-novel/tools/renderers.py --at 3.2` → Abweichungen für `mobile`.
9. `.venv/bin/python tools/collect_prompts.py anime-visual-novel`.
10. `style.json`: `status` done/partial, `summary` ohne „wartet“, Pipeline-Schritte „geplant“ durch das
    Tatsächliche ersetzen (Backend, `verbatim`, gelieferte Größe), `assets` um `assets/bg.png` und
    `assets/badger_*.png` mit `prompt` (`assets/raw/sheet.json`, `bg.json`, `faces.json`) ergänzen, Bewertungen
    und `ratings_note`, `verdict`, `image_generations` (3 + Nachbesserungen), `pitfalls`/`lessons` prüfen.
11. `python3 build.py` (keine Datenfehler).

Nachbesserungen: höchstens zwei direkt mit genimg.py (`--prompt-file assets/prompts/<name>.txt`, Referenzen
wie in `image_jobs.json`, `--force` oder das alte Bild vorher umbenennen). Erst das wichtigste Problem
beheben: ein unbrauchbares Blatt (Auftrag 1) macht auch Auftrag 3 wertlos, dann müssen beide neu (= zwei
Nachbesserungen). Ist agy gesperrt, mit dem Vorhandenen fertigstellen und es in `pitfalls` sagen.

## Worauf beim Ansehen der Bilder achten

**Blatt (Auftrag 1)**
- Genau zwei Figuren, Vorderansicht, gleiche Pose und gleiche Kopfhaltung, deutliche Lücke dazwischen
  (prep.py teilt an der Lücke; ohne Lücke steht „WARNUNG: keine Lücke“ in der Ausgabe). Kein
  Dreiansichten-Blatt, keine Beschriftung.
- Anime-Look statt Bilderbuch: dünne gleichmäßige Kontur, Cel-Shading mit harten Schattenformen, große
  glänzende Augen, keine Felltextur. Kein 3D-Render-Look (Gemini neigt dazu).
- Kostüm vollständig: dunkelgrüne Schirmmütze mit Messingknopf, grüne Weste, cremefarbenes Hemd mit
  aufgekrempelten Ärmeln, langer roter Schal, braune Umhängetasche, Paket unter dem Arm (links im Bild).
- Links neutral mit kleinem geschlossenem Lächeln, rechts Lachen mit Bogenaugen.
- Magenta flach, kein Boden, kein Schatten; Rosa der Wangen nicht magentastichig.
- Ausgabe von prep.py: `A1 -> A0` Maßstab nahe 1 (±2 %), Restfehler deutlich unter 0,1 (Testbilder: 0,05).

**Hintergrund (Auftrag 2)**
- Gemalter Anime-Hintergrund, kein Foto, kein 3D; großer Abendhimmel mit plastischen Wolken und warmem
  Kantenlicht.
- Aufbau: Häuschen am linken Rand, Laterne bei etwa 20 % der Breite, Mitte frei (dort steht die Figur, Sprite
  etwa x 350–850), Leuchtturm bei etwa 84 %, Lampe ohne Strahl, kein Rauch, keine Vögel, keine Figuren.
- agy hielt Lagevorgaben in anderen Einträgen nur grob ein: in `bg_marks.jpg` prüfen, ob Laterne und Fenster
  sichtbar neben der Figur liegen; sonst `center_x` der Figur verschieben.
- Mitgemalter Rauch oder Strahl würde doppelt zu den Godot-Effekten stehen; dann `pitfalls`.

**Bearbeitung (Auftrag 3)**
- Gleiches Layout wie das Blatt (prep.py: `B0 -> A0` Maßstab ≈ 1, kleiner Versatz). Die Codex-Bearbeitung kam mit
  Maßstab 0,996, Versatz 1,7/2,4 px und Restfehler 0,10 (alle Konturen leicht neu gezeichnet); mit `regions` in
  `tools/prep_config.json` reicht das, ohne `regions` findet die Trennzeile die Mützenkante.
- Links: Augen als Bogenlinien geschlossen und auf dem dunklen Streifen sichtbar, Mund offen. Ohne `regions`
  muss die gelbe Trennlinie in `sprite_debug.png` zwischen Augen und Mund liegen (Ausgabe „split_from:
  Zeilenlücke“); mit `regions` zeigt das Prüfbild türkis die Rechtecke und rot die Masken je Quelle.
- Rechts: runde, weit offene Augen, hochgezogene Brauen, kleiner runder Mund.
- Hat das Modell Wangenröte oder Brauen mitgeändert, werden die Masken größer; Blinzeln dann im Prüfbild auf
  Flimmern um die Augen prüfen.

## Ablauf der Demo (6 s, 30 fps)

| Zeit | Ereignis |
|---|---|
| 0,0–0,4 s | Figur blendet ein und gleitet 36 px nach rechts; Ortskarte wischt herein |
| 0,5–1,44 s | Satz 1 wird getippt, Mund neutral ↔ talk in 3-Bilder-Phasen (Bild 15 + 3n) |
| 1,50 s | Blinzeln (3 Bilder) |
| 1,76–2,85 s | Satz 2, ab 1,80 s freudig (hart) mit Hüpfer, Mund happy ↔ happy_closed |
| 3,0–3,5 s | Nahe Möwe fliegt von rechts unten über den Kopf nach links oben; 3,40 s Schreck (hart), Hüpfer, Schreck-Striche |
| 4,2–4,44 s | Drei Auswahlfelder gleiten herein; 4,5 s zurück zu neutral (hart) |
| 5,0 s | Auswahl 2 hervorgehoben; 5,22 s Blinzeln |

Alle Mimikwechsel liegen auf dem 3-Bilder-Raster der Lippen; main.gd rundet die Zeit dafür auf das aktuelle Bild.

## Werkzeuge im Eintragsordner

| Datei | Zweck |
|---|---|
| `tools/make_refs.py` | Layoutbild `assets/ref_pair.png` |
| `tools/make_jobs.py` | Prompts und `assets/image_jobs.json` |
| `tools/prep.py` | Rohbilder → Fassungen, Hintergrund, `sprite.json`, `layout.json`, Prüfbilder; `--test`, `--raw`, `--config` |
| `tools/make_testinputs.py` | Testbilder (nur in einen Temp-Ordner, nie nach `assets/raw/`) |
| `tools/fx.py` | Effekt-Texturen aus Code (auch `gull_near.png`, die nahe Möwe) |
| `tools/measure.py` | Figur in der laufenden Demo messen, auch Haltezeiten der Gesichtszustände (`--out` für Probeläufe) |
| `tools/renderers.py` | Renderer-Vergleich (`--out` für Probeläufe) |

Probelauf mit Testbildern:

```
T=<Temp>/anime-visual-novel/raw_test
.venv/bin/python styles/anime-visual-novel/tools/make_testinputs.py --out $T
echo '{}' > $T/../leer.json
.venv/bin/python styles/anime-visual-novel/tools/prep.py --raw $T --test --config $T/../leer.json
```

Danach `demo/art/` wieder mit den echten Bildern füllen: `.venv/bin/python styles/anime-visual-novel/tools/prep.py`
(ohne `--test`, entfernt `TESTBILDER.txt`), `godot --headless --path styles/anime-visual-novel/demo --import`.
