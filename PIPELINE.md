# Bauanleitung für einen Katalogeintrag

Diese Datei ist der Vertrag für jeden, der einen Stil oder eine Technik für den Katalog baut (Mensch oder Agent).
Ziel des Katalogs: herausfinden, welche Spielgrafik-Stile wir **selbst und wiederholbar** erzeugen können, mit
KI-Bildern, Code, Blender und Godot. Jeder Eintrag zeigt dieselbe Szene (`data/motif.json`: der Hafen von
Lornholm in der Abenddämmerung mit dem Dachs-Kurier), damit sich Stile direkt vergleichen lassen.

Ein Eintrag ist erst fertig, wenn eine **laufende Godot-Demo** existiert, die Aufnahme sauber ist und
`style.json` ehrlich beschreibt, was funktioniert hat und was nicht.

## Verzeichnis je Eintrag

```
styles/<slug>/
  style.json        Steckbrief (Schema unten) – Pflicht
  assets/raw/       Rohbilder aus genimg.py samt .json mit Prompt (nicht im Git)
  assets/           verarbeitete Assets, aus denen die Demo gebaut ist (Kopie liegt in demo/)
  blender/          Blender-Skripte, falls genutzt (keine .blend-Dateien einchecken)
  demo/             eigenständiges Godot-4.7-Projekt (project.godot, main.tscn, Skripte, Shader, Assets, Schriften)
  media/            von tools/capture.py erzeugt: poster.png/.webp, demo.mp4, preview.gif, frames.jpg, capture.json
```

`prompts.json` im Eintragsordner erzeugt später `tools/collect_prompts.py` aus `assets/raw/*.json`; nicht von Hand
schreiben. Den Auftrag (`brief`) immer frisch aus `data/catalog.json` lesen.

Nur im eigenen Ordner `styles/<slug>/` schreiben. `tools/`, `shared/`, `data/` und fremde Einträge nicht ändern.
Findest du einen Fehler in einem Werkzeug, umgehe ihn lokal (eigenes Skript in deinem Ordner) und melde ihn in
`style.json` unter `tool_issues`.

## Werkzeuge

Python immer mit `.venv/bin/python` (Pillow und NumPy sind installiert; weitere Pakete nur in eigenem venv).
Mehrere Agenten arbeiten gleichzeitig: Temporäre Dateien nur in einem eigenen Unterordner (z. B.
`<Scratchpad>/<slug>/`), Hilfsskripte nie wie Standardmodule benennen (`inspect.py`, `types.py` …).

| Aufgabe | Aufruf |
|---|---|
| Bild erzeugen (agy oder Codex, automatisch gewählt) | `.venv/bin/python tools/genimg.py --out styles/<slug>/assets/raw/bg.png --size 1536x1024 --prompt-file p.txt [--ref shared/badger/master_sheet.png]` |
| Mehrere Bilder parallel | `.venv/bin/python tools/genimg.py --jobs jobs.json --workers 2` |
| Bildaufträge zentral abarbeiten (nur Orchestrierung) | `.venv/bin/python tools/imagequeue.py styles/<slug>/assets/image_jobs.json …` |
| Hintergrundfarbe freistellen | `.venv/bin/python tools/sprites.py key in.png out.png --color ff00ff` |
| Sprite-Sheet zerlegen | `.venv/bin/python tools/sprites.py slice sheet.png walk.png --frames 6 --height 128 [--nearest]` |
| Auf Pixelraster + Palette bringen | `.venv/bin/python tools/sprites.py pixelize in.png out.png --width 320 --palette ega [--dither bayer] [--resample mode]` |
| Palette eines Bildes | `.venv/bin/python tools/sprites.py palette in.png pal.png --colors 16` |
| Blender ohne Oberfläche | `blender -b --factory-startup -P styles/<slug>/blender/build.py -- <args>` (Blender 5.2 LTS) |
| Godot-Skripte prüfen | `godot --headless --path styles/<slug>/demo --import` und `godot --headless --path styles/<slug>/demo --quit-after 5` |
| Demo aufnehmen | `.venv/bin/python tools/capture.py styles/<slug>` (6 s, 30 fps, 1280×720) |

## Bilderzeugung (genimg.py)

- Prompts auf Englisch, Aufbau: **Stilblock** (Medium, Technik, Raster/Auflösung, Palette, Licht, Komposition,
  Was vermeiden) + **Motivblock** aus `data/motif.json` (wörtlich) + **Schutzregeln** (`guards_en`) + Formatangabe
  im Text ("Image format: landscape 3:2"). Hintergründe zusätzlich mit `background_only_en`.
- **Keine Namen** von Spielen, Studios, Franchises, Künstlerinnen oder Künstlern in Prompts, kein "in the style of".
  Stile werden über Technik, Epoche, Medium und Hardwaregrenzen beschrieben. In `style.json` dürfen Vorbilder als
  Text genannt werden.
