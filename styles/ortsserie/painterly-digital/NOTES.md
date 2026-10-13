# Ortsserie – painterly-digital (agy-Probe)

Stand 13.10.2026. Frage: Hält agy (Gemini-Bildmodell) den Look von painterly-digital über drei neue Orte
(Lampenraum im Leuchtturm, Stube des Hafenmeisters, Klippenpfad)? Technik: Kinemagramm (lebendes Standbild).
Alle Messwerte in `measure.json`, Vergleichsbogen `assets/sheet.png`, Standbilder `assets/<ort>_scene.png`.

## Vorgehen

1. **Prompts** (`scripts/prompts.py`): Stilblock wörtlich aus `styles/painterly-digital/prompts/master.txt`.
   Nur der Satz mit den Lichthöfen an Hütte, Laterne und Leuchtturm ist ersetzt, weil er zum Hafen gehört und
   den Effektverboten der Orte widerspricht. Serienregeln: Abend wie im Hafen, kühles Licht mit warmen Quellen,
   „strict side view at eye level, flat horizon at 45 %“, ruhiges unteres Viertel für die Textleiste, klare
   Flächen fürs Kinemagramm. Ortsblock, Effektverbote und `anchor_extra` sind aus
   `styles/hintergrund-serie/tools/prompts.py` importiert (wörtlich, dort nichts geändert). Masken: Einleitung
   aus `styles/kinemagramm/assets/prompts/mask.txt` und Farbcodes je Ort.
2. **Experiment am Leuchtturm:** A mit dem Hafenbild des Stils (`styles/painterly-digital/assets/raw/master.png`)
   als Stilreferenz (Ankerabsatz: nur Malweise, nicht Aufbau), B nur mit Stilblock.
   - Layout-Kopie (Bandpass-Korrelation `struct_corr`, unabhängige Bilder |r| ≤ 0,03): A 0,02, B 0,015. Keine
     Kopie. A und B ähneln sich untereinander viel stärker (gray 0,72, edge 0,58) als dem Anker: Den Aufbau
     bestimmt der Prompt.
   - Palette zum Anker (Oklab × 100, 8 Farben 1:1 / 12 Farben gerichtet / Mittelwert): A 3,2 / 2,6 / 2,1,
     B 4,1 / 1,6 / 2,4. Detail (Gradientenenergie): A 1,85×, B 1,36× des Ankers.
   - Wahl: **A**, weil keine Kopie messbar war, zwei von drei Palettenmaßen näher lagen, der Himmel in den Fenstern
     dem Anker am nächsten kam und der Ortsinhalt treuer war (B: keine Wendeltreppe). Der Preis ist gut ein Drittel
     mehr Detail (Gradientenenergie 1,85 gegen 1,36 × Anker).
   - Nachtrag nach dem gemeinsamen Einheitsmaß (`styles/ortsserie/assets/einheitsmass.json`, gilt für alle
     Vergleiche zwischen den Stilen): Dort liegt B näher am Anker (Palette 1,97 gegen 2,41, Detail ×1,41 gegen
     ×1,83). Für A sprechen dort nur die Helligkeit (L 46,5 gegen 43,2, Anker 46,3) und der Inhalt. Das Detail
     ×1,83, das die Serie für den Lampenraum nennt, gehört zu Fassung A.
3. **Serie mit A:** Die Stube passt (struct 0,02). Die **Klippe mit A übernahm das Wolkenbild des Ankers fast
   deckungsgleich**, dazu Leuchtturmlage und Kaimauer (struct 0,215, Himmel 0,428). Deshalb wurde die Klippe
   **ohne Referenz (B)** neu erzeugt (struct 0,065, Detail 1,03×) und verwendet. `stube_b` entstand nur als dritter
   A/B-Punkt (struct 0,04, Palette 6,1 statt 6,6) und wird nicht verarbeitet.
