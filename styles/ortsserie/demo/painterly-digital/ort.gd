extends Control
## Ortsserie, Stil painterly-digital: ein Ort von Lornholm als lebendes Standbild (Kinemagramm) mit der
## Textleiste unten (Form „Vollbild“ aus dem Eintrag textoberflaeche, auf 1280x720 verdoppelt).
## Bild, Masken und Lagen aus res://painterly-digital/art/<ort>/ (von scripts/process.py erzeugt).
## Zeit: in der Aufnahme (--write-movie) aus dem Bildzähler (t = t0 + n/30), sonst aufsummiertes delta.
## Zufall nur aus RandomNumberGenerator mit festem Seed. Prüfschalter nach „--“:
##   --t0=SEKUNDEN (Startzeit), --frozen (Standbild ohne Leben), --no-ui (ohne Textleiste)

const RevealFX := preload("res://painterly-digital/reveal_fx.gd")
const SEED := 20261013
const FPS := 30.0
const BEAM_PHI0 := 0.35

# Textleiste (textoberflaeche, ui_fullscreen.gd, Maße x2)
const PANEL := Rect2(20, 536, 1240, 164)
const LOC_POS := Vector2(52, 548)
const TEXT_POS := Vector2(52, 592)
const TEXT_W := 800.0
const BAG_POS := Vector2(880, 546)
const SLOT0 := Vector2(880, 588)
const SLOT := 76.0
const SLOT_GAP := 14.0
const ICON := 60.0
const ITEMS := ["", "key", "letter", "compass"]
const TEXT_T := 0.35
const CREAM := Color(0.95, 0.92, 0.85)
const AMBER := Color(0.93, 0.72, 0.42)

@export var ort := "leuchtturm"
@export var title := ""
@export_multiline var line := ""

var t := 0.0
var t0 := 0.0
var frame := 0
var movie := false
var frozen := false
var scene: Dictionary = {}
var fx: Dictionary = {}
var mat: ShaderMaterial
var tabs := {}           # Kanal -> PackedFloat32Array (Flackerwerte)
var rates := {}          # Kanal -> Werte je Sekunde
var lights: Array = []   # Dictionaries aus scene.json
var gulls: Array = []
var reveal := RevealFX.new()