- Figuren: immer `--ref shared/badger/master_sheet.png` mitgeben und im Prompt sagen, dass nur das Kostüm und die
  Proportionen übernommen werden, Zeichenstil/Palette/Auflösung folgen dem Stilblock. Für weitere Bilder derselben
  Figur im selben Stil das eigene, bereits gelungene Bild als zweite Referenz mitgeben (hält den Stil konstant).
- Sprites und Requisiten: "isolated on a fully transparent background" schreiben. Codex liefert echten Alphakanal,
  bei agy stellt genimg.py frei (siehe unten). Das Bild kann beschnitten oder in anderer Größe zurückkommen
  (genimg.py warnt dann und schreibt `actual_size` in die .json): Größe nicht annehmen, sondern messen.
- **Effekte, die später animiert werden, nicht mitmalen lassen.** Sonst malt das Modell Leuchtturmstrahl, Rauch
  oder Lichtschein statisch ins Bild, und du musst sie mühsam wegflicken. Im Prompt sagen, z. B. "the lighthouse
  lamp only as a small glowing spot without any beam, no smoke from the chimney (both are animated separately)".
- **Stilblock stark machen.** Beide Modelle ziehen zu ihrer Grundhaltung: gpt-image zu detailreicher
  Postkarten-Romantik, das Gemini-Modell (agy) zu fotorealistischem 3D-Render-Look. Medium, Technik und
  Reduktion ausdrücklich nennen ("large flat brushes, few big strokes, few objects, muted broken colours") und
  sagen, was es nicht sein soll ("not a photograph, not a 3D render, not a postcard").
- **Technische Schlüsselbilder** (Farbcode-Maske, Tiefenkarte, saubere Platte ohne Gegenstände, Schnee- oder
  Nachtfassung) mit dem Grundbild als Referenz anfordern: "as if traced on a clear sheet laid on top of it".
  gpt-image lieferte so im ersten Versuch deckungsgleiche Bilder (Versatz 0 px). KI-Tiefenkarten trotzdem auf
  Inseln prüfen (kleine Teile wie Turmspitzen oder Schornsteine kommen oft viel zu nah).
- Kompositionsvorgaben in Prozent hält gpt-image nur auf etwa ±8 % der Bildhöhe; ein Oberflächen-Layout, das ein
  bestimmtes Bildband braucht, erst nach dem Bild festlegen. Auslaufende Ränder im Shader planen, nicht im Prompt.
- Sprite-Sheets: "one row of N animation frames, evenly spaced, same scale, feet on the same baseline" plus die
  Phasen benennen. Danach mit `sprites.py slice` zerlegen und das Ergebnis ansehen.
- Größen: 1536x1024 (quer), 1024x1536 (hoch), 1024x1024.
- **Kontingent:** höchstens 10 Bilderzeugungen pro Eintrag (inkl. Wiederholungen; gezählt wie `image_generations`,
  siehe „style.json“), `--workers` höchstens 2.
  Das Bildwerkzeug hat ein Tageslimit für alle Einträge zusammen.
