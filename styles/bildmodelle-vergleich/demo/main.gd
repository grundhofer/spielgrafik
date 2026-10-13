extends Node2D
## Bildmodelle im Vergleich: dieselben Prompts über gpt-image (Codex) und das Gemini-Bildmodell (agy).
## 0–3,9 s Vergleichsansicht: links Codex, rechts agy, eine Trennlinie wischt über jedes Paar, eine waagerechte
## Wischblende wechselt zum nächsten Paar. Ab 3,9 s wischt die Schlussszene herein: der Hafen im VGA-Stil aus
## dem jeweils besseren Bild (Hintergrund Codex, Dachs agy), 320×180, ganzzahlig ×4.
## Alles hängt nur von der aufsummierten Zeit t ab; Zufall nur mit festem Seed.

const SEED := 20261013

# Bildpaare: id = Dateinamen in art/pairs/<id>_codex.png und <id>_agy.png. Texte aus assets/measurements.json
# und der Sichtprüfung (style.json → vergleich).
const PAIRS := [
	{
		"id": "vga_bg",
		"title": "VGA-Hintergrund",
		"source": "aus vga-adventure/bg, ohne Referenzbild",
		"codex": ["1536 × 1024 px", "57 s", "kein festes Pixelraster, weiche Pseudo-Pixel", "Bühne wie verlangt: Himmel oben, Pflaster unten", "viele Farbverläufe (1063 Farben)"],
		"agy": ["1264 × 848 px", "199 s (mit Wartezeit), 2. Lauf 67 s", "festes Raster 2,7 px (≈ 460 × 310)", "malt Letterbox-Balken oben und unten ins Bild", "flach, 313 Farben"],
		"verdict": "Besser für diesen Stil: Codex. agy rastert sauberer, nimmt „letterboxed“ aber wörtlich (in beiden Läufen).",
	},
	{
		"id": "oel_bg",
		"title": "Ölmalerei-Hintergrund",
		"source": "aus oelmalerei/bg3, ohne Referenzbild",
		"codex": ["1536 × 1024 px", "73 s", "viel Kleinteil trotz „few big strokes“", "Leuchtturm bei 74 % der Breite", "dunkel, Postkarten-Abendrot"],
		"agy": ["1264 × 848 px", "85 s", "große flache Striche, wenige Objekte", "Leuchtturm bei 66 % (verlangt: zwei Drittel)", "gedämpfte Mischtöne; eine dünne senkrechte Linie im Himmel rechts"],
		"verdict": "Besser für diesen Stil: agy. Es folgt dem Stilblock, Codex malt detailreicher als verlangt.",
	},
	{
		"id": "vga_badger",
		"title": "Figurenblatt mit Referenzblatt",
		"source": "aus vga-adventure/badger_small, Referenz: Figurenblatt shared/badger",
		"codex": ["1536 × 1024 px", "65 s", "echtes Alpha, aber Figur nur zu 98 % deckend, 9 % Dunst", "Laufposen teils doppelt, Kopf starr", "Reihen gleich groß (1,05)"],
		"agy": ["1264 × 848 px", "67 s", "Magenta freigestellt, dunkler Lila-Saum", "Kontakt und Durchgang klar, Kopf wippt", "Stehreihe 1,29-mal größer gezeichnet"],
		"verdict": "Für die Schlussszene: der agy-Dachs (deutlichere Posen, Gesichtsstreifen wie im Referenzblatt).",
	},
]
# Zeitplan: je Paar [Beginn, Ende]; Wischblende zum nächsten Paar über WIPE s ab Ende - WIPE/2
const SEG := [[0.0, 1.42], [1.42, 2.84], [2.84, 3.98]]
const WIPE := 0.26
const FINAL_WIPE := [3.92, 4.27]

# Schlussszene
const WALK_FPS := 6.0
const WALK_START := 2.3          # Dachs läuft schon unsichtbar los, damit er beim Hereinwischen mitten im Gang ist
const WALK_FRAMES := 18          # Anzahl gezeigter Laufbilder; das letzte ist ein Durchgangsbild (Index 5)
const BADGER_X0 := -12           # linke Zellkante beim ersten Laufbild
const FEET_Y := 130              # Fußzeile in der Szene
const BREATH_PERIOD := 1.0
const TYPE_START := 4.4
const TYPE_CPS := 55.0
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const PARSER := "> nimm paket"
const PARSER_CPS := 40.0