4. **Verarbeitung** (`scripts/process.py`): Die Kinemagramm-Kette ist für beliebige Orte umgebaut. Aus
   kinemagramm werden nur `aimask.py` und `imgops.py` importiert; `process.py`, `auto_scene.py` und `prep.py`
   sind dort auf den Hafen verdrahtet. Die Schritte: Maske einordnen und am Gemälde ausrichten (gemessen
   höchstens 1 px Versatz, Skalierung 0,996–1,008), 16:9-Schnitt mit dem Horizont auf Zeile 270, Masken (Wasser,
   Himmel, Sterne, Lichter mit Schein, Gras, Lichtempfänger, Strahl), eine saubere Platte, `scene.json`. Die
   Effektplanung je Ort steht im FX-Block von `process.py`. Korrekturen von Hand nur in
   `scripts/scene.override.json`.
5. **Godot** (`styles/ortsserie/demo/painterly-digital/`): `leuchtturm.tscn`, `stube.tscn`, `klippe.tscn`
   (von `scripts/make_scenes.py`). Jede Szene hat als Wurzel ein Control 1280×720 mit `ort.gd`; ein Shader
   `shaders/ort.gdshader` rechnet in einem Durchgang Himmel, Wasser, Glitzern, Sterne, Flackern, Linsenblitz und
   wandernden Lichtfleck, Flammen, Leuchtturmstrahl, Gras im Wind, Möwen, Nebelbänder, Lichtteilchen,
   Lichthöfe und Vignette. Die Textleiste unten ist die Form „Vollbild“ aus textoberflaeche in doppelter Größe
   (Alegreya SC/Sans, OFL), mit `reveal_fx.gd` und Icons aus textoberflaeche (kopiert). Zeit in der Aufnahme
   aus dem Bildzähler. Schalter nach `--`: `--t0=`, `--frozen`, `--no-ui`.
6. **Prüfung** (`scripts/render_test.py`): Kopie von `project.godot` und `painterly-digital/` im Scratchpad,
   `--import`, je Szene 180 Bilder mit `--write-movie`. Das ergab 0 Fehlerzeilen, wenn man die fehlende
   `res://main.tscn` des gemeinsamen Projekts ausnimmt. Dazu kamen Bilder bei t = 20 s und 30 s und ein Lauf
   unter gl_compatibility (Klippe: mittlere Abweichung 0,16/255, höchstens 2/255).

## Ergebnis

| Ort | Fassung | Versuche (Bild/Maske) | Palette ΔE (1:1 / Mittel) | Detail × Anker | struct_corr | Handarbeit |
|---|---|---|---|---|---|---|
| Leuchtturm | A | 1 / 1 | 3,2 / 2,1 | 1,85 | 0,02 | 1 Eintrag, 4 Zahlen (Linse ohne Sockel), ~45 min |
| Stube | A | 1 / 1 | 6,6 / 10,0 | 1,44 | −0,02 | 1 Eintrag, 8 Zahlen (Flammen), ~60 min |
| Klippe | B | 2 / 1 | 4,2 / 2,4 | 1,03 | 0,065 | 1 Eintrag, 6 Zahlen (Laterne), ~48 min |

9 Erzeugungen (Budget 10), alle `--backend agy`, alle 1264×848 geliefert (1536×1024 bestellt), 54–98 s,
`verbatim: true`, keine Fehlschläge, keine Sperre. Die Minuten sind geschätzt für jemanden mit den fertigen
Skripten: Korrektur, Effektplanung (etwa 25 min je Ort) und Prüfen. Die Skripte selbst und der Shader waren
einmaliger Aufwand.

Zum Vergleich die Codex-Serie (hintergrund-serie) mit denselben Maßen gegen ihren eigenen Hafen: Palette 1:1
1,8–4,1, Mittel 1,2–4,9, Detail 1,22–1,28×. Auch die Codex-Klippe übernimmt die Anordnung ihres Hafens
(struct 0,188), aber mit eigenen Wolken; bei agy-A sind die Wolken selbst kopiert.

Die Stube ist dunkler als der Anker (mehr Fläche im Schatten; Oklab-L im Mittel 34 gegen 44). Daher kommt der größere
Mittelwertabstand; die 12-Farben-Palette liegt mit 2,3 so nah wie bei den anderen Orten.

## Probleme