- **Zwei Wege, automatisch verteilt:** Standard ist `--backend auto`. Seit 12.10.2026 trägt **agy**
  (Antigravity CLI, Gemini-Bildmodell) die Hauptlast;
  **Codex** (gpt-image) ist Reserve. genimg.py wählt je Auftrag und schreibt den Grund als `backend_choice` in die .json:
  1. **Gebunden:** Gibt es das Ziel schon (`--force`) oder ein Referenzbild aus demselben Eintrag, das Codex
     oder agy erzeugt hat, läuft der Auftrag nur über dasselbe Modell, ohne Ausweichen. So bleiben Masken,
     Tiefenkarten, Varianten und Bildserien deckungsgleich, gleich groß und im selben Strich. Ist dieses Modell
     gesperrt, endet der Aufruf mit `usage limit`. Das andere Modell nur bewusst mit `--backend` wählen, dann
     Größe und Deckung selbst prüfen und es in `pipeline` sagen.
  2. **Transparenz** ("isolated on a fully transparent background"): Codex zuerst (echter Alphakanal), agy als
     Ausweichweg.
  3. **Alles andere:** agy zuerst, Codex als Ausweichweg.
  Gesperrte Wege überspringt genimg.py; meldet der erste Weg sein Kontingent erschöpft, nimmt es den zweiten und
  sagt das in der Ausgabe. Codex meldet zeitweise „out of credits“ (dann 6 Stunden gesperrt). Erst wenn alle
  passenden Wege gesperrt sind, endet ein Aufruf sofort mit `usage limit (… gesperrt bis HH:MM …)`. Wird es
  trotzdem knapp, gilt der Ablauf „Bildaufträge“ unten. Ob ein Auftrag Bildaufträge schreiben oder direkt
  erzeugen soll, steht in deinem Arbeitsauftrag.
  Unterschiede, die du beachten musst:
  - agy liefert kleinere Bilder als bestellt: 1264x848 statt 1536x1024 (quer) und vermutlich 848x1264 (hoch);
    Codex liefert quadratisch oft 1254x1254. Maße immer messen, nicht annehmen.
  - agy liefert JPEG ohne Alphakanal. Verlangt der Prompt "isolated on a fully transparent background", ersetzt
    genimg.py das durch eine flache Magenta-Fläche ("chroma-key background, no floor, no shadow …") und stellt
    automatisch frei, inklusive Entfernen des Farbsaums am Rand (`<name>.keyed-src.png` bleibt als Original
    liegen). Ist danach kaum etwas transparent (Modell hat Boden oder Verlauf gemalt), meldet genimg.py
    `key-failed` und legt den Versuch als `<name>.keyfail.png` ab; einmal neu erzeugen (zählt zum Kontingent).
    Glas und magentafarbene Stellen nehmen Farbe an: dann `--key-color 00ff00` wählen oder ohne Glas zeichnen
    lassen. Freigestellte Bilder vor einer dunklen und einer hellen Fläche auf Säume prüfen.
  - genimg.py verlangt von agy, den Prompt wörtlich weiterzugeben; `verbatim` in der .json zeigt, ob das geklappt
    hat (`actual_calls` enthält den tatsächlich verwendeten Prompt). Bei `verbatim: false` das in `pipeline` sagen.
  - Rechnerweit laufen höchstens 4 Codex-Erzeugungen und 2 agy-Erzeugungen gleichzeitig; genimg.py wartet sonst
    auf einen freien Platz. Wartezeit ist kein Fehler.
  - agy hält sich bei Referenzbildern eng an deren Layout (aus einem Dreiansichten-Blatt wird wieder ein
    Dreiansichten-Blatt). Für Sprite-Sheets ein Bild mit dem gewünschten Layout als erste Referenz mitgeben
    (z. B. `shared/badger/walk_painted.png`, ein eigenes Blatt oder ein Blender-Render aus `shared/3d`) und das
    Referenzblatt bzw. ein gelungenes Bild im Zielstil als Stilreferenz. So lassen sich auch vorhandene Blätter
    in einen neuen Stil übermalen.
  - Ein Bild aus agy ist kein Fehler; `backend` steht in der .json und gehört in `style.json` → `pipeline`.
  - Erst wenn genimg.py "usage limit" meldet (alle passenden Wege gesperrt): aufhören, Status `blocked` mit
    Grund in `style.json`.
  - `--backend agy` darfst du auch bewusst wählen, wenn der Stil damit besser gelingt (z. B. Pixel-Art-Umsetzung
    einer Referenz); dann in `lessons` festhalten, warum.
- Bei "network error"/Timeout einmal wiederholen (vorhandene Ziele werden übersprungen).
- Meldet agy oder Codex sein Kontingent erschöpft, sperrt genimg.py diesen Weg bis zur gemeldeten
  Freigabezeit; sind alle passenden Wege gesperrt, enden weitere Aufrufe sofort mit `usage limit (… gesperrt
  bis HH:MM …)`, ohne zu fragen. Nicht wiederholen. Jeder Fehlschlag steht mit voller Antwort in
  `<name>.fail.json` neben dem Ziel.

### Bildaufträge (solange Bilder knapp sind)

Bilder werden nicht mehr während des Baus einzeln angefordert, sondern zentral erzeugt:

1. **Planen:** Der Eintrag schreibt `styles/<slug>/assets/image_jobs.json` – eine Liste von Aufträgen im Format
   von `genimg.py --jobs` (`out`, `size`, `prompt`, optional `refs`, `key_color`), Pfade relativ zum
   Projektordner, Ziele in `styles/<slug>/assets/raw/`, **in Prioritätsreihenfolge** (das wichtigste Bild zuerst)
   und höchstens so viele, wie der Auftrag erlaubt. `refs` dürfen auf Ziele früherer Aufträge derselben Datei
   zeigen. Prompts mit besonderer Sorgfalt schreiben: Es gibt kaum Wiederholungen.
   Alles, was nicht von den Bildern abhängt, wird in dieser Phase fertig gebaut (Demo, Oberfläche, Shader,
   Verarbeitungsskripte, mit Platzhaltern getestet). Den Stand und die restlichen Schritte in
   `styles/<slug>/NOTES.md` festhalten.
2. **Erzeugen:** `tools/imagequeue.py` arbeitet die Aufträge aller Einträge reihum im Takt des Kontingents ab
   (über Stunden) und schreibt `image_jobs.status.json`.
3. **Fertigstellen:** Die Bilder einbauen, aufnehmen, prüfen, `style.json` schreiben. Höchstens zwei
   Nachbesserungen direkt mit `genimg.py` (endet sofort, wenn alle passenden Wege gesperrt sind; dann mit dem
   Vorhandenen fertigstellen und es in `pitfalls` sagen).

