extends Node2D
## Isometrisches Rollenspiel mit vorgerenderter Szene: Hafen von Lornholm.
##
## Die Karte ist ein Blender-Rendering (640×480, 256 Farben), der Dachs ein vorgerendertes Sprite-Blatt derselben
## Kamera. Licht, Verdeckung und Schatten rechnen map.gdshader und badger.gdshader aus Palettenindex, Tiefenbild
## und Lichttabelle. Zeit wird über delta aufsummiert; Zufall nur aus RandomNumberGenerator mit festem Seed.
##
## Benutzerargumente (nach "--"): --t0=<s> Startzeit, --noocc ohne Verdeckung, --noshadow, --noui,
## --nolight (heller), --noring, --nobadger (Figur, Schatten, Ring aus; für Differenzmessungen),
## --pose=<frame>@<x>,<z> Dachs fest an eine Weltstelle (Prüfbilder).

const FPS := 30
const WALK_CYCLES := 7
const SPRITE_STEP := 2          # Laufbilder auf Zweien: 15 Bilder/s
const T_STAND := 112            # Aufnahmebild: Halt
const T_TURN := 122             # Drehung zur Kamera
const T_WAVE := 132             # Winken (10 Bilder/s, 15 Bilder)
const T_IDLE := 177

var data: Dictionary
var t := 0.0
var args := {}
var map_mat: ShaderMaterial
var bad_mat: ShaderMaterial
var water: Array[Texture2D] = []
var beam: Array[Texture2D] = []
var rng := RandomNumberGenerator.new()
var flicker := 1.0
var flicker_step := -1

var cam_o: Vector3
var ax_r: Vector3
var ax_u: Vector3
var ax_d: Vector3
var pxm: float
var map_size: Vector2
var view_row: int
var cell: Vector2i
var anchor: Vector2i
var start_px: Vector2i
var cyc: Vector2i
var halt_back := Vector2i(2, 1)     # Halt: Stehbild so, dass der zuletzt aufgesetzte Fuß stehen bleibt (gemessen)
var frames: Dictionary
var lantern: Vector3
var window_light: Vector3
var lamp: Vector3

var log_text: Label
var parser_label: Label
var cursor_label: Label
var log_full := ""


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	t = float(args.get("t0", "0"))
	rng.seed = 20261013
	data = JSON.parse_string(FileAccess.get_file_as_string("res://data/bake.json"))
	var sc: Dictionary = data["scene"]
	view_row = int(sc["map"]["view_row"])
	map_size = Vector2(data["map_size"][0], data["map_size"][1])
	pxm = float(data["px_per_m"])
	cam_o = _v3(data["cam_location"])
	ax_r = _v3(data["R"])
	ax_u = _v3(data["U"])
	ax_d = _v3(data["D"])
	var b: Dictionary = data["badger"]
	cell = Vector2i(b["cell"][0], b["cell"][1])
	anchor = Vector2i(b["anchor"][0], b["anchor"][1])
	frames = b["frames"]
	var c: Array = b["cycle_px"]["SE"]
	cyc = Vector2i(roundi(c[0]), roundi(c[1]))
	var p0: Array = sc["badger_path"]["start"]
	var m := world_to_map(_gb(Vector3(p0[0], p0[1], p0[2])))
	start_px = Vector2i(roundi(m.x), roundi(m.y))
	lantern = _gb(_v3(data["lantern"]))
	window_light = _gb(_v3(data["window"])) + Vector3(0, -0.6, 0)
	lamp = _gb(_v3(data["lighthouse_light"]))

	for i in int(data["water_frames"]):
		water.append(load("res://art/water/w_%02d.png" % i))
	for i in int(data["beam_frames"]):
		beam.append(load("res://art/beam/b_%02d.png" % i))

	$World.position = Vector2(0, -view_row)
	map_mat = $World/Map.material
	bad_mat = $World/Badger.material
	var lut: Texture2D = load("res://art/lut.png")
	var depth: Texture2D = load("res://art/depth.png")
	var levels := PackedFloat32Array()
	for v in data["levels"]:
		levels.append(float(v))
	for mat: ShaderMaterial in [map_mat, bad_mat]:
		mat.set_shader_parameter("depth_tex", depth)
		mat.set_shader_parameter("lut_tex", lut)
		mat.set_shader_parameter("cam_o", cam_o)
		mat.set_shader_parameter("ax_r", ax_r)
		mat.set_shader_parameter("ax_u", ax_u)
		mat.set_shader_parameter("ax_d", ax_d)
		mat.set_shader_parameter("pxm", pxm)
		mat.set_shader_parameter("map_size", map_size)
		mat.set_shader_parameter("d0", float(data["depth_d0"]))
		mat.set_shader_parameter("d1", float(data["depth_d1"]))
		mat.set_shader_parameter("levels", levels)
		mat.set_shader_parameter("ambient", 0.33)
	map_mat.set_shader_parameter("badger_tex", $World/Badger.texture)
	map_mat.set_shader_parameter("water_mask", load("res://art/water_mask.png"))
	var wr: Array = data["water_rect"]
	map_mat.set_shader_parameter("water_rect", Vector4i(wr[0], wr[1], wr[2], wr[3]))
	map_mat.set_shader_parameter("cell_size", cell)
	map_mat.set_shader_parameter("shadow_on", not (args.has("noshadow") or args.has("nobadger")))
	map_mat.set_shader_parameter("ring_on", not (args.has("noring") or args.has("nobadger")))
	map_mat.set_shader_parameter("ring_idx", int(data["ring_idx"]))
	$World/Badger.visible = not args.has("nobadger")
	bad_mat.set_shader_parameter("zrange", float(b["depth_range_m"]))
	bad_mat.set_shader_parameter("occlusion_on", not args.has("noocc"))
	if args.has("nolight"):
		for mat: ShaderMaterial in [map_mat, bad_mat]:
			mat.set_shader_parameter("ambient", 1.0)
	if not args.has("noui"):
		_build_ui()
	_update(0.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)


