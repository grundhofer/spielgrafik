#!/usr/bin/env python3
"""Baut die Website des Spielgrafik-Katalogs nach docs/.

    python3 build.py                                   # Projektdaten -> docs/
    python3 build.py --root tests/fixtures --out DIR   # anderer Datenstand (Tests)
    python3 build.py --copy-only                       # Bilder nur kopieren, nicht verkleinern

Quellen (relativ zu --root):
  data/catalog.json              Familien und alle Einträge, auch ungebaute (werden als „geplant“ gezeigt)
  data/motif.json                gemeinsame Szene und Figur
  styles/<slug>/style.json       Steckbrief eines gebauten Eintrags (Schema: PIPELINE.md)
  styles/<slug>/media/           poster.webp, demo.mp4, preview.gif, frames.jpg (tools/capture.py)
  styles/<slug>/prompts.json     Prompts der KI-Bilder (tools/collect_prompts.py, eingecheckt)
  shared/badger/master_sheet.png Referenzblatt der Figur
Seitenstil, Seitenskript, Theme-Skript und Schriften (site/fonts/) liegen in site/, die Hinweise zu Code Dritter in
THIRD_PARTY_NOTICES.txt, die Angaben für das Impressum in data/legal.json (alle immer aus diesem Projekt).

Nur Standardbibliothek. Große PNG/JPEG-Assets werden mit cwebp (sonst sips) verkleinert, wenn eines davon
installiert ist; sonst wird das Original kopiert und gezeigt. Der Build bricht bei Datenfehlern ab, statt eine
halbe Seite auszuliefern; er baut in ein Zwischenverzeichnis und tauscht erst am Ende.
"""
import argparse, hashlib, html, json, pathlib, re, shutil, struct, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent
SITE_SRC = ROOT / "site"
SITE_URL = "https://grundhofer.github.io/spielgrafik"
REPO_URL = "https://github.com/grundhofer/spielgrafik"
SIBLING_URL = "https://grundhofer.github.io/bildsprache/de/"

# Hell/Dunkel: Aufbau wie bildsprache/web/theme.py, eigene Signalfarbe (Petrol statt Rot).
PALETTES = {
    "light": {
        "ground": "#FFFFFF", "surface": "#FFFFFF", "surface-2": "#F2F2F2",
        "ink": "#0B0B0B", "ink-2": "#3A3A3A", "ink-3": "#5E5E5E",
        "rule": "#B0B0B0", "rule-soft": "#DADADA",
        "accent": "#00707A", "accent-ink": "#FFFFFF", "accent-soft": "#E3F1F2",
    },
    "dark": {
        "ground": "#0B0B0B", "surface": "#0B0B0B", "surface-2": "#1A1A1A",
        "ink": "#FFFFFF", "ink-2": "#D0D0D0", "ink-3": "#A6A6A6",
        "rule": "#5C5C5C", "rule-soft": "#2A2A2A",
        "accent": "#4FD1D9", "accent-ink": "#0B0B0B", "accent-soft": "#10292B",
    },
}
# Schriften liefert die Seite selbst aus, keine Anfrage an fremde Server (Aufbau wie bildsprache): Dateien, Herkunft,
# sha256 und unicode-range in site/fonts/fonts.json, die OFL-Texte daneben. Alles geht nach docs/assets/fonts/; die
# @font-face-Regeln stehen vorn in der ausgelieferten site.css (site_css). Vorgeladen wird die Inter-Datei für Latein.
FONTDATA = json.loads((SITE_SRC / "fonts" / "fonts.json").read_text(encoding="utf-8"))
PRELOAD_FONTS = ("inter-latin.woff2",)
NOTICES = ROOT / "THIRD_PARTY_NOTICES.txt"   # Lizenzen Dritter, wird nach docs/ kopiert und im Fuß verlinkt
# Impressum (Seite impressum/, im Fuß verlinkt): Angaben nur aus data/legal.json, unverändert aus bildsprache übernommen
LEGAL = json.loads((ROOT / "data" / "legal.json").read_text(encoding="utf-8"))
# Zeichen: Leuchtturm aus Pixelblöcken mit Lichtstrahl
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
           "%3Crect width='32' height='32' fill='%2300707A'/%3E%3Crect x='11' y='6' width='8' height='5' fill='%23FFFFFF'/%3E"
           "%3Crect x='12' y='13' width='6' height='13' fill='%23FFFFFF'/%3E%3Crect x='7' y='26' width='16' height='2' fill='%23FFFFFF'/%3E"
           "%3Cpath d='M20 8l8-3v7z' fill='%23FFFFFF'/%3E%3C/svg%3E")
LOGO = ('<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" fill="var(--accent)"/>'
        '<rect x="11" y="6" width="8" height="5" fill="var(--surface)"/><rect x="12" y="13" width="6" height="13" fill="var(--surface)"/>'
        '<rect x="7" y="26" width="16" height="2" fill="var(--surface)"/><path d="M20 8l8-3v7z" fill="var(--surface)"/></svg>')

STATUS = {
    "done": ("Fertig", "Demo läuft, Aufnahme geprüft."),
    "partial": ("Teilweise", "Demo läuft, die Lücken sind benannt."),
    "blocked": ("Blockiert", "Bau angehalten, zum Beispiel durch das Bildlimit."),
    "failed": ("Gescheitert", "Der Stil ließ sich so nicht umsetzen."),
    "wip": ("In Arbeit", "Ordner angelegt, der Steckbrief fehlt noch."),
    "planned": ("Geplant", "Bisher steht nur der Auftrag fest."),
}
STYLE_STATUS = ("done", "partial", "blocked", "failed")       # Werte, die in style.json stehen dürfen
KIND = {"style": "Stil", "technique": "Technik"}
BACKENDS = {"codex": "gpt-image (Codex CLI)", "agy": "Gemini (Antigravity CLI)"}  # "backend" aus tools/genimg.py
AXES = (  # Schlüssel, Name, Kurzname für Karten, Erklärung
    ("text_adventure", "Textadventure", "Textadv.", "Eignung für unser erstes Spiel, ein Textadventure."),
    ("ai_fit", "KI-Beitrag", "KI-Beitrag", "Wie viel die KI-Bilder tatsächlich zum Look der Demo beitragen (1 = nichts)."),
    ("consistency", "Konsistenz", "Konsistenz", "Wie gleichmäßig der Stil über viele Assets bleibt."),
    ("effort", "Aufwand", "Aufwand", "Aufwand pro Asset; 5 heißt hoch, weniger ist besser."),
    ("mobile", "Mobil (geschätzt)", "Mobil (geschätzt)",
     "Geschätzte Mobiltauglichkeit: Vergleich der Godot-Renderer auf dem Mac, nicht auf Geräten gemessen."),
)
AXIS = {a[0]: a for a in AXES}
SORTS = (("family", "Familie"), ("name", "Name"), ("text_adventure", "Eignung Textadventure"),
         ("ai_fit", "KI-Beitrag"), ("effort", "Aufwand (geringster zuerst)"))
# Sichtbare Namen der Steckbrief-Felder, wie die Abschnitte auf der Eintragsseite heißen (ratings_note steht im
# Kasten „Bewertungen“, camera und image_generations in der Tabelle). de_keys() setzt sie für rohe Feldnamen in den
# deutschen Texten ein („siehe pitfalls“ → „siehe „Fallstricke““), Achsen ohne Anführungszeichen („ai_fit 4“ → „KI-Beitrag 4“).
SECTION = {"traits": "Merkmale", "pipeline": "Werkzeugkette", "godot": "Umsetzung in Godot", "pitfalls": "Fallstricke",
           "lessons": "Erkenntnisse", "tool_issues": "Probleme mit Werkzeugen", "verdict": "Für unser Textadventure",
           "ratings_note": "Bewertungen", "camera": "Kamera", "assets": "Assets", "image_generations": "KI-Bilder"}
AXIS_WORD = {key: name.split(" (")[0] for key, name, *_ in AXES}         # „Mobil (geschätzt)“ → „Mobil“
WEAK_KEYS = {"godot", "camera", "assets"}   # nur nach „siehe“, „unter“, „in“; sonst Befehl oder Pfad (godot --import)
FIELD_RE = re.compile(r"(?<![\w./=-])(" + "|".join(sorted(set(AXIS_WORD) | set(SECTION), key=len, reverse=True))
                      + r")(?![\w/=-]|\.\w)")
CODE_RE = re.compile(r"`([^`\n]+)`")                         # Markdown-Code in den Texten
URL_RE = re.compile(r"https?://[^\s<>\"'(),;]+")
# Interne Aufrufnamen der Bildwerkzeuge (Werkzeugname mit angehängter Zahl) erscheinen auf der Seite als Werkzeugname
ALIAS_RE = re.compile(r"(?<![\w./-])(" + "|".join(BACKENDS) + r")\d+(?![\w-])")
# Interne Felder der Begleitdateien von tools/genimg.py; werden beim Kopieren von JSON-Assets entfernt
PRIVATE_JSON_KEYS = {"agy_account", "conversation_id", "thread_id"}
ALT_MAX = 150
PATH_RE = re.compile(r"(?<![\w/])(?:[\w.-]+/)+([\w.*-]+)")   # styles/x/assets/bg.png → bg.png (für Alt-Texte)
# Asset-Arten (style.json → assets[].kind) auf Deutsch; Arten, die schon deutsch beschrieben sind, bleiben stehen.
KIND_DE = {
    "animation": "Animation", "background": "Hintergrund", "background-layer": "Hintergrundebene",
    "character": "Figur", "character-part": "Figurenteil", "check": "Prüfbild", "code": "Code",
    "comparison": "Vergleich", "data": "Daten", "depth": "Tiefenkarte", "doku": "Dokumentation", "effect": "Effekt",
    "effects": "Effekte", "font": "Schrift", "fx": "Effekt", "icon": "Symbol", "layer": "Ebene", "layout": "Layout",
    "light-layer": "Lichtebene", "light-mask": "Lichtmaske", "lut": "Farbtabelle (LUT)", "map": "Karte",
    "mask": "Maske", "measurement": "Messung", "messung": "Messung", "model": "Modell", "noise": "Rauschen",
    "normalmap": "Normal-Map", "palette": "Palette", "pattern": "Muster", "plate": "Platte",
    "polygon data": "Polygondaten", "portrait": "Porträt", "preview": "Vorschau", "prop": "Requisit",
    "reference": "Referenz", "report": "Bericht", "rig": "Rig", "scene": "Szene", "script": "Skript",
    "shader": "Shader", "specular": "Glanzkarte", "sprite": "Sprite", "sprite sheet": "Sprite-Blatt",
    "sprite-sheet": "Sprite-Blatt", "sprite_sheet": "Sprite-Blatt", "spritesheet": "Sprite-Blatt",
    "sprite-stack": "Sprite-Stapel", "sprite-strip": "Sprite-Streifen", "spriteframes": "SpriteFrames (Godot)",
    "test": "Test", "texture": "Textur", "texture-sheet": "Texturblatt", "tile": "Kachel", "tileset": "Kachelsatz",
    "tone-plate": "Tonplatte", "tonemap": "Tonwertkarte", "ui": "Oberfläche", "vector": "Vektorgrafik",
    "voxels": "Voxel",
}
RESERVED = {"assets", "vergleich", "techniken", "textadventure", "werkzeuge", "impressum"}
KNOWN_KEYS = {"slug", "name", "family", "kind", "era", "summary", "references", "traits", "camera", "resolution",
              "pipeline", "godot", "techniques", "ratings", "ratings_note", "verdict", "pitfalls", "lessons", "assets",
              "licenses", "image_generations", "tool_issues", "status"}