- Klippe mit Referenz: Wolkenbild, Leuchtturm rechts und Kaimauer unten aus dem Anker übernommen. agy hängt bei
  Außenorten, die dem Anker ähneln, trotz „Do not copy its composition“ am Referenzbild. Innenräume waren nicht
  betroffen.
- Alle Gemälde außer Klippe A (dort die kopierte Kaimauer) haben unten einen flachen, fast einfarbigen Streifen
  von 16,5–17,7 % der Höhe (gemessen). agy nimmt „bottom quarter calm … text bar will cover it“ wörtlich. Bei
  leuchtturm_b (10 %) und klippe_b (9 %) kam oben ein zweiter Streifen dazu; bei klippe_b entfernt ihn der Schnitt. Der Schnitt legt den unteren Streifen unter die Textleiste. Er bleibt in den Zahlen zur Ruhe der Textfläche
  sichtbar: Die Streuung von L ist 2,8–3,7-mal so groß wie beim Anker, weil die Kante zwischen Boden und Streifen
  in der Leiste liegt. Die Gradienten sind gleich (1,0–1,2×). Unter der Leiste mit 80 % Deckung ist das kaum zu
  sehen.
- agy malte trotz Verbot kleine Flammen und Funken in den Kamin. Die Masken fassten mehr als verlangt: die Linse
  samt Messingsockel, die Kerze samt Kerzenkörper. Korrigiert wurde mit einem Rechteck bzw. über die Lage der
  Flamme. Die Laterne am Wegweiser (nicht im Farbcode) ist von Hand ergänzt.
- Shader: Rauschkanal b der Kinemagramm-Rauschtextur (Spektrum 1/f^0,7) und zu kleine Kacheln machten Flammen-
  und Linsenränder körnig. Jetzt werden nur die Kanäle r/g mit Kacheln ab 600 px benutzt. Der gemalte Lichthof
  der Leuchtturmlampe wanderte mit dem pendelnden Himmel mit; im Umkreis der Lampe steht der Himmel jetzt still.
  Die Kerze flackerte über die Empfängerfläche im Takt des Kamins (r = 0,98); jetzt ist die Fläche auf die
  Umgebung des Feuers begrenzt (r = −0,08).
- Bewegungsmaß wie in capture.py (Pixel > 6/255 in 0,5 s) unterschätzt weiches Flackern: In der Stube sind es nach
  dem Texteinblenden nur 0,5–1 %, obwohl der Kaminbereich in der Helligkeit zwischen 76 und 93 schwankt.
- `.gitignore` deckt mit `styles/*/assets/raw/*` die Ordner `styles/ortsserie/<stil>/assets/raw/` nicht ab:
  Rohbilder (je ~1,1 MB) und Begleit-JSON würden eingecheckt. Die JSON sind mit `scripts/sanitize_raw.py`
  bereinigt (ohne Sitzungs-ID und Kontoname, Pfade projektrelativ). Das Muster muss jemand anpassen, der
  `.gitignore` ändern darf.
- `scripts/prompts.py` lud `styles/hintergrund-serie/tools/prompts.py` ohne `sys.dont_write_bytecode` und legte
  dabei am 13.10. um 20:02 `styles/hintergrund-serie/tools/__pycache__/prompts.cpython-313.pyc` an (gleiche Minute
  wie `assets/jobs_1_leuchtturm_ab.json`). Die Datei ist von `.gitignore` erfasst und harmlos; `prompts.py` setzt
  jetzt `sys.dont_write_bytecode = True` (geprüft mit `PYTHONPYCACHEPREFIX`: kein Cache mehr für die fremde
  Datei). Die vorhandene `.pyc` liegt in einem fremden Eintrag und ist nicht gelöscht; das übernimmt der Besitzer.
- Im echten Demo-Ordner wurde kein `--import` ausgeführt (parallel arbeitende Agenten), dort fehlen also noch
  `.import`-Dateien. Das gemeinsame `project.godot` zeigt auf eine noch fehlende `res://main.tscn`.

## Lehren

