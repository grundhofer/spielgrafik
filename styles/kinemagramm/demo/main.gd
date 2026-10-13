extends Node2D
## Kinemagramm: der Hafen von Lornholm als ein einziges gemaltes Standbild, das nur durch Masken und
## Shader lebt. Alle Bewegungen hängen nur von der aufsummierten Zeit t ab; Zufall nur mit festem Seed.

const SEED := 20261010

# Leuchtfeuer: eine Umdrehung in BEAM_PERIOD s. phi = 0 zeigt nach rechts, PI/2 zur Kamera, PI nach links.
const BEAM_PERIOD := 10.0
const BEAM_PHI0 := deg_to_rad(20.0)

# Dachs
const BREATH_PERIOD := 3.2
const BREATH_AMP := 0.011
# Gewicht verlagern: Kopf wandert um bis zu SWAY_PX seitlich, Füße bleiben (Scherung ab den Füßen)
const SWAY_PERIOD := 5.3
const SWAY_PX := 1.6
# Blinzeln: die ersten beiden fest (in der 6-s-Aufnahme), danach aus einer geseedeten Tabelle alle 3–6 s,
# gelegentlich doppelt; die Tabelle wiederholt sich nach BLINK_SPAN s
const BLINKS := [1.55, 4.85]
const BLINK_LEN := 0.2
const BLINK_SPAN := 600.0
# Möwen: fliegen über den Bildrand hinaus und kommen auf der anderen Seite in neuer Höhe wieder
const GULL_MARGIN := 40.0
const GULL_Y_RANGE := Vector2(60.0, 200.0)

# Text
const LOCATION := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf\u00A0dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"
const PANEL_T := 0.25
const TYPE_START := 0.6
const TYPE_CPS := 32.0
const CHOICE_T := [2.75, 2.95, 3.15]
const HOVER_T := 4.25
const PARSER_T := 4.7
const PARSER_CPS := 14.0

const GOLD := Color(0.86, 0.68, 0.40)
const CREAM := Color(0.94, 0.90, 0.82)
const CHOICE_COL := Color(0.80, 0.74, 0.64)
const HOVER_COL := Color(1.0, 0.86, 0.58)

var t := 0.0
# Vergleichsschalter: godot --path demo -- --no-badger (Figur aus, für Messungen) --frozen (Standbild ohne Leben)
var frozen := false
var scene := {}
var bmeta := {}
var lantern_tab := PackedFloat32Array()
var window_tab := PackedFloat32Array()
var gust_tab := PackedFloat32Array()
var blink_tab := PackedFloat32Array()
var gull_y_tab := PackedFloat32Array()
var gulls: Array = []

var still_mat: ShaderMaterial
var badger_mat: ShaderMaterial
var light_pos: Array = []      # Vector2 je Lichthof
var light_base: Array = []     # Color (rgb, a = Grundstärke)
var light_chan: Array = []     # 0 Fenster, 1 Laterne, 2 Leuchtfeuer
var badger_feet := Vector2(560, 660)

@onready var still: Sprite2D = $Still
@onready var badger: Sprite2D = $Badger
@onready var shadow: Sprite2D = $BadgerShadow
@onready var panel: ColorRect = $UI/Panel
var loc_label: Label
var line_label: Label
var choice_labels: Array = []
var num_labels: Array = []
var parser_label: Label


func _read_json(path: String) -> Dictionary:
	var f := FileAccess.open(path, FileAccess.READ)
	var d = JSON.parse_string(f.get_as_text())
	return d if d is Dictionary else {}


func _v2(a) -> Vector2:
	return Vector2(float(a[0]), float(a[1]))