LIST_KEYS = ("references", "traits", "godot", "techniques", "pitfalls", "lessons", "tool_issues", "pipeline",
             "assets", "licenses")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
THUMB_MAX = 960            # längste Kante der verkleinerten Fassung
LARGE_BYTES = 600_000      # ab hier gilt ein Bild als groß
LARGE_EDGE = 1600
PIXEL_EDGE = 640           # kleinere Bilder werden ohne Glättung vergrößert (Pixel-Art)
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class DataError(Exception):
    pass


def h(s):
    """Escapt Text für HTML; interne Aufrufnamen (ALIAS_RE) werden dabei zum Werkzeugnamen, in Dateinamen nicht."""
    return html.escape(ALIAS_RE.sub(r"\1", str(s if s is not None else "")), quote=True)


def de_keys(s):
    """Setzt für rohe Feldnamen aus style.json die sichtbaren Bezeichnungen ein (Text ohne Code-Spans)."""
    def sub(m):
        key, after = m.group(1), s[m.end():]
        number = re.match(r"\s*=?\s*\d", after)
        if key == "mobile" and not number:           # Godot-Renderer „mobile“, keine Bewertung
            return key
        if key in WEAK_KEYS and not re.search(r"(?:\b[Ss]iehe|\bunter|\bin) $", s[:m.start()]):
            return key
        if key in AXIS_WORD:
            return AXIS_WORD[key]
        return SECTION[key] if number else f"„{SECTION[key]}“"
    return FIELD_RE.sub(sub, s)


def txt(s):
    """Deutscher Text aus Steckbrief oder Katalog als HTML: `Code` wird <code>, rohe Feldnamen werden Bezeichnungen.
    Nur für deutsche Felder; englische Prompts und Zitate laufen weiter über h()."""
    parts = CODE_RE.split(str(s if s is not None else ""))
    return "".join(f"<code>{h(p)}</code>" if i % 2 else h(de_keys(p)) for i, p in enumerate(parts))


def plain(s):
    """Wie txt(), aber als reiner Text (für Attribute wie alt): Backticks entfallen."""
    parts = CODE_RE.split(str(s if s is not None else ""))
    return "".join(p if i % 2 else de_keys(p) for i, p in enumerate(parts))


def linkify(s):
    """Text mit Adressen (z. B. Lizenzquellen): nur die URLs werden Links, der Rest bleibt Text."""
    s, out, pos = str(s if s is not None else ""), [], 0
    for m in URL_RE.finditer(s):
        url = m.group(0).rstrip(".")
        out.append(txt(s[pos:m.start()]))
        out.append(f'<a href="{h(url)}" rel="noopener">{h(url)}</a>')
        pos = m.start() + len(url)
    out.append(txt(s[pos:]))
    return "".join(out)


def shorten(s, n=ALT_MAX):
    """Kürzt an einer Wortgrenze auf höchstens n Zeichen (mit …)."""
    s = " ".join(str(s).split())
    if len(s) <= n:
        return s
    cut = s[:n - 1]
    cut = cut.rsplit(" ", 1)[0] if " " in cut else cut
    return cut.rstrip(" ,;:(–-") + "…"


def asset_kind(kind):
    """Deutsche Bezeichnung einer Asset-Art; schon deutsch beschriebene Arten bleiben, wie sie sind."""
    if not kind:
        return "Asset"
    return KIND_DE.get(str(kind).strip().lower(), str(kind))


def strip_private(value):
    """Entfernt PRIVATE_JSON_KEYS aus verschachtelten JSON-Daten; gibt (daten, anzahl_entfernt) zurück."""
    if isinstance(value, dict):
        out, n = {}, 0
        for k, v in value.items():
            if k in PRIVATE_JSON_KEYS:
                n += 1
                continue
            out[k], m = strip_private(v)
            n += m
        return out, n
    if isinstance(value, list):
        items = [strip_private(v) for v in value]
        return [v for v, _ in items], sum(m for _, m in items)
    return value, 0


def num(n):
    return f"{n:,}".replace(",", ".")


def rel(page, target):
    """Pfad von einer Seite (relativ zu docs/, z. B. 'vergleich/') zu einem Ziel relativ zu docs/."""
    if page and target.startswith(page):
        return target[len(page):]
    return "../" * page.count("/") + target


def link(page, target):
    return rel(page, target) or "./"


# ---------------------------------------------------------------------------
# Bildgrößen ohne Pillow
# ---------------------------------------------------------------------------
def image_size(path):
    """(Breite, Höhe) für PNG, GIF, JPEG und WebP aus dem Dateikopf; None, wenn unbekannt."""
    path = pathlib.Path(path)
    with open(path, "rb") as f:
        head = f.read(64)
        if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
            return struct.unpack(">II", head[16:24])
        if head[:6] in (b"GIF87a", b"GIF89a"):
            return struct.unpack("<HH", head[6:10])
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            chunk = head[12:16]
            if chunk == b"VP8 " and head[23:26] == b"\x9d\x01\x2a":
                w, hh = struct.unpack("<HH", head[26:30])
                return w & 0x3FFF, hh & 0x3FFF
            if chunk == b"VP8L" and head[20] == 0x2F:
                bits = int.from_bytes(head[21:25], "little")
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
            if chunk == b"VP8X":
                return int.from_bytes(head[24:27], "little") + 1, int.from_bytes(head[27:30], "little") + 1
            return None
        if head[:2] == b"\xff\xd8":
            data = head + f.read()
            i = 2
            while i + 9 < len(data):
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker == 0xFF:
                    i += 1
                    continue
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                length = struct.unpack(">H", data[i + 2:i + 4])[0]
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    hh, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return w, hh
                i += 2 + length
    return None


# ---------------------------------------------------------------------------
# Daten laden und prüfen
# ---------------------------------------------------------------------------
def read_json(path, root, problems):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        problems.append(f"{path.relative_to(root)}: fehlt")
    except (ValueError, UnicodeDecodeError) as exc:
        problems.append(f"{path.relative_to(root)}: kein gültiges JSON ({exc})")
    return None


def as_text_list(value, where, problems):
    if value is None:
        return []
    if not isinstance(value, list):
        problems.append(f"{where}: muss eine Liste sein")
        return []
    return value


def load(root):
    """Liest Katalog, Szene und alle Steckbriefe. Gibt (data, warnings) zurück oder wirft DataError."""
    root = pathlib.Path(root).resolve()
    problems, warnings = [], []
    catalog = read_json(root / "data" / "catalog.json", root, problems)
    motif = read_json(root / "data" / "motif.json", root, problems)
    if problems:
        raise DataError(problems)
    families = catalog.get("families", [])
    fam = {f["id"]: f for f in families}
    entries, by_slug = [], {}
    for i, c in enumerate(catalog.get("entries", [])):
        slug = c.get("slug", "")
        where = f"data/catalog.json → {slug or i}"
        if not SLUG_RE.match(slug):
            problems.append(f"{where}: ungültiger Slug")
            continue
        if slug in by_slug:
            problems.append(f"{where}: Slug doppelt")
            continue
        if slug in RESERVED:
            problems.append(f"{where}: Slug kollidiert mit einer Seite ({', '.join(sorted(RESERVED))})")
        if c.get("family") not in fam:
            problems.append(f"{where}: unbekannte Familie {c.get('family')!r}")
        if c.get("kind") not in KIND:
            problems.append(f"{where}: unbekannte Art {c.get('kind')!r}")
        e = {"slug": slug, "name": c.get("name") or slug, "family": c.get("family"), "kind": c.get("kind"),
             "brief": c.get("brief", ""), "needs": c.get("needs") or [], "order": i, "in_catalog": True,
             "status": "planned", "st": None, "media": {}, "prompts": [], "assets": [], "capture": {}}
        entries.append(e)
        by_slug[slug] = e

    styles_dir = root / "styles"
    dirs = sorted(d for d in styles_dir.iterdir() if d.is_dir() and not d.name.startswith(".")) if styles_dir.is_dir() else []
    for d in dirs:
        slug = d.name
        sj = d / "style.json"
        e = by_slug.get(slug)
        if e is None:
            if not sj.exists():
                warnings.append(f"styles/{slug}/: nicht im Katalog und ohne style.json – übersprungen")
                continue
            warnings.append(f"styles/{slug}/: nicht in data/catalog.json – wird trotzdem gezeigt")
            if not SLUG_RE.match(slug) or slug in RESERVED:
                problems.append(f"styles/{slug}/: ungültiger oder reservierter Ordnername")
                continue
            e = {"slug": slug, "name": slug, "family": None, "kind": None, "brief": "", "needs": [],
                 "order": 10_000 + len(entries), "in_catalog": False, "status": "planned", "st": None,
                 "media": {}, "prompts": [], "assets": [], "capture": {}}
            entries.append(e)
            by_slug[slug] = e
        if not sj.exists():
            e["status"] = "wip"
            continue
        st = read_json(sj, root, problems)
        if not isinstance(st, dict):
            if st is not None:
                problems.append(f"styles/{slug}/style.json: muss ein Objekt sein")
            continue
        load_style(root, d, e, st, fam, problems, warnings)

    if problems:
        raise DataError(problems)
    for e in entries:  # Einträge außerhalb des Katalogs brauchen Familie und Art aus style.json
        if e["family"] not in fam or e["kind"] not in KIND:
            problems.append(f"styles/{e['slug']}/style.json: family/kind fehlen oder sind unbekannt")
    if problems:
        raise DataError(problems)
    return {"root": root, "families": families, "fam": fam, "entries": entries, "by": by_slug, "motif": motif}, warnings


