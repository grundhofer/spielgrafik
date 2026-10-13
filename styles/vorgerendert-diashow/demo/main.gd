extends Node2D
## Vorgerenderte Ich-Perspektive (Standbild-Erkundung, CD-ROM-Spiele 1993–1997).
##
## Drei Knoten (Kai, Steg, Leuchtturmtür) sind fertige Blender-Bilder mit 544×332 Bildpunkten und 256 Farben
## (nodes/<knoten>/base.png). Bewegung kommt nur aus kleinen eingebetteten Bildfolgen (clip_*.png, 15 Bilder/s,
## 2-s-Schleife) und dem vorgerenderten Dachs-Clip (steg/badger.png), alle aus derselben Palette. Godot setzt die
## Ausschnitte nur übereinander; jeder Knoten wird in einem eigenen SubViewport zusammengesetzt, das Bild auf dem
## Schirm mischt höchstens zwei Knoten (shaders/compose.gdshader). Zum Schluss rastet shaders/palette_snap.gdshader
## den Bildschirm auf Palettenfarben ein (8-Bit-Anzeige): das Bild auf die 256 Farben, das Textband darunter nur auf
## die 12 Textfarben (Schwarz, Textrampe, Gold), damit die geglättete Schrift keine Szenenfarben als Säume bekommt.
##
## Ablauf der 6 s (deterministisch, Zeit = aufsummiertes delta, keine Zufallswerte):
##   0,00–1,50  Kai: Rauch, Fensterlicht, Wasser. Der Zeiger fährt an den rechten Rand und wird zur Drehhand.
##   1,50–1,95  Drehung nach rechts als Pixel-Auflösung zum Steg.
##   1,95–5,40  Steg: Der Dachs kommt den Steg entlang, bleibt stehen, dreht sich zur Kamera und winkt
##              (Clip ab 1,40 s). Leuchtfeuer blitzt, Laterne flackert, Wasser und Boote bewegen sich.
##              Der Zeiger wird über dem Dachs zur offenen Hand.
##   5,40–5,72  Klick auf die Leuchtturmtür: schneller Zoom ins alte Bild, dann Auflösung.
##   5,72–6,00  Leuchtturmtür.

const IMG_SIZE := Vector2i(544, 332)
const IMG_POS := Vector2(48, 2)          # Bild schwarz eingebettet; capture.py skaliert 640×360 ×2 auf 1280×720
const CLIP_FPS := 15.0
const EPS := 1e-4

const T_BADGER := 1.40                   # Start des Dachs-Clips (er läuft schon, wenn der Steg erscheint)
const DISSOLVE := [1.50, 1.95]           # Kai -> Steg
const ZOOM := [5.40, 5.72]               # Steg -> Leuchtturmtür
const ZOOM_CENTER := Vector2(316, 150)   # Tür im Steg-Bild (Projektion von (9,4 | 5,0 | −25,6), gerundet)
const ZOOM_MAX := 3.0
const ZOOM_DISSOLVE_FROM := 0.35         # Anteil der Zoomzeit, ab dem sich das neue Bild einlöst

## Zeigerweg in Bildschirmkoordinaten (640×360): [Zeit, Position]; dazwischen weich (smoothstep).
const CURSOR_KEYS := [
	[0.00, Vector2(330, 232)],
	[0.30, Vector2(330, 232)],
	[1.05, Vector2(568, 178)],
	[1.95, Vector2(568, 178)],
	[3.20, Vector2(372, 250)],          # neben der Schulter: Schatten und Füße des Dachses bleiben frei
	[5.12, Vector2(372, 250)],
	[5.36, Vector2(364, 152)],
	[6.00, Vector2(364, 152)],
]
## Bereiche im Bild (544×332), über denen der Zeiger die Form wechselt
const TURN_RIGHT_X := 500                       # rechter Rand: Drehhand (nach rechts drehen)
const BADGER_HOTSPOT := Rect2(264, 222, 62, 88) # Dachs im Steg-Bild nach dem Anhalten: offene Hand

