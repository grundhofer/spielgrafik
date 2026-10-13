extends Node2D
## Tageszeit & Wetter: ein KI-Gemälde, sechs Zustände. main.gd blendet die Zustandswerte über die Zeit
## und setzt sie auf alle Materialien (Hintergrund, Dachs, Niederschlag) und Partikel.
##
## Schalter (nach "--"): --state=N friert Zustand N ein (0 Tag .. 5 Schnee), --t0=SEK startet später,
## --no-ui blendet die Oberfläche aus, --no-badger den Dachs, --no-shadow seinen Schatten (für Messungen).

const STATE_NAMES := ["Tag", "Dämmerung", "Nacht", "Regen", "Nebel", "Schnee"]

# Zeitplan der 6-s-Aufnahme: [von, nach, Beginn, Ende] der Überblendungen; dazwischen stehen die Zustände.
const TIMELINE := [
	[0, 1, 0.45, 0.80],
	[1, 2, 1.25, 1.60],
	[2, 3, 2.05, 2.40],
	[3, 4, 3.60, 3.95],
	[4, 5, 4.50, 4.85],
]

const STATES := [
	{ # 0 Tag: gemaltes Grundbild fast unverändert
		"sky_orig": 1.0, "sky_top": Color(0.30, 0.55, 0.90), "sky_hor": Color(0.68, 0.80, 0.94),
		"cloud_lit": Color(1, 1, 1), "cloud_shade": Color(0.78, 0.82, 0.90), "cloud_vis": 1.0,
		"glow": 0.0, "glow_col": Color(1.0, 0.52, 0.22), "stars": 0.0,
		"overcast": 0.0, "overcast_col": Color(0.5, 0.5, 0.5),
		"win": 0.0, "lan": 0.0, "lamp": 0.0, "beam": 0.0,
		"fog": 0.0, "fog_col": Color(0.75, 0.80, 0.85), "wet": 0.0, "ripple": 0.0,
		"snow_cover": 0.0, "sparkle": 1.0, "water_tint": Color(1, 1, 1), "rain": 0.0, "snowfall": 0.0,
		"rain_tint": Color(0.80, 0.85, 0.92, 0.30), "snow_tint": Color(1, 1, 1, 0.9),
		"smoke": Color(0.93, 0.93, 0.93, 0.55), "shadow": 0.38, "wind": 0.5,
	},
	{ # 1 Dämmerung: Abendrot am Horizont, Lichter gehen an
		"sky_orig": 0.0, "sky_top": Color(0.16, 0.17, 0.38), "sky_hor": Color(0.93, 0.55, 0.36),
		"cloud_lit": Color(1.0, 0.62, 0.46), "cloud_shade": Color(0.34, 0.27, 0.44), "cloud_vis": 1.0,
		"glow": 0.55, "glow_col": Color(1.0, 0.50, 0.22), "stars": 0.25,
		"overcast": 0.0, "overcast_col": Color(0.3, 0.3, 0.35),
		"win": 0.75, "lan": 0.8, "lamp": 1.0, "beam": 0.6,
		"fog": 0.0, "fog_col": Color(0.45, 0.40, 0.50), "wet": 0.0, "ripple": 0.0,
		"snow_cover": 0.0, "sparkle": 0.12, "water_tint": Color(1, 1, 1), "rain": 0.0, "snowfall": 0.0,
		"rain_tint": Color(0.70, 0.62, 0.70, 0.30), "snow_tint": Color(0.9, 0.85, 0.9, 0.9),
		"smoke": Color(0.52, 0.48, 0.60, 0.50), "shadow": 0.20, "wind": 0.45,
	},
	{ # 2 Nacht: Nacht-LUT und Lichtbild aus dem KI-Nachtschlüssel, Sterne, Strahl
		"sky_orig": 0.0, "sky_top": Color(0.015, 0.07, 0.22), "sky_hor": Color(0.05, 0.16, 0.36),
		"cloud_lit": Color(0.13, 0.20, 0.37), "cloud_shade": Color(0.06, 0.10, 0.24), "cloud_vis": 1.0,
		"glow": 0.0, "glow_col": Color(1.0, 0.50, 0.22), "stars": 1.0,
		"overcast": 0.0, "overcast_col": Color(0.1, 0.12, 0.18),
		"win": 1.0, "lan": 1.0, "lamp": 1.0, "beam": 1.0,
		"fog": 0.0, "fog_col": Color(0.10, 0.13, 0.20), "wet": 0.0, "ripple": 0.0,
		"snow_cover": 0.0, "sparkle": 0.0, "water_tint": Color(1, 1, 1), "rain": 0.0, "snowfall": 0.0,
		"rain_tint": Color(0.60, 0.68, 0.85, 0.36), "snow_tint": Color(0.75, 0.8, 0.95, 0.9),
		"smoke": Color(0.27, 0.31, 0.45, 0.45), "shadow": 0.12, "wind": 0.4,
	},
	{ # 3 Regen (nachts): Wolkendecke, Nässe, Ringe, zwei Regenebenen, Spritzer, Blitz
		"sky_orig": 0.0, "sky_top": Color(0.05, 0.07, 0.11), "sky_hor": Color(0.09, 0.11, 0.15),
		"cloud_lit": Color(0.12, 0.14, 0.18), "cloud_shade": Color(0.06, 0.07, 0.10), "cloud_vis": 1.0,
		"glow": 0.0, "glow_col": Color(1.0, 0.50, 0.22), "stars": 0.0,
		"overcast": 1.0, "overcast_col": Color(0.085, 0.10, 0.14),
		"win": 1.0, "lan": 1.1, "lamp": 1.0, "beam": 0.85,
		"fog": 0.22, "fog_col": Color(0.10, 0.12, 0.16), "wet": 1.0, "ripple": 1.0,
		"snow_cover": 0.0, "sparkle": 0.0, "water_tint": Color(0.85, 0.9, 0.92), "rain": 1.0, "snowfall": 0.0,
		"rain_tint": Color(0.60, 0.68, 0.84, 0.55), "snow_tint": Color(0.75, 0.8, 0.95, 0.9),
		"smoke": Color(0.20, 0.22, 0.27, 0.30), "shadow": 0.10, "wind": 1.0,
	},
	{ # 4 Nebel (Morgen): Tiefennebel aus der KI-Tiefenkarte, Strahl im Dunst
		"sky_orig": 0.0, "sky_top": Color(0.55, 0.59, 0.64), "sky_hor": Color(0.64, 0.68, 0.72),
		"cloud_lit": Color(0.70, 0.73, 0.76), "cloud_shade": Color(0.58, 0.61, 0.66), "cloud_vis": 1.0,
		"glow": 0.0, "glow_col": Color(1.0, 0.50, 0.22), "stars": 0.0,
		"overcast": 1.0, "overcast_col": Color(0.58, 0.62, 0.66),
		"win": 0.55, "lan": 0.85, "lamp": 1.0, "beam": 1.0,
		"fog": 1.0, "fog_col": Color(0.60, 0.64, 0.68), "wet": 0.3, "ripple": 0.0,
		"snow_cover": 0.0, "sparkle": 0.0, "water_tint": Color(0.92, 0.95, 0.96), "rain": 0.0, "snowfall": 0.0,
		"rain_tint": Color(0.80, 0.82, 0.86, 0.25), "snow_tint": Color(0.9, 0.92, 0.95, 0.9),
		"smoke": Color(0.70, 0.72, 0.75, 0.22), "shadow": 0.06, "wind": 0.15,
	},
	{ # 5 Schnee (später Nachmittag): Schneeschicht aus dem KI-Schneeschlüssel wächst, zwei Flockenebenen
		"sky_orig": 0.0, "sky_top": Color(0.60, 0.64, 0.72), "sky_hor": Color(0.74, 0.77, 0.83),
		"cloud_lit": Color(0.80, 0.83, 0.88), "cloud_shade": Color(0.62, 0.66, 0.74), "cloud_vis": 1.0,
		"glow": 0.0, "glow_col": Color(1.0, 0.50, 0.22), "stars": 0.0,
		"overcast": 1.0, "overcast_col": Color(0.66, 0.70, 0.77),
		"win": 0.8, "lan": 0.9, "lamp": 0.8, "beam": 0.35,
		"fog": 0.28, "fog_col": Color(0.74, 0.78, 0.85), "wet": 0.0, "ripple": 0.0,
		"snow_cover": 1.0, "sparkle": 0.0, "water_tint": Color(0.66, 0.74, 0.78), "rain": 0.0, "snowfall": 1.0,
		"rain_tint": Color(0.80, 0.82, 0.86, 0.25), "snow_tint": Color(0.97, 0.98, 1.0, 0.92),
		"smoke": Color(0.78, 0.80, 0.86, 0.50), "shadow": 0.18, "wind": 0.6,
	},
]