func _ready() -> void:
	scene = _read_json("res://art/scene.json")
	bmeta = _read_json("res://art/badger.json")
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	# Flackern als Tabellen (20 bzw. 6 Werte je Sekunde), dazwischen weich interpoliert
	for i in 20 * 12:
		var v := rng.randf_range(0.80, 1.12)
		if rng.randf() < 0.07:
			v = rng.randf_range(0.62, 0.75)   # kurzer Einbruch, wenn der Wind in die Flamme fährt
		lantern_tab.append(v)
	for i in 6 * 12:
		window_tab.append(rng.randf_range(0.90, 1.07))
	for i in 3 * 12:
		gust_tab.append(rng.randf_range(0.65, 1.25))
	# erst nach den vorhandenen Tabellen ziehen, damit Flackern und Böen gleich bleiben
	for b in BLINKS:
		blink_tab.append(b)
	while blink_tab[blink_tab.size() - 1] < BLINK_SPAN:
		var nb := blink_tab[blink_tab.size() - 1] + rng.randf_range(3.0, 6.0)
		blink_tab.append(nb)
		if rng.randf() < 0.15:
			blink_tab.append(nb + 0.32)   # Doppelblinzeln
	for i in 64:
		gull_y_tab.append(rng.randf_range(GULL_Y_RANGE.x, GULL_Y_RANGE.y))

	still_mat = still.material
	still_mat.set_shader_parameter("horizon_y", float(scene.get("horizon_y", 260)))
	still_mat.set_shader_parameter("quay_y", float(scene.get("quay_y", 600)))
	still_mat.set_shader_parameter("lamp_pos", _v2(scene["lamp"]))
	still_mat.set_shader_parameter("chimney", _v2(scene["chimney"]))
	if scene.has("beam_len"):
		still_mat.set_shader_parameter("beam_len", float(scene["beam_len"]))
	var chan_ids := {"window": 0, "lantern": 1, "lamp": 2}
	var warm := {"window": Color(1.0, 0.62, 0.28), "lantern": Color(1.0, 0.66, 0.30), "lamp": Color(1.0, 0.86, 0.55)}
	var radii := PackedFloat32Array()
	for li in scene["lights"]:
		light_pos.append(_v2(li["pos"]))
		var c: Color = warm[li["channel"]]
		c.a = float(li.get("glow_k", 0.16))
		light_base.append(c)
		light_chan.append(chan_ids[li["channel"]])
		radii.append(float(li.get("glow", 60)))
	while light_pos.size() < 4:
		light_pos.append(Vector2(-999, -999))
		light_base.append(Color(0, 0, 0, 0))
		light_chan.append(0)
		radii.append(1.0)
	still_mat.set_shader_parameter("glow_pos", PackedVector2Array(light_pos))
	still_mat.set_shader_parameter("glow_r", radii)
	var piv := PackedVector2Array()
	for b in scene.get("boats", []):
		piv.append(_v2(b["pivot"]))
	while piv.size() < 2:
		piv.append(Vector2(-9999, -9999))
	still_mat.set_shader_parameter("boat_pivot", piv)

	gulls = scene.get("gulls", [{"start": [300, 70], "vel": [26, -2], "size": 10}, {"start": [980, 120], "vel": [-18, 1], "size": 7}])
	var gz := PackedFloat32Array()
	for g in gulls:
		gz.append(float(g["size"]))
	still_mat.set_shader_parameter("gull_size", gz)

	# Dachs: Ursprung an den Füßen, damit Atmen im vertex() die Füße stehen lässt
	badger_mat = badger.material
	var bs := _v2(bmeta["size"])
	var bcfg: Dictionary = scene.get("badger", {})
	badger_feet = Vector2(float(bcfg.get("x", 560)), float(bcfg.get("feet_y", 660)))
	badger.offset = Vector2(-bs.x * 0.5, -bs.y * float(bmeta["feet_v"]))
	badger.position = badger_feet
	badger.flip_h = bool(bcfg.get("flip", false))
	badger_mat.set_shader_parameter("tex_size", bs)
	# Schalachse vom Ansatz zur Spitze (UV); ohne Angabe hängt der Schal senkrecht
	var root := Vector2(0.5, float(bmeta["anchor_v"]))
	var tip := Vector2(0.5, float(bmeta["tail_end_v"]))
	if bmeta.has("tail_axis"):
		root = _v2(bmeta["tail_axis"][0])
		tip = _v2(bmeta["tail_axis"][1])
	badger_mat.set_shader_parameter("tail_root", root)
	badger_mat.set_shader_parameter("tail_tip", tip)
	badger_mat.set_shader_parameter("scarf_amp", float(bcfg.get("scarf_amp", 5.0)))
	var tint = bcfg.get("tint", [1, 1, 1])
	badger_mat.set_shader_parameter("tint", Vector3(tint[0], tint[1], tint[2]))
	var lantern: Vector2 = light_pos[1] if light_pos.size() > 1 else Vector2(0, 0)
	for i in light_pos.size():
		if light_chan[i] == 1:
			lantern = light_pos[i]
	var ld := lantern - (badger_feet - Vector2(0, bs.y * 0.6))
	if badger.flip_h:
		ld.x = -ld.x
	badger_mat.set_shader_parameter("light_dir", ld.normalized())
	shadow.position = badger_feet + Vector2(float(bcfg.get("shadow_dx", 0)), 2)
	shadow.scale = Vector2(bs.x * float(bcfg.get("shadow_w", 0.95)) / 128.0, 0.16)

	_build_ui()
	var args := OS.get_cmdline_user_args()
	frozen = args.has("--frozen")
	for a in args:
		if a.begins_with("--t0="):
			t = float(a.substr(5))   # Prüfschalter: Demo ab Zeitpunkt t0 starten (z. B. Himmel, Möwen, Blinzeln)
	if args.has("--no-badger"):
		badger.visible = false
		shadow.visible = false
	if args.has("--no-shadow"):
		shadow.visible = false
	if args.has("--no-ui"):
		$UI.visible = false
	_update()