def load_style(root, d, e, st, fam, problems, warnings):
    slug = e["slug"]
    where = f"styles/{slug}/style.json"
    if st.get("slug") != slug:
        problems.append(f"{where}: slug {st.get('slug')!r} passt nicht zum Ordner")
    status = st.get("status")
    if status not in STYLE_STATUS:
        problems.append(f"{where}: status {status!r} unbekannt (erlaubt: {', '.join(STYLE_STATUS)})")
        return
    for key in LIST_KEYS:
        st[key] = as_text_list(st.get(key), f"{where} → {key}", problems)
    ratings = st.get("ratings") or {}
    if not isinstance(ratings, dict):
        problems.append(f"{where} → ratings: muss ein Objekt sein")
        ratings = {}
    for k, v in ratings.items():
        if k not in AXIS:
            warnings.append(f"{where} → ratings.{k}: unbekannte Achse, wird nicht gezeigt")
        elif isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 5:
            problems.append(f"{where} → ratings.{k}: {v!r} ist keine ganze Zahl von 1 bis 5")
    st["ratings"] = {k: v for k, v in ratings.items() if k in AXIS}
    gens = st.get("image_generations")
    if gens is not None and (isinstance(gens, bool) or not isinstance(gens, int) or gens < 0):
        problems.append(f"{where} → image_generations: {gens!r} ist keine Zahl ≥ 0")
    if e["in_catalog"]:
        for key in ("family", "kind"):
            if st.get(key) and st[key] != e[key]:
                warnings.append(f"{where}: {key} {st[key]!r} weicht vom Katalog ab ({e[key]!r}); Katalog gilt")
    else:
        e["family"], e["kind"] = st.get("family"), st.get("kind")
    e["name"] = st.get("name") or e["name"]
    e["st"], e["status"] = st, status

    # Medien aus tools/capture.py
    media = d / "media"
    m = {}
    if (media / "poster.webp").exists():
        m["poster"] = media / "poster.webp"
    elif (media / "poster.png").exists():
        m["poster"] = media / "poster.png"
        warnings.append(f"styles/{slug}/media/poster.webp fehlt – nehme poster.png")
    for name, key in (("demo.mp4", "video"), ("preview.gif", "gif"), ("frames.jpg", "frames")):
        if (media / name).exists():
            m[key] = media / name
    if status in ("done", "partial"):
        for key, name in (("video", "demo.mp4"), ("poster", "poster.webp")):
            if key not in m:
                problems.append(f"styles/{slug}/media/{name}: fehlt, obwohl status {status!r} eine Demo verlangt")
        if "frames" not in m:
            warnings.append(f"styles/{slug}/media/frames.jpg fehlt")
    if (media / "capture.json").exists():
        cap = read_json(media / "capture.json", root, problems)
        e["capture"] = cap if isinstance(cap, dict) else {}
    e["media"] = m

    # Assets aus style.json
    base = d.resolve()
    for i, a in enumerate(st["assets"]):
        if isinstance(a, str):
            a = {"file": a}
        if not isinstance(a, dict) or not isinstance(a.get("file"), str) or not a["file"]:
            problems.append(f"{where} → assets[{i}]: braucht 'file'")
            continue
        src = (d / a["file"]).resolve()
        if base not in src.parents:
            problems.append(f"{where} → assets[{i}]: {a['file']!r} liegt außerhalb von styles/{slug}/")
            continue
        if not src.is_file():
            problems.append(f"{where} → assets[{i}]: Datei {a['file']!r} fehlt")
            continue
        e["assets"].append(dict(a, src=src, file=src.relative_to(base).as_posix()))

    # Prompts aus tools/collect_prompts.py
    pj = d / "prompts.json"
    if pj.exists():
        prompts = read_json(pj, root, problems)
        if prompts is not None:
            if not isinstance(prompts, list) or not all(isinstance(p, dict) and p.get("prompt") for p in prompts):
                problems.append(f"styles/{slug}/prompts.json: erwartet eine Liste von Objekten mit 'prompt'")
            else:
                e["prompts"] = prompts
    if status in ("done", "partial"):
        for key in ("summary", "verdict", "ratings"):
            if not st.get(key):
                warnings.append(f"{where}: {key} fehlt")


# ---------------------------------------------------------------------------
# Ausgabe: Dateien kopieren und verkleinern
# ---------------------------------------------------------------------------
class Out:
    def __init__(self, out, old, use_tools):
        self.out, self.old = out, old
        self.cwebp = shutil.which("cwebp") if use_tools else None
        self.sips = shutil.which("sips") if use_tools else None
        self.files = 0
        self.thumbs = 0
        self.reused = 0

    def copy(self, src, dst):
        target = self.out / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        self.files += 1
        return dst

    def copy_json(self, src, dst):
        """Kopiert ein JSON-Asset; Felder aus PRIVATE_JSON_KEYS werden vorher entfernt."""
        text = src.read_text(encoding="utf-8", errors="replace")
        try:
            data = json.loads(text)
        except ValueError:
            if any(k in text for k in PRIVATE_JSON_KEYS):
                print(f"  WARNUNG: {src.name} ist kein gültiges JSON und enthält {', '.join(sorted(PRIVATE_JSON_KEYS))} "
                      "– unverändert kopiert", file=sys.stderr)
            return self.copy(src, dst)
        data, removed = strip_private(data)
        if not removed:
            return self.copy(src, dst)
        target = self.out / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        self.files += 1
        return dst

    def write(self, page, text):
        target = self.out / page / "index.html" if not page.endswith(".html") else self.out / page
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def image(self, src, dst):
        """Kopiert ein Bild nach dst und gibt (anzeige_pfad, breite, höhe, original_größe) zurück.
        Große Bilder bekommen eine verkleinerte Fassung, wenn cwebp oder sips vorhanden ist."""
        self.copy(src, dst)
        size = image_size(src) or (None, None)
        w, hh = size
        big = src.suffix.lower() in (".png", ".jpg", ".jpeg") and (
            src.stat().st_size > LARGE_BYTES or (w and max(w, hh) > LARGE_EDGE))
        if not big or not (self.cwebp or self.sips):
            return dst, w, hh, size
        digest = hashlib.sha1(src.read_bytes()).hexdigest()[:10]
        stem = dst.rsplit("/", 1)
        folder = stem[0] + "/" if len(stem) == 2 else ""
        name = pathlib.PurePosixPath(stem[-1]).stem
        scale = min(1.0, THUMB_MAX / max(w, hh)) if w else 1.0
        tw, th = (round(w * scale), round(hh * scale)) if w else (None, None)
        thumb = f"{folder}{name}.{digest}.{'webp' if self.cwebp else src.suffix.lstrip('.').lower()}"
        target = self.out / thumb
        previous = self.old / thumb if self.old else None
        if previous and previous.exists():          # unverändertes Bild: Fassung aus dem letzten Build
            shutil.copyfile(previous, target)
            self.reused += 1
            return thumb, tw, th, size
        if self.cwebp:
            resize = ["-resize", str(tw), str(th)] if scale < 1 else []
            run = subprocess.run([self.cwebp, "-quiet", "-q", "82", *resize, str(src), "-o", str(target)],
                                 capture_output=True, text=True)
        else:
            if scale >= 1:
                return dst, w, hh, size
            run = subprocess.run([self.sips, "-Z", str(THUMB_MAX), str(src), "--out", str(target)],
                                 capture_output=True, text=True)
        if run.returncode or not target.exists():
            print(f"  WARNUNG: Verkleinern fehlgeschlagen ({src.name}): {run.stderr.strip()[:200]} – zeige Original",
                  file=sys.stderr)
            target.unlink(missing_ok=True)
            return dst, w, hh, size
        self.thumbs += 1
        real = image_size(target)
        if real:
            tw, th = real
        return thumb, tw, th, size


def font_url(f):
    """Adresse einer Schriftdatei relativ zu assets/site.css, mit Prüfsumme als Version."""
    return f"fonts/{f['file']}?v={f['sha256'][:10]}"


def site_css():
    """Die ausgelieferte site.css: @font-face-Regeln aus site/fonts/fonts.json, dann site/site.css."""
    rules = [f'@font-face {{ font-family:"{f["family"]}"; font-style:normal; font-weight:{f["weight"]}; font-display:swap; '
             f'src:url({font_url(f)}) format("woff2"); unicode-range:{f["unicode_range"]}; }}'
             for f in FONTDATA["faces"]]
    return ("/* Schriften: erzeugt von build.py aus site/fonts/fonts.json */\n" + "\n".join(rules) + "\n"
            + (SITE_SRC / "site.css").read_text(encoding="utf-8"))


def asset_version(name):
    data = site_css().encode("utf-8") if name == "site.css" else (SITE_SRC / name).read_bytes()
    return hashlib.sha1(data).hexdigest()[:10]


# ---------------------------------------------------------------------------
# Seitenrahmen
# ---------------------------------------------------------------------------
def theme_css():
    def values(mode):
        return "".join(f"--{k}:{v};" for k, v in PALETTES[mode].items()) + f"color-scheme:{mode};"
    return (":root {" + values("light") + "}\n"
            '@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {' + values("dark") + "} }\n"
            ':root[data-theme="dark"] {' + values("dark") + "}\n")


THEME_CONTROLS = ('<div class="theme-switch" data-theme-controls role="group" aria-label="Darstellung" hidden>'
                  + "".join(f'<button type="button" data-theme-choice="{m}" aria-pressed="false">{label}</button>'
                            for m, label in (("system", "System"), ("light", "Hell"), ("dark", "Dunkel")))
                  + "</div>")
NAV = (("home", "", "Katalog"), ("vergleich", "vergleich/", "Vergleich"), ("techniken", "techniken/", "Techniken"),
       ("textadventure", "textadventure/", "Textadventure"), ("werkzeuge", "werkzeuge/", "Werkzeuge"))


def head(page, title, desc, nav, og_image=None):
    og = ""
    if og_image:
        og = (f'<meta property="og:image" content="{SITE_URL}/{h(og_image)}">\n'
              '<meta name="twitter:card" content="summary_large_image">\n')
    links = "".join(
        f'<a href="{link(page, target)}"{" aria-current=\"page\"" if key == nav else ""}>{label}</a>'
        for key, target, label in NAV)
    fonts = "".join(f'<link rel="preload" href="{rel(page, "assets/" + font_url(f))}" as="font" type="font/woff2" crossorigin>'
                    for f in FONTDATA["faces"] if f["file"] in PRELOAD_FONTS)
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{h(title)}</title>
<meta name="description" content="{h(desc)}">
<meta name="author" content="Sebastian Grundhöfer">
<link rel="canonical" href="{SITE_URL}/{page}">
<meta property="og:type" content="website">
<meta property="og:title" content="{h(title)}">
<meta property="og:description" content="{h(desc)}">
<meta property="og:url" content="{SITE_URL}/{page}">
<meta property="og:locale" content="de_DE">
{og}<link rel="icon" href="{FAVICON}">
{fonts}
<script id="theme-controller">
{(SITE_SRC / 'theme.js').read_text(encoding='utf-8')}
</script>
<style>{theme_css()}</style>
<link rel="stylesheet" href="{rel(page, 'assets/site.css')}?v={asset_version('site.css')}">
</head>
<body>
<a class="skip" href="#main">Zum Inhalt springen</a>
<header class="topbar"><div class="wrap topbar-in">
<a class="tb-brand" href="{link(page, '')}">{LOGO}Spielgrafik</a>
<nav class="tb-nav" aria-label="Hauptnavigation">{links}</nav>
<div class="tb-end">{THEME_CONTROLS}</div>
</div></header>
<main id="main">
"""


def foot(page):
    return f"""</main>
