extends Node2D
## Hafen von Lornholm als Scherenschnitt-Bühne: farbiger Himmel und Wasser hinten (Shader), davor vier
## Papierebenen aus einem einzigen KI-Bild, nach Tiefe eingefärbt (je ferner, desto heller und nebliger),
## dazwischen Seidenpapier-Nebel. Lichter scheinen durch die geschnittenen Löcher (Fenster, Laternenglas,
## Lampenraum). Davor läuft der Dachs als Gliederpuppe (puppet.gd) im Takt eines Legetrickfilms
## (15 Posen/s) unter die Laterne, schaut hinauf und hält das Paket hoch.
## Alles hängt nur von der aufsummierten Zeit ab; Flackern über FastNoiseLite mit festem Seed.
##
## Benutzerargumente (nach "--"):
##   --t0=<s>        Startzeit (Langzeitprüfung)
##   --badger-only   nur die Puppe vor hellem Grund (Messung von Füßen und Kopf)
##   --smooth        Puppe mit 30 statt 15 Posen/s (Vergleich)
##   --no-gap        ohne Schnittfuge an Arm und Bein (Vergleich)
##   --no-lining     ohne Seidenpapier-Futter hinter den Schnitten der Puppe (Vergleich)
##   --no-fog        ohne Nebelstreifen (Vergleich)
##   --only=a,b      nur diese Puppenteile zeigen (z. B. leg_n,foot_n), für die Fußmessung

const PAPER := Color(0.07, 0.045, 0.09)
const C_FAR := Color(0.72, 0.46, 0.54)
const C_CLOUD := Color(0.47, 0.27, 0.45)
const C_HEAD := Color(0.47, 0.29, 0.43)
const C_BAND := Color(0.62, 0.20, 0.27)
const C_JETTY := Color(0.33, 0.20, 0.32)
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"
const PUPPET_FPS := 15.0
const BEAM_PERIOD := 7.0
const BEAM_PHASE := -1.14        # Blitz bei 2,65 s, Strahl ganz nach links bei 4,8 s

var t := 0.0
var t0 := 0.0
var scene: Dictionary
var smooth := false
var badger_only := false
var mats := []                   # Shader mit Uniform t
var noise := FastNoiseLite.new()
var puppet: Node2D
var gulls: Node2D
var sky_mat: ShaderMaterial
var clouds := []
var boats := []                  # [Sprite2D, Basisposition, Phase, Spiegelbild]
var light_window: Sprite2D
var light_lantern: Sprite2D
var light_lamp: Sprite2D
var glow_lantern: ColorRect
var glow_window: ColorRect
var ui_line: Label
var ui_choices := []
var ui_parser: Label
var ui_cursor: ColorRect
var font_text: FontFile
var font_sc: FontFile


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a == "--badger-only":
			badger_only = true
		elif a == "--smooth":
			smooth = true
	noise.seed = 7
	noise.noise_type = FastNoiseLite.TYPE_SIMPLEX
	noise.frequency = 1.0
	scene = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene.json"))
	if badger_only:
		var bg := ColorRect.new()
		bg.color = Color(0.93, 0.86, 0.74)
		bg.size = Vector2(1280, 720)
		add_child(bg)
	else:
		_build_stage()
	puppet = preload("res://puppet.gd").new()
	add_child(puppet)
	puppet.build("res://art/puppet/rig.json")
	if "--no-gap" in OS.get_cmdline_user_args():
		puppet.set_gap(false)
	if "--no-lining" in OS.get_cmdline_user_args():
		puppet.set_lining(false)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--only="):
			puppet.show_only(a.substr(7).split(","))
	if not badger_only:
		_build_front_fx()
		_build_ui()
	t = t0
	_apply()


func _sprite(file: String, pos: Vector2, col: Color) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = load("res://art/" + file)
	s.centered = false
	s.position = pos
	s.modulate = col
	add_child(s)
	return s


func _rect(pos: Vector2, size: Vector2, shader: String, params := {}) -> ColorRect:
	var r := ColorRect.new()
	r.position = pos
	r.size = size
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/" + shader)
	for k in params:
		m.set_shader_parameter(k, params[k])
	r.material = m
	mats.append(m)
	add_child(r)
	return r