@onready var bg: Sprite2D = $BG
@onready var badger: Sprite2D = $Badger
@onready var shadow: Sprite2D = $Shadow
@onready var smoke: GPUParticles2D = $Smoke
@onready var rain_far: GPUParticles2D = $RainFar
@onready var rain_near: GPUParticles2D = $RainNear
@onready var splash: GPUParticles2D = $Splash
@onready var snow_far: GPUParticles2D = $SnowFar
@onready var snow_near: GPUParticles2D = $SnowNear

var t := 0.0
var frozen := -1
var scene_data := {}
var badger_data := {}
var flicker_l: PackedFloat32Array
var flicker_w: PackedFloat32Array
var gust: PackedFloat32Array
var mats: Array[ShaderMaterial] = []
var precip: Array[ShaderMaterial] = []
var ui_line: Label
var ui_parser: Label
var ui_states: Array[Label] = []
var ui_marker: ColorRect
var line_text := ""


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--state="):
			frozen = int(a.get_slice("=", 1))
		elif a.begins_with("--t0="):
			t = float(a.get_slice("=", 1))
		elif a == "--no-badger":
			badger.visible = false
		elif a == "--no-shadow":
			shadow.visible = false
	scene_data = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene.json"))
	badger_data = JSON.parse_string(FileAccess.get_file_as_string("res://art/badger.json"))
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261011
	flicker_l = PackedFloat32Array()
	flicker_w = PackedFloat32Array()
	gust = PackedFloat32Array()
	for i in 4096:
		flicker_l.append(rng.randf())
		flicker_w.append(rng.randf())
		gust.append(rng.randf())

	mats = [bg.material as ShaderMaterial, badger.material as ShaderMaterial]
	precip = [rain_far.material as ShaderMaterial, rain_near.material as ShaderMaterial,
		splash.material as ShaderMaterial, snow_far.material as ShaderMaterial, snow_near.material as ShaderMaterial]

	var bm := bg.material as ShaderMaterial
	bm.set_shader_parameter("horizon_y", scene_data["horizon_y"])
	bm.set_shader_parameter("window_pos", _v2(scene_data["window"]))
	bm.set_shader_parameter("lantern_pos", _v2(scene_data["lantern"]))
	bm.set_shader_parameter("lamp_pos", _v2(scene_data["lamp"]))
	for m in precip:
		m.set_shader_parameter("lantern_pos", _v2(scene_data["lantern"]))
		m.set_shader_parameter("window_pos", _v2(scene_data["window"]))
	(snow_far.material as ShaderMaterial).set_shader_parameter("sway_amp", 14.0)
	(snow_near.material as ShaderMaterial).set_shader_parameter("sway_amp", 22.0)

	var feet := _v2(scene_data["badger_feet"])
	var size := _v2(badger_data["size"])
	badger.position = feet.round()
	badger.offset = Vector2(-round(size.x * 0.5), -round(badger_data["feet_y"]))
	shadow.position = feet + Vector2(0, -2)
	var dm := badger.material as ShaderMaterial
	dm.set_shader_parameter("tex_size", size)
	dm.set_shader_parameter("feet_y", badger_data["feet_y"])
	dm.set_shader_parameter("scarf_root_y", badger_data["scarf_root_y"])
	dm.set_shader_parameter("scarf_tip_y", badger_data["scarf_tip_y"])
	var irr: Array = scene_data["badger_irradiance"]
	dm.set_shader_parameter("irr", Vector3(irr[0], irr[1], irr[2]))
	smoke.position = _v2(scene_data["chimney"]) + Vector2(0, 4)

	if not "--no-ui" in OS.get_cmdline_user_args():
		_build_ui()
	_apply(t)