<footer class="foot"><div class="wrap foot-in">
<span>© Sebastian Grundhöfer</span>
<span>Bilder KI-erzeugt (Gemini über agy und gpt-image über Codex CLI), Demos mit Godot 4.7</span>
<span>Code MIT · Texte CC BY 4.0 · Bilder, Videos und Modelle CC0</span>
<a href="{rel(page, 'werkzeuge/')}#lizenzen">Lizenzhinweise</a>
<a href="{rel(page, 'THIRD_PARTY_NOTICES.txt')}">Lizenzen Dritter</a>
<a href="{REPO_URL}" rel="noopener">GitHub</a>
<a href="{SIBLING_URL}" rel="noopener">Geschwisterprojekt: Bildsprache</a>
<a href="{link(page, 'impressum/')}">Impressum</a>
<span>Genannte Marken und Spielenamen gehören ihren Inhabern; dieses Projekt steht in keiner Verbindung zu ihnen.</span>
</div></footer>
<script src="{rel(page, 'assets/site.js')}?v={asset_version('site.js')}" defer></script>
</body>
</html>
"""


def mast(eyebrow, title_html, lede_html, facts, crumbs=""):
    fx = "".join(fact(v, label) for v, label in facts)
    top = f'<p class="crumbs">{crumbs}</p>' if crumbs else f'<p class="eyebrow">{eyebrow}</p>'
    return (f'<section class="mast"><div class="wrap mast-in">'
            f'<div>{top}<h1>{title_html}</h1>{f"<p class=\"lede\">{lede_html}</p>" if lede_html else ""}</div>'
            f'<div class="facts">{fx}</div></div></section>')


def fact(value, label):
    v = str(value)
    small = len(v) > 5 or not v[:1].isdigit()
    return f'<div><b{" class=\"t\"" if small else ""}>{h(v)}</b><span>{h(label)}</span></div>'


def sec_head(title, text="", id_=None, block=False):
    """Abschnittskopf; text ist HTML, block=True setzt es ohne umschließendes <p> (z. B. Listen)."""
    body = (f"<div>{text}</div>" if block else f"<p>{text}</p>") if text else ""
    return f'<div class="sec-head"{f" id=\"{id_}\"" if id_ else ""}><h2>{title}</h2>{body}</div>'


def badge(status):
    return f'<span class="badge s-{status}">{STATUS[status][0]}</span>'


def pips(value, hl=False):
    v = value or 0
    cells = "".join(f'<i class="on"></i>' if i < v else "<i></i>" for i in range(5))
    return f'<span class="pips{" hl" if hl else ""}" aria-hidden="true">{cells}</span>'


def mini_ratings(st):
    r = st.get("ratings") or {}
    if not r:
        return ""
    rows = []
    for key, name, short, _ in AXES:
        v = r.get(key)
        val = f'{pips(v, key == "text_adventure")}<span aria-hidden="true">{v}</span><span class="sr-only">{v} von 5</span>' \
            if v else '<span>–</span><span class="sr-only">keine Angabe</span>'
        label = h(name) if short == name else f'<span aria-hidden="true">{h(short)}</span><span class="sr-only">{h(name)}</span>'
        rows.append(f'<dt title="{h(name)}">{label}</dt><dd>{val}</dd>')
    return f'<dl class="rt">{"".join(rows)}</dl>'


def alt_text(e):
    """Kurz: Die Zusammenfassung steht schon als Text daneben oder auf der Eintragsseite."""
    return shorten(f"{e['name']}: Poster der Demo")


def media_url(e, key):
    p = e["media"].get(key)
    return f"{e['slug']}/media/{p.name}" if p else None


def is_built(e):
    return e["st"] is not None


# ---------------------------------------------------------------------------
# Karten
# ---------------------------------------------------------------------------
def card(D, e, page, extra=""):
    st = e["st"] or {}
    href = link(page, f"{e['slug']}/")
    fam = D["fam"][e["family"]]["name"]
    attrs = [f'data-fam="{h(e["family"])}"', f'data-kind="{h(e["kind"])}"', f'data-status="{e["status"]}"',
             f'data-order="{e["order"]}"', f'data-name="{h(e["name"])}"']
    for key in AXIS:
        if (st.get("ratings") or {}).get(key):
            attrs.append(f'data-r-{key}="{st["ratings"][key]}"')
    poster = media_url(e, "poster")
    video = media_url(e, "video")
    if poster:
        w, hh = e["media_dims"]["poster"]
        vid = (f'<video muted loop playsinline preload="none" src="{rel(page, video)}" aria-hidden="true" tabindex="-1"></video>'
               if video else "")
        play = '<span class="play" aria-hidden="true"></span>' if video else ""
        media = (f'<a class="cimg" href="{href}" tabindex="-1"><img src="{rel(page, poster)}" width="{w}" height="{hh}" '
                 f'loading="lazy" decoding="async" alt="{h(alt_text(e))}">{vid}{play}</a>')
        if video:
            attrs.append('data-video')
    else:
        text = st.get("summary") or e["brief"]
        label = STATUS[e["status"]][0] + (" · Auftrag" if not st.get("summary") and e["brief"] else "")
        media = (f'<div class="cimg ph"><span class="ph-lab">{h(label)}</span>'
                 f'<span class="ph-brief">{txt(text)}</span></div>')
    meta = h(fam) + (f" · {h(st['era'])}" if st.get("era") else "")
    gens = st.get("image_generations")
    gens_html = f"<span>{gens} KI-Bilder</span>" if isinstance(gens, int) else ""
    return (f'<article class="card" {" ".join(attrs)}>{media}<div class="cap">'
            f'<p class="meta">{meta}</p><h3><a href="{href}">{h(e["name"])}</a></h3>'
            f'<p class="row">{badge(e["status"])}<span>{KIND[e["kind"]]}</span>{gens_html}</p>'
            f'{mini_ratings(st)}{extra}</div></article>')


# ---------------------------------------------------------------------------
# Seiten
# ---------------------------------------------------------------------------
def counts(D):
    es = D["entries"]
    return {
        "all": len(es),
        "demo": sum(e["status"] in ("done", "partial") for e in es),
        "built": sum(is_built(e) for e in es),
        "planned": sum(e["status"] == "planned" for e in es),
        "tech": sum(e["kind"] == "technique" for e in es),
        "ai": sum((e["st"] or {}).get("image_generations") or 0 for e in es if is_built(e)),
    }


def page_home(D, O):
    page = ""
    c = counts(D)
    es = D["entries"]
    out = [head(page, "Spielgrafik – Stilkatalog für unser Spielprojekt",
                "Dieselbe Hafenszene in vielen Spielgrafik-Stilen, selbst erzeugt mit KI-Bildern, Code, Blender und Godot.",
                "home")]
    out.append(mast(
        "Spielgrafik · Stilkatalog",
        "Eine Szene, <em>viele Spielgrafiken</em>",
        "Jeder Eintrag zeigt dieselbe Szene: <strong>den Hafen von Lornholm in der Abenddämmerung</strong>, über den der "
        "Dachs-Kurier läuft. Alles ist selbst erzeugt, mit KI-Bildern, Code, Blender und Godot, und läuft als kurze "
        "Godot-Demo. Der Katalog dient der Stilwahl für unser Spielprojekt; das erste Spiel wird ein Textadventure.",
        [(c["all"], "Einträge"), (c["demo"], "mit Demo"), (c["planned"], "geplant"), (num(c["ai"]), "KI-Bilder")]))

    def chips(group, options):
        items = [f'<button type="button" class="chip" data-value="*" aria-pressed="true">Alle <small>{len(es)}</small></button>']
        for value, label, n in options:
            if n:
                items.append(f'<button type="button" class="chip" data-value="{h(value)}" aria-pressed="false">'
                             f'{h(label)} <small>{n}</small></button>')
        return f'<div class="chips" data-filter-group="{group}">{"".join(items)}</div>'

    fam_opts = [(f["id"], f["name"], sum(e["family"] == f["id"] for e in es)) for f in D["families"]]
    kind_opts = [(k, label, sum(e["kind"] == k for e in es)) for k, label in KIND.items()]
    stat_opts = [(s, STATUS[s][0], sum(e["status"] == s for e in es)) for s in STATUS]
    sort_opts = "".join(f'<option value="{k}">{h(label)}</option>' for k, label in SORTS)
    # Filter „Stand“ nur, wenn es etwas zu wählen gibt (mehr als ein Status kommt vor)
    stat_group = (f'<div class="fgroup" role="group" aria-labelledby="fl-status"><span class="ctl-label" id="fl-status">'
                  f'Stand</span>{chips("status", stat_opts)}</div>\n' if sum(1 for *_, n in stat_opts if n) > 1 else "")
    bar = f"""<div class="bar" data-needs-js hidden>
