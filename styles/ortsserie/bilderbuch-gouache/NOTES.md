# Ortsserie · Bilderbuch & Gouache (agy)

Stand 13.10.2026. Frage: Hält agy (Gemini-Bildmodell) den Look des Eintrags `bilderbuch-gouache` über drei neue
Orte (Lampenraum im Leuchtturm, Stube des Hafenmeisters, Klippenpfad)? Alle Messwerte stehen in `measure.json`,
die Bögen in `assets/sheet.png` (Anker + drei Orte) und `assets/ab_sheet.png` (Experiment).

## Vorgehen

- **Prompt** (`scripts/make_jobs.py`, lesbar in `assets/prompts/*.txt`): [nur Variante A: Ankerabsatz] + Stilblock +
  Bildaufbau mit Serienregeln + Ortsblock + Effekte, die Godot animiert + freier Boden + `guards_en` + Format.
  Stilblock aus `bilderbuch-gouache/scripts/make_jobs.py` (Sätze 1, 2, 6 wörtlich; in 3–5 nur Leuchtturm, Häuschen,
  Kai durch allgemeine Wörter ersetzt). Ortsblock, `anim` und `anchor_extra` sowie `FREE_EN` werden aus
  `hintergrund-serie/tools/prompts.py` importiert (wörtlich, ohne Bytecode-Cache dort). Serienregeln für alle Orte
  gleich: Abend wie der Hafen, Horizont 46 %, Laufband ab 70 %, ruhige Fläche 25–72 % Breite bis 33 % Höhe für den
  Text (außen Himmel, innen Wand oder Decke).
- **Erzeugung:** nur `genimg.py --backend agy`, `--workers` ≤ 2. **6 von 10 Erzeugungen**: `leuchtturm_a` 2 (der
  erste Aufruf endete mit „image failed to generate: no image generated in response“, Beleg
  `assets/raw/leuchtturm_a.fail.json`), `leuchtturm_b` 1, `stube` 1, `klippe` 1, `klippe_b` 1 (Nachprüfung des
  Experiments an einem Außenort). Alle 1264×848 statt 1536×1024, alle `verbatim: true`, 60–72 s je Bild
  (`leuchtturm_b` 123 s laut .json; in dem Lauf war ein agy-Konto gesperrt und genimg.py nahm das nächste).
- **Experiment am Leuchtturm** (A = Hafenbild des Stils als einzige Referenz + Ankerabsatz „nur Malweise“, B = ohne
  Referenz), wiederholt an der Klippe. Beide Varianten im selben mittigen Schnitt gemessen:

  | | Layout r Kanten / Grau | Palettenabstand (± Streuung) | Detail ×Anker (Gradient / Kanten) |
  |---|---|---|---|
  | Leuchtturm A | 0,15 / −0,08 | 3,82 ± 0,43 | 1,38 / 1,52 |
  | Leuchtturm B | 0,22 / 0,06 | 3,23 ± 0,26 | 2,50 / 2,92 |
  | Klippe A | 0,13 / 0,30 | 2,49 ± 0,30 | 1,03 / 1,05 |
  | Klippe B | 0,20 / 0,20 | 3,20 ± 0,30 | 1,38 / 1,48 |

  Vergleich: gleiches Motiv in anderen Einträgen (18 Hafenbilder) Kanten-r 0,19 ± 0,05 (höchstens 0,27); andere
  Orte der Codex-Serie −0,05 bis 0,15. Rauschboden des Palettenmaßes (Anker gegen sich selbst) 1,1.
  **Gewählt: A.** A kopiert das Hafen-Layout nicht (Kanten-r unter dem Wert für „gleiches Motiv“ und unter B) und
  hält Strich und Detailgrad des Ankers (×1,0–1,4 statt ×1,4–2,5). Beim Palettenabstand ist das Bild gemischt
  (Leuchtturm B näher, Klippe A näher). Angesehen: B malt dünne dunkle Konturen, mehr Kleinkram und baut Motiv-
  Klischees ein (Häuser und Wolken im Lampenraum, Häuschen auf der Klippe); A sieht aus wie dieselbe Hand.
