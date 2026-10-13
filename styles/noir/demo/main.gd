extends Node2D
## Film noir – Hafen von Lornholm (Katalogeintrag "noir").
##
## Schwarzweiß-Hintergrund aus gpt-image (scripts/build_bg.py), der Dachs als KI-Laufbogen über ein Blender-Layout
## (scripts/build_badger.py) mit Kissen-Normalen, im Spiel hart beleuchtet: Jalousienlicht aus dem Fenster in
## Streifen auf Pflaster und Figur, Laterne mit Flackern, Gegenlicht als Kantenlicht. Dazu Regen, Nebel,
## Leuchtturmstrahl, Spiegelungen auf dem nassen Pflaster und ein Filmlook (Korn, Halation, Vignette), in dem nur
## der rote Schal Farbe behält. Die Oberfläche ist eine Titelkarte im Stil der 1940er.
## Alles hängt nur von der aufsummierten Zeit t ab; Zufall nur aus RandomNumberGenerator mit festem Seed.

const SEED := 20261012
const VIEW := Vector2(1280, 720)
const SPRITE_FPS := 15.0                # Figur auf Zweien (30 fps / 2)

# Lagen im Hintergrund (Bildschirmkoordinaten, aus art/scene.json bzw. im aufbereiteten bg.png gemessen)
var LANTERN := Vector2(771.7, 191.7)
var LAMP := Vector2(1135.0, 110.0)
var HORIZON_Y := 345.8
var QUAY_Y := 468.3
const WINDOW_POS := Vector2(104, 262)   # Mitte des Jalousienfensters (Lichtquelle für die Figur)

# Jalousienlicht: Fleck auf dem Pflaster (A-B Wandseite, D-C vorn) und Strahlbreite auf Höhe der Figur.
# Die Werte stehen auch als Standard in shaders/window.gdshaderinc; hier werden sie gesetzt.
const WIN_A := Vector2(95, 566)
const WIN_B := Vector2(205, 543)
const WIN_C := Vector2(560, 705)
const WIN_D := Vector2(300, 760)
const BEAM_X := Vector2(178, 429)       # Schnitt des Flecks mit der Fußlinie FEET_Y

# Dachs. Vorschub = gemessener Rückweg des Standfußes je Laufbild im KI-Bogen (21 px) × 3/7 = 9 px.
const FEET_Y := 645.0
const X_START := -69.0                  # Ursprung des Rigs im ersten Laufbild (Figur ganz links außerhalb)
const STEP := 9.0
const WALK_N := 42                      # Laufbilder 0..41; Bild k zeigt walk_((1 + k) % 8), Bild 41 = walk_2
const STAND_SHIFT := 4.0                # stand hat den Standfuß 4 px weiter links im Bild als walk_2
const T_TURN := 3.2                     # Dreiviertelansicht zur Kamera
const BLINKS := [[4.40, 4.50], [5.70, 5.80]]
const F_STAND := 8
const F_TURN := 9
const F_BLINK := 10
const SHADOW_DIR := Vector2(0.62, 0.40) # Schlagschatten im Fensterlicht je Pixel Körperhöhe

# Oberfläche
const CARD := Rect2(300, 16, 412, 224)
const T_NARR := 0.45
const NARR_CPS := 34.0
const T_CHOICES := 2.35
const T_HOVER := 3.40
const T_PARSER := 3.70
const PARSER_CPS := 9.0
const INK := Color(0.93, 0.93, 0.91)
const DIM := Color(0.60, 0.60, 0.59)

var t := 0.0
var frame_no := 0
var rng := RandomNumberGenerator.new()
var flicker_keys := PackedFloat32Array()
var parser_times := PackedFloat32Array()
var probe_no_badger := false
var probe_badger_only := false
var probe_no_rain := false

var info := {}
var anchor := Vector2.ZERO
var bg_mat: ShaderMaterial
var rain_mat: ShaderMaterial
var post_mat: ShaderMaterial
var badger_mat: ShaderMaterial
var refl_mat: ShaderMaterial
var shadow_mat: ShaderMaterial
var badger: Sprite2D
var refl: Sprite2D
var shadow: Sprite2D
var contact: Sprite2D

var narr: Label
var choices: Array[Label] = []
var hover_bar: ColorRect
var parser: Label
var cursor: ColorRect
var choice_box: Control


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	probe_no_badger = args.has("--probe-no-badger")
	probe_badger_only = args.has("--probe-badger-only")
	probe_no_rain = args.has("--probe-no-rain")
	rng.seed = SEED
	_load_data()
	_make_flicker()
	_build_scene()
	_build_badger()
	if not probe_badger_only:
		_build_rain()
		_build_post()
		_build_ui()
	_update()


