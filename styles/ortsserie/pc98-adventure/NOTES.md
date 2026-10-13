# Ortsserie – Stil pc98-adventure (agy)

Frage: Hält agy den Look des Eintrags `pc98-adventure` (16 aus 4096 Farben, 1-px-Konturen, Raster statt Verläufe)
über drei neue Orte (Lampenraum im Leuchtturm, Stube des Hafenmeisters, Klippenpfad)? Alle Messwerte in
`measure.json`, Bilder in `assets/sheet.png` und `assets/<ort>_scene.png`.

## Vorgehen

1. **Prompts** (`scripts/build_prompts.py`): Stilblock wörtlich aus `styles/pc98-adventure/prompts/bg.txt` ohne die
   hafenbezogenen Sätze (Kamera „onto the harbour“, Bildaufbau, Leuchtfeuer/Rauch); einzige Wortänderung: die
   Konturliste „every building, boat, rock, barrel and post“ wurde zu „every wall, beam, piece of furniture, rock,
   post and object“. Ortsblock, FREE_EN, Effektliste, guards und Format per `importlib` wörtlich aus
   `styles/hintergrund-serie/tools/prompts.py`. Serienregeln für alle drei Orte gleich: Abenddämmerung wie der Hafen,
   Licht (innen Lampe/Kerze/Feuer, außen Horizontband, Schatten blauviolett), Augenhöhe/Horizont bei 45 %, randlos,
   oben und unten 6 % frei (Bildfenster schneidet), Mitte unten ruhig für ein späteres Porträt.
2. **Experiment am Leuchtturm**: A mit dem Hafenbild des Stils als Stilreferenz (Ankerabsatz nach ANCHOR_EN: nur
   Machart, nicht Aufbau), B ohne Referenz. Gewählt: **A** (Begründung unten).
3. **Serie** mit Variante A: leuchtturm (neu, mit korrigierter Serienregel), stube, klippe. Dazu eine Gegenprobe
   klippe_b ohne Referenz, weil klippe A Teile des Ankers kopierte.
4. **Verarbeitung** (`scripts/build_ort.py`, nutzt `pc98lib` des Eintrags): BOX auf 416×279, Zeilen 10–265 als
   Bildfenster 416×256, Palette, Musterdithering (5 Stufen, Bayer 4×4, bildschirmfest), Licht auf Register 14,
   Blitz/Leuchtfeuer auf Register 15 (nur auf Pixeln der Aus-Farbe), Wasser in 3 Einzelbildern. Drei Palettenwege
   verglichen: feste Hafen-Palette, eigene Palette je Bild, **gemeinsame Serienpalette** (5 feste Akzente + 9 k-means
   über Hafen + 3 Orte, je Bild gleich gewichtet). Die Godot-Szenen nutzen die Serienpalette.
5. **Godot** (`styles/ortsserie/demo/pc98-adventure/`): `leuchtturm.tscn`, `stube.tscn`, `klippe.tscn` (Wurzel Node2D,
   Skript `scripts/ort.gd` mit `ort`), Indexbild im SubViewport 640×360, Palettenshader, ×2 auf 1280×720, Oberfläche
   wie pc98-adventure (`scripts/ui.gd`, DotGothic16-Atlas) ohne Figur: Ortsfenster, Befehlsmenü, Objektliste des Ortes
   (grau), Erzähltext Zeichen für Zeichen, danach ▼. Zeit aus dem Bildzähler.
6. **Messen** (`scripts/metrics.py`, `scripts/measure.py`), Bogen (`scripts/make_sheet.py`).

Neu bauen (aus dem Projektordner):

```
ORTSSERIE_SCRATCH=<scratch> .venv/bin/python styles/ortsserie/pc98-adventure/scripts/build_ort.py \
    leuchtturm stube klippe --alt leuchtturm_a leuchtturm_b klippe_b --palette serie
ORTSSERIE_SCRATCH=<scratch> .venv/bin/python styles/ortsserie/pc98-adventure/scripts/measure.py --frames <aufnahme>
.venv/bin/python styles/ortsserie/pc98-adventure/scripts/make_sheet.py
```

## Ergebnis

- **Erzeugungen: 6 von 10** (leuchtturm_a, leuchtturm_b, leuchtturm, stube, klippe, klippe_b), alle agy, je
  1264×848 statt 1536×1024, `verbatim: true`, 65–91 s (klippe 186 s, weil ein agy-Konto gesperrt meldete und
  genimg.py auf das nächste auswich; Sperren zählen nicht).