Einträge, die ohne KI-Bilder auskommen (3D, Code) oder alle KI-Bilder verworfen haben, geben `ai_fit` 1 und sagen
in `ratings_note`, dass die KI nichts zum Look beigetragen hat, statt zu raten, wie gut KI den Stil träfe
(Definition unter „style.json“).

## Figuren und Animation

- **Messen, nicht nur ansehen.** frames.jpg zeigt keine Sprünge von 2–3 px. Für jede animierte Figur ein kleines
  Prüfskript im Eintragsordner schreiben, das in den gerenderten Bildern (Godot-Aufnahme oder Einzelbilder) Füße
  und Kopf misst: Der Standfuß bleibt beim Laufen über 2–3 Bilder ortsfest (±1 px), und die Fußzeilen sind in
  allen Steh- und Sprechbildern gleich.
- **Prüfmodus in der Demo:** Benutzerargumente nach `--` (`OS.get_cmdline_user_args()`) zeigen die Figur allein vor
  Magenta oder Grün (`--only=badger`, `--solo`), den Hintergrund allein (`--only=bg`) oder schalten Effekte ab
  (`--no-dance`, `--no-detail` …). So misst man Füße, Farben und Hardwareregeln im echten Godot-Bild und Effekte als
  Differenzbild (nes-8bit, painterly-digital, gummischlauch). Aufnahme von Hand wie in Selbstprüfung, Schritt 3.
- KI-Laufzyklen enthalten oft fast gleiche Posen. Bilder nach Beinstellung sortieren (Kontakt, Durchgang, Hoch,
  Ausschritt), Doppelte weglassen und den Vorschub je Bild aus dem gemessenen Standfuß ableiten, statt mit
  konstantem Tempo zu schieben (sonst rutschen die Füße).
- Einzelbilder am Kopf ausrichten (oberes Viertel der Figur), nicht am Schwerpunkt: ein erhobener Arm verschiebt
  sonst das ganze Bild. Alle Bilder einer Reihe auf einem gemeinsamen Raster verkleinern.
- Sprechen und Blinzeln wie in klassischen Adventures aus Teilen bauen (fester Körper + Gesicht + Gestikarm,
  gemeinsame Beine). Ganze KI-Bilder unterscheiden sich in vielen Einzelpixeln und lassen den Körper flimmern.
- Figuren beim Verkleinern zuerst nach Kostümteilen (Material) einteilen und je Zielpixel die Mehrheit
  entscheiden lassen; reines Mitteln mit k-means macht aus Weste und Paket Rauschen.
- **Bildraten, die in 30 fps aufgehen:** 15, 10 oder 6 Bilder/s (auf Zweien, Dreien, Fünfen). 12 oder 8 Bilder/s
  ergeben ungleiche Haltezeiten (3-2-3-2) und sichtbares Ruckeln.
- **3D-Figuren anhalten ohne Rutschen:** `AnimationPlayer` bzw. `AnimationTree` manuell mit `advance()` an
  Bildgrenzen führen und den Standfuß je Bild festhalten (realistisch-pbr, nachbearbeitung, knete). Beim Überblenden
  läuft die alte Animation weiter: Tempo über `play(name, -1, Tempo)` statt `speed_scale`, den Lauf vorher einfrieren
  (`play("Walk", 0, 0)`) und so bremsen, dass er in einer Durchgangsphase endet (lowpoly-flat, handpainted-3d).
- **Die Figur muss groß genug sein, um den Stil zu zeigen.** In der Totale ist der Dachs oft nur 18–25 px hoch;
  Facetten, Strich oder Kostüm sieht man dann nicht. Dann die Kamera nah heranfahren oder auf eine zweite feste
  Einstellung schneiden (Totale, dann Nahaufnahme), und `--poster-at` in die Nahaufnahme legen. Alle
  `elements_required` aus `data/motif.json` müssen trotzdem in der Demo vorkommen, mindestens in einer kurzen Totale;
  das Poster darf die Nahaufnahme sein. Fehlt ein Pflichtelement in der Demo, steht das mit Grund in `pitfalls`.
- **Größenverhältnisse per Skript messen:** KI-Teilebögen und Requisitenbögen haben keinen gemeinsamen Maßstab. Tür
  und Figur messen, das Verhältnis bewusst wählen und nennen (gummischlauch: Cartoon, Tür ≈ 0,7–0,8 der Figurenhöhe;
  flat-vektor fordert fürs Spiel Tür ≥ Figur). Merkpunkte (Schornsteinoberkante, Fenster- und Lampenmittelpunkt) per
  Regel bestimmen statt von Hand ablesen (gummischlauch; von Hand abgelesen in silhouette-scherenschnitt).
- Bewusst vom Auftrag abweichen ist erlaubt, wenn es den Stil besser zeigt, muss aber in `verdict` oder
  `pitfalls` mit Grund stehen.

## Pixel-Stile

