[Deutsch lesen → README.de.md](README.de.md)

# Spielgrafik

**One scene, many game-art styles.**

A catalogue of 86 game-art styles and techniques (67 styles, 19 techniques), from 1-bit pixel art via
home-computer graphics, watercolour and woodcut to PS1-style 3D and toon shading. Every entry shows the same
scene: the harbour of Lornholm at dusk, crossed by the badger courier. Everything is made in-house with AI
images, code, Blender and Godot, and every entry runs as a short Godot demo with a recording, ratings, the prompts
of its AI images and an honest account of what worked and what did not.

**[Open the catalogue](https://grundhofer.github.io/spielgrafik/)** (the site is in German)

## What this is about

The catalogue is used to choose a visual style for our game project; the first game will be a text adventure.
Because every entry shows the same scene, styles can be compared directly. Each entry asks: can we produce this
style ourselves, repeatably, from AI images, scripts and a game engine?

- **Catalogue:** all entries with demo video, filterable by family and kind.
- **Comparison:** five ratings per entry (fit for the text adventure, AI contribution, consistency, effort,
  estimated mobile suitability), sortable.
- **Techniques:** building blocks such as animation, lighting, tiles and surfaces, and which styles use them.
- **Text adventure:** the entries ranked by their fit for our first game.
- **Tools:** the tool chain, the shared scene and character, the honesty rules and licence notes.

## Project structure

| Path | Contents |
| --- | --- |
| `styles/<slug>/` | One entry: `style.json` (fact sheet), `assets/` (processed assets), `demo/` (standalone Godot 4.7 project), `scripts/` and `blender/` (build scripts), `media/` (recording), `prompts.json` (prompts of the AI images) |
| `styles/<slug>/assets/raw/` | Raw AI images; only those an entry shows are committed |
| `shared/badger/` | Reference sheet of the badger courier |
| `shared/3d/` | Shared 3D base: harbour scene and rigged badger as glTF, built by Blender scripts, plus a Godot sample scene ([README](shared/3d/README.md)) |
| `data/catalog.json` | Families and all entries with their brief |
| `data/motif.json` | The shared scene and character, including the English prompt blocks |
| `data/legal.json` | Details for the legal notice; the only place they are stored |
| `tools/` | Image generation (`genimg.py`, `imagequeue.py`), sprite processing (`sprites.py`), recording (`capture.py`), prompt collection (`collect_prompts.py`) |
| [`PIPELINE.md`](PIPELINE.md) | How an entry is built (in German): folder layout, tools, image generation, Godot, Blender, self-check, `style.json` schema |
| `site/`, `build.py` | Page style, page script, fonts and the static site generator |
| `tests/` | Tests for `build.py` and `tools/collect_prompts.py` with small fixtures |
| `docs/` | Generated site; not committed |

## Build and test

The site generator needs Python 3.12+ and only the standard library. If `cwebp` (or `sips` on macOS) is
installed, large images get a smaller WebP copy.

```sh
python3 build.py
python3 -m http.server 8000 --directory docs
python3 -m unittest discover -s tests -v      # or: python3 -m pytest -q
```

GitHub Actions builds the site from the repository, runs the tests and deploys `main` to GitHub Pages.

## Building an entry

[PIPELINE.md](PIPELINE.md) is the contract for every entry. The tools need more than the site generator:

- `tools/sprites.py` and `tools/capture.py`: Python with Pillow and NumPy; `capture.py` also needs Godot 4.7 and
  ffmpeg. `genimg.py` calls `sprites.py` when it has to key out a background.
- `tools/genimg.py`: a logged-in [Codex CLI](https://github.com/openai/codex) (gpt-image) or Antigravity CLI
  (Gemini image model). Next to every image it writes a JSON file with the prompt; `tools/collect_prompts.py`
  turns these into the committed `prompts.json`.
- 3D entries: Blender 5.2 LTS, run headless by script.

```sh
python3 tools/genimg.py --out styles/<slug>/assets/raw/bg.png --size 1536x1024 \
  --prompt-file p.txt --ref shared/badger/master_sheet.png
python3 tools/sprites.py pixelize in.png out.png --width 320 --palette ega
godot --headless --path styles/<slug>/demo --import
python3 tools/capture.py styles/<slug>
python3 tools/collect_prompts.py && python3 build.py
```

## Labelling and licence

AI images are generated with gpt-image (OpenAI) via Codex CLI or with Google's Gemini image model via
Antigravity CLI and are labelled as such on the site.
Code: [MIT](LICENSE). Texts: [CC BY 4.0](LICENSE-CONTENT.md). Images, videos and 3D models:
[CC0](LICENSE-CONTENT.md). Prompts: free to use.
Third-party code and data: [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) and the licence list of each entry.
Fonts: Inter and IBM Plex Mono on the site, the demo fonts in each entry's `fonts/` folder, all under their own
licences (SIL Open Font License 1.1 or CC0); the site serves its fonts itself and loads nothing from Google Fonts.
The legal notice details in `data/legal.json` are not covered by these licences.
Names of games, consoles and studios describe a historical style; they belong to their owners, and this project is
not affiliated with them.

Sister project: [Bildsprache](https://github.com/grundhofer/bildsprache), image styles for AI images by use case.

© Sebastian Grundhöfer