<div class="fgroup" role="group" aria-labelledby="fl-fam"><span class="ctl-label" id="fl-fam">Familie</span>{chips("fam", fam_opts)}</div>
<div class="fgroup" role="group" aria-labelledby="fl-kind"><span class="ctl-label" id="fl-kind">Art</span>{chips("kind", kind_opts)}</div>
{stat_group}<div class="bar-end"><label class="ctl-label" for="sort">Sortieren</label><select id="sort" data-sort>{sort_opts}</select>
<span class="tally" data-tally aria-live="polite"></span></div>
</div>"""
    grid = []
    for f in D["families"]:
        members = [e for e in es if e["family"] == f["id"]]
        if not members:
            continue
        built = sum(is_built(e) for e in members)
        grid.append(f'<h2 class="fam-h" data-fam="{h(f["id"])}">{h(f["name"])} '
                    f'<small>{len(members)} Einträge · {built} gebaut</small></h2>')
        grid += [card(D, e, page) for e in members]
    legend = ("Balken je Eintrag: Textadventure-Eignung, KI-Beitrag, Konsistenz, Aufwand (5 = hoch) und "
              "Mobiltauglichkeit (geschätzt, nicht auf Geräten gemessen), jeweils 1 bis 5. ")
    planned_note = "Geplante Einträge zeigen ihren Auftrag. " if c["planned"] else ""
    out.append(f"""<section class="sec" data-catalog><div class="wrap">
{sec_head("Alle Einträge", "Gebaute Einträge spielen ihre Demo ab, wenn man mit der Maus darüberfährt, sie mit der Tastatur "
          f"erreicht oder auf dem Telefon antippt. {planned_note}"
          f'<a href="vergleich/">Alle Bewertungen im Vergleich</a>.')}
{bar}
<p class="legend">{legend}</p>
<p class="empty" data-none hidden>Keine Einträge für diese Auswahl.</p>
<div class="cat-grid" style="margin-top:18px">{"".join(grid)}</div>
</div></section>""")
    out.append(foot(page))
    return O.write(page, "".join(out))


def pager(D, e, page):
    same = sorted((x for x in D["entries"] if x["family"] == e["family"]), key=lambda x: x["order"])
    i = same.index(e)
    fam = D["fam"][e["family"]]["name"]
    parts = []
    for j, cls, label in ((i - 1, "prev", "← Zurück"), (i + 1, "next", "Weiter →")):
        if 0 <= j < len(same):
            x = same[j]
            state = "" if x["status"] in ("done", "partial") else f'<span>{STATUS[x["status"]][0]}</span>'
            parts.append(f'<a class="{cls}" href="{rel(page, x["slug"] + "/")}" rel="{cls}">'
                         f'<span>{label} · {h(fam)}</span><b>{h(x["name"])}</b>{state}</a>')
    if not parts:
        return ""
    return (f'<section class="sec"><div class="wrap"><nav class="pager" aria-label="Weitere Einträge der Familie {h(fam)}">'
            f'{"".join(parts)}</nav></div></section>')


def technique_users(D):
    """Technik-Slug -> Liste der gebauten Einträge, die sie in style.json → techniques nennen."""
    users = {}
    for e in D["entries"]:
        if is_built(e):
            for t in e["st"].get("techniques", []):
                users.setdefault(str(t), []).append(e)
    return users


def tech_tag(D, slug, page):
    t = D["by"].get(slug)
    if t and t["slug"] + "/" == page:              # die Seite selbst: kein Link auf sich
        return f'<span class="tag" aria-current="page">{h(t["name"])}</span>'
    if t:
        return f'<a class="tag" href="{rel(page, t["slug"] + "/")}">{h(t["name"])}</a>'
    return f'<span class="tag">{h(slug)}</span>'


def entry_tags(entries, page):
    return "".join(f'<a class="tag" href="{rel(page, x["slug"] + "/")}">{h(x["name"])}</a>' for x in entries)


def lst(items):
    """Liste deutscher Texte (Steckbrief, Szene); `Code` und Feldnamen wie in txt()."""
    return f'<ul class="list">{"".join(f"<li>{txt(x)}</li>" for x in items)}</ul>'


def tool_chips(tool):
    parts = [p.strip() for p in re.split(r"\s\+\s|,\s*", str(tool or "")) if p.strip()]
    return "".join(f'<span class="tag tool">{h(p)}</span>' for p in parts)


def render_extra(value):
    if isinstance(value, str):
        return f"<p>{txt(value)}</p>"
    if isinstance(value, list) and all(isinstance(x, (str, int, float)) for x in value):
        return lst(value)
    if isinstance(value, (int, float)):
        return f"<p>{h(value)}</p>"
    return f'<pre class="prompt">{h(json.dumps(value, ensure_ascii=False, indent=1))}</pre>'


def page_entry(D, O, e, users):
    page = f"{e['slug']}/"
    st = e["st"]
    fam = D["fam"][e["family"]]
    nav = "techniken" if e["kind"] == "technique" else "home"
    crumbs = (f'<a href="{link(page, "")}">Katalog</a> / {h(fam["name"])}'
              if e["kind"] == "style" else
              f'<a href="{link(page, "")}">Katalog</a> / <a href="{rel(page, "techniken/")}">Techniken</a>')
    needs3d = ("Baut auf der gemeinsamen 3D-Grundlage auf (shared/3d)." if "shared3d" in e["needs"] else "")
    if not st:
        return page_planned(D, O, e, users, page, crumbs, nav, needs3d)

    ratings = st.get("ratings") or {}
    poster = media_url(e, "poster")
    out = [head(page, f"{e['name']} – Spielgrafik", plain(st.get("summary") or e["brief"][:200]), nav, og_image=poster)]
    facts = [(STATUS[e["status"]][0], "Status"), (KIND[e["kind"]], fam["name"] if e["kind"] == "style" else "Art"),
             (st.get("era") or "–", "Epoche"),
             (st.get("image_generations") if isinstance(st.get("image_generations"), int) else "–", "KI-Bilder")]
    out.append(mast("", h(e["name"]), txt(st.get("summary") or ""), facts, crumbs))

    # Video groß, daneben das Urteil fürs Textadventure und die Bewertungen
    video = media_url(e, "video")
    if video:
        w, hh = e["media_dims"].get("poster") or (1280, 720)
        links = [f'<a href="{rel(page, video)}" download>Video (MP4)</a>']
        if e["media"].get("gif"):
            links.append(f'<a href="{rel(page, media_url(e, "gif"))}">Vorschau als GIF</a>')
        if poster:
            links.append(f'<a href="{rel(page, poster)}">Standbild</a>')
        cap = e["capture"]
        if cap.get("native") and cap.get("size") and cap["native"] != cap["size"]:
            links.append(f'<span>Basisauflösung {cap["native"][0]}×{cap["native"][1]}, '
                         f'aufgenommen in {cap["size"][0]}×{cap["size"][1]}</span>')
        player = (f'<figure class="player"><video controls muted loop playsinline preload="none" data-autoplay '
                  f'{f"poster=\"{rel(page, poster)}\" " if poster else ""}width="{w}" height="{hh}" src="{rel(page, video)}" '
                  f'aria-label="Demo: {h(e["name"])}"></video>'
                  f'<figcaption>{" · ".join(links)}</figcaption></figure>')
    elif poster:
        w, hh = e["media_dims"]["poster"]
        player = (f'<figure class="player"><img src="{rel(page, poster)}" width="{w}" height="{hh}" alt="{h(alt_text(e))}">'
                  f'<figcaption>Standbild, kein Video vorhanden</figcaption></figure>')
    else:
        player = (f'<figure class="player"><div class="ph-big"><p><b>{STATUS[e["status"]][0]}.</b> '
                  f'Keine Aufnahme vorhanden. {h(STATUS[e["status"]][1])}</p></div></figure>')
    verdict = ""
    if st.get("verdict") or ratings.get("text_adventure"):
        ta = ratings.get("text_adventure")
        score = (f'<p class="score">{pips(ta, True)}<span>Eignung {ta} von 5</span></p>' if ta else "")
        verdict = (f'<div class="verdict"><h2>Für unser Textadventure</h2>{score}'
                   f'{f"<p>{txt(st["verdict"])}</p>" if st.get("verdict") else ""}</div>')
    axes = ""
    if ratings:
        rows = []
        for key, name, _, expl in AXES:
            v = ratings.get(key)
            val = (f'{pips(v, key == "text_adventure")}<b>{v}</b><span class="sr-only"> von 5</span>' if v
                   else '<b>–</b><span class="sr-only">keine Angabe</span>')
            rows.append(f'<div class="axis"><span class="ax-l">{h(name)}</span><span class="ax-v">{val}</span>'
                        f'<p>{h(expl)}</p></div>')
        note = f'<p class="muted" style="font-size:14.5px;margin-top:10px">{txt(st["ratings_note"])}</p>' if st.get("ratings_note") else ""
        axes = f'<div class="box"><h2>Bewertungen</h2><div class="axes">{"".join(rows)}</div>{note}</div>'
    out.append(f'<section class="sec"><h2 class="sr-only">Demo</h2><div class="wrap hero">{player}'
               f'<div class="side">{verdict}{axes}</div></div></section>')

    if e["media"].get("frames"):
        fw, fh = e["media_dims"]["frames"]
        out.append(f'<section class="sec"><div class="wrap">{sec_head("Kontaktbogen", "Acht Zeitpunkte aus der Aufnahme, für die Sichtprüfung.")}'
                   f'<figure class="frames figure"><img src="{rel(page, media_url(e, "frames"))}" width="{fw}" height="{fh}" '
                   f'loading="lazy" alt="Kontaktbogen von {h(e["name"])}: acht Standbilder der Demo über sechs Sekunden">'
                   f'<figcaption>Erzeugt von tools/capture.py, Zeitstempel oben links.</figcaption></figure></div></section>')

    left, right = [], []
    if st.get("traits"):
        left.append(f'<div class="box"><h2>Merkmale</h2>{lst(st["traits"])}</div>')
    if st.get("pipeline"):
        steps = []
        for p in st["pipeline"]:
            if isinstance(p, dict):
                detail = f"<p>{txt(p['detail'])}</p>" if p.get("detail") else ""
                steps.append(f'<li><b>{txt(p.get("step", ""))}</b><span class="tags">{tool_chips(p.get("tool"))}</span>'
                             f'{detail}</li>')
            else:
                steps.append(f"<li><b>{txt(p)}</b></li>")
        left.append(f'<div class="box"><h2>Werkzeugkette</h2><ol class="steps">{"".join(steps)}</ol></div>')
    if st.get("godot"):
        left.append(f'<div class="box"><h2>Umsetzung in Godot</h2>{lst(st["godot"])}</div>')
    if st.get("pitfalls"):
        left.append(f'<div class="box"><h2>Fallstricke</h2>{lst(st["pitfalls"])}</div>')
    if st.get("lessons"):
        left.append(f'<div class="box"><h2>Erkenntnisse</h2>{lst(st["lessons"])}</div>')
    if st.get("tool_issues"):
        left.append(f'<div class="box"><h2>Probleme mit Werkzeugen</h2>{lst(st["tool_issues"])}</div>')

    kv = [("Status", f'{badge(e["status"])} <span class="muted">{h(STATUS[e["status"]][1])}</span>'),
          ("Art", h(KIND[e["kind"]])), ("Familie", h(fam["name"]))]
    for key, label in (("era", "Epoche"), ("camera", "Kamera"), ("resolution", "Auflösung")):
        if st.get(key):
            kv.append((label, txt(st[key])))
    if isinstance(st.get("image_generations"), int):
        kv.append(("KI-Bilder", f'{st["image_generations"]} Bilderzeugungen, Wiederholungen eingerechnet'
                   + (f'; {len(e["prompts"])} Prompts dokumentiert' if e["prompts"] else "")))
    if needs3d:
        kv.append(("Grundlage", h(needs3d)))
    right.append(f'<dl class="kv box">{"".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in kv)}</dl>')
    if st.get("references"):
        right.append(f'<div class="box"><h2>Vorbilder</h2>{lst(st["references"])}</div>')
    if st.get("techniques"):
        right.append(f'<div class="box"><h2>Gezeigte Techniken</h2><div class="tags">'
                     f'{"".join(tech_tag(D, str(t), page) for t in st["techniques"])}</div></div>')
    if e["kind"] == "technique":
        used = [x for x in users.get(e["slug"], []) if x is not e]
        right.append(f'<div class="box"><h2>Kommt vor in</h2>'
                     + (f'<div class="tags">{entry_tags(used, page)}</div>' if used else
                        '<p class="muted">Noch kein gebauter Stil nennt diese Technik.</p>') + "</div>")
    if e["brief"]:
        right.append(f'<div class="box"><h2>Auftrag aus dem Katalog</h2><p class="muted">{txt(e["brief"])}</p></div>')
    if st.get("licenses"):
        rows = []
        for item in st["licenses"]:
            if isinstance(item, dict):
                src = item.get("source", "")
                src_html = linkify(src)                    # nur die Adressen werden Links, der Rest bleibt Text
                rows.append(f'<li><b>{txt(item.get("item", ""))}</b> · {txt(item.get("license", ""))}'
                            f'{f" · {src_html}" if src else ""}</li>')
            else:
                rows.append(f"<li>{linkify(item)}</li>")
        right.append(f'<div class="box"><h2>Lizenzen</h2><ul class="list">{"".join(rows)}</ul></div>')
    out.append(f'<section class="sec"><h2 class="sr-only">Steckbrief</h2><div class="wrap sheet">'
               f'<div>{"".join(left)}</div><div>{"".join(right)}</div></div></section>')

    # Assets
    if e["assets"]:
        prompt_ids = {pathlib.PurePosixPath(str(p.get("file", ""))).with_suffix("").as_posix(): i
                      for i, p in enumerate(e["prompts"], 1)}
        figs = []
        for a in e["assets"]:
            info = e["asset_out"][a["file"]]
            label = asset_kind(a.get("kind"))
            made = a.get("made_with") or ""
            pid = None
            if a.get("prompt"):
                pid = prompt_ids.get(pathlib.PurePosixPath(str(a["prompt"])).with_suffix("").as_posix())
            plink = f' · <a href="#prompt-{pid}">Prompt</a>' if pid else ""
            href = rel(page, info["href"])
            if info["image"]:
                ow, oh = info["orig"]
                pixel = " pixel" if ow and max(ow, oh) <= PIXEL_EDGE else ""
                dims = f' width="{info["w"]}" height="{info["h"]}"' if info["w"] else ""
                # Art und Beschriftung statt Dateipfad (Pfade in made_with nur als Dateiname), höchstens ALT_MAX Zeichen
                desc = PATH_RE.sub(r"\1", plain(made))
                alt = shorten(f"{label}: {desc}" if made else f"{label} aus {e['name']}")
                body = (f'<a class="aimg{pixel}" href="{href}"><img src="{rel(page, info["src"])}"{dims} loading="lazy" '
                        f'decoding="async" alt="{h(alt)}"></a>')
                size = f" · {ow}×{oh}" if ow else ""
            else:
                body = f'<a class="afile" href="{href}">{h(pathlib.PurePosixPath(a["file"]).name)}</a>'
                size = ""
            figs.append(f'<figure class="asset">{body}<figcaption><b>{h(label)}</b>'
                        f'{f"<span>{txt(made)}</span>" if made else ""}'
                        f'<span><a href="{href}">{h(a["file"])}</a>{size}{plink}</span></figcaption></figure>')
        out.append(f'<section class="sec"><div class="wrap">{sec_head("Assets", "Die verarbeiteten Dateien, aus denen die Demo gebaut ist. Ein Klick öffnet das Original.")}'
                   f'<div class="gallery">{"".join(figs)}</div></div></section>')

    if e["prompts"]:
        items = []
        for i, p in enumerate(e["prompts"], 1):
            refs = p.get("refs") or []
            model = BACKENDS.get(p.get("backend") or "codex", p.get("backend"))
            meta = [x for x in (model, p.get("size"),
                                f"{len(refs)} Referenzbild{'er' if len(refs) != 1 else ''}" if refs else "") if x]
            sent = (f'<p class="refs">Tatsächlich gesendet (weicht vom Auftrag ab):</p>'
                    f'<pre class="prompt" lang="en">{h(p["prompt_sent"])}</pre>' if p.get("prompt_sent") else "")
            items.append(f'<details id="prompt-{i}"><summary><b>{h(p.get("file") or f"Prompt {i}")}</b>'
                         f'<span>{h(" · ".join(meta))}</span></summary>'
                         f'<pre class="prompt" lang="en">{h(p["prompt"])}</pre>{sent}'
                         + (f'<p class="refs">Referenzen: {h(", ".join(map(str, refs)))}</p>' if refs else "")
                         + "</details>")
        out.append(f'<section class="sec"><div class="wrap">{sec_head("Prompts", "Wortlaut der Bildaufträge, gesammelt aus den Begleitdateien von tools/genimg.py, mit dem Bildmodell, das das Bild erzeugt hat.")}'
                   f'<div class="prompts">{"".join(items)}</div></div></section>')

    extra = {k: v for k, v in st.items() if k not in KNOWN_KEYS and v not in (None, "", [], {})}
    if extra:
        boxes = "".join(f'<div class="box"><h3 class="mono">{h(k)}</h3>{render_extra(v)}</div>' for k, v in extra.items())
        out.append(f'<section class="sec"><div class="wrap">{sec_head("Weitere Angaben", "Felder aus style.json, die nicht zum festen Schema gehören.")}'
                   f'<div class="sheet"><div>{boxes}</div></div></div></section>')

    out.append(pager(D, e, page))
    out.append(foot(page))
    return O.write(page, "".join(out))


def page_planned(D, O, e, users, page, crumbs, nav, needs3d):
    fam = D["fam"][e["family"]]
    out = [head(page, f"{e['name']} – Spielgrafik", e["brief"][:200] or e["name"], nav)]
    lede = ("Für diesen Eintrag ist ein Ordner angelegt, der Steckbrief fehlt noch." if e["status"] == "wip"
            else "Noch nicht gebaut. Bisher steht nur der Auftrag fest.")
    out.append(mast("", h(e["name"]), h(lede),
                    [(STATUS[e["status"]][0], "Status"), (KIND[e["kind"]], "Art"), ("3D" if needs3d else "2D", "Grundlage"),
                     (f'{e["order"] + 1}/{len(D["entries"])}', "im Katalog")], crumbs))
    boxes = [f'<div class="box"><h2>Auftrag</h2><p>{txt(e["brief"] or "Kein Auftragstext.")}</p></div>']
    if needs3d:
        boxes.append(f'<div class="box"><h2>Grundlage</h2><p>{h(needs3d)}</p></div>')
    side = []
    if e["kind"] == "technique":
        used = users.get(e["slug"], [])
        side.append(f'<div class="box"><h2>Kommt vor in</h2>'
                    + (f'<div class="tags">{entry_tags(used, page)}</div>' if used else
                       '<p class="muted">Noch kein gebauter Stil nennt diese Technik.</p>') + "</div>")
    side.append(f'<div class="box"><h2>Wie ein Eintrag entsteht</h2><p class="muted">Bilder erzeugen, verarbeiten, '
                f'als Godot-Demo zusammensetzen, aufnehmen und ehrlich beschreiben. '
                f'<a href="{rel(page, "werkzeuge/")}">Werkzeuge und Regeln</a>.</p></div>')
    out.append(f'<section class="sec"><h2 class="sr-only">Auftrag</h2><div class="wrap sheet"><div>{"".join(boxes)}</div>'
               f'<div>{"".join(side)}</div></div></section>')
    out.append(pager(D, e, page))
    out.append(foot(page))
    return O.write(page, "".join(out))


def page_compare(D, O):
    page = "vergleich/"
    built = [e for e in D["entries"] if is_built(e)]
    out = [head(page, "Vergleich – Spielgrafik", "Alle gebauten Einträge mit fünf Bewertungen im Vergleich.", "vergleich")]
    out.append(mast("Vergleich", "Bewertungen <em>im Vergleich</em>",
                    "Fünf Achsen von 1 bis 5, vergeben nach der Sichtprüfung der Demo. Es sind Einschätzungen der "
                    "Bauenden, keine Messwerte; die Begründung steht jeweils auf der Seite des Eintrags.",
                    [(len(built), "gebaut"), (sum(e["status"] == "done" for e in built), "fertig"),
                     (sum(e["status"] == "partial" for e in built), "teilweise"),
                     (sum(e["status"] in ("blocked", "failed") for e in built), "blockiert oder gescheitert")]))
    expl = "".join(f"<li><b>{h(name)}</b>: {h(expl)}</li>" for _, name, _, expl in AXES)
    if not built:
        body = '<p class="empty">Noch keine gebauten Einträge. Sobald ein Steckbrief vorliegt, erscheint er hier.</p>'
    else:
        heads = ['<th scope="col" data-type="text"><button type="button">Eintrag</button></th>',
                 '<th scope="col" data-type="text"><button type="button">Familie</button></th>',
                 '<th scope="col" data-type="num"><button type="button">Status</button></th>']
        heads += [f'<th scope="col" data-type="num"><button type="button">{h(name)}</button></th>' for _, name, _, _ in AXES]
        heads.append('<th scope="col" data-type="num"><button type="button">KI-Bilder</button></th>')
        rows = []
        for e in built:
            st = e["st"]
            r = st.get("ratings") or {}
            era = f" · {h(st['era'])}" if st.get("era") else ""
            cells = [f'<th scope="row" data-v="{h(e["name"])}"><a href="{rel(page, e["slug"] + "/")}">{h(e["name"])}</a>'
                     f'<small>{h(KIND[e["kind"]])}{era}</small></th>',
                     f'<td data-v="{h(D["fam"][e["family"]]["name"])}">{h(D["fam"][e["family"]]["name"])}</td>',
                     f'<td data-v="{list(STATUS).index(e["status"])}">{badge(e["status"])}</td>']
            for key, *_ in AXES:
                v = r.get(key)
                cells.append(f'<td class="num" data-v="{v or ""}">{pips(v, key == "text_adventure") + str(v) if v else "–"}</td>')
            g = st.get("image_generations")
            cells.append(f'<td class="num" data-v="{g if isinstance(g, int) else ""}">{g if isinstance(g, int) else "–"}</td>')
            rows.append(f'<tr data-order="{e["order"]}">{"".join(cells)}</tr>')
        body = (f'<div class="tbl-wrap" role="region" aria-labelledby="cmp-cap" tabindex="0">'
                f'<table class="cmp" data-sortable><caption id="cmp-cap">{len(built)} gebaute Einträge. '
                f'Spaltenköpfe sortieren; Aufwand: 5 = hoch.</caption>'
                f'<thead><tr>{"".join(heads)}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    out.append(f'<section class="sec"><div class="wrap">{sec_head("Alle gebauten Einträge", f"<ul class=\"list\">{expl}</ul>", block=True)}'
               f'{body}</div></section>')
    out.append(foot(page))
    return O.write(page, "".join(out))


def page_techniques(D, O, users):
    page = "techniken/"
    techs = [e for e in D["entries"] if e["kind"] == "technique"]
    out = [head(page, "Techniken – Spielgrafik", "Techniken des Katalogs und in welchen Stilen sie vorkommen.", "techniken")]
    out.append(mast("Techniken", "Techniken <em>quer zu den Stilen</em>",
                    "Techniken sind Bausteine, die in vielen Stilen funktionieren: Animation, Licht, Kacheln, "
                    "Oberflächen. Jede hat einen eigenen Eintrag mit Demo; darunter steht, welche Stile sie verwenden.",
                    [(len(techs), "Technik-Einträge"), (sum(is_built(e) for e in techs), "gebaut"),
                     (len(users), "genannte Techniken"), (sum(len(v) for v in users.values()), "Verwendungen")]))
    cards = []
    for e in techs:
        used = [x for x in users.get(e["slug"], []) if x is not e]
        extra = (f'<p class="uses">Kommt vor in: {", ".join(f"<a href=\"{rel(page, x["slug"] + "/")}\">{h(x["name"])}</a>" for x in used)}</p>'
                 if used else '<p class="uses muted">Noch in keinem gebauten Stil genannt.</p>')
        cards.append(card(D, e, page, extra))
    out.append(f'<section class="sec"><div class="wrap">{sec_head("Technik-Einträge", "Eigene Demos zu einer Technik, mit Auftrag, Werkzeugkette und Ergebnis.")}'
               f'<div class="cat-grid">{"".join(cards)}</div></div></section>')
    other = sorted((slug for slug in users if slug not in D["by"] or D["by"][slug]["kind"] != "technique"))
    if other:
        rows = "".join(f'<div class="box"><h3 class="mono">{h(slug)}</h3><div class="tags">{entry_tags(users[slug], page)}</div></div>'
                       for slug in other)
        out.append(f'<section class="sec"><div class="wrap">{sec_head("Weitere Techniken aus den Steckbriefen", "Techniken, die gebaute Stile in style.json nennen, ohne eigenen Technik-Eintrag.")}'
                   f'<div class="tools">{rows}</div></div></section>')
    out.append(foot(page))
    return O.write(page, "".join(out))


def page_adventure(D, O):
    page = "textadventure/"
    built = [e for e in D["entries"] if is_built(e)]
    rated = [e for e in built if (e["st"].get("ratings") or {}).get("text_adventure")]

    def key(e):
        r = e["st"]["ratings"]
        return (-r["text_adventure"], -(r.get("ai_fit") or 0), r.get("effort") or 6, e["order"])
    rated.sort(key=key)
    out = [head(page, "Für unser Textadventure – Spielgrafik",
                "Rangliste der gebauten Stile nach ihrer Eignung für unser erstes Spiel, ein Textadventure.", "textadventure")]
    out.append(mast("Rangliste", "Für unser <em>Textadventure</em>",
                    "Unser erstes Spiel ist ein Textadventure. Es braucht viele Orte mit je einem Bild, gut lesbaren "
                    "Text darüber, wenige Figuren und kaum Animation. Wichtig sind deshalb gleichbleibende Qualität über "
                    "viele Hintergründe, geringer Aufwand pro Bild und Lesbarkeit auf dem Telefon.",
                    [(len(rated), "bewertet"), (sum(e["st"]["ratings"]["text_adventure"] >= 4 for e in rated), "mit 4 oder 5"),
                     (len(built) - len(rated), "ohne Bewertung"),
                     (sum(e["status"] in ("planned", "wip") for e in D["entries"]), "noch nicht gebaut")]))
    if not rated:
        body = '<p class="empty">Noch keine bewerteten Einträge.</p>'
    else:
        items = []
        for i, e in enumerate(rated, 1):
            st = e["st"]
            poster = media_url(e, "poster")
            img = ""
            if poster:
                w, hh = e["media_dims"]["poster"]
                img = (f'<a class="rimg" href="{rel(page, e["slug"] + "/")}" tabindex="-1"><img src="{rel(page, poster)}" '
                       f'width="{w}" height="{hh}" loading="lazy" decoding="async" alt="{h(alt_text(e))}"></a>')
            ta = st["ratings"]["text_adventure"]
            items.append(f'<li><span class="no" aria-hidden="true">{i}</span>{img}<div class="rbody">'
                         f'<p class="rmeta">{h(D["fam"][e["family"]]["name"])}</p>'
                         f'<h3><a href="{rel(page, e["slug"] + "/")}">{h(e["name"])}</a></h3>'
                         f'<p class="rrow">{badge(e["status"])}{pips(ta, True)}'
                         f'<span>Eignung {ta} von 5</span></p>'
                         f'<p>{txt(st.get("verdict") or "Kein Urteil eingetragen.")}</p></div></li>')
        body = f'<ol class="rank">{"".join(items)}</ol>'
    out.append(f'<section class="sec"><div class="wrap">{sec_head("Rangliste", "Sortiert nach Eignung, bei Gleichstand nach KI-Beitrag und geringerem Aufwand.")}'
               f'{body}</div></section>')
    out.append(foot(page))
    return O.write(page, "".join(out))


def page_tools(D, O, sheet):
    page = "werkzeuge/"
    m = D["motif"]
    scene, char, ui = m.get("scene", {}), m.get("character", {}), m.get("ui_text", {})
    out = [head(page, "Werkzeuge – Spielgrafik",
                "Werkzeugkette, gemeinsame Szene und Figur, Ehrlichkeitsregeln und Lizenzhinweise des Spielgrafik-Katalogs.",
                "werkzeuge")]
    out.append(mast("Werkzeuge & Regeln", "Wie ein Eintrag <em>entsteht</em>",
                    "Jeder Eintrag folgt derselben Anleitung (PIPELINE.md): Bilder erzeugen, verarbeiten, in Godot "
                    "zusammensetzen, aufnehmen, ehrlich beschreiben. Alles läuft per Skript, damit es wiederholbar ist.",
                    [("gpt-image, Gemini", "Bilder"), ("Godot 4.7", "Demos"), ("Blender 5.2", "3D"), ("6 s · 30 fps", "Aufnahme")]))
    flow = [("Auftrag", "data/catalog.json beschreibt Merkmale, Auflösung und Kamera."),
            ("Bilder", "genimg.py erzeugt Hintergründe, Figuren und Requisiten, höchstens 10 je Eintrag."),
            ("Verarbeiten", "sprites.py stellt frei, zerlegt Sprite-Sheets und rastet auf Pixelraster und Palette ein."),
            ("3D", "Blender baut Szenen per Skript und exportiert glTF, wo der Stil 3D braucht."),
            ("Demo", "Ein eigenständiges Godot-Projekt zeigt Szene, Figur, Umgebungsanimation und Textbox."),
            ("Aufnahme", "capture.py nimmt sechs Sekunden auf und prüft auf Fehler und Bewegung."),
            ("Steckbrief", "style.json hält fest, was funktioniert hat und was nicht."),
            ("Website", "collect_prompts.py und build.py erzeugen diese Seiten.")]
    out.append(f'<section class="sec"><div class="wrap">{sec_head("Ablauf")}'
               f'<ol class="flow">{"".join(f"<li><b>{h(t)}</b>{h(d)}</li>" for t, d in flow)}</ol></div></section>')

    tools = [
        ("Bilderzeugung", "tools/genimg.py",
         "Ruft das Gemini-Bildmodell über Antigravity CLI (agy) oder gpt-image über das "
         "eingebaute image_gen-Werkzeug von Codex CLI auf. Standard ist agy; Bilder mit transparentem Hintergrund "
         "gehen zuerst an gpt-image (echter Alphakanal), Folgebilder eigener Referenzbilder (Masken, Varianten) "
         "bleiben beim Modell ihrer Vorlage, und ist ein Weg erschöpft, übernimmt der andere. Wo agy freistellen "
         "muss, wird vor Magenta erzeugt und automatisch freigestellt. Referenzbilder (--ref) halten Figur "
         "und Palette über mehrere Bilder gleich. Neben jedes Bild schreibt das Werkzeug eine JSON-Datei mit Prompt, "
         "Größe, Referenzen, Bildmodell und Dauer. Prompts sind englisch, nennen keine Spiele, Studios oder Künstler "
         "und bestehen aus Stilblock, Motivblock und Schutzregeln.",
         "genimg.py --out styles/<slug>/assets/raw/bg.png --size 1536x1024 \\\n  --prompt-file p.txt --ref shared/badger/master_sheet.png"),
        ("Sprites und Pixel", "tools/sprites.py",
         "Stellt einfarbige Hintergründe frei (key), zerlegt Sprite-Sheets in Einzelbilder (slice), bringt Bilder auf "
         "ein echtes Pixelraster mit fester Palette (pixelize, optional mit Bayer-Dithering) und zieht Paletten aus "
         "Bildern (palette).",
         "sprites.py pixelize in.png out.png --width 320 --palette ega --resample mode"),
        ("Aufnahme", "tools/capture.py",
         "Importiert das Godot-Projekt, nimmt mit dem Movie Maker sechs Sekunden bei 30 fps auf, skaliert Pixel-Stile "
         "ganzzahlig auf 1280×720 und schreibt Video, GIF, Standbild und Kontaktbogen. Bricht ab bei Godot-Fehlern, "
         "fehlender Bewegung oder fast einfarbigem Bild.",
         "capture.py styles/<slug>"),
        ("3D per Skript", "Blender 5.2 LTS",
         "Läuft ohne Oberfläche (blender -b --factory-startup -P …). Szenen entstehen im Skript, Export als glTF nach "
         "Godot oder gerenderte Bilder; .blend-Dateien werden nicht eingecheckt. 3D-Stile sollen auf einer gemeinsamen "
         "Hafenszene mit geriggtem Dachs aufbauen, damit sie vergleichbar bleiben.",
         "blender -b --factory-startup -P styles/<slug>/blender/build.py"),
        ("Spiel-Engine", "Godot 4.7",
         "Jede Demo ist ein eigenständiges Projekt mit GDScript, Szenen und Shadern als Textdateien, ohne Editor und "
         "ohne Plugins. Zeit und Zufall sind deterministisch (feste Seeds), damit Aufnahmen reproduzierbar sind. "
         "Pixel-Stile rendern in Rasterauflösung mit Nearest-Filter.",
         "godot --headless --path styles/<slug>/demo --import"),
        ("Website", "tools/collect_prompts.py · build.py",
         "collect_prompts.py liest die Begleitdateien der Rohbilder (die nicht eingecheckt werden) und schreibt "
         "prompts.json je Eintrag. build.py erzeugt daraus und aus den Steckbriefen diese statische Website, nur mit der "
         "Python-Standardbibliothek.",
         "python3 tools/collect_prompts.py && python3 build.py"),
    ]
    cards = "".join(f'<div class="tool-c"><span class="lab">{h(lab)}</span><h3>{h(name)}</h3><p>{h(text)}</p>'
                    f'<pre class="cmd">{h(cmd)}</pre></div>' for lab, name, text, cmd in tools)
    out.append(f'<section class="sec"><div class="wrap">{sec_head("Werkzeugkette", "Jedes Werkzeug ist ein Skript im Repository oder ein frei verfügbares Programm.")}'
               f'<div class="tools">{cards}</div></div></section>')

    elements = lst(scene.get("elements_required", []))
    ambient = lst(scene.get("ambient_animations", []))
    reqs = lst(m.get("demo", {}).get("requirements_de", []))
    choices = "".join(f"<li>{h(c)}</li>" for c in ui.get("choices", []))
    choices_html = f"<ol>{choices}</ol>" if choices else ""
    parser_html = f'<p class="parser">{h(ui["parser_prompt"])}</p>' if ui.get("parser_prompt") else ""
    uibox = (f'<div class="uibox"><span class="loc">{h(ui.get("location", ""))}</span>'
             f'<p>{h(ui.get("line", ""))}</p>{choices_html}{parser_html}</div>')
    out.append(f"""<section class="sec"><div class="wrap">{sec_head("Die gemeinsame Szene", h(scene.get("name_de", "")) + ". Jeder Eintrag zeigt sie, damit sich Stile direkt vergleichen lassen.")}