- Das Bildmodell erzeugt keine echte Pixel-Art. Zwei Wege:
  1. Als Pixel-Art im Stil erzeugen lassen (große, klare Pixel, begrenzte Palette, keine Verläufe) und dann mit
     `pixelize --resample mode` auf das echte Raster einrasten. Bevorzugt für Figuren und Hintergründe.
  2. Ein gemaltes Bild mit `pixelize` (BOX) verkleinern. Ergibt oft verwaschene Pixel-Suppe; nur wenn Weg 1 scheitert.
- Ein Raster pro Bild: keine gemischten Pixelgrößen, keine Kantenglättung, Sprites mit 1-Bit-Alpha.
- Godot: Viewport in Rasterauflösung (z. B. 320×180, 320×200 oder 256×224), `window/stretch/mode="viewport"`,
  `scale_mode="integer"`, `rendering/textures/canvas_textures/default_texture_filter=0` (Nearest),
  Fenstergröße per `window_width_override`/`window_height_override`. capture.py skaliert ganzzahlig auf 1280×720.
- **Auflösung so wählen, dass sie ganzzahlig in 1280×720 passt:** 320×180 (×4), 426×240 (×3), 640×360 (×2),
  256×240 und 256×224 (×3), 320×240 und 320×200 (×3), 160×144 (×5), 400×240 (×3). Nicht 480×270 oder 384×216
  (nur ×2 bzw. ×3 mit breitem Rand).
- Alte Bildschirme hatten oft keine quadratischen Pixel (320×200 auf 4:3 sind 1,2-mal so hoch wie breit). Ob du
  das nachbildest oder quadratisch bleibst, in `style.json` sagen.
- Hardware-Stile (NES, Game Boy, C64, Spectrum, EGA …): Palette und Rastergrenzen ehrlich einhalten und in
  `style.json` sagen, welche Hardware-Regeln eingehalten und welche vereinfacht wurden. `pixelize` rastet nur
  auf Palette und Raster ein; Zell- und Attributregeln (Farben je 8×8- oder 4×8-Zelle, Paletten je Block,
  Sprites je Zeile) brauchen ein eigenes Prüf- und Einrastskript im Eintragsordner.
- **Hardware als Bauweise:** Videohardware als Shader plus Speicherabbild (Kacheln, Karten, OAM, Paletten als Daten)
  macht fremde Farben und Regelverstöße undarstellbar (gameboy, nes-8bit, pico8-fantasy); eine Python-Referenz prüft
  per `--dump` pixelgleich (videotext, ega-adventure). Eigene Zeichensätze gegen ein ROM abgleichen
  (`c64-multicolor/scripts/rom_compare.py`, ROM nur vorübergehend außerhalb des Projekts): Aus dem Gedächtnis
  gezeichnet entstehen fast zwangsläufig Original-Glyphen.
- **Farben in Oklab und nach Gruppen zuordnen:** unbunte Gruppen nur auf Graustufen (Grau vorher auf die Grauleiter
  der Hardware heben, sonst wird dunkles Grau zu Oliv), kleine Pflichtfarben (Fensterlicht, Leuchtturmband) vor dem
  k-means als eigene Einträge reservieren und am Ausschnitt prüfen (ega-adventure, nes-8bit, farbzyklus).
- Pixelschriften im gerenderten Bild prüfen: Viele 8-px-Schriften zeichnen Ä/Ö/Ü in Kleinbuchstabenhöhe, und
  geschätzte Spaltenabstände liegen leicht 1 px daneben.
- Farbzyklus-Masken: die Fläche über den Farbton auswählen und nur Objekte und deren Schatten als Polygone
  ausschließen. Rechteck-Bereiche hinterlassen harte Kanten und starre Lücken.

## Godot-Demo

- Godot 4.7.2 (`godot` im PATH), GDScript, Szenen und Ressourcen als Text (.tscn/.tres/.gdshader) von Hand
  geschrieben, kein Editor. Hauptszene `res://main.tscn`. Keine Plugins/Addons.
- Inhalt nach `data/motif.json` → `demo.requirements_de`: Hafenszene, animierter Dachs-Kurier, mindestens zwei
  Umgebungsanimationen, Textbox im Stil mit `ui_text`. Länge 6 s bei 30 fps; die Animation soll in 6 s etwas
  zeigen (Dachs kommt ins Bild und bleibt stehen, oder läuft durch).
- Deterministisch: Zeit aus dem Bildzähler rechnen (t = n/30, eigener Zähler in `_process` bzw.
  `Engine.get_frames_drawn()`), nicht über `delta` aufsummieren: Der Movie Maker liefert trotz `--fixed-fps 30` in den
  ersten 4–7 Bildern ungleiche `delta` (gemessen 0,025 / 0,033 / 0,042 / 0,029 s). Zusätzlich
  `physics/common/physics_jitter_fix = 0` und `application/run/delta_smoothing = false` setzen (mode7,
  nachbearbeitung, prozedurale-animation). Ganze Schritte und Pixel über `floor(t·Rate + 0.001)` mit Raten, die in
  30 fps aufgehen, Schaltpunkte zwischen zwei Bildzeiten (nes-8bit, ps1-lowpoly, c64-multicolor). Zufall nur mit
  `RandomNumberGenerator` und fester `seed`.