func _load_data() -> void:
	var sc: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene.json"))
	LANTERN = Vector2(sc["lantern"][0], sc["lantern"][1])
	LAMP = Vector2(sc["lighthouse_lamp"][0], sc["lighthouse_lamp"][1])
	HORIZON_Y = sc["horizon_y"]
	QUAY_Y = sc["quay_edge_y"]
	info = JSON.parse_string(FileAccess.get_file_as_string("res://art/badger.json"))
	anchor = Vector2(info["anchor"][0], info["anchor"][1])


func _make_flicker() -> void:
	# Stützwerte alle 1/12 s: meist leichtes Zittern, selten ein Einbruch (Wind), dazwischen linear.
	for i in 12 * 8:
		var v := 1.0 + rng.randf_range(-0.09, 0.07)
		if rng.randf() < 0.09:
			v = rng.randf_range(0.62, 0.78)
		flicker_keys.append(v)
	# Tippzeiten der Parserzeile: Schreibmaschinenrhythmus mit kleinen Schwankungen
	var tt := T_PARSER
	for i in 12:
		parser_times.append(tt)
		tt += 1.0 / PARSER_CPS * rng.randf_range(0.7, 1.35)


func flicker_at(time: float) -> float:
	var x := time * 12.0
	var i := int(floor(x))
	var f := x - i
	var a: float = flicker_keys[i % flicker_keys.size()]
	var b: float = flicker_keys[(i + 1) % flicker_keys.size()]
	return clampf(lerpf(a, b, f) + 0.025 * sin(time * 41.0), 0.55, 1.12)


func _shader(path: String) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = load(path)
	return m


func _set_window(m: ShaderMaterial) -> void:
	m.set_shader_parameter("win_a", WIN_A)
	m.set_shader_parameter("win_b", WIN_B)
	m.set_shader_parameter("win_c", WIN_C)
	m.set_shader_parameter("win_d", WIN_D)


func _build_scene() -> void:
	var bg := Sprite2D.new()
	bg.texture = load("res://art/bg.png")
	bg.centered = false
	bg_mat = _shader("res://shaders/scene.gdshader")
	bg_mat.set_shader_parameter("fx_mask", load("res://art/fx_mask.png"))
	bg_mat.set_shader_parameter("aux_mask", load("res://art/aux_mask.png"))
	bg_mat.set_shader_parameter("noise_tex", load("res://art/noise.png"))
	bg_mat.set_shader_parameter("lantern", LANTERN)
	bg_mat.set_shader_parameter("lamp", LAMP)
	bg_mat.set_shader_parameter("quay_y", QUAY_Y)
	_set_window(bg_mat)
	bg.material = bg_mat
	add_child(bg)
	if probe_badger_only:
		bg.visible = false
		var plate := ColorRect.new()
		plate.color = Color(1, 0, 1)
		plate.size = VIEW
		add_child(plate)


func _make_soft_ellipse(w: int, h: int) -> ImageTexture:
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	for y in h:
		for x in w:
			var dx := (x + 0.5 - w * 0.5) / (w * 0.5)
			var dy := (y + 0.5 - h * 0.5) / (h * 0.5)
			var d := sqrt(dx * dx + dy * dy)
			var a := clampf(1.0 - d, 0.0, 1.0)
			img.set_pixel(x, y, Color(0, 0, 0, a * a * 0.75))
	return ImageTexture.create_from_image(img)


func _build_badger() -> void:
	var sheet: Texture2D = load("res://art/badger.png")
	var nframes: int = info["frames"].size()

	refl = Sprite2D.new()
	refl.texture = sheet
	refl.hframes = nframes
	refl.centered = false
	refl_mat = _shader("res://shaders/badger_refl.gdshader")
	refl_mat.set_shader_parameter("feet_y", FEET_Y)
	refl.material = refl_mat

	contact = Sprite2D.new()
	contact.texture = _make_soft_ellipse(96, 14)

	shadow = Sprite2D.new()
	shadow.texture = sheet
	shadow.hframes = nframes
	shadow.centered = false
	shadow_mat = _shader("res://shaders/badger_shadow.gdshader")
	shadow_mat.set_shader_parameter("bg_tex", load("res://art/bg.png"))
	shadow_mat.set_shader_parameter("aux_mask", load("res://art/aux_mask.png"))
	_set_window(shadow_mat)
	shadow.material = shadow_mat

	badger = Sprite2D.new()
	badger.texture = sheet
	badger.hframes = nframes
	badger.centered = false
	badger_mat = _shader("res://shaders/badger.gdshader")
	badger_mat.set_shader_parameter("normal_tex", load("res://art/badger_n.png"))
	badger_mat.set_shader_parameter("lantern", LANTERN)
	badger_mat.set_shader_parameter("window_pos", WINDOW_POS)
	badger_mat.set_shader_parameter("beam_x", BEAM_X)
	badger.material = badger_mat

	# Prüfschalter: Knoten bleiben im Baum (sonst meldet Godot beim Beenden verwaiste Materialien), nur unsichtbar
	for n in [refl, contact, shadow, badger]:
		add_child(n)
		n.visible = not probe_no_badger and (n == badger or not probe_badger_only)


