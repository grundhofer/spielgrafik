"""Prüft build.py und tools/collect_prompts.py mit den Testdaten in tests/fixtures/.

    python3 -m unittest discover -s tests

tests/fixtures/ hat den Aufbau des Projekts (data/, shared/, styles/); die Medien sind kleine ffmpeg-Testbilder:
  probe-pixel            fertig, alle Medien, Assets (großes PNG, kleines Sprite, Nicht-Bild, JSON mit internen
                         Feldern), prompts.json, Roh-Begleitdateien in assets/raw/ (plus eine Auftragsliste, die
                         übersprungen werden muss); Texte mit rohen Feldnamen, `Code`, internen Aufrufnamen und
                         Lizenzquellen mit URLs
  probe-gemalt           teilweise, nur poster.png und demo.mp4 (Ersatz für fehlendes poster.webp)
  probe-blockiert        blockiert, ohne Medien, mit einem Feld außerhalb des Schemas
  probe-technik          Technik, fertig, nennt sich selbst unter techniques
  probe-wip              Ordner ohne style.json (in Arbeit)
  probe-geplant, probe-technik-geplant   nur im Katalog (geplant)
TestProjectSite prüft zusätzlich das gebaute docs/ des Projekts, wenn es existiert (vorher python3 build.py), auch auf
lokale Pfade, interne Felder und E-Mail-Adressen außer der des Impressums.
TestGitignore prüft, dass git keine Datei ignoriert, die ein Steckbrief zeigt (braucht git und ein Repository).
"""
import hashlib, html.parser, json, pathlib, re, shutil, subprocess, sys, tempfile, unittest, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import build  # noqa: E402
import collect_prompts  # noqa: E402

BUILT = ["probe-pixel", "probe-gemalt", "probe-blockiert", "probe-technik"]
ALL = BUILT + ["probe-wip", "probe-geplant", "probe-technik-geplant"]
SECTIONS = ["vergleich", "techniken", "textadventure", "werkzeuge", "impressum"]


