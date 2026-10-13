extends Node2D
## Hafen von Lornholm als Bilderbuch-Seite in Gouache.
## Alles hängt nur von der aufsummierten Zeit t ab; Zufall nur mit RandomNumberGenerator und festem Seed.
## Lage der Lichter, Sterne und Boote: res://art/scene.json (scripts/build_scene.py).
## Ablauf der Figur (ein Eintrag je Bild bei 30 fps): res://art/timeline.json (scripts/choreo.py).

const FPS := 30.0
const SMOKE_LIFE := 4.6
const SMOKE_EVERY := 0.75
const SMOKE_TEX := [preload("res://art/fx/smoke_0.png"), preload("res://art/fx/smoke_1.png"),
		preload("res://art/fx/smoke_2.png")]
const GLINT_TEX := [preload("res://art/fx/glint_0.png"), preload("res://art/fx/glint_1.png"),
		preload("res://art/fx/glint_2.png"), preload("res://art/fx/glint_3.png")]
const RIPPLE_TEX := [preload("res://art/fx/ripple_0.png"), preload("res://art/fx/ripple_1.png")]
const BULLET_TEX := [preload("res://art/fx/bullet_0.png"), preload("res://art/fx/bullet_1.png"),
		preload("res://art/fx/bullet_2.png")]
const WATERLINE := preload("res://shaders/waterline.gdshader")
const REFLECTION := preload("res://shaders/reflection.gdshader")

# Text (Bilderbuch: der Text steht im ruhigen Himmel über der Szene)
const TITLE := "HAFEN VON LORNHOLM"
const LINE := "Die Laterne flackert im Wind.\nAm Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"
const TITLE_T := 0.15
const TYPE_START := 0.5
const TYPE_CPS := 34.0
const CHOICE_T := [2.6, 2.8, 3.0]
const CHOICE_Y := 150.0
const CHOICE_DY := 27.0
const HOVER_T := 3.7
const HOVER_DUR := 0.45
const PARSER_T := 4.1
const PARSER_CPS := 14.0
const CREAM := Color(0.973, 0.925, 0.84)
const APRICOT := Color(0.957, 0.71, 0.52)
const HOVER_COL := Color(1.0, 0.86, 0.64)
const DIGIT_COL := Color(0.25, 0.17, 0.2)

var t := 0.0
var scene: Dictionary
var tl: Dictionary
var rows: Array = []
var badger_cell := Vector2(162, 210)
var badger_foot_y := 0.0

var stars: Array = []       # [Sprite2D, phase, speed, base_scale]
var glints: Array = []      # [Sprite2D, Vector2 base, phase, period, drift]
var smoke: Array = []       # Sprite2D-Pool
var smoke_seed: Array = []  # je Rauchtupfer: [variant, sway_phase, size, drift]
var boats: Array = []       # [Node2D pivot, Sprite2D refl, float water_y, float phase, Array ripples, Vector2 base]
var flicker := PackedFloat32Array()

var lamp_halo: Sprite2D
var lamp_rays: Sprite2D
var lantern_halo: Sprite2D
var window_halo: Sprite2D
var badger: Sprite2D
var shadow: Sprite2D
var tex_walk: Texture2D
var tex_idle: Texture2D

var title_lbl: Label
var line_lbl: Label
var choice_lbls: Array = []
var choice_items: Array = []   # Control je Antwort (Tupfer + Text)
var hover_clip: Control
var band: TextureRect
var hover_w := 0.0
var parser_lbl: Label


func _ready() -> void:
	scene = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene.json"))
	tl = JSON.parse_string(FileAccess.get_file_as_string("res://art/timeline.json"))
	var bj: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/badger.json"))
	rows = tl["rows"]
	badger_cell = Vector2(bj["cell_w"], bj["cell_h"])
	badger_foot_y = float(bj["foot_y"])
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261011
	# Flackertabelle (glattes Rauschen über Zeit), deterministisch
	for i in range(256):
		flicker.append(rng.randf())
	_build_sky(rng)
	_build_water(rng)
	_build_boats()
	_build_lights()
	_build_actor()
	_build_ui()
	_update()