- **Verarbeitung** (`scripts/build_orte.py`): Papierrand automatisch gefunden (`paperframe.py`, 10 px eingerückt,
  Ränder geprüft), 16:9 mittig; Außenorte automatisch auf die Horizontzeile des Hafens geschnitten (Klippe 339 → 389,
  Hafen 410; mehr gab der Rand nicht her). Effekte mit der Pinselbibliothek des Eintrags (`fx_orte.py`: Lichthöfe,
  Strahlen, Glitzer, Sterne aus `bilderbuch-gouache/scripts/build_scene.py`, neu Flammen-Tupfer, Dampf,
  Lichtwanderung). Sterne, Dorffenster, Grasbüschel (Wind) und Textlage automatisch; Textfarbe nach Helligkeit der
  Stelle (Creme im Himmel, dunkle Tinte #3b3352 auf heller Wand), Kontrastprüfung, dunkler Fleck nur bei Kontrast
  < 3 (nirgends nötig).
- **Godot** (`styles/ortsserie/demo/bilderbuch-gouache/`): `<ort>.tscn` (Wurzel Node2D) + `ort.gd` liest
  `art/<ort>.json`; `shaders/paper.gdshader` (Papierkorn wie im Hafen), `shaders/sway.gdshader` (Wind im Gras).
  Zeit aus dem Bildzähler, `autoplay = false` + `set_time(t)` für die Hauptdemo; Prüfschalter `-- --only=bg`,
  `--no-text`, `--no-fx`, `--t0=`. Getestet in einer Kopie (Import, je 180 Bilder Movie Maker): keine Fehler, Klippe
  zweimal bitgleich, Bewegung in jedem 0,5-s-Abstand (`measure.json` → `godot`).

## Ergebnis je Ort (Variante A, Maße am Spielbild)

| Ort | Versuche | Palettenabstand | Detail ×Anker | Textfläche L-Streuung (Hafen 2,4) | Handarbeit |
|---|---|---|---|---|---|
| Leuchtturm | 2 (1. ohne Bild) | 3,82 | 1,38 | 0,5, dunkle Schrift, 2 Zeilen | 1 Punkt, 2 Rechtecke, ~10 min |
| Stube | 1 | 4,55 | 1,49 | 2,0, dunkle Schrift, 2 Zeilen | 4 Punkte, ~12 min |
| Klippe | 1 | 2,20 | 0,99 | 1,8, helle Schrift im Himmel | 1 Punkt, 3 Rechtecke, ~12 min |

Codex-Serie (`hintergrund-serie`) mit denselben Maßen gegen ihren eigenen Anker: Palettenabstand 2,4–3,1, Detail
×1,20–1,24. Die agy-Gouache-Serie streut stärker: die Klippe liegt näher am Anker (Detail ×0,99, Palette 2,2),
die Innenräume weiter weg (×1,38 und ×1,49, Palette 3,8 und 4,6).

## Probleme

- Innenräume sind heller als der Abend-Anker (mittleres Oklab-L 75 und 67 gegen 62): weiß gekalkte Wände wie am Tag,
  nur die Fenster zeigen Dämmerung. Der Text steht dort dunkel auf der Wand statt hell im Himmel.
- Leuchtturm: die Fenster zeigen nur den Himmelsverlauf mit Sternen und Abendband, kein Meer, keine Wolken (Ortsblock
  verlangt beides); deshalb kein Glitzern dort. Die Decke ist salbeigrün statt Holz.
- Stube: der Tisch steht mit zwei Stühlen im Raum statt an der Rückwand; das Laufband ist in der Mitte nicht frei.
- Kerze (Stube) und Leuchtturmlampe (Klippe) kamen mit gemaltem Lichtschein, obwohl der Prompt ihn verbot; die
  animierten Lichthöfe liegen darüber.
- Die Dorffenster der Klippe und der Kerzenschein flackern kaum sichtbar (0,1–1,3 % der Pixel im Bereich ändern sich).
  Der Dampf wirkt etwas wie Blasen.
- Das Palettenmaß schwankt je Lauf um ±0,3–0,4 und hat einen Rauschboden von 1,1; Unterschiede unter etwa 0,7 sind
  nicht belastbar.
- Die `.gitignore` des Projekts schließt nur `styles/*/assets/raw/*` aus, nicht `styles/ortsserie/*/assets/raw/`.
  Rohbilder (6,8 MB) und Begleitdateien würden mit eingecheckt. Die Begleitdateien sind deshalb bereinigt
  (`scripts/sanitize_raw.py`: keine Sitzungs-ID, kein Kontoname, keine absoluten Pfade). Für den Orchestrator offen.
- Nicht geprüft: Renderer `mobile`/`gl_compatibility`, Figur in den Orten.
- `godot --import` im Projekt meldet „Cannot open file 'res://main.tscn'“, weil die Hauptszene noch fehlt (baut der
  spätere Agent). Die Ortsszenen selbst laufen ohne Fehler und Warnungen.
- In `styles/hintergrund-serie/tools/__pycache__/` liegt seit 20:02 eine `prompts.cpython-313.pyc`. Sie stammt nicht
  aus diesem Teil (alle Läufe hier mit `-B` bzw. `sys.dont_write_bytecode`), sondern aus
  `painterly-digital/scripts/prompts.py` (gleiche Minute wie dessen erste Aufträge; dort inzwischen behoben, siehe
  `painterly-digital/NOTES.md`). Nicht angefasst, das Löschen übernimmt der Besitzer.

## Lehren

- agy mit dem eigenen Hafenbild als Stilreferenz und dem Absatz „nur Malweise, nicht Aufbau“ hält den Look über
  drei Orte, ohne das Layout zu kopieren. Ohne Referenz driftet agy beim selben Stilblock zu detailreicherem
  Bilderbuch-Cartoon mit Konturen.
- Effekt-Lagen in Rohbild-Pixeln speichern, nicht in Bildschirmpixeln: ein geänderter Schnitt verschiebt sie sonst
  (breiterer Rand: bis 4 px, Horizont-Ausrichtung der Klippe: rund 48 px).
- Die Textlage lässt sich automatisch finden (ruhigste Stelle aus Gradientenenergie + Helligkeitsstreuung, ein- oder
  zweizeilig); die Streuung verhindert, dass der Text auf einer weichen Kante zwischen Decke und Wand sitzt.

## Nachbau (aus dem Projektordner)

1. `.venv/bin/python -B styles/ortsserie/bilderbuch-gouache/scripts/make_jobs.py`
2. `.venv/bin/python tools/genimg.py --backend agy --jobs styles/ortsserie/bilderbuch-gouache/assets/jobs_ab.json --workers 2`,
   ebenso `jobs_serie.json` und `jobs_ab_klippe.json`; danach `scripts/sanitize_raw.py`
3. `.venv/bin/python -B styles/ortsserie/bilderbuch-gouache/scripts/build_orte.py` (Hintergründe, Effekte,
   `art/<ort>.json`, `assets/build.json`)
4. `scripts/measure.py`, dann `scripts/make_sheet.py`; nach einem Movie-Maker-Lauf in einer Kopie des Demo-Ordners
   `scripts/motion_check.py <ordner>` (ergänzt `measure.json` → `godot`)