func _v2(a) -> Vector2:
	return Vector2(float(a[0]), float(a[1]))


func _process(delta: float) -> void:
	t += delta
	_apply(t)


# Glatte Tabellenwerte (linear zwischen Stützstellen, Rate in Hz)
func _table(tab: PackedFloat32Array, x: float, rate: float) -> float:
	var p := x * rate
	var i := int(floor(p))
	var f := p - i
	f = f * f * (3.0 - 2.0 * f)
	return lerp(tab[i % tab.size()], tab[(i + 1) % tab.size()], f)


func _state_at(time: float) -> Array:
	# -> [a, b, mix]
	if frozen >= 0:
		return [frozen, frozen, 0.0]
	var cur := 0
	for seg in TIMELINE:
		if time < seg[2]:
			return [seg[0], seg[0], 0.0]
		if time < seg[3]:
			var s: float = (time - seg[2]) / (seg[3] - seg[2])
			return [seg[0], seg[1], s * s * (3.0 - 2.0 * s)]
		cur = seg[1]
	return [cur, cur, 0.0]


func _mixv(a: Dictionary, b: Dictionary, k: String, s: float):
	var va = a[k]
	var vb = b[k]
	if va is Color:
		return (va as Color).lerp(vb, s)
	return lerp(float(va), float(vb), s)