func _process(delta: float) -> void:
	t += delta
	_update()


func _noise(x: float) -> float:
	var i := int(floorf(x))
	var f := x - floorf(x)
	var a := flicker[posmod(i, 256)]
	var b := flicker[posmod(i + 1, 256)]
	var s := f * f * (3.0 - 2.0 * f)
	return lerpf(a, b, s)


func _sprite(tex: Texture2D, parent: Node, pos: Vector2) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = tex
	s.position = pos
	parent.add_child(s)
	return s


# --- Aufbau -------------------------------------------------------------------------------------------------------

func _build_sky(rng: RandomNumberGenerator) -> void:
	var star_tex: Texture2D = load("res://art/fx/star.png")
	var text_box := Rect2(320, 8, 640, 225)
	for p in scene["stars"]:
		var pos := Vector2(p[0], p[1])
		if text_box.has_point(pos):
			continue   # keine funkelnden Sterne hinter der Schrift
		var s := _sprite(star_tex, $World/Sky, pos.round())
		stars.append([s, rng.randf() * TAU, rng.randf_range(1.6, 2.8), rng.randf_range(0.55, 0.8)])
	var n := int(ceilf(SMOKE_LIFE / SMOKE_EVERY)) + 1
	for i in range(n):
		var s := Sprite2D.new()
		$World/Sky.add_child(s)
		smoke.append(s)
	for i in range(64):
		smoke_seed.append([rng.randi_range(0, 2), rng.randf() * TAU, rng.randf_range(0.85, 1.1),
				rng.randf_range(8.0, 14.0)])


func _build_water(rng: RandomNumberGenerator) -> void:
	var w: Array = scene["water"]
	var jetty := Rect2(478, 448, 236, 90)
	var placed := 0
	while placed < 16:
		var y := rng.randf_range(float(w[1]) + 6.0, float(w[3]) - 8.0)
		var x := rng.randf_range(float(w[0]) + 20.0, float(w[2]) - 30.0)
		if jetty.has_point(Vector2(x, y)):
			continue
		var near_horizon := y < float(w[1]) + 26.0
		var ti := 2 if near_horizon else rng.randi_range(0, 3)
		if ti == 2 and not near_horizon:
			ti = 0
		var s := _sprite(GLINT_TEX[ti], $World/Water, Vector2(x, y).round())
		glints.append([s, Vector2(x, y), rng.randf() * TAU, rng.randf_range(2.2, 3.6), rng.randf_range(4.0, 9.0)])
		placed += 1


func _build_boats() -> void:
	var bs: Dictionary = scene["boats"]
	for name in ["boat_b", "boat_a"]:
		var b: Dictionary = bs[name]
		var tex: Texture2D = load("res://art/%s.png" % name)
		var wy := float(b["water_y"])
		var wl := float(b["water_local"])
		var base := Vector2(float(b["x"]), wy)
		# Spiegelbild (gespiegelt um die Wasserlinie)
		var refl := Sprite2D.new()
		refl.texture = tex
		refl.flip_v = true
		refl.centered = false
		refl.offset = Vector2(-tex.get_width() / 2.0, -(tex.get_height() - wl))
		var rm := ShaderMaterial.new()
		rm.shader = REFLECTION
		rm.set_shader_parameter("water_y", wy)
		rm.set_shader_parameter("phase", float(b["phase"]))
		refl.material = rm
		$World/Boats.add_child(refl)
		# Boot mit Drehpunkt auf der Wasserlinie
		var pivot := Node2D.new()
		$World/Boats.add_child(pivot)
		var spr := Sprite2D.new()
		spr.texture = tex
		spr.centered = false
		spr.offset = Vector2(-tex.get_width() / 2.0, -wl)
		var m := ShaderMaterial.new()
		m.shader = WATERLINE
		m.set_shader_parameter("water_y", wy)
		spr.material = m
		pivot.add_child(spr)
		var ripples: Array = []
		for k in range(2):
			var r := _sprite(RIPPLE_TEX[k], $World/Boats, base + Vector2(-28 + 52 * k, 1 + k))
			ripples.append(r)
		boats.append([pivot, refl, wy, float(b["phase"]), ripples, base, rm])


