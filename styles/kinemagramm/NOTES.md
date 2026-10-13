# kinemagramm – Arbeitsstand

Stand 11.10.2026, fertig (Phase 3 von 3, PIPELINE.md → „Bildaufträge“), danach Nachbesserung nach unabhängiger
Prüfung (Rauch, Glitzern, Himmel, Möwen, Blinzeln, Kai-Lichtschein, Takelage, Textfeld, Dachsgröße; keine neuen
KI-Bilder). Status in `style.json`: `done`.
Alle drei Bildaufträge kamen über Codex (gpt-image) im ersten Versuch; `media/` ist mit den eigenen Bildern
aufgenommen. Keine Platzhalterdaten mehr in `demo/art/` oder `tools/`.

## Was da ist

- **Rohbilder** (`assets/raw/`, nicht im Git): `bg.png` (Gemälde), `badger.png` (gemalter Dachs, echter
  Alphakanal), `mask.png` (KI-Farbcode-Maske), je mit `.json` (Prompt, Backend `codex`). `bg.agylog.json` ist das
  Protokoll der gescheiterten agy-Versuche vom 10.10.2026 (kein Bild).
- **Verarbeitung** (`tools/`), ein Aufruf: `process.py` → `assets/` und Kopie nach `demo/art/`.
  Korrekturen von Hand stehen nur in `tools/scene.override.json` (Textfeld, Rauchpunkt auf dem rechten Aufsatz,
  Lichtschein der Laterne auf dem Kai als `floor_pools`, Tönung des Dachses) und `tools/badger.override.json`
  (Schalende als Polygon, Schalachse, Figurenhöhe 198, `despill: false` für Codex-Alpha).
- **Godot-Demo** (`demo/`): `still.gdshader` (alle Hintergrundebenen; Rauch als Kette von Ballen, Himmel pendelt),
  `badger.gdshader` (Atmen, Gewicht, Schal quer zur Achse `tail_root` → `tail_tip`, Lider, Kantenlicht),
  `panel.gdshader` (Textfeld). Schalter nach `--`: `--frozen`, `--no-badger`, `--no-shadow`, `--no-ui`, `--t0=SEKUNDEN`.
- **Prüfwerkzeuge**: `measure_fx.py` (Bewegung je Maskenbereich, Sprünge > 20 Stufen), `measure_badger.py` (Füße/Kopf
  je Bild), `measure_sky.py` (feinste Himmelsstruktur gegen das Gemälde zu beliebigen Zeitpunkten),
  `selftest.py` (verschiebt/skaliert die echte Maske als JPEG wie agy und prüft die Wiederfindung),
  `compare_masks.py` (KI- gegen Handmaske, braucht eine `scene.hand.json`), `render.py` (Aufnahme in beliebigen
  Ordner, auch `--method mobile|gl_compatibility`).

## Neu bauen

Temporäre Dateien nur in `<Scratchpad>/kinemagramm/`.

```
.venv/bin/python styles/kinemagramm/tools/process.py --work <Scratchpad>/kinemagramm/process
.venv/bin/python styles/kinemagramm/tools/measure_fx.py <Scratchpad>/kinemagramm/fx
.venv/bin/python styles/kinemagramm/tools/measure_badger.py <Scratchpad>/kinemagramm/mb
.venv/bin/python styles/kinemagramm/tools/measure_sky.py <Scratchpad>/kinemagramm/sky
.venv/bin/python styles/kinemagramm/tools/selftest.py --work <Scratchpad>/kinemagramm/selftest
.venv/bin/python tools/capture.py styles/kinemagramm
```

Kontrollbilder im Arbeitsordner: `scene_overlay.png` (Raster, Lichter, Schornstein, Drehpunkte, Dachsplatz,
Textfeld), `prep/masks_overlay.png`, `badger_overlay.png` (Raster in Quellpixeln für Polygone), `check_frame.png`.
`crop_y` in `scene.override.json` wirkt schon beim Ausrichten (alle Positionen hängen am Ausschnitt).

## Weiterer Ort mit derselben Technik

1. Gemälde und Farbcode-Maske mit `assets/prompts/bg.txt` und `mask.txt` erzeugen (Motivblock tauschen; Maske mit
   dem Gemälde als Referenz). Mit gpt-image passte die Maske ohne Verschiebung; bei agy richtet `aimask.align` aus.
2. `process.py` laufen lassen, Kontrollbilder ansehen, Textfeld und Dachsplatz in `scene.override.json` setzen.
3. Ohne Maske (Exit 3): Entwurf `scene.hand.draft.json` + `scene_overlay.png`; `sky`/`water` als Polygone in
   1280×720, `boats` als `[{poly, masts, pivot}]`, `chimney` als Punkt, Felder siehe `prep.py`.

## Ergebnis der Messungen (11.10.2026, nach der Nachbesserung)

- Ausrichtung der echten KI-Maske: unverändert (sx 1,0, sy 0,996, dx 0, dy 0). Selbsttest mit verschobener
  JPEG-Maske: IoU Himmel 0,999, Wasser 0,993, Boote 0,96/0,98 (mit Takelage), Ausrichtung ≤ 1,9 px.
- measure_fx: Wasser 27 %, Himmel 27 %, Boote 75 %, Fenster 68 %, Laterne samt Kai 100 %, Strahlzone 52 %,
  Rauchzone 7 % sichtbar bewegt; Sprünge > 20 Stufen je Bild im fernen Wasserband 0,06 % (vorher ~5 %);
  ruhiger Rest 1,8 % (Ränder des Kai-Lichtscheins). Kai-Lichtfleck 250–420 × 570–640: Spannweite 24 Stufen.
- Glitzern (Vergleich mit/ohne): 1,6 % der Wasserpixel, nur auf Helligkeit ≥ 0,33 (Wasser-Median 0,27).
- measure_sky: feinste Himmelsstruktur 0,93–1,05 des Gemäldes (alte Fassung mit Wabern 0,86).
- measure_badger: Fußzeile 656 in allen 180 Bildern, Fußspalten 486/569 (±0), Kopf 457–460, Höhe 196–199,
  Sprung ≤ 1 px.
- Langzeit: Blinzeln ab t = 100 s bei 101,9 / 102,2 / 106,6 / 112,0 / 117,2 s (Vergleich mit Kopie ohne
  Blinzeln); Möwen kehren nach dem Bildrand wieder (Lagen bis 3600 s ausgegeben).
- Renderer: mobile identisch, gl_compatibility höchstens 2 Stufen Abweichung zu Forward+ (sin-freier Hash).

## Bekannte Grenzen

- Himmel pendelt (±24 px, 80 s) statt endlos zu ziehen; Umkehr alle 40 s, langsam.
- Rauchballen sind in voller Bildgröße weich und nur mäßig ausgeprägt; kein Volumenrauch.
- Nur 12 Sternpixel (das Gemälde hat kaum Sterne, die meisten liegen im weggeschnittenen oberen Rand).
- Der Dachs ist niedlicher und heller gemalt als die Szene; Tönung im Shader gleicht das aus. Er läuft nicht und
  ist mit 196–199 px bewusst etwas über Maßstab.
- Zwischen Mast und Wanten von Boot 2 liegt etwas Wasser in der KI-Bootsmaske und steht still.