func _apply(time: float) -> void:
	var st := _state_at(time)
	var A: Dictionary = STATES[st[0]]
	var B: Dictionary = STATES[st[1]]
	var s: float = st[2]
	var v := {}
	for k in A.keys():
		v[k] = _mixv(A, B, k, s)
	# Lichter gehen nacheinander an (Fenster, Laterne mit kurzem Zünden, Leuchtfeuer)
	for lk in [["win", 0.0, 0.45], ["lan", 0.3, 0.7], ["lamp", 0.55, 0.95], ["beam", 0.6, 1.0]]:
		if float(B[lk[0]]) > float(A[lk[0]]) + 0.2:
			var ss := smoothstep(lk[1], lk[2], s)
			if lk[0] == "lan" and ss > 0.0 and ss < 1.0:
				ss *= 0.55 + 0.45 * _table(flicker_l, time + 7.0, 30.0)
			v[lk[0]] = lerp(float(A[lk[0]]), float(B[lk[0]]), ss)
	# Nebel zieht von See her herein (fern zuerst); beim Abziehen nur dünner
	var front := 1.0
	if float(B["fog"]) > float(A["fog"]) + 0.3:
		front = s

	# Lichter mit Flackern (Laterne schnell, Fenster ruhig), Leuchtturm dreht (Periode 9 s)
	var fl := 0.80 + 0.20 * _table(flicker_l, time, 11.0) + 0.06 * (_table(flicker_l, time + 50.0, 23.0) - 0.5)
	var fw := 0.94 + 0.06 * _table(flicker_w, time, 3.0)
	var light := Vector3(v["win"] * fw, v["lan"] * fl, v["lamp"])
	var phi := deg_to_rad(68.0) + TAU * time / 9.0
	var flash := 0.0
	if v["rain"] > 0.5 and frozen < 0:
		flash = _pulse(time, 3.02, 0.05) + 0.6 * _pulse(time, 3.18, 0.04)
	var wind: float = v["wind"] * (0.75 + 0.5 * _table(gust, time, 1.3))

	var p := {
		"lut_a": float(st[0]), "lut_b": float(st[1]), "lut_mix": s, "time": time,
		"fog": v["fog"], "fog_col": _c3(v["fog_col"]), "flash": flash, "fog_front": front,
	}
	for m in mats:
		for k in p:
			m.set_shader_parameter(k, p[k])

	var bm := bg.material as ShaderMaterial
	for k in ["sky_orig", "cloud_vis", "glow", "stars", "overcast", "beam", "wet", "ripple", "snow_cover", "sparkle"]:
		bm.set_shader_parameter(k, v[k])
	for k in ["sky_top", "sky_hor", "cloud_lit", "cloud_shade", "glow_col", "overcast_col", "water_tint"]:
		bm.set_shader_parameter(k, _c3(v[k]))
	bm.set_shader_parameter("light_mul", light)
	bm.set_shader_parameter("beam_phi", phi)
	# Wolken pendeln (±40 px, 30 s) statt linear zu ziehen: in den ersten Sekunden wie 8 px/s, aber im
	# Dauerbetrieb kommen die aufgefüllten Plattenbereiche unter Häuschen und Masten nie ins Bild
	bm.set_shader_parameter("cloud_drift", -40.0 * sin(TAU * time / 30.0))

	# Dachs: Atmen (3 s), Gewicht (5,3 s), Schal im Wind, Blinzeln
	var dm := badger.material as ShaderMaterial
	dm.set_shader_parameter("breath", sin(TAU * time / 3.0))
	dm.set_shader_parameter("sway", 0.9 * sin(TAU * time / 5.3 + 1.0))
	dm.set_shader_parameter("scarf_off", wind * (2.2 + 1.3 * sin(time * 2.6) + 0.7 * sin(time * 5.9 + 1.0)))
	dm.set_shader_parameter("blink", _blink(time))
	dm.set_shader_parameter("lantern_i", light.y)
	dm.set_shader_parameter("wet", v["rain"])
	shadow.modulate = Color(0, 0, 0, v["shadow"])

	# Niederschlag und Rauch
	_set_precip(rain_far, v["rain"], _scale_a(v["rain_tint"], 0.7), light, flash)
	_set_precip(rain_near, v["rain"], v["rain_tint"], light, flash)
	_set_precip(splash, v["rain"], _scale_a(v["rain_tint"], 1.4), light, flash)
	_set_precip(snow_far, v["snowfall"], _scale_a(v["snow_tint"], 0.7), light, 0.0)
	_set_precip(snow_near, v["snowfall"], v["snow_tint"], light, 0.0)
	smoke.modulate = v["smoke"]

	_update_ui(time, st, s)