func _build_lights() -> void:
	window_halo = _sprite(load("res://art/fx/halo_window.png"), $World/Lights,
			Vector2(scene["window"][0], scene["window"][1]))
	lantern_halo = _sprite(load("res://art/fx/halo_lantern.png"), $World/Lights,
			Vector2(scene["lantern"][0], scene["lantern"][1]))
	lamp_halo = _sprite(load("res://art/fx/halo_lamp.png"), $World/Lights,
			Vector2(scene["lamp"][0], scene["lamp"][1]))
	lamp_rays = _sprite(load("res://art/fx/rays.png"), $World/Lights,
			Vector2(scene["lamp"][0], scene["lamp"][1]))


func _build_actor() -> void:
	tex_walk = load("res://art/badger_walk.png")
	tex_idle = load("res://art/badger_idle.png")
	shadow = _sprite(load("res://art/fx/shadow.png"), $World/Actor, Vector2.ZERO)
	shadow.modulate = Color(1, 1, 1, 0.5)
	badger = Sprite2D.new()
	badger.centered = false
	badger.region_enabled = true
	badger.offset = Vector2(-float(tl["pivot_x"]), -badger_foot_y)
	$World/Actor.add_child(badger)


func _font(path: String, wght: float, opsz: float, spacing := 0) -> FontVariation:
	var ts := TextServerManager.get_primary_interface()
	var fv := FontVariation.new()
	fv.base_font = load(path)
	fv.variation_opentype = {ts.name_to_tag("wght"): wght, ts.name_to_tag("opsz"): opsz,
			ts.name_to_tag("SOFT"): 100.0, ts.name_to_tag("WONK"): 0.0}
	fv.spacing_glyph = spacing
	return fv