- Bild i der Aufnahme zeigt Takt i + 1 (das erste Bild entsteht nach dem ersten `_process`): Zähler so beginnen, dass
  Bild i genau t = i/30 zeigt, und Protokollzeilen eines Prüflaufs über `Engine.get_frames_drawn()` den Bildern
  zuordnen; den Versatz einmal messen, nicht annehmen (kupferstich, nes-8bit, apple2-hires, knete).
- Schriften nur mit freier Lizenz (SIL OFL oder CC0), z. B. aus github.com/google/fonts (`ofl/<name>/`).
  Schriftdatei und Lizenztext in `demo/fonts/` ablegen, in `style.json` → `licenses` eintragen.
- **Schriften in Godot:** `antialiasing`, `hinting` und `subpixel_positioning` einmal nach dem Laden setzen, nie in
  `_draw()` (sonst volle Rechtecke); Pixelschriften nur in ihrer Rastergröße (vga-adventure, farbzyklus, einbit-3d).
  Ligaturen aus (`liga`/`clig` = 0) und Zierligaturen im gerenderten Bild suchen (gummischlauch, sprite-skalierung);
  Tags über `TextServerManager.get_primary_interface().name_to_tag()`; Tipptext mit `VC_CHARS_AFTER_SHAPING`.
- **Gleiches Bild in allen Renderern:** unter `gl_compatibility` HDR-2D abschalten (`use_hdr_2d = false`), kein
  2D-MSAA voraussetzen, `blend_mix` statt `blend_mul`, Hashes ohne `sin` (painterly-digital, minimal-geometrisch,
  handpainted-3d, kinemagramm). Globale Shaderfarben sind linear (moebius-linien). Renderer-Weiche im Shader über
  `CURRENT_RENDERER`, im Skript über `RenderingServer.get_current_rendering_method()`. Bildschirm-Shader
  (`hint_screen_texture`, Nearest) nie genau auf Pixelgrenzen abtasten (gummischlauch). Der „Hash without Sine“
  (Dave Hoskins) ist MIT-lizenziert: in `licenses` und `THIRD_PARTY_NOTICES.txt` nennen.
- Texturen aus fremden Quellen nur CC0 (Poly Haven, ambientCG), Quelle in `licenses`.
- 3D: `Camera3D` fest oder langsam bewegt, `WorldEnvironment` für Licht/Nebel/Glow, Shader für den Look.
  Renderer: Standard (Forward+); für Retro-Looks Auflösung über SubViewport oder `scaling_3d_scale` senken.
- 2D-Shader (`canvas_item`): `COLOR` enthält in `fragment()` schon die Texturfarbe. Wer `TEXTURE` selbst abtastet,
  holt die Vertexfarbe über ein `varying` aus `vertex()`, sonst werden die Farben quadriert und das Sprite dunkel.
- Figuren nicht vom `PointLight2D` des Hintergrunds beleuchten lassen (`light_mask = 0`), sonst wirken sie
  ausgewaschen; Licht auf der Figur über Shader-Tönung oder Kantenlicht.
- Effekte, die um Bruchteile eines Pixels verschieben (Flimmern, Wabern), verwischen feine Details durch lineare
  Filterung: um ganze Pixel oder Texel verschieben, Sprite-Positionen runden.
- Bildfilter wie Kuwahara auf Sprite-Größe (≈150 px) löschen Gesichtszüge. Für gemalte Looks Striche offline in
  Quellauflösung malen (grob nach fein) und erst danach verkleinern.
- Ein 2D-Himmel hinter einer schwenkenden Kamera braucht seitlich und oben Rand.
- Neue PNGs, die nur per `load()` im Code genutzt werden, importiert Godot mit Standardwerten (in 3D mit
  VRAM-Kompression, `detect_3d/compress_to=1`). Für Paletten- und Pixeltexturen die `.import`-Datei prüfen und
  Kompression bzw. Filter passend setzen.
- Masken nie im Alphakanal speichern: Godots Import (`fix_alpha_border`) überschreibt die Farbe transparenter
  Pixel. Masken als RGB- oder L-Textur ablegen.
- In Shadern Texturen vor Verzweigungen abtasten; in einem `if` fehlen die Mipmap-Ableitungen (helle Striche).
- Effekte (Blitz, Aufblitzen) zu einer eigenen Effektfarbe mischen, nie zum ungetönten Grundbild – sonst kehren
  Tagesfarben und der gemalte Himmel zurück.