func _font(path: String, size: int, spacing := 0) -> Font:
	var f := FontVariation.new()
	f.base_font = load(path)
	f.spacing_glyph = spacing
	return f


func _label(font: Font, size: int, col: Color) -> Label:
	var l := Label.new()
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.55))
	l.add_theme_constant_override("shadow_offset_x", 0)
	l.add_theme_constant_override("shadow_offset_y", 1)
	$UI.add_child(l)
	return l


func _build_ui() -> void:
	# Kompaktes Feld unten rechts über dem Kai: Zeile einzeilig, Antworten eng, damit Wasser und Boote frei bleiben
	var ui: Dictionary = scene.get("ui", {})
	var r := Rect2(float(ui.get("x", 645)), float(ui.get("y", 530)), float(ui.get("w", 615)), float(ui.get("h", 182)))
	panel.position = r.position
	panel.size = r.size
	panel.material.set_shader_parameter("rect_size", r.size)
	var serif := _font("res://fonts/Alegreya-wght.ttf", 20)
	var caps := _font("res://fonts/AlegreyaSC-Medium.ttf", 19, 2)
	var ital := _font("res://fonts/Alegreya-Italic-wght.ttf", 18)
	var x := r.position.x + 30
	loc_label = _label(caps, 19, GOLD)
	loc_label.text = LOCATION
	loc_label.position = Vector2(x, r.position.y + 9)
	panel.material.set_shader_parameter("line_y", 38.0)
	line_label = _label(serif, 20, CREAM)
	line_label.text = LINE
	line_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	line_label.size = Vector2(r.size.x - 56, 30)
	line_label.position = Vector2(x, r.position.y + 43)
	line_label.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	for i in CHOICES.size():
		var n := _label(serif, 19, GOLD)
		n.text = "%d." % (i + 1)
		n.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		n.size = Vector2(22, 24)
		n.position = Vector2(x - 4, r.position.y + 72 + i * 23)
		num_labels.append(n)
		var c := _label(serif, 19, CHOICE_COL)
		c.text = CHOICES[i]
		c.position = Vector2(x + 26, r.position.y + 72 + i * 23)
		choice_labels.append(c)
	parser_label = _label(ital, 18, Color(0.72, 0.68, 0.60))
	parser_label.text = PARSER
	parser_label.position = Vector2(x, r.position.y + 72 + 3 * 23 + 0)
	parser_label.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING


func _tab(tab: PackedFloat32Array, rate: float) -> float:
	var x := t * rate
	var i := int(floor(x))
	var f := x - i
	f = f * f * (3.0 - 2.0 * f)
	return lerpf(tab[i % tab.size()], tab[(i + 1) % tab.size()], f)


func _blink_amount() -> float:
	var tb := fposmod(t, BLINK_SPAN)
	var i := blink_tab.bsearch(tb, false) - 1   # letzter Blinzelbeginn <= tb
	for k in [i, i - 1]:
		if k < 0:
			continue
		var u: float = (tb - blink_tab[k]) / BLINK_LEN
		if u >= 0.0 and u <= 1.0:
			return clampf(1.0 - absf(u * 2.0 - 1.0) * 1.25 + 0.25, 0.0, 1.0)
	return 0.0