var t := 0.0
var frozen_split := -1.0         # Prüfschalter --split=0.5: Trennlinie fest
var only_final := false          # Prüfschalter --final: nur Schlussszene
var no_badger := false           # Prüfschalter --no-badger: Figur aus (Differenzbild für Messungen)
var bmeta := {}
var walk_x := PackedInt32Array() # linke Zellkante je gezeigtem Laufbild
var lantern_tab := PackedFloat32Array()
var window_tab := PackedFloat32Array()

var pair_tex := {}
@onready var compare: ColorRect = $Compare
@onready var hud = $Hud
@onready var final_rect: TextureRect = $Final
@onready var pixel: SubViewport = $Pixel
@onready var badger: Sprite2D = $Pixel/Badger
@onready var lamp_glow: Sprite2D = $Pixel/LampGlow
@onready var lantern_glow: Sprite2D = $Pixel/LanternGlow
@onready var window_glow: Sprite2D = $Pixel/WindowGlow
@onready var pixel_ui = $Pixel/Ui
@onready var glints = $Pixel/Glints

var walk_tex: Texture2D
var idle_tex: Texture2D


func _read_json(path: String) -> Dictionary:
	var f := FileAccess.open(path, FileAccess.READ)
	var d = JSON.parse_string(f.get_as_text())
	return d if d is Dictionary else {}


func _ready() -> void:
	for p in PAIRS:
		for side in ["codex", "agy"]:
			pair_tex["%s_%s" % [p["id"], side]] = load("res://art/pairs/%s_%s.png" % [p["id"], side])
	bmeta = _read_json("res://art/badger.json")
	walk_tex = load("res://art/badger_walk.png")
	idle_tex = load("res://art/badger_idle.png")
	# Laufweg: Vorschub je Bildwechsel aus dem gemessenen Standfuß (build_final.py), nicht konstantes Tempo
	var adv: Array = bmeta["advance"]
	var x := BADGER_X0
	for i in WALK_FRAMES:
		walk_x.append(x)
		x += int(adv[i % adv.size()])
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	for i in 12 * 20:
		var v := rng.randf_range(0.72, 1.0)
		if rng.randf() < 0.08:
			v = rng.randf_range(0.45, 0.6)   # Windstoß in die Flamme
		lantern_tab.append(v)
	for i in 6 * 20:
		window_tab.append(rng.randf_range(0.8, 1.0))
	glints.setup(rng)
	final_rect.texture = pixel.get_texture()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t = float(a.substr(5))
		elif a.begins_with("--split="):
			frozen_split = float(a.substr(8))
		elif a == "--final":
			only_final = true
		elif a == "--no-badger":
			no_badger = true
	_update()


func _process(delta: float) -> void:
	t += delta
	_update()


static func _ease(x: float) -> float:
	x = clampf(x, 0.0, 1.0)
	return x * x * (3.0 - 2.0 * x)


func split_at(i: int, tt: float) -> float:
	## Trennlinie eines Paars: von 0,85 zur Mitte, kurz halten, weiter bis 0,15 (Anteil Codex von links).
	if frozen_split >= 0.0:
		return frozen_split
	var a: float = SEG[i][0] + (0.12 if i == 0 else WIPE * 0.5)
	var b: float = SEG[i][1] - WIPE * 0.5 if i < SEG.size() - 1 else FINAL_WIPE[0]
	var mv := (b - a) * 0.36
	if tt < a + mv:
		return lerpf(0.85, 0.5, _ease((tt - a) / mv))
	if tt < b - mv:
		return 0.5
	return lerpf(0.5, 0.15, _ease((tt - (b - mv)) / mv))


func pair_state(tt: float) -> Dictionary:
	## aktuelles Paar, nächstes Paar und Fortschritt der Wischblende (über SEG[i][1] ± WIPE/2)
	for i in SEG.size() - 1:
		var w0: float = SEG[i][1] - WIPE * 0.5
		if tt < w0:
			return {"cur": i, "next": i, "change": 0.0}
		if tt < w0 + WIPE:
			return {"cur": i, "next": i + 1, "change": (tt - w0) / WIPE}
	var last := SEG.size() - 1
	return {"cur": last, "next": last, "change": 0.0}