- **Licht in der Bildsprache des Stils:** Wo der Stil kein Glühen kennt, keine weichen additiven Verläufe und keinen
  Engine-Glow, sondern in Pixelstilen gestufte, geditherte Lichthöfe oder Aufhell-Tabellen (hibit-pixel,
  vga-adventure), in Mal- und Druckstilen Lasur, ausgedünnte Linien oder Ornament (oelmalerei, kupferstich,
  jugendstil). Lichthöfe auf Regionen begrenzen (Himmel, Wasser), sonst hellen sie Rahmen mit auf (einbit-pixel).
- Vor der Aufnahme: `godot --headless --path demo --import` und einen Probelauf; die Ausgabe darf keine
  `ERROR`/`SCRIPT ERROR` enthalten. Ein normaler Lauf importiert geänderte PNGs nicht neu: eigene Prüfskripte
  rufen vorher ebenfalls `--import` auf.

## Blender

- Nur per Skript: `blender -b --factory-startup -P blender/build.py -- …`. Szenen im Skript aufbauen, glTF
  (`.glb`) nach `demo/` exportieren oder Bilder rendern. EEVEE ist schnell (Sekunden); Cycles nur, wenn nötig, mit
  wenigen Samples (der erste Cycles-Start kompiliert Metal-Kernel, ca. 1 Minute).
- Gemeinsame 3D-Grundlage: `shared/3d/` mit `harbor.glb`, `badger.glb` (Idle, Walk, Wave), `badger_low.glb` und
  einer stilneutralen Probeszene in `shared/3d/demo/`. **Zuerst `shared/3d/README.md` lesen** (Achsen, Kamera,
  Material- und Knotennamen, Kopiervorlagen, Fallstricke). 3D-Stile bauen darauf auf und erzeugen den Look über
  Materialien, Shader, Auflösung und Nachbearbeitung, statt alles neu zu modellieren (sonst sind Stile nicht
  vergleichbar). Die glb in den eigenen `demo/`-Ordner kopieren, `shared/` nie ändern.
- Braucht ein Stil andere Geometrie (z. B. stärker reduzierte Fässer für PS1), erzeugt ein Blender-Skript im
  Eintragsordner aus der gemeinsamen glb eine eigene Fassung (`demo/models/harbor_<slug>.glb`) und behält Namen
  und Lage bei.
- Wichtige Punkte aus der README: glTF kennt kein Loop-Flag, Idle und Walk im Code auf Schleife stellen. Das
  Winken ist von der Seite nicht zu sehen; die Figur vorher zur Kamera drehen. Material `Grass` gibt es
  zusätzlich zu den übrigen. Das Pflaster liegt bis 8 mm über y = 0; ein eigener Boden darüber gehört auf
  etwa 12 mm, die Figur auf dieselbe Höhe.
- Bildausschnitt vor dem Godot-Lauf in Python ausrechnen (Projektion mit Godots YXZ-Euler, Keep Height), statt
  Kamerawerte auszuprobieren. Beispiel: `styles/ps1-lowpoly/scripts/frame_closeup.py`.
- Effekte, die von Geometrie oder Kamera abhängen (affine Texturen, Vertex-Snapping, Dither-Muster), mit einem
  Vergleichsschalter messen (Anteil geänderter Pixel mit und ohne Effekt). 2–5 % sieht praktisch niemand; der
  Effekt muss deutlich im Bild stehen, sonst die Szene so wählen, dass er sichtbar wird.

## Selbstprüfung

1. `.venv/bin/python tools/capture.py styles/<slug>` ausführen; die Ausgabe muss mit `ok:` enden.
2. `media/frames.jpg` (8 Zeitpunkte) und `media/poster.png` **ansehen** und kritisch prüfen:
   Sind die Merkmale aus `traits` sichtbar? Ist die Szene erkennbar? Bewegt sich der Dachs sichtbar und richtig
   (keine zitternden oder springenden Einzelbilder, keine Farbsäume vom Freistellen, nicht verzerrt)? Sitzt die
   Textbox im Stil und ist sie lesbar? Gibt es Lücken, Platzhalter, schwarze Flächen?
3. Animierte Figuren zusätzlich messen (siehe „Figuren und Animation“). `frames.jpg` zeigt nur 8 Zeitpunkte:
   kurze Effekte (Blitz, Zünden, Aufblitzen) als Einzelbilder rendern und ansehen. Was beliebig lange laufen
   soll, zusätzlich ab 20–40 s prüfen (linear geschobene Ebenen zeigen erst dann Schlieren und Ränder).
   `capture.py` hat dafür keine Option: `main.gd` liest ein Benutzerargument (`OS.get_cmdline_user_args()`,
   z. B. `--t0=30`), aufgenommen wird von Hand in ein Temp-Verzeichnis:
   `godot --path demo --write-movie <tmp>/f.png --fixed-fps 30 --quit-after 60 -- --t0=30`.
4. Verbessern und erneut aufnehmen, bis es überzeugt. Wenn ein Punkt nicht lösbar ist: ehrlich in
   `style.json` → `pitfalls` und `status: "partial"`.
