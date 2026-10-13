# painterly-digital – Stand

Stand 12.10.2026: fertig (`status: done`). Demo läuft mit den getrennt erzeugten Ebenen, aufgenommen (`media/`).

- Hauptbild `assets/raw/master.png` (agy) ist Stil- und Motivreferenz.
- Ebenen: `assets/raw/{backdrop,headland,harbour,boats,foreground}.png` (Codex, Bildwarteschlange 12.10.), mit
  `scripts/build_sep_layers.py` verkleinert, Alpha korrigiert (≥250 → 255), Boote einzeln, Vordergrund in zwei
  Eckteile. Lage und Maßstab in `assets/sep/layout.json`; dieselben Zahlen stehen in `demo/main.tscn`/`main.gd`.
- Figur: `assets/raw/badger_side.png` (agy), Schnittfigur aus `scripts/build_badger.py`.
- Laufblatt `assets/raw/badger.png` (Codex) erzeugt, aber nicht eingebaut (Zeile 2 wiederholt Zeile 1, siehe
  `style.json` → pitfalls).
- Frühere Fassung (Ebenen aus dem Gemälde geschnitten): `scripts/build_layers.py` → `assets/layers/`, nur Vergleich.
  Prozeduraler Vordergrund aus `scripts/build_fx.py` → `assets/fx/foreground.png`, nur Vergleich.
- Prüfung: `scripts/measure_badger.py OUTDIR` (Standfuß, Fußzeile, Kopf), `scripts/probe.py OUTDIR --keep
  [--method mobile|gl_compatibility]`. Temporäre Dateien in `$TMPDIR/painterly-digital/`.

Bildaufträge (`assets/image_jobs.json`): 1 übersprungen (schon vorhanden), 2–7 am 12.10. erzeugt. Insgesamt
8 Bilder (Hauptbild, Figur, 6 aus der Warteschlange), keine direkten Nachbesserungen.

Neu bauen: `scripts/build_sep_layers.py`, dann `godot --headless --path demo --import`,
`tools/capture.py styles/painterly-digital --poster-at 0.9`.