class Page(html.parser.HTMLParser):
    """Sammelt Verweise, IDs, Bilder und Videos einer Seite."""

    def __init__(self, text):
        super().__init__()
        self.refs, self.ids, self.imgs, self.videos, self.articles = [], set(), [], [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        for key in ("href", "src", "poster"):
            if a.get(key) and tag in ("a", "link", "img", "video", "source", "script"):
                self.refs.append(a[key])
        if tag == "img":
            self.imgs.append(a)
        if tag == "video":
            self.videos.append(a)
        if tag == "article":
            self.articles.append(a)


def pages(out):
    return sorted(p for p in out.rglob("*.html"))


def broken_refs(out):
    """Relative Verweise, die nicht auf eine vorhandene Datei oder ID zeigen; absolute Pfade gelten als Fehler."""
    problems = []
    parsed = {p: Page(p.read_text(encoding="utf-8")) for p in pages(out)}
    for page, doc in parsed.items():
        if page.name == "404.html":       # liegt unter beliebigen Pfaden, verweist absolut auf /spielgrafik/
            continue
        for ref in doc.refs:
            parts = urllib.parse.urlsplit(ref)
            if parts.scheme in ("http", "https", "data", "mailto"):
                continue
            where = f"{page.relative_to(out)} → {ref}"
            if parts.path.startswith("/"):
                problems.append(f"{where}: absoluter Pfad")
                continue
            if not parts.path:
                if parts.fragment and parts.fragment not in doc.ids:
                    problems.append(f"{where}: ID fehlt")
                continue
            target = (page.parent / urllib.parse.unquote(parts.path)).resolve()
            if out.resolve() not in target.parents and target != out.resolve():
                problems.append(f"{where}: zeigt aus der Website heraus")
                continue
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                problems.append(f"{where}: Datei fehlt")
                continue
            if parts.fragment and target.suffix == ".html":
                other = parsed.get(target) or Page(target.read_text(encoding="utf-8"))
                if parts.fragment not in other.ids:
                    problems.append(f"{where}: ID fehlt im Ziel")
    return problems


def luminance(hexcolor):
    rgb = [int(hexcolor[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class TestFixtureBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="spielgrafik-test-"))
        cls.out = cls.tmp / "site"
        cls.warnings = build.build(FIX, cls.out, use_tools=True, quiet=True)
        cls.ci = cls.tmp / "ci"                  # --copy-only: ohne cwebp/sips
        build.build(FIX, cls.ci, use_tools=False, quiet=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def read(self, rel, out=None):
        return ((out or self.out) / rel).read_text(encoding="utf-8")

    def test_pages_exist(self):
        for out in (self.out, self.ci):
            for rel in ["index.html", "404.html", "assets/site.css", "assets/site.js", ".nojekyll"] + \
                       [f"{s}/index.html" for s in SECTIONS + ALL]:
                with self.subTest(out=out.name, page=rel):
                    self.assertTrue((out / rel).is_file())
        self.assertFalse((self.tmp / "site.tmp").exists(), "Zwischenverzeichnis wurde nicht aufgeräumt")

    def test_links_and_media_resolve(self):
        for out in (self.out, self.ci):
            with self.subTest(out=out.name):
                self.assertEqual(broken_refs(out), [])

    def test_no_block_elements_inside_paragraphs(self):
        bad = re.compile(r"<p[ >](?:(?!</p>).)*?<(?:ul|ol|div|dl|pre|figure|section|h[1-6])[ >]", re.S)
        for page in pages(self.out):
            with self.subTest(page=str(page.relative_to(self.out))):
                self.assertIsNone(bad.search(page.read_text(encoding="utf-8")))

    def test_html_lang_and_titles(self):
        for page in pages(self.out):
            text = page.read_text(encoding="utf-8")
            with self.subTest(page=str(page.relative_to(self.out))):
                self.assertIn('<html lang="de">', text)
                self.assertRegex(text, r"<title>[^<]+</title>")
                self.assertNotIn("<script src=\"http", text, "kein externes JavaScript")

    def test_planned_and_wip_entries_listed_with_brief(self):
        doc = Page(self.read("index.html"))
        status = {a["data-name"]: a["data-status"] for a in doc.articles}
        self.assertEqual(status["Probe geplant"], "planned")
        self.assertEqual(status["Geplante Technik"], "planned")
        self.assertEqual(status["Probe in Arbeit"], "wip")
        self.assertEqual(status["Probe-Pixel"], "done")
        self.assertEqual(status["Probe gemalt"], "partial")
        self.assertEqual(status["Probe blockiert"], "blocked")
        self.assertEqual(len(doc.articles), len(ALL))
        home = self.read("index.html")
        self.assertIn("Auftrag für einen geplanten Eintrag: 320×180, feste Kamera.", home)
        planned = self.read("probe-geplant/index.html")
        self.assertIn("Geplant", planned)
        self.assertIn("Auftrag für einen geplanten Eintrag", planned)
        self.assertIn("shared/3d", planned)

    def test_card_videos_are_quiet_and_lazy(self):
        doc = Page(self.read("index.html"))
        self.assertEqual(len(doc.videos), 3)    # pixel, gemalt, technik
        for v in doc.videos:
            for attr in ("muted", "loop", "playsinline"):
                self.assertIn(attr, v)
            self.assertEqual(v.get("preload"), "none")
        self.assertIn('data-catalog', self.read("index.html"))

    def test_entry_page_content(self):
        text = self.read("probe-pixel/index.html")
        doc = Page(text)
        self.assertEqual(len(doc.videos), 1)
        self.assertEqual(doc.videos[0]["src"], "media/demo.mp4")
        self.assertEqual(doc.videos[0]["poster"], "media/poster.webp")
        for needle in ("Für unser Textadventure", "Gut geeignet für viele Orte.", "Kontaktbogen", "Merkmal eins",
                       "Merkmal zwei &lt;mit Klammern&gt; &amp; Zeichen", "Werkzeugkette", "pixelize",
                       "Umsetzung in Godot", "Fallstricke", "Erkenntnisse", "Vorbilder", "Lizenzen", "OFL-1.1",
                       "Pixel art background test prompt.", "shared/badger/master_sheet.png",
                       "Begründung der Bewertungen.", "320×180, 16 Farben", "Seitenansicht, feste Kamera",
                       "gpt-image (Codex CLI)", "Gemini (Antigravity CLI)", "Tatsächlich gesendet",
                       "pure magenta background (#FF00FF)",
                       "4 Bilderzeugungen", "2 Prompts dokumentiert", "Basisauflösung 320×180"):
            self.assertIn(needle, text)
        self.assertIn('href="../probe-technik/"', text)
        self.assertIn('href="../probe-technik-geplant/"', text)
        self.assertIn('<span class="tag">parallax</span>', text)
        self.assertIn('href="#prompt-1"', text)          # Asset verweist auf seinen Prompt
        self.assertIn('rel="next"', text)               # nächster Eintrag der Familie
        self.assertNotIn('rel="prev"', text)            # erster der Familie

    def test_alt_texts(self):
        for page in pages(self.out):
            for img in Page(page.read_text(encoding="utf-8")).imgs:
                with self.subTest(page=str(page.relative_to(self.out)), src=img.get("src")):
                    self.assertTrue((img.get("alt") or "").strip())
        home = Page(self.read("index.html"))
        alts = [i["alt"] for i in home.imgs]
        self.assertIn("Probe-Pixel: Poster der Demo", alts)
        assets = [i["alt"] for i in Page(self.read("probe-pixel/index.html")).imgs]
        self.assertIn("Hintergrund: gpt-image + pixelize", assets)
        self.assertIn("Sprite: gpt-image + sprites.py key", assets)
        for page in pages(self.out):
            for img in Page(page.read_text(encoding="utf-8")).imgs:
                with self.subTest(page=str(page.relative_to(self.out)), alt=img.get("alt")):
                    self.assertLessEqual(len(img["alt"]), build.ALT_MAX)
                    self.assertNotRegex(img["alt"], r"assets/\S+\.\w+")   # kein Dateipfad

    def test_only_listed_media_copied(self):
        files = lambda d: sorted(p.name for p in d.iterdir())  # noqa: E731
        self.assertEqual(files(self.out / "probe-pixel" / "media"), ["demo.mp4", "frames.jpg", "poster.webp", "preview.gif"])
        self.assertEqual(files(self.out / "probe-gemalt" / "media"), ["demo.mp4", "poster.png"])
        self.assertFalse((self.out / "probe-blockiert" / "media").exists())
        self.assertIn('src="probe-gemalt/media/poster.png"', self.read("index.html"))
        self.assertIn('poster="media/poster.png"', self.read("probe-gemalt/index.html"))
        self.assertTrue(any("poster.webp fehlt" in w for w in self.warnings))

    def test_assets_and_reduced_copies(self):
        for out in (self.out, self.ci):
            for name in ("bg.png", "sprite.png", "palette.gpl"):
                self.assertTrue((out / "probe-pixel" / "assets" / name).is_file(), name)
        ci_page = self.read("probe-pixel/index.html", self.ci)
        self.assertIn('<img src="assets/bg.png"', ci_page)
        self.assertEqual(list((self.ci / "probe-pixel" / "assets").glob("bg.*.*")), [])
        if shutil.which("cwebp") or shutil.which("sips"):
            thumbs = list((self.out / "probe-pixel" / "assets").glob("bg.*.*"))
            self.assertEqual(len(thumbs), 1, "großes PNG sollte verkleinert werden")
            self.assertIn(f'<img src="assets/{thumbs[0].name}"', self.read("probe-pixel/index.html"))
            self.assertIn('href="assets/bg.png"', self.read("probe-pixel/index.html"))
        self.assertIn('class="aimg pixel"', ci_page)   # kleines Sprite ohne Glättung

    def test_compare_table(self):
        text = self.read("vergleich/index.html")
        for slug in BUILT:
            self.assertIn(f'href="../{slug}/"', text)
        for slug in ("probe-geplant", "probe-wip", "probe-technik-geplant"):
            self.assertNotIn(f'href="../{slug}/"', text)
        self.assertEqual(text.count("<tr data-order="), len(BUILT))
        self.assertIn("data-sortable", text)

    def test_text_adventure_ranking(self):
        text = self.read("textadventure/index.html")
        order = [text.index(f'<h3><a href="../{s}/">') for s in ("probe-pixel", "probe-technik", "probe-gemalt")]
        self.assertEqual(order, sorted(order))   # 5 (KI 4), 5 (KI 3), 3
        self.assertNotIn('href="../probe-blockiert/"', text)   # ohne Bewertung
        self.assertIn("Gut geeignet für viele Orte.", text)

    def test_techniques_page(self):
        text = self.read("techniken/index.html")
        self.assertIn("Probe-Technik", text)
        self.assertIn("Geplante Technik", text)
        uses = text[text.index("Probe-Technik"):]
        self.assertIn('href="../probe-gemalt/"', uses)
        self.assertIn("parallax", text)
        self.assertIn("Kommt vor in", self.read("probe-technik/index.html"))
        self.assertIn('href="../probe-pixel/"', self.read("probe-technik-geplant/index.html"))

    def test_tools_page(self):
        text = self.read("werkzeuge/index.html")
        for needle in ("genimg.py", "sprites.py", "capture.py", "Blender", "Godot 4.7", "Ehrlichkeitsregeln",
                       'id="lizenzen"', "Steam", "CC0", "Hafen von Lornholm", "&gt; nimm paket",
                       "Test reference sheet prompt."):
            self.assertIn(needle, text)
        self.assertTrue((self.out / "assets" / "master_sheet.png").is_file())

    def test_unknown_fields_are_shown(self):
        text = self.read("probe-blockiert/index.html")
        self.assertIn("blocked_reason", text)
        self.assertIn("Tageslimit des Bildwerkzeugs erreicht", text)
        self.assertIn("Keine Aufnahme vorhanden", text)

    def test_theme_contrast(self):
        for mode, p in build.PALETTES.items():
            for fg in ("ink", "ink-2", "ink-3", "accent"):
                for bg in ("ground", "surface", "surface-2", "accent-soft"):
                    with self.subTest(mode=mode, fg=fg, bg=bg):
                        self.assertGreaterEqual(contrast(p[fg], p[bg]), 4.5)
            self.assertGreaterEqual(contrast(p["accent-ink"], p["accent"]), 4.5)
            self.assertGreaterEqual(contrast(p["ground"], p["ink"]), 4.5)   # Status „Fertig“
            self.assertGreaterEqual(contrast(p["ink"], p["rule-soft"]), 3.0)  # Balken an/aus

    def test_license_sources_link_only_urls(self):
        text = self.read("probe-pixel/index.html")
        box = text.split("<h2>Lizenzen</h2>", 1)[1].split("</ul>", 1)[0]
        hrefs = re.findall(r'<a href="([^"]*)"', box)
        self.assertEqual(hrefs, ["https://github.com/google/fonts", "https://ambientcg.com/view?id=Rope001",
                                 "https://ambientcg.com/view?id=Cardboard002", "https://example.org/palette"])
        self.assertIn('</a> (ofl/silkscreen); Lizenztext demo/fonts/OFL.txt', box)
        self.assertIn('Emulator-Tabelle (<a href="https://example.org/palette"', box)

    def test_field_names_and_code_in_german_text(self):
        text = self.read("probe-pixel/index.html")
        self.assertIn("KI-Beitrag 4: siehe „Fallstricke“; Mobil 5 geschätzt, Renderer mobile und gl_compatibility "
                      "geprüft (siehe „Probleme mit Werkzeugen“).", text)
        self.assertIn("importiert <code>godot --import</code> nicht neu (siehe „Erkenntnisse“); godot --headless", text)
        for key in ("ai_fit", "pitfalls", "tool_issues", "lessons", "`"):
            body = re.sub(r"<pre.*?</pre>", "", text, flags=re.S)          # Prompts (englisch) bleiben unberührt
            self.assertNotIn(key, body.split("<h2>Lizenzen</h2>")[0].split("</header>", 1)[1], key)

    def test_internal_names_hidden(self):
        text = self.read("probe-pixel/index.html")
        self.assertIn("Aufrufname agy und codex werden zum Werkzeugnamen;", text)
        self.assertIn("bg_agy0.png", text)                                  # Dateinamen bleiben, wie sie sind
        for out in (self.out, self.ci):
            data = json.loads((out / "probe-pixel" / "assets" / "measure.json").read_text(encoding="utf-8"))
            self.assertEqual(data, {"pairs": [{"id": "bg", "agy": {"seconds": 12.5, "file": "bg_agy0.png"}}]})
            for f in out.rglob("*"):
                if f.is_file() and f.suffix in (".html", ".json", ".css", ".js", ".txt"):
                    raw = f.read_text(encoding="utf-8")
                    with self.subTest(out=out.name, file=str(f.relative_to(out))):
                        for key in build.PRIVATE_JSON_KEYS:
                            self.assertNotIn(key, raw)
                        self.assertIsNone(build.ALIAS_RE.search(raw))

    def test_asset_kinds_in_german(self):
        text = self.read("probe-pixel/index.html")
        labels = re.findall(r'<figure class="asset">.*?<figcaption><b>([^<]*)</b>', text)
        self.assertEqual(labels, ["Messung", "Hintergrund", "Sprite", "Palette"])

    def test_own_technique_not_linked(self):
        text = self.read("probe-technik/index.html")
        self.assertIn('<span class="tag" aria-current="page">Probe-Technik</span>', text)
        for page in pages(self.out):
            with self.subTest(page=str(page.relative_to(self.out))):
                self.assertNotIn('href=""', page.read_text(encoding="utf-8"))

    def test_status_filter_and_planned_note(self):
        home = self.read("index.html")                  # Testdaten: mehrere Status und geplante Einträge
        self.assertIn('data-filter-group="status"', home)
        self.assertIn("Geplante Einträge zeigen ihren Auftrag.", home)

    def test_compare_name_column_sorts_by_name(self):
        text = self.read("vergleich/index.html")
        self.assertIn('<th scope="col" data-type="text"><button type="button">Eintrag</button></th>', text)
        self.assertNotIn("aria-sort", text.split("</thead>")[0])     # ohne JS: Katalogreihenfolge, keine Spalte markiert
        self.assertIn('<th scope="row" data-v="Probe-Pixel">', text)

    def test_axis_names(self):
        for rel in ("vergleich/index.html", "index.html", "probe-pixel/index.html"):
            text = self.read(rel)
            with self.subTest(page=rel):
                self.assertIn("KI-Beitrag", text)
                self.assertIn("Mobil (geschätzt)", text)
                self.assertNotIn("KI-Tauglichkeit", text)
        self.assertIn("nicht auf Geräten gemessen", self.read("vergleich/index.html"))

    def test_fonts_self_hosted(self):
        for out in (self.out, self.ci):
            css = (out / "assets" / "site.css").read_text(encoding="utf-8")
            self.assertEqual(css.count("@font-face {"), len(build.FONTDATA["faces"]))
            for f in build.FONTDATA["faces"]:
                with self.subTest(out=out.name, font=f["file"]):
                    data = (out / "assets" / "fonts" / f["file"]).read_bytes()
                    self.assertEqual(hashlib.sha256(data).hexdigest(), f["sha256"])
                    self.assertIn(f'url(fonts/{f["file"]}?v=', css)
            for lic in build.FONTDATA["licenses"]:
                data = (out / "assets" / "fonts" / lic["file"]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), lic["sha256"], lic["file"])
            for f in out.rglob("*"):
                if f.is_file() and f.suffix in (".html", ".css", ".js"):
                    with self.subTest(out=out.name, file=str(f.relative_to(out))):
                        self.assertNotRegex(f.read_text(encoding="utf-8"), r"googleapis|gstatic")
        self.assertIn('rel="preload" href="assets/fonts/inter-latin.woff2?v=', self.read("index.html"))

    def test_legal_notice(self):
        text = self.read("impressum/index.html")
        for value in [build.LEGAL["name"], build.LEGAL["vat_id"], build.LEGAL["responsible"], *build.LEGAL["address"]]:
            self.assertIn(value, text)
        self.assertIn(f'<a href="mailto:{build.LEGAL["email"]}">', text)
        self.assertIn("Angaben gemäß §\u00a05 DDG", text)
        for page in pages(self.out):
            if page.name == "404.html":
                continue
            with self.subTest(page=str(page.relative_to(self.out))):
                href = re.search(r'<a href="([^"]*)">Impressum</a>', page.read_text(encoding="utf-8"))
                self.assertIsNotNone(href, "Impressum fehlt im Fuß")
                self.assertEqual((page.parent / href.group(1)).resolve(), (self.out / "impressum").resolve())
        self.assertIn('href="/spielgrafik/impressum/"', self.read("404.html"))

    def test_footer_notices_and_trademarks(self):
        self.assertTrue((self.out / "THIRD_PARTY_NOTICES.txt").is_file())
        for page in pages(self.out):
            if page.name == "404.html":
                continue
            text = page.read_text(encoding="utf-8")
            with self.subTest(page=str(page.relative_to(self.out))):
                self.assertIn("THIRD_PARTY_NOTICES.txt\">Lizenzen Dritter</a>", text)
                self.assertIn("Genannte Marken und Spielenamen gehören ihren Inhabern", text)


class TestTextHelpers(unittest.TestCase):
    """Die Textregeln für deutsche Felder aus style.json, einzeln."""

    def test_de_keys(self):
        cases = {
            "ai_fit 4: gut": "KI-Beitrag 4: gut",
            "(consistency 3) und effort 2": "(Konsistenz 3) und Aufwand 2",
            "text_adventure 3 (siehe verdict).": "Textadventure 3 (siehe „Für unser Textadventure“).",
            "mobile 4 geschätzt": "Mobil 4 geschätzt",
            "--rendering-method mobile und gl_compatibility": "--rendering-method mobile und gl_compatibility",
            "Forward+, mobile und gl_compatibility": "Forward+, mobile und gl_compatibility",
            "(siehe pitfalls, tool_issues)": "(siehe „Fallstricke“, „Probleme mit Werkzeugen“)",
            "Ergebnis in lessons und pitfalls": "Ergebnis in „Erkenntnisse“ und „Fallstricke“",
            "siehe ratings_note; Werte in traits": "siehe „Bewertungen“; Werte in „Merkmale“",
            "(image_generations 0)": "(KI-Bilder 0)",
            "Einzelheiten unter godot": "Einzelheiten unter „Umsetzung in Godot“",
            "godot --headless --import; godot.log": "godot --headless --import; godot.log",
            "über camera.unproject_position (camera.json), siehe camera": "über camera.unproject_position (camera.json), siehe „Kamera“",
            "ai_fit_extra, my_pitfalls, pitfalls.json, scripts/verdict.py": "ai_fit_extra, my_pitfalls, pitfalls.json, scripts/verdict.py",
        }
        for raw, want in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(build.de_keys(raw), want)

    def test_txt_code_spans_and_escaping(self):
        self.assertEqual(build.txt("importiert `godot --import` <nicht> neu, siehe pitfalls"),
                         "importiert <code>godot --import</code> &lt;nicht&gt; neu, siehe „Fallstricke“")
        self.assertEqual(build.txt("`ai_fit 4` bleibt Code"), "<code>ai_fit 4</code> bleibt Code")
        self.assertEqual(build.txt("ein ` allein"), "ein ` allein")
        self.assertEqual(build.plain("`godot --import` und ai_fit 2"), "godot --import und KI-Beitrag 2")

    def test_internal_names(self):
        self.assertEqual(build.h("agy0, codex1, agy17 und agy"), "agy, codex, agy und agy")
        self.assertEqual(build.h("assets/raw/vga_bg_agy0.png, agy0x, agy-0, Codex 1"),
                         "assets/raw/vga_bg_agy0.png, agy0x, agy-0, Codex 1")
        self.assertEqual(build.strip_private({"a": [{"conversation_id": "c", "b": 1}], "thread_id": "t",
                                              "agy_account": "x"}),
                         ({"a": [{"b": 1}]}, 3))

    def test_linkify(self):
        self.assertEqual(build.linkify("https://github.com/google/fonts (ofl/caveat); Lizenztext demo/fonts/OFL.txt"),
                         '<a href="https://github.com/google/fonts" rel="noopener">https://github.com/google/fonts</a>'
                         " (ofl/caveat); Lizenztext demo/fonts/OFL.txt")
        self.assertEqual(build.linkify("nur Text"), "nur Text")
        self.assertEqual(build.linkify("Quelle: https://example.org/a."),
                         'Quelle: <a href="https://example.org/a" rel="noopener">https://example.org/a</a>.')

    def test_shorten_and_kinds(self):
        self.assertEqual(build.shorten("kurz"), "kurz")
        long = "Wort " * 60
        self.assertLessEqual(len(build.shorten(long)), build.ALT_MAX)
        self.assertTrue(build.shorten(long).endswith("Wort…"))
        self.assertEqual(build.asset_kind("sprite-sheet"), "Sprite-Blatt")
        self.assertEqual(build.asset_kind("Background"), "Hintergrund")
        self.assertEqual(build.asset_kind("Maske Wasser/Himmel"), "Maske Wasser/Himmel")   # schon deutsch
        self.assertEqual(build.asset_kind(None), "Asset")


class TestGitignore(unittest.TestCase):
    """Jede Datei, die ein Steckbrief zeigt (style.json → assets[].file), muss eingecheckt werden können; sonst bricht
    der Build in GitHub Actions mit „Datei fehlt“ ab. Prüft die Regeln (--no-index), nicht den Index."""

    def test_shown_files_not_ignored(self):
        git = shutil.which("git")
        if not git:
            self.skipTest("git ist nicht installiert – .gitignore kann nicht gegen die Steckbriefe geprüft werden")
        inside = subprocess.run([git, "rev-parse", "--is-inside-work-tree"], cwd=ROOT, capture_output=True, text=True)
        if inside.returncode or inside.stdout.strip() != "true":
            self.skipTest("kein Git-Arbeitsverzeichnis – .gitignore kann nicht gegen die Steckbriefe geprüft werden")
        files = []
        for sj in sorted((ROOT / "styles").glob("*/style.json")):
            for a in json.loads(sj.read_text(encoding="utf-8")).get("assets") or []:
                f = a if isinstance(a, str) else a.get("file") if isinstance(a, dict) else None
                if isinstance(f, str) and f:
                    files.append((sj.parent / f).relative_to(ROOT).as_posix())
        self.assertTrue(files, "keine Assets gefunden")
        run = subprocess.run([git, "check-ignore", "--no-index", "--stdin"], cwd=ROOT, input="\n".join(files) + "\n",
                             capture_output=True, text=True)
        self.assertIn(run.returncode, (0, 1), run.stderr)       # 0: etwas ignoriert, 1: nichts ignoriert
        ignored = run.stdout.splitlines()
        self.assertEqual(ignored, [], "von style.json gezeigt, aber von git ignoriert – in .gitignore aufnehmen:\n"
                         + "\n".join(f"!{f}" for f in ignored))


class TestDataErrors(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="spielgrafik-err-"))
        self.root = self.tmp / "root"
        shutil.copytree(FIX, self.root)
        self.out = self.tmp / "out"
        self.out.mkdir()
        (self.out / "marker").write_text("alt")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def edit(self, entry, **changes):
        p = self.root / "styles" / entry / "style.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data.update(changes)
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def assertFails(self, needle):
        with self.assertRaises(build.DataError) as ctx:
            build.build(self.root, self.out, quiet=True)
        self.assertTrue(any(needle in p for p in ctx.exception.args[0]), ctx.exception.args[0])
        self.assertTrue((self.out / "marker").exists(), "altes docs/ darf bei Fehlern nicht angetastet werden")

    def test_rating_out_of_range(self):
        self.edit("probe-pixel", ratings={"ai_fit": 7})
        self.assertFails("ratings.ai_fit")

    def test_unknown_status(self):
        self.edit("probe-gemalt", status="fast fertig")
        self.assertFails("status")

    def test_missing_asset(self):
        (self.root / "styles" / "probe-pixel" / "assets" / "sprite.png").unlink()
        self.assertFails("sprite.png")

    def test_asset_outside_entry(self):
        self.edit("probe-pixel", assets=[{"file": "../probe-gemalt/style.json"}])
        self.assertFails("außerhalb")

    def test_slug_mismatch(self):
        self.edit("probe-technik", slug="andere")
        self.assertFails("passt nicht zum Ordner")

    def test_done_without_video(self):
        (self.root / "styles" / "probe-technik" / "media" / "demo.mp4").unlink()
        self.assertFails("demo.mp4")

    def test_invalid_json(self):
        (self.root / "styles" / "probe-pixel" / "style.json").write_text("{ kaputt", encoding="utf-8")
        self.assertFails("kein gültiges JSON")

    def test_cli_exit_codes(self):
        ok = subprocess.run([sys.executable, str(ROOT / "build.py"), "--root", str(FIX), "--out", str(self.tmp / "cli"),
                             "--copy-only"], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.edit("probe-pixel", ratings={"mobile": 0})
        bad = subprocess.run([sys.executable, str(ROOT / "build.py"), "--root", str(self.root), "--out",
                              str(self.out)], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("Build abgebrochen", bad.stderr)


class TestCollectPrompts(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="spielgrafik-prompts-"))
        shutil.copytree(FIX / "styles", self.tmp / "styles")
        self.expected = json.loads((FIX / "styles" / "probe-pixel" / "prompts.json").read_text(encoding="utf-8"))
        (self.tmp / "styles" / "probe-pixel" / "prompts.json").unlink()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_collects_sidecars_and_skips_job_lists(self):
        self.assertEqual(collect_prompts.main(["--styles", str(self.tmp / "styles")]), 0)
        got = json.loads((self.tmp / "styles" / "probe-pixel" / "prompts.json").read_text(encoding="utf-8"))
        self.assertEqual(got, self.expected)
        self.assertEqual([p["file"] for p in got], ["assets/raw/bg.png", "assets/raw/sprite.png"])
        self.assertEqual(got[1]["refs"], ["shared/badger/master_sheet.png", "styles/probe-pixel/assets/raw/bg.png"])
        self.assertEqual(set(got[0]), {"file", "prompt", "refs", "size", "backend"})
        self.assertEqual([p["backend"] for p in got], ["codex", "agy"])   # alte Begleitdatei ohne backend = Codex
        self.assertNotIn("prompt_sent", got[0])
        self.assertIn("magenta background", got[1]["prompt_sent"])

    def test_entries_without_raw_stay_untouched(self):
        collect_prompts.main(["--styles", str(self.tmp / "styles")])
        self.assertFalse((self.tmp / "styles" / "probe-technik" / "prompts.json").exists())
        shutil.rmtree(self.tmp / "styles" / "probe-pixel" / "assets" / "raw")
        (self.tmp / "styles" / "probe-pixel" / "prompts.json").write_text("[]\n", encoding="utf-8")
        collect_prompts.main(["--styles", str(self.tmp / "styles"), "probe-pixel"])
        self.assertEqual((self.tmp / "styles" / "probe-pixel" / "prompts.json").read_text(encoding="utf-8"), "[]\n")

    def test_unknown_slug(self):
        self.assertEqual(collect_prompts.main(["--styles", str(self.tmp / "styles"), "gibt-es-nicht"]), 1)


class TestImageSize(unittest.TestCase):
    def test_formats(self):
        media = FIX / "styles" / "probe-pixel" / "media"
        self.assertEqual(tuple(build.image_size(media / "poster.png")), (320, 180))
        self.assertEqual(tuple(build.image_size(media / "poster.webp")), (320, 180))
        self.assertEqual(tuple(build.image_size(media / "frames.jpg")), (640, 180))
        self.assertEqual(tuple(build.image_size(media / "preview.gif")), (160, 90))
        self.assertEqual(tuple(build.image_size(FIX / "styles" / "probe-pixel" / "assets" / "bg.png")), (1700, 200))
        self.assertIsNone(build.image_size(FIX / "styles" / "probe-pixel" / "assets" / "palette.gpl"))


DOCS = ROOT / "docs"


@unittest.skipUnless((DOCS / "index.html").exists(), "docs/ fehlt – erst python3 build.py")
class TestProjectSite(unittest.TestCase):
    """Das echte docs/ (in CI direkt nach python3 build.py geprüft)."""

    def test_links_and_media_resolve(self):
        self.assertEqual(broken_refs(DOCS), [])

    def test_every_catalog_entry_has_a_page(self):
        catalog = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
        for e in catalog["entries"]:
            with self.subTest(slug=e["slug"]):
                self.assertTrue((DOCS / e["slug"] / "index.html").is_file())
        cards = Page((DOCS / "index.html").read_text(encoding="utf-8")).articles
        self.assertGreaterEqual(len(cards), len(catalog["entries"]))

    def test_filters_only_with_choice(self):
        home = (DOCS / "index.html").read_text(encoding="utf-8")
        statuses = {a["data-status"] for a in Page(home).articles}
        self.assertEqual('data-filter-group="status"' in home, len(statuses) > 1)
        self.assertEqual("Geplante Einträge zeigen ihren Auftrag" in home, "planned" in statuses)

    def test_no_external_fonts_and_no_self_links(self):
        for page in pages(DOCS):
            text = page.read_text(encoding="utf-8")
            with self.subTest(page=str(page.relative_to(DOCS))):
                self.assertNotRegex(text, r"googleapis|gstatic")
                self.assertNotIn('href=""', text)

    def test_no_private_data(self):
        """Keine lokalen Pfade (auch nicht in Metadaten von Bildern und Videos), keine internen Felder oder
        Aufrufnamen, keine E-Mail-Adresse außer der des Impressums und Copyright-Zeilen in Lizenztexten."""
        local = re.compile(rb"/Users/|/home/|/private/tmp/|/private/var/|/var/folders/")
        mail = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}")
        for f in sorted(DOCS.rglob("*")):
            if not f.is_file():
                continue
            raw = f.read_bytes()
            with self.subTest(file=str(f.relative_to(DOCS))):
                self.assertIsNone(local.search(raw))
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    continue                                   # Bilder, Videos, Schriften, Modelle
                for key in build.PRIVATE_JSON_KEYS:
                    self.assertNotIn(key, text)
                self.assertIsNone(build.ALIAS_RE.search(text))
                for line in text.splitlines():
                    if "Copyright" in line:
                        continue
                    self.assertEqual([m for m in mail.findall(line) if m != build.LEGAL["email"]], [], line[:200])


if __name__ == "__main__":
    unittest.main()