<div class="sheet"><div>
<div class="box"><h3>Szene</h3><p>{h(scene.get("summary_de", ""))}</p></div>
<div class="box"><h3>Pflichtelemente</h3>{elements}</div>
<div class="box"><h3>Anforderungen an die Demo</h3>{reqs}</div>
</div><div>
<div class="box"><h3>Umgebungsanimationen (mindestens zwei)</h3>{ambient}</div>
<div class="box"><h3>Text in jeder Demo</h3><p class="muted" style="margin-bottom:10px">Von Godot mit echter Schrift gesetzt, nicht vom Bildmodell; höchstens etwa 30 % des Bildes.</p>{uibox}</div>
</div></div></div></section>""")

    fig = ""
    if sheet:
        dims = f'width="{sheet["w"]}" height="{sheet["h"]}" ' if sheet["w"] else ""
        fig = (f'<figure class="figure"><a href="{rel(page, sheet["href"])}"><img src="{rel(page, sheet["src"])}" '
               f'{dims}loading="lazy" '
               f'alt="Referenzblatt des Dachs-Kuriers: Vorder-, Seiten- und Rückansicht vor magentafarbenem Grund"></a>'
               f'<figcaption>shared/badger/master_sheet.png · KI-erzeugt, Klick öffnet das Original</figcaption></figure>')
    prompt = (f'<details style="margin-top:12px"><summary>Prompt des Referenzblatts</summary>'
              f'<pre class="prompt" lang="en">{h(sheet["prompt"])}</pre></details>' if sheet and sheet.get("prompt") else "")
    out.append(f"""<section class="sec"><div class="wrap">{sec_head("Die Figur", h(char.get("name_de", "")) + ".")}