## Kartenpixel (Ecken-Koordinaten) eines Blender-Weltpunkts
func world_to_map(p: Vector3) -> Vector2:
	var q := p - cam_o
	return Vector2(q.dot(ax_r) * pxm + map_size.x * 0.5, -q.dot(ax_u) * pxm + map_size.y * 0.5)


## Bodenpunkt (z = 0) unter einem Kartenpunkt und seine Tiefe entlang der Blickachse
func ground_at(pc: Vector2) -> Array:
	var o := cam_o + (pc.x - map_size.x * 0.5) / pxm * ax_r - (pc.y - map_size.y * 0.5) / pxm * ax_u
	var d := -o.z / ax_d.z
	return [o + d * ax_d, d]


func _update(_delta: float) -> void:
	var n := int(floor(t * FPS + 0.5))
	# Wasser 10 Bilder/s, Strahl 15 Bilder/s
	map_mat.set_shader_parameter("water_tex", water[(n / 3) % water.size()])
	map_mat.set_shader_parameter("beam_tex", beam[(n / 2) % beam.size()])
	# Laterne: neue Helligkeit alle 3 Aufnahmebilder, in Stufen
	var fs := n / 3
	if fs != flicker_step:
		flicker_step = fs
		rng.seed = 7919 * fs + 20261013
		flicker = 0.72 + 0.28 * rng.randf()
	_update_badger(n)


func _update_badger(n: int) -> void:
	var name := ""
	var org := start_px
	var light_px := Vector2(start_px)
	if args.has("pose"):
		var spec: PackedStringArray = args["pose"].split("@")
		name = spec[0]
		var xz := spec[1].split(",")
		var m := world_to_map(_gb(Vector3(float(xz[0]), 0.0, float(xz[1]))))
		org = Vector2i(roundi(m.x), roundi(m.y))
		light_px = Vector2(org)
	elif n < T_STAND:
		var j := n / SPRITE_STEP
		name = "walk_SE_%d" % (j % 8)
		org = start_px + cyc * (j / 8)
		light_px = Vector2(start_px) + Vector2(cyc) * (float(j) / 8.0)
	else:
		org = start_px + cyc * WALK_CYCLES - halt_back
		light_px = Vector2(org)
		if n < T_TURN:
			name = "stand_SE"
		elif n < T_WAVE:
			name = "idle_S_%02d" % (((n - T_TURN) / 5) % 12)
		elif n < T_IDLE:
			name = "wave_S_%02d" % ((n - T_WAVE) / 3)
		else:
			name = "idle_S_%02d" % (((n - T_IDLE) / 5 + 2) % 12)
	var fp: Array = frames[name]
	var sheet := Vector2i(fp[0], fp[1])
	var cell_org := org - anchor
	var spr: Sprite2D = $World/Badger
	spr.region_rect = Rect2(Vector2(sheet), Vector2(cell))
	spr.position = Vector2(cell_org)
	var g: Array = ground_at(Vector2(org))
	bad_mat.set_shader_parameter("map_origin", cell_org)
	bad_mat.set_shader_parameter("sheet_origin", sheet)
	bad_mat.set_shader_parameter("d_anchor", float(g[1]))
	map_mat.set_shader_parameter("sh_map_origin", cell_org)
	map_mat.set_shader_parameter("sh_sheet_origin", sheet)
	map_mat.set_shader_parameter("ring_c", Vector2(roundi(light_px.x), roundi(light_px.y)))
	# Lichter: Dachs (wandert mit), Laterne (flackert), Fenster, Leuchtfeuer
	var bl: Vector3 = ground_at(light_px)[0] + Vector3(0, 0, 1.0)
	var lights := PackedVector4Array([
		Vector4(bl.x, bl.y, bl.z, 2.7),
		Vector4(lantern.x, lantern.y, lantern.z, 3.8),
		Vector4(window_light.x, window_light.y, window_light.z, 2.4),
		Vector4(lamp.x, lamp.y, lamp.z, 2.6),
		Vector4(0, 0, 0, 0),
		Vector4(0, 0, 0, 0)])
	var ints := PackedFloat32Array([0.75, 1.0 * flicker, 0.5, 0.8, 0.0, 0.0])
	for mat: ShaderMaterial in [map_mat, bad_mat]:
		mat.set_shader_parameter("lights", lights)
		mat.set_shader_parameter("light_int", ints)
	if log_text:
		_update_ui(n)