- **Stube und Klippe im ersten Versuch brauchbar, der Lampenraum in der dritten Erzeugung** (A und B kamen mit
  gemaltem Rahmen, danach wurde die Serienregel geändert, siehe Probleme), alle im Stil des Hafens: dunkle 1-px-Konturen, Zellschattierung,
  gerasterte Himmelsbänder, Pseudo-Pixelraster 2,7–3,1 px (Anker 3,11 px). Detailmaß 1,01–1,23 × Anker (Codex-Serie:
  1,21–1,33 × ihren Anker). Palettenabstand roh zum Anker: Leuchtturm 6,1, Stube 5,1, Klippe 2,5 ΔE (Innenräume haben
  andere Inhaltsfarben: Kalkwand, Holz, Messing).
- **Experiment A/B**: A näher an der Ankerpalette (5,07 gegen 5,57 ΔE), Pixelraster 2,88 px (B: keine klare
  Periode, 8,65 px), Himmel im Fenster mit denselben Rasterbändern wie der Hafen; keine messbare Layout-Kopie
  (Kanten-Korrelation A 0,25, B 0,26, unabhängige Bilder 0,15–0,32; keine Kachel kopiert). Beide malten einen
  Bildrahmen (siehe Probleme).
- **Layout-Kopie bei der Klippe**: Mit Referenz übernahm agy die obere Hälfte des Hafens fast unverändert (Kachel
  Mitte oben r = 1,00, |ΔL| = 0,01; rechts oben mit Leuchtturm und Felsnase r = 0,93, |ΔL| = 0,02; der Lampenkasten
  liegt im verkleinerten Bild an derselben Stelle wie im Hafen). Innenräume kopierten nichts. klippe_b ohne
  Referenz: eigener Aufbau, aber Meer graulila statt dunkelblau (Palettenabstand 4,19 statt 2,52).
- **Palette** (Verlust = ΔE zwischen Quelle und Raster, beide 4×4 gemittelt): feste Hafen-Palette im Mittel über
  Hafen + 3 Orte 3,42; Serienpalette 2,94; eigene Palette je Ort 2,44 (Orte allein). Die **feste Hafen-Palette hält
  Himmel und Meer, verliert aber die Kalkwand** (c7c6d4 → Creme ebdab9, ΔE 9,1 auf 20 % des Leuchtturmbilds) und
  macht den **Kerzenschein der Stube zur Pfirsichscheibe** (c0a7a7 → e89979, ΔE 8,1); Messing wird oliv. Die
  **Serienpalette** trifft Wände und Licht, kostet aber **Holzbraun** (9d6a52 → rosabraun 966665, ΔE 4,2 auf 10 % des
  Leuchtturms) und **Abendviolett** (Hafen ac6587 → 996a6e, ΔE 6,1; Klippe 6,3); der Hafen selbst verliert mit ihr
  0,7 ΔE (2,58 → 3,28). Ein zusätzlich fester Holz- oder Violettton verbessert das Mittel nicht (3,08–3,15).
  Eigene Paletten je Ort verlieren das Indigo der Fensterhimmel und ändern die Rahmenfarben der Oberfläche.
- **Godot**: je Szene 180 Bilder aufgenommen, keine Fehler, 14–16 Farben je Bild, 0 Bilder außerhalb des 12-Bit-
  Rasters, ganzzahlig ×2. Bewegung sparsam wie im Eintrag: Leuchtturm Linse atmet (Register 14) + warmer Lichtring
  auf der Wand alle 3 s (Register 15) + Glanz im Meer der Fenster; Stube Feuer- und Kerzenschein flackern
  (1796 Pixel auf Register 14) + ferner Leuchtturm blitzt (11 Pixel) + Glanz im Fenster; Klippe Leuchtfeuer mit
  Strahl + Fenster im Hafen und am Leuchtturmhaus (13 Pixel) + Glanzstriche. Stube 40 s aufgenommen: Bild 1170
  gleich Bild 450 (alles periodisch, Periode 720 Bilder), keine Drift.
- **Handarbeit** je Ort 9–11 Einträge (21–30 von Hand gesetzte Zahlen: Kästen, Mittelpunkt, Ringe, Wasserkästen,
  Schnitt), geschätzt 10–20 Minuten je Ort plus Texte.

## Probleme

- Die erste Serienregel („the picture is shown inside a framed window“) ließ agy in A **und** B einen Rahmen ins
  Bild malen (22 bzw. 34 px). Für die Serie ersetzt durch „fills the whole canvas from edge to edge, with no painted
  frame“; danach kein Rahmen. Deshalb wurde der Leuchtturm ein drittes Mal erzeugt, damit alle drei Orte denselben
  Serienblock haben.
- Klippe (A) kopiert Himmel und Leuchtturm des Ankers (siehe oben). Für das Spiel brauchbar, aber der Leuchtturm
  steht vom Klippenpfad aus genau wie vom Kai.
