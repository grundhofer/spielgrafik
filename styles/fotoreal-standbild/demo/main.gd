extends Node2D
# Fotorealistisches Standbild: KI-Foto + freigestellter KI-Dachs als "Darsteller", alles Leben aus Shadern.
# Zeit aus aufsummiertem delta, Zufall nur aus RandomNumberGenerator mit festem Seed (deterministische Aufnahme).
# Schalter nach "--": --t0=SEKUNDEN (später starten), --raw (Dachs ohne Angleichung: Rohbild, kein Kantenlicht,
# kein Lichtsaum, kein Schatten, kein Korn), --frozen (Foto ohne Leben), --no-actor, --no-ui, --no-grain, --no-shadow,
# --look=0|1 (Kopfhaltung festhalten).

const SEED := 20261013
const LOC := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PROMPT := "> "   # Eingabezeichen wie in motif.json (ui_text.parser_prompt "> nimm paket")
const PARSER := "nimm paket"

var t := 0.0
var frame := 0
var raw := false
var frozen := false
var no_actor := false
var no_ui := false
var no_grain := false
var no_shadow := false
var look_fixed := -1.0

var scene := {}
var actor := {}
var flick_tab := PackedFloat32Array()   # Laterne, 20 Werte je Sekunde
var slow_tab := PackedFloat32Array()    # langsame Schwankung (Laterne, Fenster), 2 je Sekunde
var gust_tab := PackedFloat32Array()    # Böen für den Schal, 2 je Sekunde
var look_events := []                   # [start, dauer]

var photo_mat: ShaderMaterial
var actor_mat: ShaderMaterial
var shadow_mat: ShaderMaterial
var post_mat: ShaderMaterial
var panel_mat: ShaderMaterial
var lbl_line: Label
var lbl_parser: Label
var choice_lbls := []
var choice_nums := []

const PANEL_POS := Vector2(742, 522)
const PANEL_SIZE := Vector2(520, 182)


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t = float(a.substr(5))
		elif a == "--raw":
			raw = true
		elif a == "--frozen":
			frozen = true
		elif a == "--no-actor":
			no_actor = true
		elif a == "--no-ui":
			no_ui = true
		elif a == "--no-grain":
			no_grain = true
		elif a == "--no-shadow":
			no_shadow = true
		elif a.begins_with("--look="):
			look_fixed = float(a.substr(7))
	scene = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene.json"))
	actor = JSON.parse_string(FileAccess.get_file_as_string("res://art/actor.json"))
	_make_tables()
	photo_mat = $Photo.material
	actor_mat = $Actor.material
	shadow_mat = $Shadow.material
	post_mat = $Post/Grain.material
	panel_mat = $UI/Panel.material
	_setup_scene()
	_setup_actor()
	_setup_ui()
	_update()


func _make_tables() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	for i in 20 * 700:
		flick_tab.append(rng.randf_range(-1.0, 1.0))
	for i in 2 * 700:
		slow_tab.append(rng.randf_range(-1.0, 1.0))
	for i in 2 * 700:
		gust_tab.append(rng.randf_range(0.0, 1.0))
	# Kopfdrehungen: erste fest (in der Aufnahme sichtbar), danach alle 7-13 s eine für 1,5-2,6 s
	look_events.append([1.7, 2.0])
	var s := 1.7 + 2.0
	while s < 700.0:
		s += rng.randf_range(7.0, 13.0)
		var d := rng.randf_range(1.5, 2.6)
		look_events.append([s, d])
		s += d


# weich interpolierter Tabellenwert (Catmull-Rom-ähnlich über smoothstep)
func _tab(tab: PackedFloat32Array, rate: float, x: float) -> float:
	var f := x * rate
	var n := tab.size()
	var i := int(floor(f))
	var a := tab[posmod(i, n)]
	var b := tab[posmod(i + 1, n)]
	var u := f - floorf(f)
	u = u * u * (3.0 - 2.0 * u)
	return lerpf(a, b, u)


func _lantern(x: float) -> float:
	# Flamme: schnelles Zittern + langsames Atmen + gelegentliches Einknicken bei Böen
	var v := 1.0 + 0.055 * _tab(flick_tab, 20.0, x) + 0.06 * _tab(slow_tab, 2.0, x + 3.1)
	var g := _tab(gust_tab, 2.0, x + 11.0)
	v -= 0.10 * smoothstep(0.78, 0.95, g)
	return v


func _window(x: float) -> float:
	return 1.0 + 0.035 * _tab(slow_tab, 2.0, x + 40.0) + 0.02 * _tab(flick_tab, 20.0, x * 0.5 + 9.0)


func _gust(x: float) -> float:
	return 0.75 + 0.6 * _tab(gust_tab, 2.0, x)