<div class="sheet"><div>{fig}</div><div>
<div class="box"><h3>Beschreibung</h3><p>{h(char.get("summary_de", ""))}</p></div>
<div class="box"><h3>Referenzblatt</h3><p>{h(char.get("reference_note", ""))}</p>{prompt}</div>
</div></div></div></section>""")

    rules = [
        ("Was nicht klappt, bleibt sichtbar", "Teilerfolge stehen als „teilweise“, abgebrochene Versuche als "
         "„blockiert“ oder „gescheitert“ im Katalog, mit Begründung. Fallstricke und Probleme mit Werkzeugen stehen auf "
         "jeder Eintragsseite."),
        ("Aufnahmen unverändert", "Video, Standbild und Kontaktbogen kommen direkt aus tools/capture.py. Der Kontaktbogen "
         "zeigt acht Zeitpunkte, damit Zittern, Farbsäume oder Lücken auffallen."),
        ("Bilderzeugungen gezählt", "Jeder Eintrag nennt die Zahl der KI-Bilder einschließlich Wiederholungen "
         "(höchstens 10) und veröffentlicht die Prompts im Wortlaut, mit dem Bildmodell und, falls abweichend, dem "
         "tatsächlich gesendeten Text."),
        ("Bewertungen begründet", "Die fünf Bewertungen sind Einschätzungen nach der Sichtprüfung, keine Messwerte. "
         "Jede Eintragsseite begründet sie."),
        ("Keine fremden Namen in Prompts", "Prompts beschreiben Technik, Epoche, Medium und Hardwaregrenzen. Spiele, "
         "die einen Stil prägten, stehen nur als Text im Steckbrief; fremde Bilder werden nicht gezeigt."),
    ]
    out.append(f'<section class="sec"><div class="wrap">{sec_head("Ehrlichkeitsregeln")}'
               f'<div class="tools">{"".join(f"<div class=\"tool-c\"><h3>{h(t)}</h3><p>{h(d)}</p></div>" for t, d in rules)}</div>'
               f'<div class="box" style="margin-top:22px"><h3>Status</h3><dl class="kv">'
               f'{"".join(f"<dt>{badge(s)}</dt><dd>{h(STATUS[s][1])}</dd>" for s in STATUS)}</dl></div></div></section>')

    lic = [
        ("KI-Bilder", "Hintergründe, Figuren und Requisiten entstehen mit gpt-image über Codex CLI oder mit dem "
         "Gemini-Bildmodell über Antigravity CLI; die Rechte an den Ausgaben regeln die Nutzungsbedingungen von OpenAI "
         "bzw. Google. Rein maschinell erzeugte Bilder sind nach deutschem Recht "
         "in der Regel nicht urheberrechtlich geschützt. Die Figur ist ein eigenes Motiv."),
        ("Schriften", "In den Demos nur Schriften unter SIL Open Font License oder CC0, mit Lizenztext im Ordner "
         "demo/fonts/ des Eintrags. Diese Website nutzt Inter und IBM Plex Mono (beide SIL OFL 1.1) und liefert sie "
         "selbst aus, ohne Anfragen an Google; die Lizenztexte liegen neben den Schriftdateien in assets/fonts/."),
        ("Texturen", "Fremde Texturen nur unter CC0, etwa von Poly Haven oder ambientCG; die Quelle steht unter "
         "„Lizenzen“ auf der Eintragsseite."),
        ("Programme", "Godot steht unter MIT-Lizenz, Blender unter GPL; mit Blender erzeugte Dateien fallen nicht unter "
         "die GPL."),
        ("Steam", "Steam verlangt beim Einreichen eines Spiels Angaben zu KI-Inhalten. Vorab erzeugte Inhalte wie diese "
         "Assets müssen dort beschrieben werden und gelten wie alle Inhalte: nichts Rechtswidriges, keine fremden Rechte "
         "verletzt."),
    ]
    out.append(f'<section class="sec" id="lizenzen"><div class="wrap">{sec_head("Lizenzhinweise", "Kurzfassung, keine Rechtsberatung. Einzelne Lizenzen stehen auf jeder Eintragsseite.")}'
               f'<div class="tools">{"".join(f"<div class=\"tool-c\"><h3>{h(t)}</h3><p>{h(d)}</p></div>" for t, d in lic)}</div></div></section>')
    out.append(foot(page))
    return O.write(page, "".join(out))


def page_legal(O):
    """Impressum; die Angaben kommen nur aus data/legal.json, die Sätze wie in bildsprache (de/impressum/)."""
    page = "impressum/"
    address = "<br>".join(h(x) for x in LEGAL["address"])
    mail = h(LEGAL["email"])
    out = [head(page, "Impressum – Spielgrafik",
                "Angaben zum Anbieter von Spielgrafik nach § 5 DDG und § 18 Abs. 2 MStV.", "impressum"),
           '<section class="mast"><div class="wrap mast-in"><div><p class="eyebrow">Rechtliches</p><h1>Impressum</h1>'
           '</div></div></section>',
           f"""<section class="sec"><div class="wrap sheet"><div>