- agy hielt den Look von painterly-digital über Innen- und Außenorte auch **ohne** Referenz (je Ort ein Bildpaar).
  Detail lag ohne Referenz am nächsten am Anker (1,03× an der Klippe, 1,36× im Leuchtturm). Warum das hier klappt
  und bei Gouache nicht (dort driftete B zu Cartoon mit Konturen), ist offen: Alle drei Hafen-Anker der Serie sind
  agy-Bilder ohne Referenz, und alle drei Teile übernehmen den Stilblock ihres Ankers fast wörtlich. Am Entstehen
  des Ankers liegt es also nicht; in Frage kommen der Stil selbst oder wie fest der Stilblock das Medium beschreibt
  (ungeprüft).
- Mit Referenz: bei Innenräumen keine Kopie, bei Außenorten mit ähnlichem Aufbau (Meer, Horizont, Leuchtturm
  rechts) kopiert agy den Himmel. Für Außenorte daher ohne Referenz arbeiten, oder mit einem Anker, dessen
  Himmel nicht gebraucht wird.
- Kopie messen statt nur ansehen: Die Bandpass-Korrelation (Gauß 2 px minus 8 px, 160×107) trennt im ganzen Bild
  sauber. Unabhängige Bilder liegen bei |r| ≤ 0,03, eine Kopie bei 0,2 und im Himmel bei 0,4. Der Himmelswert allein
  trennt schlechter: Die Klippe ohne Referenz (keine Kopie möglich) liegt dort schon bei 0,27, weil agy denselben
  Aufbau malte (Leuchtturm auf dem Kap rechts, dunkle Wolken oben links). Schwelle für alle Stile siehe
  `styles/ortsserie/style.json`. Grobe Tonwert-Korrelation taugt dafür nicht, weil alle Bilder oben hell und unten
  dunkel sind.
- Farbcode-Masken von agy sitzen nach einer Skalierung um 0,996–1,008 deckungsgleich (danach höchstens 1 px
  Versatz; ohne die Skalierung wären es an den Bildrändern bis etwa 3 px) und kamen alle im ersten Versuch.
  `aimask.py` aus kinemagramm funktioniert für beliebige Orte, wenn man die Codes je Ort umdeutet.
- Für eine Textleiste unten nicht „calm plain foreground (a text bar will cover it)“ schreiben. Sonst malt agy
  einen flachen Balken; besser einen dunklen Boden mit Inhalt verlangen.
- Shader-Rauschen nie feiner als etwa 2 px je Texel abtasten und nur glatte Kanäle für Ränder nehmen. Lichtquellen
  aus der Empfängerfläche anderer Quellen herausnehmen.

## Lizenzen (für den Steckbrief der Hauptdemo)

Schriften Alegreya SC Medium und Alegreya Sans Medium (SIL OFL 1.1, Lizenztexte in
`demo/painterly-digital/fonts/`, Quelle github.com/google/fonts). „Hash without Sine“ (David Hoskins, MIT) in
`shaders/ort.gdshader`, wie in kinemagramm. Icons, Textleisten-Effekt und Rauschtextur sind eigener Code bzw.
aus eigenen Einträgen kopiert.

## Neu bauen (aus dem Projektordner)

```
.venv/bin/python -I styles/ortsserie/painterly-digital/scripts/process.py --work <Scratchpad>/ortsserie/painterly-digital/process
.venv/bin/python -I styles/ortsserie/painterly-digital/scripts/make_scenes.py
.venv/bin/python -I styles/ortsserie/painterly-digital/scripts/render_test.py --work <Scratchpad>/ortsserie/painterly-digital --still 4.0 --keep-stills stube klippe
.venv/bin/python -I styles/ortsserie/painterly-digital/scripts/render_test.py --work <Scratchpad>/ortsserie/painterly-digital --still 2.9 --keep-stills --no-copy leuchtturm
.venv/bin/python -I styles/ortsserie/painterly-digital/scripts/measure.py
.venv/bin/python -I styles/ortsserie/painterly-digital/scripts/sheet.py
```

Bildaufträge (schon erzeugt, nicht wiederholen): `assets/jobs_1_leuchtturm_ab.json`, `jobs_2_bilder.json`,
`jobs_3_klippe_b.json`, `jobs_4_klippe_mask.json`. Danach `scripts/sanitize_raw.py` ausführen.