func _label(parent: Node, text: String, font: Font, size: int, col: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	l.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	parent.add_child(l)
	return l


func _build_ui() -> void:
	var ui: CanvasLayer = $UI
	var f_title := _font("res://fonts/Fraunces-var.ttf", 620.0, 24.0, 3)
	var f_text := _font("res://fonts/Fraunces-var.ttf", 480.0, 48.0)
	var f_choice := _font("res://fonts/Fraunces-var.ttf", 520.0, 24.0)
	var f_digit := _font("res://fonts/Fraunces-var.ttf", 760.0, 14.0)
	var f_italic := _font("res://fonts/Fraunces-Italic-var.ttf", 460.0, 24.0)
	title_lbl = _label(ui, TITLE, f_title, 17, APRICOT)
	title_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title_lbl.position = Vector2(320, 20)
	title_lbl.size = Vector2(640, 24)
	line_lbl = _label(ui, LINE, f_text, 31, CREAM)
	line_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	line_lbl.add_theme_constant_override("line_spacing", -2)
	line_lbl.position = Vector2(300, 48)
	line_lbl.size = Vector2(680, 90)
	# Antworten untereinander auf einem dunklen Pinselfleck (gemalte Wolkenbank, hält die helle Schrift im
	# helleren unteren Himmel lesbar): Farbtupfer mit Ziffer, dann Text; darunter die Eingabezeile.
	var fs := 19
	var maxw := 0.0
	var widths: Array = []
	for c in CHOICES:
		var w := f_choice.get_string_size(c, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
		widths.append(w)
		maxw = maxf(maxw, w)
	var x := roundf(640.0 - (maxw + 31.0) / 2.0)
	band = TextureRect.new()
	band.texture = load("res://art/fx/band.png")
	band.position = Vector2(roundf(640.0 - band.texture.get_width() / 2.0), CHOICE_Y - 19.0)
	ui.add_child(band)
	for i in range(CHOICES.size()):
		var item := Control.new()
		item.position = Vector2(x, CHOICE_Y + CHOICE_DY * i)
		ui.add_child(item)
		var dot := TextureRect.new()
		dot.texture = BULLET_TEX[i]
		item.add_child(dot)
		var d := _label(item, str(i + 1), f_digit, 13, DIGIT_COL)
		d.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		d.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		d.position = Vector2(0, -1)
		d.size = Vector2(dot.texture.get_width(), dot.texture.get_height())
		if i == 1:
			hover_clip = Control.new()
			hover_clip.clip_contents = true
			hover_clip.position = Vector2(26, 18)
			hover_clip.size = Vector2(0, 14)
			item.add_child(hover_clip)
			var ul := TextureRect.new()
			ul.texture = load("res://art/fx/underline.png")
			ul.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			ul.stretch_mode = TextureRect.STRETCH_SCALE
			ul.size = Vector2(widths[i] + 10, 14)
			hover_clip.add_child(ul)
			hover_w = widths[i] + 10
		var l := _label(item, CHOICES[i], f_choice, fs, CREAM)
		l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		l.position = Vector2(31, -2)
		l.size = Vector2(widths[i] + 4, 26)
		choice_lbls.append(l)
		choice_items.append(item)
	# Eingabezeile linksbündig unter den Antworten (fester Anfang: der blinkende Strich verschiebt nichts)
	parser_lbl = _label(ui, "", f_italic, 17, Color(CREAM, 0.82))
	parser_lbl.position = Vector2(x + 31.0, CHOICE_Y + CHOICE_DY * 3 + 2.0)
	parser_lbl.size = Vector2(240, 24)


# --- Ablauf ------------------------------------------------------------------------------------------------------

func _update() -> void:
	var f := clampi(int(floorf(t * FPS + 0.001)), 0, rows.size() - 1)
	_update_sky()
	_update_water()
	_update_boats()
	_update_lights()
	_update_actor(f)
	_update_ui()


func _update_sky() -> void:
	for s in stars:
		var sp: Sprite2D = s[0]
		var v: float = 0.5 + 0.5 * sin(t * float(s[2]) + float(s[1]))
		sp.scale = Vector2.ONE * (float(s[3]) * (0.75 + 0.35 * v))
		sp.modulate = Color(1, 1, 1, 0.55 + 0.45 * v)
	# Rauch: Tupfer steigen auf, wachsen, treiben im Wind nach rechts, verblassen am Ende
	var origin := Vector2(scene["chimney"][0], scene["chimney"][1] + 3)
	var first := int(floorf((t - SMOKE_LIFE) / SMOKE_EVERY)) + 1
	var last := int(floorf(t / SMOKE_EVERY))
	for s in smoke:
		(s as Sprite2D).visible = false
	for i in range(first, last + 1):
		var age := t - i * SMOKE_EVERY
		if age < 0.0 or age >= SMOKE_LIFE:
			continue
		var sd: Array = smoke_seed[posmod(i, smoke_seed.size())]
		var sp: Sprite2D = smoke[posmod(i, smoke.size())]
		var u := age / SMOKE_LIFE
		sp.visible = true
		sp.texture = SMOKE_TEX[int(sd[0])]
		var sway := sin(age * 1.6 + float(sd[1])) * 5.0 * u
		sp.position = (origin + Vector2(float(sd[3]) * age + sway, -24.0 * age - 4.0 * age * age * 0.5)).round()
		var sc := (0.22 + 0.62 * sqrt(u)) * float(sd[2])
		sp.scale = Vector2(sc, sc * (0.92 + 0.08 * sin(age * 2.0 + float(sd[1]))))
		var a := clampf(age / 0.25, 0.0, 1.0) * (1.0 - smoothstep(0.55, 1.0, u))
		sp.modulate = Color(1, 1, 1, a)
		sp.z_index = 200 - i   # ältere (höhere) Tupfer liegen über den neuen


func _update_water() -> void:
	for g in glints:
		var sp: Sprite2D = g[0]
		var base: Vector2 = g[1]
		var ph := t / float(g[3]) * TAU + float(g[2])
		var v := 0.5 + 0.5 * sin(ph)
		sp.position = (base + Vector2(sin(ph * 0.5) * float(g[4]), 0)).round()
		sp.modulate = Color(1, 1, 1, smoothstep(0.25, 0.9, v) * 0.95)


func _update_boats() -> void:
	for b in boats:
		var pivot: Node2D = b[0]
		var refl: Sprite2D = b[1]
		var ph := float(b[3])
		var base: Vector2 = b[5]
		var rot := deg_to_rad(1.8) * sin(t * TAU / 3.2 + ph)
		var bob := 1.6 * sin(t * TAU / 3.2 + ph + 1.1)
		pivot.position = base + Vector2(0, bob)
		pivot.rotation = rot
		refl.position = base + Vector2(0, -bob)
		refl.rotation = -rot
		(b[6] as ShaderMaterial).set_shader_parameter("t", t)
		var rs: Array = b[4]
		for k in range(rs.size()):
			var r: Sprite2D = rs[k]
			r.position = (base + Vector2(-28 + 52 * k + 3.0 * sin(t * 1.3 + k * 2.0 + ph), 1 + k)).round()


func _update_lights() -> void:
	var fl := _noise(t * 8.0) * 0.55 + _noise(t * 19.0 + 40.0) * 0.45
	lantern_halo.modulate = Color(1, 1, 1, 0.3 + 0.7 * fl)
	lantern_halo.scale = Vector2.ONE * (0.85 + 0.25 * fl)
	var fw := _noise(t * 3.0 + 90.0)
	window_halo.modulate = Color(1, 1, 1, 0.45 + 0.25 * fw)
	# Leuchtturm: blinkt alle 2,5 s; Strahlen erscheinen nur beim Aufleuchten
	var cyc := fposmod(t + 0.6, 2.5) / 2.5
	var pulse := exp(-pow((cyc - 0.25) / 0.09, 2.0))
	lamp_halo.modulate = Color(1, 1, 1, 0.3 + 0.7 * pulse)
	lamp_halo.scale = Vector2.ONE * (0.7 + 0.35 * pulse)
	lamp_rays.modulate = Color(1, 1, 1, smoothstep(0.15, 0.7, pulse))
	lamp_rays.scale = Vector2.ONE * (0.75 + 0.3 * pulse)
	lamp_rays.rotation = t * 0.25


func _update_actor(f: int) -> void:
	var r: Array = rows[f]
	var sheet := str(r[0])
	var img := int(r[1])
	badger.texture = tex_walk if sheet == "walk" else tex_idle
	badger.region_rect = Rect2(img * badger_cell.x, 0, badger_cell.x, badger_cell.y)
	var feet := Vector2(float(r[2]) + float(tl["pivot_x"]), float(tl["feet_y"]))
	badger.position = feet
	badger.scale = Vector2(float(r[3]), float(r[4]))
	shadow.position = feet + Vector2(-2, 2)
	shadow.scale = Vector2(0.78 if sheet == "walk" else 0.9, 1.0)


func _update_ui() -> void:
	title_lbl.modulate = Color(1, 1, 1, smoothstep(TITLE_T, TITLE_T + 0.5, t))
	var n := int(floorf(maxf(0.0, t - TYPE_START) * TYPE_CPS))
	line_lbl.visible_characters = n if n < LINE.length() else -1
	for i in range(choice_items.size()):
		var it: Control = choice_items[i]
		var a := smoothstep(CHOICE_T[i], CHOICE_T[i] + 0.35, t)
		it.modulate = Color(1, 1, 1, a)
		it.position.y = CHOICE_Y + CHOICE_DY * i + 5.0 * (1.0 - a)
	band.modulate = Color(1, 1, 1, 0.9 * smoothstep(CHOICE_T[0] - 0.15, CHOICE_T[0] + 0.3, t))
	var h := smoothstep(HOVER_T, HOVER_T + HOVER_DUR, t)
	hover_clip.size.x = roundf(hover_w * h)
	(choice_lbls[1] as Label).add_theme_color_override("font_color", CREAM.lerp(HOVER_COL, h))
	var pn := int(floorf(maxf(0.0, t - PARSER_T) * PARSER_CPS))
	var shown := PARSER.substr(0, mini(pn, PARSER.length()))
	var cursor := "|" if t >= PARSER_T - 0.4 and fposmod(t, 0.9) < 0.55 else " "
	parser_lbl.text = shown + cursor if t >= PARSER_T - 0.4 else ""