func _build_stage() -> void:
	var far_tex: Texture2D = load("res://art/layer_far.png")
	var head_tex: Texture2D = load("res://art/layer_head.png")
	var lamp: Vector2 = Vector2(scene["light_lamp"]["center"][0], scene["light_lamp"]["center"][1])
	var sky := _rect(Vector2.ZERO, Vector2(1280, 720), "sky.gdshader", {
		"horizon": scene["horizon_y"], "quay": scene["quay_y"], "far_tex": far_tex, "head_tex": head_tex,
		"lamp": lamp, "wl": PackedFloat32Array(scene["head_waterline16"])})
	sky_mat = sky.material
	# Wolken (aus dem KI-Bild ausgeschnitten, neu gesetzt, driften langsam)
	var cpos := [Vector2(-40, 26), Vector2(420, 128), Vector2(770, 50)]
	for i in 3:
		var c: Dictionary = scene["clouds"][i]
		var s := _sprite(c["file"], cpos[i], C_CLOUD)
		clouds.append([s, cpos[i], [4.0, 7.0, 5.0][i]])
	_sprite("layer_far.png", Vector2.ZERO, C_FAR)
	_rect(Vector2(0, 236), Vector2(1280, 70), "fog.gdshader", {"rect_size": Vector2(1280, 70),
		"tint": Color(0.98, 0.70, 0.52), "density": 0.42, "edge_y": 26.0, "edge_amp": 7.0, "speed": -5.0,
		"fade": 0.55, "seed": 1.0})
	# Landzunge mit Leuchtturm; Licht des Lampenraums liegt hinter der Ebene und scheint durch die Löcher
	light_lamp = _sprite("light_lamp.png", _pos("light_lamp"), Color(1.0, 0.93, 0.70))
	_sprite("layer_head.png", Vector2.ZERO, C_HEAD)
	_sprite("layer_band.png", _pos("layer_band"), C_BAND)
	_rect(Vector2(0, 0), Vector2(1280, 260), "beam.gdshader", {"rect_size": Vector2(1280, 260), "lamp": lamp,
		"period": BEAM_PERIOD, "phase0": BEAM_PHASE})
	gulls = preload("res://gulls.gd").new()
	add_child(gulls)
	# Boote mit Spiegelbild, Steg
	for k in ["boat_l", "boat_r"]:
		var b: Dictionary = scene[k]
		var size := Vector2(b["size"][0], b["size"][1])
		var keel: float = b["keel_y"]
		var pivot := Vector2(float(b["center_x"]), keel)
		var refl := Sprite2D.new()
		refl.texture = load("res://art/" + b["file"])
		refl.centered = false
		refl.offset = Vector2(b["pos"][0], b["pos"][1]) - pivot
		refl.position = pivot + Vector2(0, 1)
		refl.scale = Vector2(1, -1)
		refl.modulate = Color(0.12, 0.07, 0.16)
		var rm := ShaderMaterial.new()
		rm.shader = load("res://shaders/reflect.gdshader")
		rm.set_shader_parameter("tex_size", size)
		rm.set_shader_parameter("strength", 0.42)
		refl.material = rm
		mats.append(rm)
		add_child(refl)
	var bl := _boat("boat_l")
	_sprite("layer_jetty.png", Vector2.ZERO, C_JETTY)
	var br := _boat("boat_r")
	boats = [[bl, 0.0, 2.8], [br, 1.9, 3.4]]
	_rect(Vector2(0, 500), Vector2(1280, 80), "fog.gdshader", {"rect_size": Vector2(1280, 80),
		"tint": Color(0.98, 0.74, 0.66), "density": 0.40, "edge_y": 30.0, "edge_amp": 7.0, "speed": 7.0,
		"fade": 0.0, "seed": 4.0})
	if "--no-fog" in OS.get_cmdline_user_args():
		for m in mats:
			if m.shader.resource_path.ends_with("fog.gdshader"):
				m.set_shader_parameter("density", 0.0)
	# Rauch, Lichter hinter der vorderen Ebene, vordere Ebene
	var ch: Vector2 = Vector2(scene["chimney_top"][0], scene["chimney_top"][1])
	_rect(Vector2(ch.x - 210, ch.y - 136), Vector2(240, 140), "smoke.gdshader", {"rect_size": Vector2(240, 140),
		"source": Vector2(210, 138)})
	light_window = _sprite("light_window.png", _pos("light_window"), Color(1.0, 0.72, 0.32))
	light_lantern = _sprite("light_lantern.png", _pos("light_lantern"), Color(1.0, 0.80, 0.42))
	_sprite("layer_front.png", Vector2.ZERO, PAPER)