func _build_rain() -> void:
	var r := ColorRect.new()
	r.size = VIEW
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	rain_mat = _shader("res://shaders/rain.gdshader")
	rain_mat.set_shader_parameter("fx_mask", load("res://art/fx_mask.png"))
	rain_mat.set_shader_parameter("aux_mask", load("res://art/aux_mask.png"))
	rain_mat.set_shader_parameter("lantern", LANTERN)
	rain_mat.set_shader_parameter("horizon_y", HORIZON_Y)
	rain_mat.set_shader_parameter("quay_y", QUAY_Y)
	r.material = rain_mat
	add_child(r)
	r.visible = not probe_no_rain


func _build_post() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 1
	add_child(layer)
	var r := ColorRect.new()
	r.size = VIEW
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	post_mat = _shader("res://shaders/post.gdshader")
	r.material = post_mat
	layer.add_child(r)


# --- Oberfläche: Titelkarte -------------------------------------------------------------------------------------

class CardFrame extends Control:
	## Doppelrahmen mit Art-déco-Ecken (drei ineinanderliegende Winkel je Ecke), alles 1 px.
	func _draw() -> void:
		var r := Rect2(Vector2.ZERO, size)
		draw_rect(r, Color(0.02, 0.02, 0.02, 0.88), true)
		var outer := Color(0.88, 0.88, 0.86, 0.95)
		var inner := Color(0.62, 0.62, 0.60, 0.85)
		draw_rect(r.grow(-0.5), outer, false, 1.0)
		var ri := r.grow(-5.5)
		draw_rect(ri, inner, false, 1.0)
		# Je Stufe ein geschlossenes L aus ganzen Pixeln, Eckpunkt auf der Diagonale (d|d) ab der Pixelzeile bzw.
		# -spalte des Innenrahmens; die Schenkel enden am Innenrahmen und kreuzen sich nicht.
		var w := int(size.x)
		var h := int(size.y)
		for c in [Vector2i(0, 0), Vector2i(1, 0), Vector2i(0, 1), Vector2i(1, 1)]:
			var px := 5 if c.x == 0 else w - 6
			var py := 5 if c.y == 0 else h - 6
			var sx := 1 if c.x == 0 else -1
			var sy := 1 if c.y == 0 else -1
			for k in 3:
				var d := 4 + k * 4
				var cx := px + sx * d
				var cy := py + sy * d
				draw_rect(Rect2(cx, mini(py + sy, cy), 1, d), outer, true)
				draw_rect(Rect2(px + 1 if sx > 0 else px - d + 1, cy, d - 1, 1), outer, true)   # ohne Eckpixel


func _label(text: String, font: Font, size: int, color: Color, spacing := 0.0) -> Label:
	var l := Label.new()
	l.text = text
	var ls := LabelSettings.new()
	if spacing != 0.0:
		var fv := FontVariation.new()
		fv.base_font = font
		fv.spacing_glyph = int(spacing)
		ls.font = fv
	else:
		ls.font = font
	ls.font_size = size
	ls.font_color = color
	l.label_settings = ls
	return l


func _build_ui() -> void:
	var M: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/ui_text.json"))
	var deco: Font = load("res://fonts/Limelight-Regular.ttf")
	var mono: Font = load("res://fonts/CourierPrime-Regular.ttf")
	var mono_b: Font = load("res://fonts/CourierPrime-Bold.ttf")
	var layer := CanvasLayer.new()
	layer.layer = 2
	add_child(layer)

	var card := CardFrame.new()
	card.position = CARD.position
	card.size = CARD.size
	layer.add_child(card)

	var loc := _label(String(M["location"]).to_upper(), deco, 17, INK, 3.0)
	loc.position = Vector2(22, 17)
	card.add_child(loc)
	var rule := ColorRect.new()
	rule.color = Color(0.62, 0.62, 0.60, 0.85)
	rule.position = Vector2(22, 46)
	rule.size = Vector2(CARD.size.x - 44, 1)
	card.add_child(rule)

	# Zeilenumbruch nach dem ersten Satz von Hand (Label-Autowrap ergab hier die volle Breite, siehe pitfalls)
	narr = _label(String(M["line"]).replace(". ", ".\n"), mono, 18, INK)
	narr.position = Vector2(22, 54)
	narr.label_settings.line_spacing = 1.0
	narr.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	card.add_child(narr)

	choice_box = Control.new()
	choice_box.position = Vector2(22, 108)
	card.add_child(choice_box)
	hover_bar = ColorRect.new()
	hover_bar.color = INK
	hover_bar.size = Vector2(3, 17)
	hover_bar.visible = false
	choice_box.add_child(hover_bar)
	var arr: Array = M["choices"]
	for i in arr.size():
		var l := _label("%d  %s" % [i + 1, arr[i]], mono, 16, DIM)
		l.position = Vector2(10, i * 23)
		choice_box.add_child(l)
		choices.append(l)

	parser = _label(M["parser_prompt"], mono_b, 17, INK)
	parser.position = Vector2(22, 183)
	parser.visible_characters = 0
	card.add_child(parser)
	cursor = ColorRect.new()
	cursor.color = INK
	cursor.size = Vector2(9, 16)
	card.add_child(cursor)