func _set_precip(n: GPUParticles2D, density: float, tint: Color, light: Vector3, flash: float) -> void:
	var m := n.material as ShaderMaterial
	m.set_shader_parameter("density", density)
	m.set_shader_parameter("tint", tint)
	m.set_shader_parameter("lantern_i", light.y)
	m.set_shader_parameter("window_i", light.x)
	m.set_shader_parameter("flash", flash)
	m.set_shader_parameter("time", t)


func _scale_a(c: Color, k: float) -> Color:
	return Color(c.r, c.g, c.b, clamp(c.a * k, 0.0, 1.0))


func _c3(c: Color) -> Vector3:
	return Vector3(c.r, c.g, c.b)


func _pulse(time: float, at: float, w: float) -> float:
	var d := (time - at) / w
	if d < -1.0 or d > 3.0:
		return 0.0
	return exp(-d * d) if d < 0.0 else exp(-d)


func _blink(time: float) -> float:
	# geschlossen für 2 Bilder, je 1 Bild halb (30 fps); Zeitpunkte fest, danach alle 4,1 s
	var starts := [1.35, 3.85, 5.45]
	var x := time
	if time > 6.0:
		x = 6.0 + fmod(time - 6.0, 4.1)
		starts = [6.9]
	for b in starts:
		var d: float = x - b
		if d >= 0.0 and d < 0.0334:
			return 0.5
		if d >= 0.0334 and d < 0.1:
			return 1.0
		if d >= 0.1 and d < 0.1334:
			return 0.5
	return 0.0


# ---------------------------------------------------------------- Oberfläche
func _font(weight: int) -> FontVariation:
	var f := FontVariation.new()
	f.base_font = load("res://fonts/Nunito-wght.ttf")
	# Schlüssel als OpenType-Tag (int); der String "wght" wird in Godot 4.7 stillschweigend ignoriert
	f.variation_opentype = {TextServerManager.get_primary_interface().name_to_tag("wght"): weight}
	return f