<div class="box"><h2>Angaben gemäß § 5 DDG</h2><p>{h(LEGAL['name'])}<br>{address}</p>
<p class="muted">Bitte versende keine Pakete an diese Adresse.</p></div>
<div class="box"><h2>Kontakt</h2><p>E-Mail: <a href="mailto:{mail}">{mail}</a></p></div>
<div class="box"><h2>Umsatzsteuer-ID</h2><p>Umsatzsteuer-Identifikationsnummer gemäß § 27 a Umsatzsteuergesetz:<br>{h(LEGAL['vat_id'])}</p></div>
<div class="box"><h2>Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV</h2><p>{h(LEGAL['responsible'])}<br>{address}</p></div>
</div></div></section>""",
           foot(page)]
    return O.write(page, "".join(out))


def page_404(O):
    O.write("404.html", f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Nicht gefunden – Spielgrafik</title>
<script>{(SITE_SRC / 'theme.js').read_text(encoding='utf-8')}</script><style>{theme_css()}body{{margin:0;font:17px/1.6 Inter,Helvetica,Arial,sans-serif;background:var(--ground);
color:var(--ink);display:grid;place-items:center;min-height:100vh;padding:16px}}a{{color:var(--accent)}}</style></head>
<body><main><h1>404</h1><p>Diese Seite gibt es nicht.</p><p><a href="/spielgrafik/">Zum Katalog</a></p>
<p><a href="/spielgrafik/impressum/">Impressum</a></p></main></body></html>
""")


# ---------------------------------------------------------------------------
# Ablauf
# ---------------------------------------------------------------------------
def copy_media(D, O):
    for e in D["entries"]:
        e["media_dims"] = {}
        e["asset_out"] = {}
        if not is_built(e):
            continue
        for key, p in e["media"].items():
            O.copy(p, f"{e['slug']}/media/{p.name}")
            if key in ("poster", "frames"):
                e["media_dims"][key] = image_size(p) or (1280, 720)
        for a in e["assets"]:
            dst = f"{e['slug']}/{a['file']}"
            if a["src"].suffix.lower() in IMAGE_EXT:
                src, w, hh, orig = O.image(a["src"], dst)
                e["asset_out"][a["file"]] = {"image": True, "href": dst, "src": src, "w": w, "h": hh, "orig": orig}
            elif a["src"].suffix.lower() == ".json":
                O.copy_json(a["src"], dst)                  # ohne PRIVATE_JSON_KEYS
                e["asset_out"][a["file"]] = {"image": False, "href": dst}
            else:
                O.copy(a["src"], dst)
                e["asset_out"][a["file"]] = {"image": False, "href": dst}


def copy_sheet(D, O):
    src = D["root"] / "shared" / "badger" / "master_sheet.png"
    if not src.exists():
        print("  WARNUNG: shared/badger/master_sheet.png fehlt – Werkzeugseite ohne Figurenbild", file=sys.stderr)
        return None
    shown, w, hh, _ = O.image(src, "assets/master_sheet.png")
    meta = src.with_suffix(".json")
    prompt = None
    if meta.exists():
        try:
            prompt = json.loads(meta.read_text(encoding="utf-8")).get("prompt")
        except ValueError:
            print("  WARNUNG: shared/badger/master_sheet.json ist kein gültiges JSON", file=sys.stderr)
    return {"href": "assets/master_sheet.png", "src": shown, "w": w, "h": hh, "prompt": prompt}


def build(root=ROOT, out=None, use_tools=True, quiet=False):
    """Baut die Website. Gibt die Liste der Warnungen zurück; wirft DataError bei Datenfehlern."""
    root = pathlib.Path(root).resolve()
    final = pathlib.Path(out).resolve() if out else ROOT / "docs"
    D, warnings = load(root)
    tmp = final.parent / (final.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    O = Out(tmp, final if final.exists() else None, use_tools)
    try:
        (tmp / "assets").mkdir()
        (tmp / "assets" / "site.css").write_text(site_css(), encoding="utf-8")   # mit @font-face-Regeln
        O.copy(SITE_SRC / "site.js", "assets/site.js")
        for f in FONTDATA["faces"]:
            O.copy(SITE_SRC / "fonts" / f["file"], f"assets/fonts/{f['file']}")
        for lic in FONTDATA["licenses"]:          # Lizenztexte neben den Schriften (SIL OFL 1.1, Bedingung 2)
            O.copy(SITE_SRC / "fonts" / lic["file"], f"assets/fonts/{lic['file']}")
        O.copy(NOTICES, "THIRD_PARTY_NOTICES.txt")
        (tmp / ".nojekyll").write_text("", encoding="utf-8")
        copy_media(D, O)
        sheet = copy_sheet(D, O)
        users = technique_users(D)
        pages = [page_home(D, O), page_compare(D, O), page_techniques(D, O, users), page_adventure(D, O),
                 page_tools(D, O, sheet), page_legal(O)]
        pages += [page_entry(D, O, e, users) for e in D["entries"]]
        page_404(O)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    if final.exists():
        shutil.rmtree(final)
    tmp.rename(final)
    if not quiet:
        for w in warnings:
            print("  WARNUNG:", w, file=sys.stderr)
        c = counts(D)
        how = ("cwebp" if O.cwebp else "sips" if O.sips else "ohne Verkleinerung")
        print(f"  {len(pages)} Seiten, {c['all']} Einträge ({c['built']} gebaut, {c['planned']} geplant), "
              f"{O.files} Dateien kopiert, {O.thumbs} Bilder verkleinert ({how}), {O.reused} wiederverwendet "
              f"-> {final}")
    return warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description="Baut die Website des Spielgrafik-Katalogs.")
    ap.add_argument("--root", default=str(ROOT), help="Projektverzeichnis mit data/, styles/, shared/ (Standard: hier)")
    ap.add_argument("--out", default=None, help="Zielverzeichnis (Standard: docs/ im Projekt)")
    ap.add_argument("--copy-only", action="store_true", help="Bilder nur kopieren, nicht mit cwebp/sips verkleinern")
    a = ap.parse_args(argv)
    try:
        build(a.root, a.out, use_tools=not a.copy_only)
    except DataError as exc:
        for p in exc.args[0]:
            print("  FEHLER", p, file=sys.stderr)
        print(f"{len(exc.args[0])} Datenfehler – Build abgebrochen", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