# --- Ablauf -----------------------------------------------------------------------------------------------------

func badger_state(time: float) -> Array:
	## [Bildnummer im Bogen, x des Rig-Ursprungs]
	var k := int(floor(time * SPRITE_FPS + 1e-4))
	if k < WALK_N:
		return [(1 + k) % 8, X_START + STEP * k]
	var x_stop := X_START + STEP * (WALK_N - 1) + STAND_SHIFT
	if time < T_TURN:
		return [F_STAND, x_stop]
	for b in BLINKS:
		if time >= b[0] and time < b[1]:
			return [F_BLINK, x_stop]
	return [F_TURN, x_stop]


func _process(delta: float) -> void:
	t += delta
	frame_no += 1
	_update()


func _update() -> void:
	var fl := flicker_at(t)
	var phi := TAU * (t - 5.2) / 5.0 - PI * 0.5   # bei 5,2 s zeigt der Strahl ganz nach links
	if bg_mat:
		bg_mat.set_shader_parameter("t", t)
		bg_mat.set_shader_parameter("flicker", fl)
		bg_mat.set_shader_parameter("beam_phi", phi)

	var st := badger_state(t)
	var f: int = st[0]
	var xr: float = st[1]
	var sx := roundf(xr - anchor.x)
	var sole := roundf(anchor.y)
	# Atmen in der Dreiviertelansicht: Skalierung um den Fußpunkt
	var breathe := 1.0
	if t >= T_TURN:
		breathe = 1.0 + 0.0045 * sin(TAU * (t - T_TURN) / 2.2)
	badger.frame = f
	badger.transform = Transform2D(Vector2(1, 0), Vector2(0, breathe), Vector2(sx, FEET_Y - sole * breathe))
	badger_mat.set_shader_parameter("flicker", fl)

	var inbeam := clampf((xr - BEAM_X.x + 20.0) / 60.0, 0.0, 1.0) * clampf((BEAM_X.y + 20.0 - xr) / 60.0, 0.0, 1.0)
	refl.frame = f
	refl.transform = Transform2D(Vector2(1, 0), Vector2(0, -0.85 * breathe), Vector2(sx, FEET_Y + 1.0 + sole * 0.85 * breathe))
	refl_mat.set_shader_parameter("t", t)
	refl_mat.set_shader_parameter("refl_gain", 0.26 + 0.24 * inbeam)
	contact.position = Vector2(xr + 4.0, FEET_Y + 1.0)
	shadow.frame = f
	shadow.transform = Transform2D(Vector2(1, 0), -SHADOW_DIR * breathe, Vector2(sx, FEET_Y) + SHADOW_DIR * sole * breathe)

	if rain_mat:
		rain_mat.set_shader_parameter("t", t)
		rain_mat.set_shader_parameter("flicker", fl)
	if post_mat:
		post_mat.set_shader_parameter("frame", float(frame_no % 997))
		post_mat.set_shader_parameter("exposure", 1.0 + 0.018 * (fposmod(sin(frame_no * 12.9898) * 43758.5453, 1.0) - 0.5))
	if narr:
		_update_ui()


func _update_ui() -> void:
	narr.visible_characters = int(clampf((t - T_NARR) * NARR_CPS, 0.0, 999.0))
	var ca := clampf((t - T_CHOICES) / 0.35, 0.0, 1.0)
	choice_box.modulate.a = ca
	var hover := t >= T_HOVER
	hover_bar.visible = hover
	hover_bar.position = Vector2(0, 23 * 1 + 2)
	for i in choices.size():
		choices[i].label_settings.font_color = INK if (hover and i == 1) else DIM
	var n := 0
	for pt in parser_times:
		if t >= pt:
			n += 1
	parser.visible_characters = n
	# Cursor hinter dem letzten sichtbaren Zeichen; blinkt erst nach dem Tippen
	var adv := 10.2
	cursor.position = Vector2(22 + 1 + n * adv, 185)
	var done_t: float = parser_times[parser_times.size() - 1]
	cursor.visible = t < done_t or fposmod((t - done_t) / 0.6, 1.0) < 0.55