func _ready() -> void:
	var path := "res://painterly-digital/art/%s/scene.json" % ort
	scene = JSON.parse_string(FileAccess.get_file_as_string(path))
	fx = scene.get("fx", {})
	lights = scene.get("lights", [])
	mat = $Bild.material
	movie = OS.get_cmdline_args().has("--write-movie")
	var args := OS.get_cmdline_user_args()
	frozen = args.has("--frozen")
	for a in args:
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
	t = t0

	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	var fl: Dictionary = fx.get("flicker", {})
	for ch in ["fire", "small", "lamp"]:
		var spec: Array = fl.get(ch, [1.0, 1.0, 1.0])
		var tab := PackedFloat32Array()
		var n := int(maxf(float(spec[2]), 1.0) * 12.0)
		for i in n:
			var v := rng.randf_range(float(spec[0]), float(spec[1]))
			if ch == "fire" and float(spec[1]) - float(spec[0]) > 0.2 and rng.randf() < 0.06:
				v = float(spec[0]) - 0.08   # kurzes Einsinken der Glut
			tab.append(v)
		tabs[ch] = tab
		rates[ch] = float(spec[2])

	mat.set_shader_parameter("horizon_y", float(scene.get("horizon_y", 300.0)))
	mat.set_shader_parameter("water_bottom", float(scene.get("water_bottom", 600.0)))
	mat.set_shader_parameter("sky_amp", float(fx.get("sky_amp", 8.0)))
	mat.set_shader_parameter("sky_period", float(fx.get("sky_period", 70.0)))
	mat.set_shader_parameter("water_amp", float(fx.get("water_amp", 2.0)))
	mat.set_shader_parameter("sparkle_k", float(fx.get("sparkle_k", 0.4)))
	mat.set_shader_parameter("glint_lo", float(fx.get("glint_lo", 0.30)))
	mat.set_shader_parameter("receiver_k", float(fx.get("receiver_k", 0.0)))
	mat.set_shader_parameter("grass_amp", float(fx.get("grass_amp", 0.0)))
	mat.set_shader_parameter("vignette", float(fx.get("vignette", 0.22)))

	# Lichthöfe: je Licht Lage, Radius, Grundfarbe
	var pos := PackedVector2Array()
	var rad := PackedFloat32Array()
	for i in 6:
		if i < lights.size():
			pos.append(_v2(lights[i]["pos"]))
			rad.append(float(lights[i]["glow"]))
		else:
			pos.append(Vector2(-9999, -9999))
			rad.append(1.0)
	mat.set_shader_parameter("glow_pos", pos)
	mat.set_shader_parameter("glow_r", rad)

	# Flammen
	var fv: Array[Vector4] = []
	var fk := PackedFloat32Array()
	var flames: Array = scene.get("flames", [])
	for i in 2:
		if i < flames.size():
			var f: Dictionary = flames[i]
			fv.append(Vector4(f["pos"][0], f["pos"][1], f["w"], f["h"]))
			fk.append(float(f["k"]))
		else:
			fv.append(Vector4(-9999, -9999, 1, 1))
			fk.append(0.0)
	mat.set_shader_parameter("flame", fv)
	mat.set_shader_parameter("flame_k", fk)

	# Nebelbänder
	var fb: Array[Vector4] = []
	var fm: Array[Vector4] = []
	var fog: Array = fx.get("fog", [])
	for i in 4:
		if i < fog.size():
			var b: Dictionary = fog[i]
			fb.append(Vector4(b["y"], b["hh"], b["k"], b["speed"]))
			fm.append(Vector4(b["mode"], b["scale"], b["lift"], 0.0))
		else:
			fb.append(Vector4(0, 1, 0, 0))
			fm.append(Vector4(0, 300, 0, 0))
	mat.set_shader_parameter("fog_band", fb)
	mat.set_shader_parameter("fog_mode", fm)

	# Lichtteilchen
	var mo: Dictionary = fx.get("motes", {})
	if not mo.is_empty():
		var r: Array = mo["rect"]
		mat.set_shader_parameter("mote_rect", Vector4(r[0], r[1], r[2], r[3]))
		mat.set_shader_parameter("mote_n", int(mo["n"]))
		mat.set_shader_parameter("mote_k", float(mo["k"]))
		mat.set_shader_parameter("mote_light", _v2(mo["light"]))

	# Linse (Leuchtturm)
	var lens: Dictionary = fx.get("lens", {})
	if not lens.is_empty():
		var lr: Array = lens["rect"]
		mat.set_shader_parameter("lens_rect", Vector4(lr[0], lr[1], lr[2], lr[3]))
		mat.set_shader_parameter("lens_k", float(lens["k"]))
		mat.set_shader_parameter("sweep_k", float(lens["sweep_k"]))
		mat.set_shader_parameter("sweep_w", float(lens["sweep_w"]))

	# Leuchtturmstrahl
	var beam: Dictionary = fx.get("beam", {})
	if not beam.is_empty() and scene.has("lamp"):
		mat.set_shader_parameter("lamp_pos", _v2(scene["lamp"]))
		mat.set_shader_parameter("beam_len", float(beam["len"]))
		mat.set_shader_parameter("beam_k", float(beam["k"]))

	gulls = fx.get("gulls", [])
	var gz := PackedFloat32Array()
	for i in 2:
		gz.append(float(gulls[i]["size"]) if i < gulls.size() else 0.0)
	mat.set_shader_parameter("gull_size", gz)

	_build_ui()
	if args.has("--no-ui"):
		for c in get_children():
			if c != $Bild:
				c.visible = false
	_update()


func _v2(a) -> Vector2:
	return Vector2(float(a[0]), float(a[1]))


func _font(path: String, spacing := 0) -> Font:
	var f := FontVariation.new()
	f.base_font = load(path)
	f.spacing_glyph = spacing
	var ts := TextServerManager.get_primary_interface()
	f.opentype_features = {ts.name_to_tag("liga"): 0, ts.name_to_tag("clig"): 0}
	return f


func _box(bg: Color, border: Color, radius: int, bw: int = 2) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.border_color = border
	sb.set_border_width_all(bw)
	sb.set_corner_radius_all(radius)
	sb.anti_aliasing = true
	return sb