const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const LOCATION := "Hafen von Lornholm"
const COL_GOLD := Color8(0xF2, 0xC8, 0x5A)
const COL_TEXT := Color8(0xEA, 0xDC, 0xBA)
const TEXT_BASELINE := 351.0

var meta: Dictionary
var views := {}              # Knoten -> {"vp": SubViewport, "clips": [{sprite, frames, loop_from, kind}]}
var cursor_meta: Dictionary
var t := 0.0
var shown_location := ""

@onready var screen: ColorRect = $Screen
@onready var compose: ShaderMaterial = $Screen.material
@onready var location_label: Label = $Band/Location
@onready var line_label: Label = $Band/Line
@onready var cursor: Sprite2D = $Cursor


func _ready() -> void:
	meta = _load_json("res://nodes/nodes_meta.json")
	cursor_meta = _load_json("res://ui/cursors.json")
	for node_name in meta["nodes"]:
		_build_view(node_name, meta["nodes"][node_name])
	_setup_text()
	_update(0.0)


func _load_json(path: String) -> Dictionary:
	var txt := FileAccess.get_file_as_string(path)
	var data = JSON.parse_string(txt)
	if typeof(data) != TYPE_DICTIONARY:
		push_error("JSON nicht lesbar: " + path)
		return {}
	return data


func _build_view(node_name: String, m: Dictionary) -> void:
	var vp := SubViewport.new()
	vp.name = "View_" + node_name
	vp.size = IMG_SIZE
	vp.disable_3d = true
	vp.transparent_bg = false
	vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	$Views.add_child(vp)
	var base := Sprite2D.new()
	base.texture = load("res://nodes/%s/%s" % [node_name, m["base"]])
	base.centered = false
	vp.add_child(base)
	var clips := []
	for c in m["clips"]:
		var s := Sprite2D.new()
		s.texture = load("res://nodes/%s/%s" % [node_name, c["file"]])
		s.centered = false
		s.position = Vector2(c["rect"][0], c["rect"][1])
		s.hframes = int(c["cols"])
		s.vframes = int(ceil(float(c["frames"]) / float(c["cols"])))
		vp.add_child(s)
		clips.append({"sprite": s, "frames": int(c["frames"]), "loop_from": int(c["loop_from"]), "kind": c["kind"]})
	views[node_name] = {"vp": vp, "clips": clips}


func _setup_text() -> void:
	var f := load("res://fonts/EBGaramond-wght.ttf") as FontFile
	f.antialiasing = TextServer.FONT_ANTIALIASING_GRAY
	f.hinting = TextServer.HINTING_LIGHT
	# halbe Pixel: Ohne Subpixel-Positionierung rundet jeder Vorschub auf ganze Pixel, in den Kapitälchen von
	# „Leuchtturmtür“ wirkten einzelne Lücken dann wie Leerzeichen
	f.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_ONE_HALF
	var caps := FontVariation.new()
	caps.base_font = f
	caps.opentype_features = {TextServerManager.get_primary_interface().name_to_tag("smcp"): 1}
	location_label.add_theme_font_override("font", caps)
	location_label.add_theme_font_size_override("font_size", 13)
	location_label.add_theme_color_override("font_color", COL_GOLD)
	line_label.add_theme_font_override("font", f)
	line_label.add_theme_font_size_override("font_size", 14)
	line_label.add_theme_color_override("font_color", COL_TEXT)
	line_label.text = LINE


func _layout_text() -> void:
	# beide Zeilenteile auf eine gemeinsame Grundlinie, zusammen mittig unter dem Bild
	var lf: Font = location_label.get_theme_font("font")
	var ls := location_label.get_theme_font_size("font_size")
	var tf: Font = line_label.get_theme_font("font")
	var ts := line_label.get_theme_font_size("font_size")
	var gap := 14.0
	var w_loc := lf.get_string_size(location_label.text, HORIZONTAL_ALIGNMENT_LEFT, -1, ls).x
	var w_line := tf.get_string_size(LINE, HORIZONTAL_ALIGNMENT_LEFT, -1, ts).x
	var x0 := roundf(IMG_POS.x + (IMG_SIZE.x - (w_loc + gap + w_line)) / 2.0)
	location_label.position = Vector2(x0, roundf(TEXT_BASELINE - lf.get_ascent(ls)))
	line_label.position = Vector2(x0 + roundf(w_loc + gap), roundf(TEXT_BASELINE - tf.get_ascent(ts)))