func _gull_positions() -> PackedVector2Array:
	# Erster Durchgang wie bisher (Start + Geschwindigkeit · t); verlässt eine Möwe das Bild, kommt sie auf der
	# anderen Seite wieder, in einer Höhe aus der geseedeten Tabelle
	var out := PackedVector2Array()
	var span := 1280.0 + 2.0 * GULL_MARGIN
	for gi in gulls.size():
		var g: Dictionary = gulls[gi]
		var st := _v2(g["start"])
		var v := _v2(g["vel"])
		var s := st.x + GULL_MARGIN + v.x * t          # Weg ab dem linken Rand außerhalb des Bildes
		var k := int(floor(s / span))
		var sm := fposmod(s, span)
		var y: float
		if k == 0:
			y = st.y + v.y * t
		else:
			var tau := sm / v.x if v.x > 0.0 else (span - sm) / -v.x   # Zeit seit dem Eintritt
			var y0 := gull_y_tab[(absi(k) * 7 + gi * 13) % gull_y_tab.size()]
			var vy := absf(v.y) * (1.0 if y0 < (GULL_Y_RANGE.x + GULL_Y_RANGE.y) * 0.5 else -1.0)   # bleibt im Himmel
			y = y0 + vy * tau
		out.append(Vector2(sm - GULL_MARGIN, y + 6.0 * sin(t * 0.9 + float(gi) * 2.0)))
	return out


func _process(delta: float) -> void:
	t += delta
	if frozen:
		t = 0.0
	_update()


func _update() -> void:
	var lan := _tab(lantern_tab, 20.0)
	var win := _tab(window_tab, 6.0)
	var phi := BEAM_PHI0 + TAU * t / BEAM_PERIOD
	var toward := maxf(sin(phi), 0.0)
	var lamp := 1.0 + 0.55 * pow(toward, 6.0)
	still_mat.set_shader_parameter("t", t)
	still_mat.set_shader_parameter("flick", Vector3(win, lan, lamp))
	still_mat.set_shader_parameter("beam_phi", phi)
	still_mat.set_shader_parameter("gull_pos", _gull_positions())
	var cols := PackedVector4Array()
	for i in light_pos.size():
		var c: Color = light_base[i]
		var k: float = [win, lan, lamp][light_chan[i]]
		if light_chan[i] == 2:
			k = 0.7 + 1.6 * pow(toward, 4.0)
		cols.append(Vector4(c.r, c.g, c.b, c.a * k))
	still_mat.set_shader_parameter("glow_col", cols)
	var ang := PackedFloat32Array()
	var bob := PackedFloat32Array()
	for b in scene.get("boats", []):
		var w := TAU * t / float(b["period"]) + float(b["phase"])
		ang.append(deg_to_rad(float(b["amp_deg"])) * sin(w))
		bob.append(float(b.get("bob", 1.0)) * sin(w * 0.5 + 0.9))
	while ang.size() < 2:
		ang.append(0.0)
		bob.append(0.0)
	still_mat.set_shader_parameter("boat_angle", ang)
	still_mat.set_shader_parameter("boat_bob", bob)

	# Dachs
	var br := BREATH_AMP * (0.5 - 0.5 * cos(TAU * t / BREATH_PERIOD))
	badger_mat.set_shader_parameter("t", t)
	badger_mat.set_shader_parameter("breath", br)
	var bh := float(bmeta["size"][1]) * float(bmeta["feet_v"])
	badger_mat.set_shader_parameter("sway", SWAY_PX / maxf(bh, 1.0) * sin(TAU * t / SWAY_PERIOD + 0.6))
	badger_mat.set_shader_parameter("blink", _blink_amount())
	badger_mat.set_shader_parameter("gust", _tab(gust_tab, 3.0))
	badger_mat.set_shader_parameter("rim_k", 0.32 * lan)
	shadow.scale.x = shadow.scale.x  # Schatten bleibt, die Füße bewegen sich nicht

	# Text
	var reveal := clampf((t - PANEL_T) / 0.35, 0.0, 1.0)
	panel.material.set_shader_parameter("reveal", reveal)
	loc_label.modulate.a = reveal
	line_label.visible_characters = clampi(int((t - TYPE_START) * TYPE_CPS), 0, LINE.length())
	for i in choice_labels.size():
		var a := clampf((t - CHOICE_T[i]) / 0.25, 0.0, 1.0)
		var hover := i == 1 and t >= HOVER_T
		choice_labels[i].modulate.a = a
		num_labels[i].modulate.a = a
		choice_labels[i].add_theme_color_override("font_color", HOVER_COL if hover else CHOICE_COL)
		num_labels[i].add_theme_color_override("font_color", HOVER_COL if hover else GOLD)
	parser_label.visible_characters = clampi(int((t - PARSER_T) * PARSER_CPS), 0, PARSER.length())