func _build_ui() -> void:
	var sans := _font("res://painterly-digital/fonts/AlegreyaSans-Medium.ttf")
	var sc := _font("res://painterly-digital/fonts/AlegreyaSC-Medium.ttf", 4)
	var panel := Panel.new()
	panel.position = PANEL.position
	panel.size = PANEL.size
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_theme_stylebox_override("panel", _box(Color(0.05, 0.06, 0.09, 0.80), Color(0.95, 0.85, 0.65, 0.30), 16))
	add_child(panel)

	var loc := Label.new()
	loc.text = title
	loc.add_theme_font_override("font", sc)
	loc.add_theme_font_size_override("font_size", 28)
	loc.add_theme_color_override("font_color", AMBER)
	loc.position = LOC_POS
	add_child(loc)

	reveal.start = TEXT_T
	var text := RichTextLabel.new()
	text.bbcode_enabled = true
	text.scroll_active = false
	text.fit_content = true
	text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text.position = TEXT_POS
	text.size = Vector2(TEXT_W, 84)
	text.add_theme_font_override("normal_font", sans)
	text.add_theme_font_size_override("normal_font_size", 34)
	text.add_theme_color_override("default_color", CREAM)
	text.add_theme_constant_override("line_separation", 2)
	text.install_effect(reveal)
	text.text = "[reveal]" + line + "[/reveal]"
	text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(text)

	var bag := Label.new()
	bag.text = "Tasche"
	bag.add_theme_font_override("font", sc)
	bag.add_theme_font_size_override("font_size", 24)
	bag.add_theme_color_override("font_color", Color(0.95, 0.88, 0.75, 0.55))
	bag.position = BAG_POS
	add_child(bag)
	for i in ITEMS.size():
		var s := Panel.new()
		s.position = SLOT0 + Vector2(i * (SLOT + SLOT_GAP), 0)
		s.size = Vector2(SLOT, SLOT)
		s.add_theme_stylebox_override("panel", _box(Color(0.95, 0.88, 0.75, 0.13), Color(0.95, 0.85, 0.65, 0.28), 12))
		add_child(s)
		if ITEMS[i] != "":
			var ic := TextureRect.new()
			ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			ic.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
			ic.size = Vector2(ICON, ICON)
			ic.position = s.position + Vector2((SLOT - ICON) / 2.0, (SLOT - ICON) / 2.0)
			ic.texture = load("res://painterly-digital/art/icons/%s.png" % ITEMS[i])
			add_child(ic)


func _tab(ch: String) -> float:
	var tab: PackedFloat32Array = tabs[ch]
	var x := t * float(rates[ch])
	var i := int(floor(x))
	var f := x - float(i)
	f = f * f * (3.0 - 2.0 * f)
	return lerpf(tab[posmod(i, tab.size())], tab[posmod(i + 1, tab.size())], f)


func _process(delta: float) -> void:
	if frozen:
		t = t0
	elif movie:
		t = t0 + float(frame) / FPS
		frame += 1
	else:
		t += delta
	_update()


func _update() -> void:
	var fire := _tab("fire")
	var small := _tab("small")
	var lamp := _tab("lamp")
	var toward := 0.0
	var beam: Dictionary = fx.get("beam", {})
	if not beam.is_empty():
		var phi := BEAM_PHI0 + TAU * t / float(beam["period"])
		toward = maxf(sin(phi), 0.0)
		lamp *= 1.0 + 0.6 * pow(toward, 6.0)
		mat.set_shader_parameter("beam_phi", phi)
	var lens_pulse := 0.0
	var lens: Dictionary = fx.get("lens", {})
	if not lens.is_empty():
		var u := fposmod(t / float(lens["period"]) + 0.15, 1.0)
		mat.set_shader_parameter("lens_phase", u)
		var c: Array = lens["center"]
		mat.set_shader_parameter("sweep_x", float(c[0]) + (u - 0.5) * 2400.0)
		lens_pulse = exp(-pow((u - 0.5) / 0.09, 2.0))
		fire *= 1.0 + 0.10 * lens_pulse
	mat.set_shader_parameter("t", t)
	mat.set_shader_parameter("flick", Vector3(fire, small, lamp))

	var warm := {"fire": Color(1.0, 0.62, 0.30), "small": Color(1.0, 0.70, 0.38), "lamp": Color(1.0, 0.86, 0.58)}
	var cols: Array[Vector4] = []
	for i in 6:
		if i < lights.size():
			var li: Dictionary = lights[i]
			var ch: String = li["channel"]
			var k: float = {"fire": fire, "small": small, "lamp": lamp}[ch]
			if ch == "lamp" and not beam.is_empty():
				k = 0.7 + 1.6 * pow(toward, 4.0)
			if ch == "fire" and not lens.is_empty():
				k *= 1.0 + 0.8 * lens_pulse
			var c: Color = warm[ch]
			cols.append(Vector4(c.r, c.g, c.b, float(li["glow_k"]) * k))
		else:
			cols.append(Vector4(0, 0, 0, 0))
	mat.set_shader_parameter("glow_col", cols)

	var gp := PackedVector2Array()
	for i in 2:
		if i < gulls.size():
			var g: Dictionary = gulls[i]
			var span := 1280.0 + 80.0
			var x := fposmod(float(g["start"][0]) + 40.0 + float(g["vel"][0]) * t, span) - 40.0
			var y := float(g["start"][1]) + float(g["vel"][1]) * 12.0 * sin(t * 0.05 + float(i)) + 6.0 * sin(t * 0.9 + float(i) * 2.0)
			gp.append(Vector2(x, y))
		else:
			gp.append(Vector2(-9999, -9999))
	mat.set_shader_parameter("gull_pos", gp)
	reveal.t = t