func _update() -> void:
	var st := pair_state(t)
	var cur: int = st["cur"]
	var nxt: int = st["next"]
	var m: ShaderMaterial = compare.material
	m.set_shader_parameter("cur_a", pair_tex["%s_codex" % PAIRS[cur]["id"]])
	m.set_shader_parameter("cur_b", pair_tex["%s_agy" % PAIRS[cur]["id"]])
	m.set_shader_parameter("next_a", pair_tex["%s_codex" % PAIRS[nxt]["id"]])
	m.set_shader_parameter("next_b", pair_tex["%s_agy" % PAIRS[nxt]["id"]])
	m.set_shader_parameter("split_cur", split_at(cur, t))
	m.set_shader_parameter("split_next", split_at(nxt, t))
	m.set_shader_parameter("change", st["change"])
	# Text wechselt in der Mitte der Wischblende
	hud.pair_index = nxt if st["change"] >= 0.5 else cur
	hud.queue_redraw()

	var reveal := 1.0 if only_final else clampf((t - FINAL_WIPE[0]) / (FINAL_WIPE[1] - FINAL_WIPE[0]), 0.0, 1.0)
	(final_rect.material as ShaderMaterial).set_shader_parameter("reveal", _ease(reveal))
	final_rect.visible = reveal > 0.0
	_update_final()


func _update_final() -> void:
	var tt := t
	# Dachs: Laufbilder mit 6 Bildern/s (jedes Bild genau 5 Videobilder), dann Stehen mit Atmen
	var k := int(floor((tt - WALK_START) * WALK_FPS + 1e-6))
	var cell_w := int(bmeta["cell"][0])
	var cell_h := int(bmeta["cell"][1])
	var top := FEET_Y - int(bmeta["foot_row"])
	if k < 0:
		badger.visible = false
	elif k < WALK_FRAMES:
		badger.visible = true
		badger.texture = walk_tex
		badger.hframes = int(bmeta["frames"])
		badger.frame = k % int(bmeta["frames"])
		badger.position = Vector2(walk_x[k], top)
	else:
		badger.visible = true
		badger.texture = idle_tex
		badger.hframes = 2
		var since := tt - (WALK_START + WALK_FRAMES / WALK_FPS)
		badger.frame = 1 if fmod(since, BREATH_PERIOD) >= BREATH_PERIOD * 0.5 else 0
		badger.position = Vector2(walk_x[WALK_FRAMES - 1], top)
	assert(cell_w > 0 and cell_h > 0)
	if no_badger:
		badger.visible = false

	# Leuchtfeuer: Blitz alle 2,4 s, in vier Helligkeitsstufen an- und abschwellend
	var ph := fmod(tt + 0.3, 2.4)
	var flash := 0.0
	if ph < 0.5:
		flash = 1.0 - absf(ph - 0.25) / 0.25
	flash = floorf(flash * 4.0 + 0.5) / 4.0
	lamp_glow.modulate = Color(1.0, 0.86, 0.5, 0.18 + 0.75 * flash)
	# Laterne und Fenster: Tabellen mit festem Seed, stufig (wie Palettenwechsel)
	var lv := _tab(lantern_tab, tt, 12.0)
	lv = floorf(lv * 5.0 + 0.5) / 5.0
	lantern_glow.modulate = Color(1.0, 0.66, 0.3, 0.55 * lv)
	var wv := _tab(window_tab, tt, 6.0)
	wv = floorf(wv * 4.0 + 0.5) / 4.0
	window_glow.modulate = Color(1.0, 0.62, 0.28, 0.32 * wv)
	glints.tt = tt
	glints.queue_redraw()
	pixel_ui.tt = tt
	pixel_ui.queue_redraw()


func _tab(tab: PackedFloat32Array, tt: float, rate: float) -> float:
	var x := tt * rate
	var i := int(floor(x))
	var f := x - float(i)
	var a := tab[i % tab.size()]
	var b := tab[(i + 1) % tab.size()]
	return lerpf(a, b, f * f * (3.0 - 2.0 * f))