func _pos(k: String) -> Vector2:
	return Vector2(scene[k]["pos"][0], scene[k]["pos"][1])


func _boat(k: String) -> Sprite2D:
	var b: Dictionary = scene[k]
	var s := Sprite2D.new()
	s.texture = load("res://art/" + b["file"])
	s.centered = false
	var pivot := Vector2(float(b["center_x"]), float(b["keel_y"]))
	s.offset = Vector2(b["pos"][0], b["pos"][1]) - pivot
	s.position = pivot
	s.modulate = C_JETTY
	s.set_meta("pivot", pivot)
	add_child(s)
	return s


func _build_front_fx() -> void:
	var lc: Vector2 = Vector2(scene["light_lantern"]["center"][0], scene["light_lantern"]["center"][1])
	glow_lantern = _rect(lc - Vector2(130, 130), Vector2(260, 260), "glow.gdshader", {"falloff": 2.4})
	var wc: Vector2 = Vector2(scene["light_window"]["center"][0], scene["light_window"]["center"][1])
	glow_window = _rect(wc - Vector2(95, 95), Vector2(190, 190), "glow.gdshader", {"falloff": 2.6})


func _font(path: String) -> FontFile:
	var f: FontFile = load(path)
	return f


func _label(parent: Node, text: String, font: Font, size: int, col: Color, pos: Vector2, spacing := 0) -> Label:
	var l := Label.new()
	l.text = text
	l.position = pos
	var ls := LabelSettings.new()
	ls.font = font
	ls.font_size = size
	ls.font_color = col
	if spacing != 0:
		var fv := FontVariation.new()
		fv.base_font = font
		fv.spacing_glyph = spacing
		ls.font = fv
	l.label_settings = ls
	parent.add_child(l)
	return l


func _build_ui() -> void:
	font_text = _font("res://fonts/Marcellus-Regular.ttf")
	font_sc = _font("res://fonts/MarcellusSC-Regular.ttf")
	var all_text := LINE + PARSER + "".join(PackedStringArray(CHOICES)) + "Hafen von Lornholm"
	for i in all_text.length():
		for f in [font_text, font_sc]:
			if not f.has_char(all_text.unicode_at(i)):
				push_warning("Schrift ohne Zeichen: " + all_text[i])
	var layer := CanvasLayer.new()
	layer.layer = 10
	add_child(layer)
	var panel := ColorRect.new()
	panel.color = PAPER
	panel.position = Vector2(0, 596)
	panel.size = Vector2(1280, 124)
	layer.add_child(panel)
	var border := ColorRect.new()
	border.position = Vector2(0, 588)
	border.size = Vector2(1280, 20)
	var bm := ShaderMaterial.new()
	bm.shader = load("res://shaders/border.gdshader")
	bm.set_shader_parameter("rect_size", Vector2(1280, 20))
	border.material = bm
	layer.add_child(border)
	var amber := Color(0.93, 0.62, 0.36)
	var cream := Color(0.96, 0.87, 0.72)
	_label(layer, "Hafen von Lornholm", font_sc, 17, amber, Vector2(44, 610), 2)
	ui_line = _label(layer, LINE, font_text, 24, cream, Vector2(44, 633))
	ui_line.visible_characters = 0
	var x := 44.0
	for i in 3:
		var h := HBoxContainer.new()
		h.position = Vector2(x, 676)
		h.add_theme_constant_override("separation", 8)
		layer.add_child(h)
		var n := _label(h, str(i + 1) + ".", font_text, 18, amber, Vector2.ZERO)
		var c := _label(h, CHOICES[i], font_text, 18, cream, Vector2.ZERO)
		h.modulate.a = 0.0
		ui_choices.append([h, c])
		x += [258.0, 236.0, 0.0][i]
	ui_parser = _label(layer, "", font_text, 20, amber, Vector2(1000, 674))
	ui_cursor = ColorRect.new()
	ui_cursor.color = amber
	ui_cursor.size = Vector2(10, 18)
	layer.add_child(ui_cursor)