func _label(parent: Node, text: String, font: Font, size: int, col: Color, pos: Vector2) -> Label:
	var l := Label.new()
	l.text = text
	l.position = pos
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.55))
	l.add_theme_constant_override("shadow_offset_x", 1)
	l.add_theme_constant_override("shadow_offset_y", 2)
	parent.add_child(l)
	return l


func _panel(parent: Node, rect: Rect2) -> Panel:
	var p := Panel.new()
	p.position = rect.position
	p.size = rect.size
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.06, 0.055, 0.08, 0.80)
	sb.border_color = Color(0.93, 0.78, 0.48, 0.85)
	sb.set_border_width_all(2)
	sb.set_corner_radius_all(12)
	sb.shadow_color = Color(0, 0, 0, 0.35)
	sb.shadow_size = 6
	sb.shadow_offset = Vector2(0, 3)
	p.add_theme_stylebox_override("panel", sb)
	parent.add_child(p)
	return p


func _build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var bold := _font(800)
	var semi := _font(600)
	var reg := _font(500)
	var cream := Color(0.98, 0.95, 0.88)
	var gold := Color(1.0, 0.80, 0.42)

	# Textfeld unten rechts
	var box := _panel(layer, Rect2(652, 548, 612, 158))
	_label(box, "Hafen von Lornholm", bold, 21, gold, Vector2(20, 9))
	var rule := ColorRect.new()
	rule.color = Color(0.93, 0.78, 0.48, 0.45)
	rule.position = Vector2(20, 39)
	rule.size = Vector2(572, 1)
	box.add_child(rule)
	line_text = "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
	ui_line = _label(box, line_text, semi, 18, cream, Vector2(20, 44))
	ui_line.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	var choices := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
	for i in choices.size():
		var y := 72 + i * 22
		var hl := i == 1
		_label(box, str(i + 1) + ".", bold, 17, gold if hl else Color(0.85, 0.80, 0.70), Vector2(24, y))
		_label(box, choices[i], semi if hl else reg, 17, gold if hl else Color(0.90, 0.87, 0.80), Vector2(46, y))
	ui_parser = _label(box, "> nimm paket", semi, 17, Color(0.75, 0.88, 0.95), Vector2(400, 116))

	# Zustandsleiste oben rechts (zeigt, welcher Zustand gerade gilt; links oben steht der Schornstein)
	var bar := _panel(layer, Rect2(0, 14, 100, 36))
	var x := 16.0
	for i in STATE_NAMES.size():
		var l := _label(bar, STATE_NAMES[i], bold, 16, Color(0.75, 0.72, 0.66), Vector2(x, 6))
		ui_states.append(l)
		x += bold.get_string_size(STATE_NAMES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x + 22.0
	bar.size.x = x - 22.0 + 16.0
	bar.position.x = 1264.0 - bar.size.x
	ui_marker = ColorRect.new()
	ui_marker.color = gold
	ui_marker.size = Vector2(30, 2)
	ui_marker.position = Vector2(16, 29)
	bar.add_child(ui_marker)


func _update_ui(time: float, st: Array, s: float) -> void:
	if ui_line == null:
		return
	ui_line.visible_characters = int(clamp(time / 1.4, 0.0, 1.0) * line_text.length()) if frozen < 0 else -1
	ui_parser.text = "> nimm paket" + ("_" if fmod(time, 1.0) < 0.55 else " ")
	var a: int = st[0]
	var b: int = st[1]
	for i in ui_states.size():
		var w := 0.0
		if i == a:
			w = 1.0 - s
		if i == b:
			w = max(w, s)
		ui_states[i].add_theme_color_override("font_color",
			Color(0.62, 0.60, 0.56).lerp(Color(1.0, 0.82, 0.45), w))
	var la := ui_states[a]
	var lb := ui_states[b]
	var x0 := la.position.x
	var x1 := lb.position.x
	var w0 := la.get_theme_font("font").get_string_size(la.text, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x
	var w1 := lb.get_theme_font("font").get_string_size(lb.text, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x
	ui_marker.position.x = lerp(x0, x1, s)
	ui_marker.size.x = lerp(w0, w1, s)