- Zusätzliche Gegenstände: Stube ein Fass, leuchtturm_a eine Deckenlampe und vier Fenster, leuchtturm_b fünf.
  agy malte trotz „no halo“ gerasterte Lichthöfe um Linse und Kerze; sie passen zum Stil und tragen jetzt den
  Lichtring des Leuchtturms.
- Mit der Serienpalette fand das Neurastern mit Register 14 im Kamin nur 7 Pixel (Feuerschein liegt näher an
  Pfirsich/Creme als an ffeeaa). Lösung: „swap“ – Pixel einer Registerfarbe mit warmer Quelle in den Kästen auf
  Register 14 legen, Grundwert = diese Farbe, Flackern um sie herum.
- Der Lichtring des Leuchtturms auf Creme (eeddbb → ffffcc) war kaum sichtbar; Aus-Farbe von Hand auf die helle
  Wand (cccccc) gelegt.
- „Stube des Hafenmeisters“ füllte das Ortsfenster bis zum Rahmen; Ortsname jetzt „Hafenmeisterstube“.
- Bewegung ist klein (0,4–1,8 % des Bildfensters ändern sich in 6 s überhaupt), wie bei den Vorbildern.
- `.gitignore` deckt mit `styles/*/assets/raw/*` den verschachtelten Ordner `styles/ortsserie/pc98-adventure/assets/raw/`
  nicht ab: die sechs Rohbilder (je etwa 1,3 MB) würden mit eingecheckt. Die Begleit-JSON enthielten Sitzungs-ID,
  Kontoname und absolute Pfade; `scripts/sanitize_raw.py` hat diese Felder entfernt bzw. Pfade relativ gemacht.
- Im Testprojekt meldet `--import` zwei Fehler, weil `res://main.tscn` (Hauptdemo) noch fehlt; die drei Szenen selbst
  laufen ohne Fehler.
- Der Hafen des Eintrags pc98-adventure hat seine eigene Palette; im Spiel müsste er mit der Serienpalette neu
  gerastert werden (`assets/hafen_bg_serie.png` zeigt ihn statisch).

## Lehren

- agy hält diesen Stil über Orte gut, solange der Stilblock Hardware und Technik beschreibt; mit der randlosen
  Serienregel war jeder Ort im ersten Versuch brauchbar (vorher zwei Lampenraum-Fassungen mit gemaltem Rahmen).
- Eine Stilreferenz hilft bei Palette und Raster, aber bei Orten, die Motive des Ankers teilen (Himmel, Leuchtturm),
  kopiert agy diese Teile fast pixelgleich. Innenräume: Referenz unbedenklich. Außenorte: Kacheln gegen den Anker
  messen; ob ein Referenzausschnitt ohne Leuchtturm hilft, ist ungetestet.
- Wörter über den Bildschirm („framed window“) malt agy ins Bild. Bildaufbau-Regeln randlos formulieren.
- Den Serien-Look trägt bei diesem Stil vor allem die Pipeline: eine gemeinsame 16-Farben-Palette für alle Orte
  (k-means mit festen Akzenten über alle Bilder) und dasselbe Musterdithering. Die Palette des ersten Ortes für alle zu
  nehmen geht nur, wenn die neuen Orte dieselben Materialien zeigen. 16 Farben für Hafen, Kalkwand, Holz, Messing und
  Abendhimmel sind ein Kompromiss (Holz oder Violett leidet).
- Die Palette gleicht Farbwerte an, nicht den Farbton eines anders gemalten Bildes (klippe_b bleibt graulila).
- Licht je Ort: Neurastern mit Register 14 passt für Lampen nahe am Grundwert; für Feuerschein die vorhandenen
  Rasterpixel einer Farbe auf das Register tauschen. Blitzringe nur auf einer Aus-Farbe mit Kontrast zur An-Farbe.

## Dateien

- `scripts/`: `build_prompts.py`, `build_ort.py`, `metrics.py`, `measure.py`, `make_sheet.py`, `sanitize_raw.py`
- `assets/`: `jobs_ab.json`, `jobs_rest.json`, `jobs_klippe_b.json`, `prompts/*.txt`, `raw/` (6 Bilder + JSON),
  `<ort>_bg.png` (Blitz aus), `<ort>_bg_lit.png`, `<ort>_bg_{fixed,serie,own}.png`, `hafen_bg_{fixed,serie}.png`,
  Gegenproben `*_bg_*.png`, `build_stats.json`, `sheet.png`, `<ort>_scene.png`
- Demo: `styles/ortsserie/demo/pc98-adventure/` (`<ort>.tscn`, `scripts/ort.gd`, `scripts/ui.gd`,
  `shaders/palette.gdshader`, `fonts/` DotGothic16-Atlas mit OFL-Text, `art/<ort>/` Indexbilder und `meta.json`)
