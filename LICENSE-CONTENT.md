# Lizenz der Inhalte / Content license

## Texte / Texts: CC BY 4.0

**Creative Commons Namensnennung 4.0 International (CC BY 4.0)** gilt für die redaktionellen Texte dieses
Repositorys: die Steckbriefe in `styles/*/style.json`, der Katalog und die Szenenbeschreibung in
`data/catalog.json` und `data/motif.json`, die Anleitungen und Notizen (`PIPELINE.md`, `shared/3d/README.md`,
weitere `*.md` in `shared/` und `styles/`) sowie die README-Dateien.

Applies to the editorial texts in this repository: the entry fact sheets in `styles/*/style.json`, the catalogue
and scene description in `data/catalog.json` and `data/motif.json`, the guides and notes (`PIPELINE.md`,
`shared/3d/README.md`, other `*.md` files in `shared/` and `styles/`) and the README files.

Empfohlene Namensnennung / Suggested attribution:

> Spielgrafik von Sebastian Grundhöfer, CC BY 4.0
> https://github.com/grundhofer/spielgrafik

Lizenztext / License text: https://creativecommons.org/licenses/by/4.0/legalcode.de ·
https://creativecommons.org/licenses/by/4.0/legalcode

Prompts sind kurze, funktionale Anweisungen (`styles/*/prompts.json`, `styles/*/prompts/`, die englischen Blöcke
in `data/motif.json`). Kopiere und verwende sie ohne Einschränkung.
Prompts are short functional instructions (`styles/*/prompts.json`, `styles/*/prompts/`, the English blocks in
`data/motif.json`). Copy and use them without restriction.

## Bilder, Videos und 3D-Modelle / Images, videos and 3D models: CC0 1.0

Die Bilder entstehen auf zwei Wegen:

- **KI-Bilder.** Hintergründe, Figuren, Requisiten und Texturen sind mit gpt-image (OpenAI) über Codex CLI oder
  mit dem Gemini-Bildmodell (Google) über Antigravity CLI erzeugt und oft per Skript weiterverarbeitet
  (freigestellt, zerlegt, auf Pixelraster und Palette gebracht). Rein KI-generierte Bilder sind in vielen
  Rechtsordnungen, in Deutschland in der Regel, nicht urheberrechtlich geschützt.
- **Eigene Renderings und Aufnahmen.** Die Aufnahmen der Godot-Demos (`styles/*/media/`: Video, Standbild, GIF,
  Kontaktbogen), Blender-Renderings, prozedural erzeugte Bilder und die 3D-Modelle (`*.glb`, etwa in `shared/3d/`)
  entstehen per Skript in Godot und Blender.

Soweit an diesen Bildern, Videos und Modellen überhaupt Rechte bestehen, werden sie unter
**CC0 1.0 Universal** gemeinfrei gestellt. Diese Erklärung schafft Klarheit, ersetzt aber keine Rechtsberatung.

The images come from two sources:

- **AI images.** Backgrounds, characters, props and textures are generated with gpt-image (OpenAI) via Codex CLI
  or with Google's Gemini image model via Antigravity CLI, and often processed further by script (keyed, sliced,
  snapped to a pixel grid and palette). Purely AI-generated images are not protected by copyright in many
  jurisdictions, generally including Germany.
- **Own renders and recordings.** The recordings of the Godot demos (`styles/*/media/`: video, still, GIF,
  contact sheet), Blender renders, procedurally generated images and the 3D models (`*.glb`, e.g. in
  `shared/3d/`) are made by script in Godot and Blender.

To the extent any rights exist in these images, videos and models, they are dedicated to the public domain under
**CC0 1.0 Universal**. This statement provides clarity but is not legal advice.

https://creativecommons.org/publicdomain/zero/1.0/

Bitte kennzeichne KI-erzeugte Bilder bei Weiterverwendung als KI-generiert.
Please label AI-generated images as such when you reuse them.

## Nicht von diesen Lizenzen erfasst / Not covered

- **Inhalte Dritter.** Code und Daten Dritter stehen in `THIRD_PARTY_NOTICES.txt`; fremde Texturen (CC0, etwa von
  Poly Haven oder ambientCG) und andere fremde Bestandteile nennt die Lizenzliste des jeweiligen Eintrags
  (`style.json` → `licenses`, auf der Website unter „Lizenzen“). Sie behalten ihre eigene Lizenz. / Third-party
  code and data are listed in `THIRD_PARTY_NOTICES.txt`; third-party textures (CC0, e.g. from Poly Haven or
  ambientCG) and other third-party parts are named in each entry's licence list. They keep their own licences.
- **Schriften.** Die Website liefert Inter und IBM Plex Mono selbst aus (`site/fonts/`), unter der SIL Open Font
  License 1.1 (Lizenztexte daneben, Herkunft und Prüfsummen in `site/fonts/fonts.json`). Die Schriften der Demos
  liegen mit ihrem Lizenztext (SIL Open Font License 1.1 oder CC0) im Ordner `fonts/` des Eintrags. Weder MIT noch
  CC BY oder CC0 gelten für sie. / The site serves Inter and IBM Plex Mono itself (`site/fonts/`) under the SIL
  Open Font License 1.1; the demo fonts sit with their licence text (OFL 1.1 or CC0) in the entry's `fonts/`
  folder. Neither MIT nor CC BY or CC0 applies to them.
- **Impressum.** Die Anbieterangaben in `data/legal.json` (Name, Anschrift, E-Mail-Adresse, Umsatzsteuer-ID) sind
  Pflichtangaben für das Impressum und stehen unter keiner der Lizenzen oben. / The provider details in
  `data/legal.json` (name, address, email address, VAT ID) are the required details for the legal notice and are
  not covered by the licenses above.
- **Spiel- und Markennamen.** Namen von Spielen, Konsolen, Heimcomputern, Studios und Programmen stehen nur als
  Beschreibung eines historischen Stils oder eines Werkzeugs in den Texten; sie gehören ihren Inhabern, und dieses
  Projekt steht in keiner Verbindung zu ihnen. / Names of games, consoles, home computers, studios and software
  appear only to describe a historical style or a tool; they belong to their owners, and this project is not
  affiliated with them.