# --------------------------------------------------------------------------------------------
# Bedienleiste
# --------------------------------------------------------------------------------------------
func _font(path: String, weight := 0) -> Font:
	var f: FontFile = load(path)
	f.hinting = TextServer.HINTING_NORMAL
	f.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	f.antialiasing = TextServer.FONT_ANTIALIASING_GRAY
	# Bei 13 px ohne Subpixel-Lage rundet Alegreya das Leerzeichen auf 1–2 px: Wortabstand um 2 px erweitern
	var v := FontVariation.new()
	v.base_font = f
	v.spacing_space = 2
	if weight > 0:
		v.variation_opentype = {TextServerManager.get_primary_interface().name_to_tag("wght"): weight}
	return v


func _label(text: String, font: Font, size: int, color: Color, pos: Vector2, width := 0.0) -> Label:
	var l := Label.new()
	var ls := LabelSettings.new()
	ls.font = font
	ls.font_size = size
	ls.font_color = color
	ls.shadow_color = Color(0, 0, 0, 0.85)
	ls.shadow_offset = Vector2(1, 1)
	ls.shadow_size = 0
	ls.line_spacing = -2
	l.label_settings = ls
	if width > 0:
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.custom_minimum_size = Vector2(width, 0)
		l.size = Vector2(width, 32)
	l.text = text
	l.position = pos
	$UI.add_child(l)
	return l


func _build_ui() -> void:
	var ui: Dictionary = data["ui"]
	var top := 360 - int(ui["size"][1])
	var bar := TextureRect.new()
	bar.texture = load("res://art/bar.png")
	bar.position = Vector2(0, top)
	$UI.add_child(bar)
	var pr: Array = ui["portrait"]
	var por := TextureRect.new()
	por.texture = load("res://art/portrait.png")
	por.position = Vector2(pr[0], top + pr[1])
	$UI.add_child(por)
	var lg: Array = ui["log"]
	var serif := _font("res://fonts/Alegreya-wght.ttf", 500)
	var caps := _font("res://fonts/AlegreyaSC-Medium.ttf")
	var x0 := float(lg[0]) + 6
	var y0 := float(top + lg[1])
	_label("Hafen von Lornholm", caps, 13, Color("e2b65c"), Vector2(x0, y0 + 1))
	log_full = "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
	log_text = _label(log_full, serif, 13, Color("d9ceb2"), Vector2(x0, y0 + 16), float(lg[2] - lg[0]) - 12)
	parser_label = _label("> nimm paket", serif, 13, Color("a9c7d8"), Vector2(x0, y0 + 48))
	cursor_label = _label("_", serif, 13, Color("a9c7d8"), Vector2(x0 + 66, y0 + 48))
	var choices := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
	var btns: Array = ui["buttons"]
	for i in 3:
		var bt: Array = btns[i]
		var hot := i == 1
		var col := Color("f0c66a") if hot else Color("cfc3a6")
		_label(choices[i], serif, 13, col, Vector2(float(bt[0]) + 10, top + float(bt[1]) + 1))
		if hot:
			var fr := ReferenceRect.new()
			fr.border_color = Color("d9a948")
			fr.border_width = 1
			fr.editor_only = false
			fr.position = Vector2(float(bt[0]) - 1, top + float(bt[1]) - 1)
			fr.size = Vector2(float(bt[2] - bt[0]) + 2, float(bt[3] - bt[1]) + 2)
			$UI.add_child(fr)


func _update_ui(n: int) -> void:
	# Schreibmaschine: 40 Zeichen/s ab 0,2 s, Parserzeile danach mit blinkendem Cursor
	var shown := clampi(int((t - 0.2) * 40.0), 0, log_full.length())
	log_text.visible_characters = shown
	parser_label.visible = shown >= log_full.length()
	cursor_label.visible = parser_label.visible and (n / 12) % 2 == 0
	cursor_label.position.x = parser_label.position.x + parser_label.get_minimum_size().x


func _v3(a: Array) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))


## Godot-Achsen (x, y, z) -> Blender-Achsen (x, -z, y)
func _gb(v: Vector3) -> Vector3:
	return Vector3(v.x, -v.z, v.y)