func _process(delta: float) -> void:
	t += delta
	_update(t)


func _phase(node_name: String, time: float) -> int:
	# Bildnummer der Umgebungsschleife; auf dem Steg an den Dachs-Clip gekoppelt (der Clip enthält um die Figur
	# herum die Umgebung derselben Phase und passt nur dann nahtlos auf die Wasser-Bildfolge)
	var origin := T_BADGER if node_name == "steg" else 0.0
	return int(floor((time - origin) * CLIP_FPS + EPS))


func _step_view(node_name: String, time: float) -> void:
	var n := _phase(node_name, time)
	for c in views[node_name]["clips"]:
		var frames: int = c["frames"]
		var i: int
		if c["kind"] == "badger":
			i = max(n, 0)
			if i >= frames:
				var lf: int = c["loop_from"]
				i = lf + (i - lf) % (frames - lf)
		else:
			i = posmod(n, frames)
		c["sprite"].frame = i


func _smooth(x: float) -> float:
	x = clampf(x, 0.0, 1.0)
	return x * x * (3.0 - 2.0 * x)


func _update(time: float) -> void:
	var a := "kai"
	var b := "kai"
	var mix_p := 0.0
	var zoom := 1.0
	if time >= DISSOLVE[0] and time < DISSOLVE[1]:
		a = "kai"
		b = "steg"
		mix_p = (time - DISSOLVE[0]) / (DISSOLVE[1] - DISSOLVE[0])
	elif time >= DISSOLVE[1] and time < ZOOM[0]:
		a = "steg"
		b = "steg"
	elif time >= ZOOM[0] and time < ZOOM[1]:
		a = "steg"
		b = "tuer"
		var u := (time - ZOOM[0]) / (ZOOM[1] - ZOOM[0])
		zoom = 1.0 + (ZOOM_MAX - 1.0) * u * u
		mix_p = clampf((u - ZOOM_DISSOLVE_FROM) / (1.0 - ZOOM_DISSOLVE_FROM), 0.0, 1.0)
	elif time >= ZOOM[1]:
		a = "tuer"
		b = "tuer"
	for node_name in views:
		_step_view(node_name, time)
	compose.set_shader_parameter("tex_a", views[a]["vp"].get_texture())
	compose.set_shader_parameter("tex_b", views[b]["vp"].get_texture())
	compose.set_shader_parameter("mix_p", mix_p)
	compose.set_shader_parameter("zoom_a", zoom)
	compose.set_shader_parameter("zoom_center", ZOOM_CENTER)
	var current := b if mix_p >= 0.5 else a
	var loc: String = LOCATION + " · " + String(meta["nodes"][current]["name"])
	if loc != shown_location:
		shown_location = loc
		location_label.text = loc
		_layout_text()
	_update_cursor(time, current)


func _update_cursor(time: float, current: String) -> void:
	var pos: Vector2 = CURSOR_KEYS[0][1]
	for k in range(CURSOR_KEYS.size() - 1):
		var k0: Array = CURSOR_KEYS[k]
		var k1: Array = CURSOR_KEYS[k + 1]
		if time >= k0[0] and time < k1[0]:
			pos = (k0[1] as Vector2).lerp(k1[1], _smooth((time - k0[0]) / (k1[0] - k0[0])))
			break
		elif time >= k1[0]:
			pos = k1[1]
	var p := pos - IMG_POS
	var shape := "point_up"
	if p.x >= TURN_RIGHT_X:
		shape = "point_right"
	elif current == "steg" and BADGER_HOTSPOT.has_point(p):
		shape = "open"
	var cm: Dictionary = cursor_meta["cursors"][shape]
	var cell := float(cursor_meta["cell"])
	cursor.region_rect = Rect2(float(cm["index"]) * cell, 0.0, cell, cell)
	cursor.offset = -Vector2(cm["hotspot"][0], cm["hotspot"][1])
	cursor.position = pos.round()