func _process(delta: float) -> void:
	t += delta
	_apply()


func _apply() -> void:
	for m in mats:
		m.set_shader_parameter("t", t)
	var tq: float = t if smooth else floor(t * PUPPET_FPS + 1e-4) / PUPPET_FPS
	puppet.pose(tq)
	if badger_only:
		return
	# Leuchtfeuer: Aufblitzen auch im Wasser (gleiche Phase wie beam.gdshader)
	var ph := TAU * t / BEAM_PERIOD + BEAM_PHASE
	var flash := pow(maxf(sin(ph), 0.0), 6.0)
	sky_mat.set_shader_parameter("lamp_flash", flash)
	light_lamp.modulate = Color(1.0, 0.93, 0.70) * (0.75 + 0.5 * flash)
	light_lamp.modulate.a = 1.0
	# Laterne: Grundflackern + Windböen
	var f := 0.82 + 0.12 * noise.get_noise_1d(t * 9.0) + 0.06 * noise.get_noise_1d(t * 23.0 + 50.0)
	var gust := smoothstep(0.55, 0.9, noise.get_noise_1d(t * 0.7 + 100.0) * 0.5 + 0.5)
	f -= 0.25 * gust * (0.5 + 0.5 * noise.get_noise_1d(t * 31.0 + 7.0))
	light_lantern.modulate = Color(1.0, 0.80, 0.42).lerp(Color(1.0, 0.62, 0.30), 1.0 - f)
	light_lantern.modulate.a = 1.0
	glow_lantern.modulate = Color(1.0, 0.72, 0.38, 0.42 * f)
	var fw := 0.92 + 0.06 * noise.get_noise_1d(t * 4.0 + 300.0)
	light_window.modulate = Color(1.0, 0.72, 0.32) * fw
	light_window.modulate.a = 1.0
	glow_window.modulate = Color(1.0, 0.66, 0.30, 0.22 * fw)
	# Wolken driften (ganze Pixel, Wiederholung nach Bildbreite)
	for c in clouds:
		var s: Sprite2D = c[0]
		var w := float(s.texture.get_width())
		var x: float = c[1].x - floor(t * c[2])
		x = fposmod(x + w, 1280.0 + w) - w
		s.position = Vector2(x, c[1].y)
	# Boote schaukeln um den Kiel
	for b in boats:
		var s: Sprite2D = b[0]
		var ph2: float = b[1]
		var per: float = b[2]
		s.rotation = deg_to_rad(1.3) * sin(TAU * t / per + ph2)
		s.position = s.get_meta("pivot") + Vector2(0, round(1.2 * sin(TAU * t / per + ph2 + 1.2)))
	gulls.t = t
	gulls.queue_redraw()
	# Textfeld: Zeile tippt, dann Auswahl, dann Parser
	ui_line.visible_characters = int(clampf((t - 0.4) * 32.0, 0.0, LINE.length()))
	for i in 3:
		var h: Control = ui_choices[i][0]
		h.modulate.a = smoothstep(2.6 + 0.25 * i, 2.9 + 0.25 * i, t)
	var hl := smoothstep(4.65, 4.8, t)
	ui_choices[1][1].label_settings.font_color = Color(0.96, 0.87, 0.72).lerp(Color(1.0, 0.66, 0.34), hl)
	var n := int(clampf((t - 3.3) * 9.0, 0.0, PARSER.length() - 2)) + 2 if t > 3.1 else 0
	ui_parser.text = PARSER.substr(0, n)
	var tw := font_text.get_string_size(ui_parser.text, HORIZONTAL_ALIGNMENT_LEFT, -1, 20).x
	ui_cursor.position = Vector2(1000 + tw + 4, 680)
	ui_cursor.visible = t > 3.1 and fmod(t, 0.9) < 0.55