5. Bewertungen gegen die eigenen `pitfalls` lesen: Sie dürfen sich nicht widersprechen. `ai_fit` bewertet, wie
   viel die KI-Bilder tatsächlich zum Look der Demo beitragen; kommt der Look vor allem aus Shadern oder Code, steht
   das in `ratings_note`. `mobile` ist eine Schätzung aus einem Probelauf mit `--rendering-method mobile` und
   `--rendering-method gl_compatibility` (Aufnahme in ein Temp-Verzeichnis, Abweichung zum Forward+-Bild nennen) und
   einer Kostenabschätzung (z. B. Vollbild-Durchgänge, Zeichenaufrufe, Renderzeit auf dem Mac). Bei reinen
   2D-Szenen ist Mobile pixelgleich mit Forward+; aussagekräftig ist dort nur `gl_compatibility`. Ein Test auf einem
   Telefon ist optional; wer ihn macht, nennt Gerät und Ergebnis in `ratings_note`.

## style.json

```json
{
 "slug": "vga-adventure",
 "name": "VGA-Adventure",
 "family": "computer",
 "kind": "style",
 "era": "1990–1995",
 "summary": "Ein bis zwei Sätze: was den Stil ausmacht.",
 "references": ["Spiele, die den Stil prägten (nur als Text, keine fremden Bilder)"],
 "related": ["Slugs anderer Katalogeinträge zum direkten Vergleich (optional, keine Selbstverweise)"],
 "traits": ["prüfbare Merkmale, an denen die Prüfung das Ergebnis misst"],
 "camera": "Seitenansicht, feste Kamera",
 "resolution": "320×200, 256 Farben",
 "pipeline": [
  {"step": "Hintergrund erzeugen", "tool": "genimg (gpt-image)", "detail": "…"},
  {"step": "Auf 320×200 / 256 Farben einrasten", "tool": "sprites.py pixelize", "detail": "…"}
 ],
 "godot": ["Umsetzungsdetails: Projekteinstellungen, Knoten, Shader"],
 "techniques": ["Slugs der gezeigten Techniken, z. B. farbzyklus, sprite-animation, parallax"],
 "ratings": {
  "ai_fit": 4,
  "consistency": 3,
  "effort": 2,
  "text_adventure": 5,
  "mobile": 5
 },
 "ratings_note": "Begründung der Bewertungen in zwei, drei Sätzen.",
 "verdict": "Was das für unser Textadventure bedeutet.",
 "pitfalls": ["was schiefging oder schwierig ist"],
 "lessons": ["was funktioniert hat und wiederverwendbar ist"],
 "assets": [
  {"file": "assets/bg.png", "kind": "background", "made_with": "gpt-image + pixelize", "prompt": "assets/raw/bg.json"}
 ],
 "licenses": [{"item": "Schrift Silkscreen", "license": "OFL-1.1", "source": "https://github.com/google/fonts"}],
 "image_generations": 4,
 "tool_issues": [],
 "status": "done"
}
```

`assets[].file` ist immer genau eine vorhandene Datei im Eintragsordner, kein Ordner (sonst bricht `build.py` ab).
Mehrere Teile eines Blatts als einzelne Einträge oder das Blatt selbst nennen.

Bewertungen 1–5: `ai_fit` (auf der Seite „KI-Beitrag“: wie viel die KI-Bilder tatsächlich zum Look der Demo
beitragen; 1 = nichts, weil keine KI-Bilder verwendet oder alle verworfen; übernommene KI-Bilder aus anderen Einträgen
zählen mit und werden in `ratings_note` genannt), `consistency` (wie gleichmäßig über viele Assets),
`effort` (Aufwand pro Asset, 5 = hoch), `text_adventure` (Eignung für unser erstes Spiel), `mobile`
(auf der Seite „Mobil (geschätzt)“: geschätzte Mobiltauglichkeit aus Renderer-Vergleich und Kostenabschätzung, siehe
Selbstprüfung, Schritt 5). `status`: `done`, `partial` (Demo läuft, Lücken benannt), `blocked` (z. B.
Bildlimit) oder `failed`.

`image_generations` zählt jeden Aufruf, der ein Bildmodell erreicht hat, gelungen oder nicht (auch `key-failed`,
Timeouts und verworfene Bilder). Sperren und Kontingentmeldungen (`status` beginnt mit `usage limit`) zählen nicht,
wie in `imagequeue.py`; sie gehören in `tool_issues`. Belege in `assets/raw/`: `<name>.json` (Erfolg) und
`<name>.fail.json` (Fehlschlag mit `status`; genimg.py schreibt sie auch bei Sperren ohne Modellaufruf). Jeder
weitere Fehlschlag für dasselbe Ziel überschreibt die `.fail.json`, eine Neuerzeugung mit `--force` die `.json`;
Wiederholungen deshalb selbst mitzählen (`NOTES.md`; bei `imagequeue.py` steht `tries` in `image_jobs.status.json`).

Texte in `style.json` auf Deutsch, sachlich, ohne Werbesprache.