func _look(x: float) -> float:
	if look_fixed >= 0.0:
		return look_fixed
	x = fmod(x, 700.0)   # Ablauf wiederholt sich nach 700 s
	for e in look_events:
		var s: float = e[0]
		var d: float = e[1]
		if x < s - 0.5:
			break
		if x < s + d + 0.5:
			# harter Wechsel wie ein Schnitt im Film: je ein Zwischenbild (0,5) hin und zurück, dazwischen halten;
			# in ganzen Bildern gerechnet (30 fps), damit kein Bild einen krummen Zwischenwert bekommt
			var f := roundi(x * 30.0)
			var k_in := f - roundi(s * 30.0)
			var k_out := f - roundi((s + d) * 30.0)
			return clampf(k_in * 0.5, 0.0, 1.0) * (1.0 - clampf(k_out * 0.5, 0.0, 1.0))
	return 0.0


func _vec2(a) -> Vector2:
	return Vector2(float(a[0]), float(a[1]))


func _setup_scene() -> void:
	photo_mat.set_shader_parameter("horizon_y", float(scene["horizon_y"]))
	photo_mat.set_shader_parameter("quay_y", float(scene["quay_y"]))
	photo_mat.set_shader_parameter("lamp_pos", _vec2(scene["lights"]["lamp"]))
	photo_mat.set_shader_parameter("chimney", _vec2(scene["chimney"]))
	photo_mat.set_shader_parameter("frozen", frozen)
	var piv := PackedVector2Array()
	for b in scene["boats"]:
		piv.append(_vec2(b["pivot"]))
	photo_mat.set_shader_parameter("boat_pivot", piv)
	var gp := PackedVector2Array([_vec2(scene["lights"]["window"]), _vec2(scene["lights"]["lantern"]),
		_vec2(scene["lights"]["lamp"])])
	photo_mat.set_shader_parameter("glow_pos", gp)
	photo_mat.set_shader_parameter("glow_r", PackedFloat32Array([34.0, 30.0, 16.0]))


func _setup_actor() -> void:
	var feet := Vector2(float(actor["feet_col"]), float(actor["feet_row"]))
	var size := _vec2(actor["size"])
	var pos := _vec2(actor["feet_screen"])
	# Farbtexturen in tex_scale-facher Auflösung (2x), Sprite entsprechend verkleinert; der Shader mittelt 3x3 Abtastpunkte
	var ts := float(actor.get("tex_scale", 1))
	$Actor.position = pos
	$Actor.scale = Vector2(1.0 / ts, 1.0 / ts)
	$Actor.offset = -feet * ts
	actor_mat.set_shader_parameter("tex_size", size)
	actor_mat.set_shader_parameter("tex_scale", ts)
	actor_mat.set_shader_parameter("feet_px", feet)
	actor_mat.set_shader_parameter("scarf_root", _vec2(actor["scarf_root"]))
	actor_mat.set_shader_parameter("scarf_tip", _vec2(actor["scarf_tip"]))
	var so := _vec2(actor["shadow_origin"])
	$Shadow.position = pos - Vector2(feet.x + so.x, so.y)
	if raw:
		$Actor.texture = load("res://art/actor_raw.png")
		actor_mat.set_shader_parameter("actor_tex", $Actor.texture)
		actor_mat.set_shader_parameter("integrate", false)
		shadow_mat.set_shader_parameter("enabled", false)
	if frozen:
		actor_mat.set_shader_parameter("animate", false)
	$Actor.visible = not no_actor
	$Shadow.visible = not (no_actor or no_shadow)
	post_mat.set_shader_parameter("enabled", not (raw or no_grain))


func _font(path: String, wght: float, opsz: float = 0.0, spacing: int = 0) -> FontVariation:
	var ts := TextServerManager.get_primary_interface()
	var fv := FontVariation.new()
	fv.base_font = load(path)
	var v := {ts.name_to_tag("wght"): wght}
	if opsz > 0.0:
		v[ts.name_to_tag("opsz")] = opsz
	fv.variation_opentype = v
	fv.spacing_glyph = spacing
	return fv


func _label(text: String, font: Font, size: int, col: Color, pos: Vector2) -> Label:
	var l := Label.new()
	l.text = text
	l.position = pos
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	$UI.add_child(l)
	return l


func _setup_ui() -> void:
	$UI.visible = not no_ui
	var panel: ColorRect = $UI/Panel
	panel.position = PANEL_POS
	panel.size = PANEL_SIZE
	panel_mat.set_shader_parameter("rect_pos", PANEL_POS)
	panel_mat.set_shader_parameter("rect_size", PANEL_SIZE)
	var inter_caps := _font("res://fonts/Inter-opsz-wght.ttf", 600.0, 14.0, 2)
	var inter := _font("res://fonts/Inter-opsz-wght.ttf", 430.0, 14.0)
	var inter_num := _font("res://fonts/Inter-opsz-wght.ttf", 600.0, 14.0)
	var news := _font("res://fonts/Newsreader-opsz-wght.ttf", 430.0, 20.0)
	var news_it := _font("res://fonts/Newsreader-Italic-opsz-wght.ttf", 420.0, 16.0)
	var x0 := PANEL_POS.x + 20.0
	_label(LOC.to_upper(), inter_caps, 11, Color(0.86, 0.84, 0.80, 0.82), Vector2(x0, PANEL_POS.y + 14))
	var acc := ColorRect.new()
	acc.color = Color(1.0, 0.66, 0.36, 0.9)
	acc.position = Vector2(x0, PANEL_POS.y + 35)
	acc.size = Vector2(24, 2)
	acc.mouse_filter = Control.MOUSE_FILTER_IGNORE
	$UI.add_child(acc)
	lbl_line = _label(LINE, news, 20, Color(0.96, 0.94, 0.90), Vector2(x0, PANEL_POS.y + 42))
	lbl_line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	lbl_line.custom_minimum_size = Vector2(PANEL_SIZE.x - 40.0, 0)
	lbl_line.size = Vector2(PANEL_SIZE.x - 40.0, 56)
	lbl_line.add_theme_constant_override("line_spacing", -3)
	lbl_line.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	for i in CHOICES.size():
		var y := PANEL_POS.y + 100.0 + i * 19.0
		choice_nums.append(_label(str(i + 1), inter_num, 13, Color(1.0, 0.68, 0.40, 1.0), Vector2(x0, y)))
		choice_lbls.append(_label(CHOICES[i], inter, 14, Color(0.84, 0.84, 0.82, 1.0), Vector2(x0 + 18.0, y - 1.0)))
	lbl_parser = _label(PROMPT + PARSER, news_it, 16, Color(0.80, 0.80, 0.78, 1.0), Vector2(x0, PANEL_POS.y + 157))


func _process(delta: float) -> void:
	t += delta
	frame += 1
	_update()


func _update() -> void:
	# --- Hintergrund
	var lan := _lantern(t)
	var win := _window(t)
	# Leuchtfeuer: eine Umdrehung in 9 s, zur Kamera bei t = 2,6 s (+ k * 9 s)
	var period := 9.0
	var phi := TAU * (t - 2.6) / period + PI * 0.5
	var facing: float = pow(max(sin(phi), 0.0), 10.0)
	var lamp := 0.85 + 0.55 * facing
	photo_mat.set_shader_parameter("t", t)
	photo_mat.set_shader_parameter("flick", Vector3(win, lan, lamp))
	photo_mat.set_shader_parameter("beam_phi", phi)
	var gc := PackedVector4Array([
		Vector4(1.0, 0.62, 0.30, 0.05 * win),
		Vector4(1.0, 0.60, 0.28, 0.13 * lan),
		Vector4(1.0, 0.86, 0.66, 0.08 + 0.55 * facing)])
	photo_mat.set_shader_parameter("glow_col", gc)
	var ang := PackedFloat32Array()
	var bob := PackedFloat32Array()
	for b in scene["boats"]:
		var w := TAU * t / float(b["period"]) + float(b["phase"])
		ang.append(deg_to_rad(float(b["amp_deg"])) * sin(w))
		bob.append(float(b["bob"]) * sin(w * 1.0 + 1.1))
	photo_mat.set_shader_parameter("boat_angle", ang)
	photo_mat.set_shader_parameter("boat_bob", bob)
	# --- Dachs
	actor_mat.set_shader_parameter("t", t)
	actor_mat.set_shader_parameter("lantern", lan)
	actor_mat.set_shader_parameter("gust", _gust(t))
	actor_mat.set_shader_parameter("look", _look(t))
	shadow_mat.set_shader_parameter("lantern", lan)
	post_mat.set_shader_parameter("frame", float(frame + int(t * 30.0)))
	# --- Oberfläche: Zeile tippt, Antworten erscheinen, Antwort 2 wird angewählt, Parser tippt.
	# Tippen in ganzen Bildern (30 fps): Zeile 30 Zeichen/s (1 je Bild) ab 0,2 s, fertig bei 2,3 s; Parser 15 Zeichen/s
	# (1 je 2 Bilder) ab 3,9 s, fertig bei 4,57 s; Schreibmarke 15 Bilder an, 15 aus.
	var fr := roundi(t * 30.0)
	lbl_line.visible_characters = clampi(fr - 6, 0, LINE.length())
	for i in choice_lbls.size():
		var a := smoothstep(2.4 + i * 0.12, 2.75 + i * 0.12, t)
		var sel := i == 1 and t > 3.4
		choice_lbls[i].modulate.a = a
		choice_nums[i].modulate.a = a
		choice_lbls[i].add_theme_color_override("font_color",
			Color(1.0, 0.86, 0.66) if sel else Color(0.84, 0.84, 0.82))
	var m := clampi(floori((fr - 117) * 0.5), 0, PARSER.length())
	var cursor := "|" if posmod(fr, 30) < 15 else ""
	lbl_parser.text = PROMPT + PARSER.substr(0, m) + cursor
	lbl_parser.modulate.a = smoothstep(3.6, 3.8, t)
