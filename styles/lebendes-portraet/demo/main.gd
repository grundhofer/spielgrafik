extends Node2D
## Dialogszene: Hafen von Lornholm als gemalter Hintergrund, davor das lebende Porträt des Dachs-Kuriers,
## der die Zeile spricht (Lippenbewegung aus dem getippten Text), atmet, blinzelt und den Kopf bewegt.
## Alles hängt nur von der aufsummierten Zeit ab; Zufall nur über RandomNumberGenerator mit festem Seed.
##
## Benutzerargumente (nach "--"):
##   --pose=<name>   feste Pose für Prüfbilder (rest, turn_l, turn_r, nod, tilt, blink, half, mouth, mouth_half)
##   --measure       nur die Figur vor Magenta, ohne Hintergrund und Oberfläche (für tools/measure.py)
##   --noblink, --nomouth  Vergleichsschalter: Augen bleiben offen bzw. Mund bleibt zu
##   --dump          Parameter je Bild auf die Konsole (Prüfung der Glättung)

const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const TYPE_START := 0.55
const CPS := 19.0
const PAUSE_AFTER := {".": 0.32, ",": 0.15}

var t := 0.0
var rng := RandomNumberGenerator.new()
var layout := {}
var char_times: Array[float] = []
var type_end := 0.0
var mouth_v := 0.0
var mouth_vel := 0.0
var pose := ""
var measure := false
var no_blink := false   # Vergleichsschalter für tools/measure.py
var no_mouth := false
var scarf_settled := false

@onready var portrait = $Portrait
@onready var line_label: Label = $UI/Box/Line
@onready var choices_box: VBoxContainer = $UI/Choices
@onready var arrow: Polygon2D = $UI/Box/Arrow   # gezeichnetes Dreieck: Fraunces hat kein ▾ (U+25BE)
@onready var bg_mat: ShaderMaterial = $Bg.material as ShaderMaterial


func _ready() -> void:
	rng.seed = 4711
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--pose="):
			pose = a.substr(7)
		elif a == "--measure":
			measure = true
		elif a == "--noblink":
			no_blink = true
		elif a == "--nomouth":
			no_mouth = true
	var f := FileAccess.open("res://art/bg_layout.json", FileAccess.READ)
	if f:
		layout = JSON.parse_string(f.get_as_text())
	# Zeitpunkte, zu denen jedes Zeichen erscheint (mit Pausen nach Satzzeichen)
	var tt := TYPE_START
	for i in LINE.length():
		char_times.append(tt)
		tt += 1.0 / CPS
		var ch := LINE[i]
		if PAUSE_AFTER.has(ch):
			tt += PAUSE_AFTER[ch]
	type_end = tt
	line_label.text = LINE
	line_label.visible_characters = 0
	for i in choices_box.get_child_count():
		choices_box.get_child(i).modulate.a = 0.0
	arrow.modulate.a = 0.0
	if measure:
		$Bg.visible = false
		$FX.visible = false
		$UI.visible = false
		$Magenta.visible = true
	_place_fx()
	if SHOW_PARAMS and not measure and pose == "":
		_build_params()


# ------------------------------------------------------------------ Parameterleiste (zeigt die Technik)
const SHOW_PARAMS := true
const PARAMS := [["Kopf X", "angle_x", true], ["Kopf Y", "angle_y", true], ["Neigung", "angle_z", true],
	["Atem", "breath", false], ["Augen", "eye_l", false], ["Mund", "mouth", false]]
var param_bars: Array[ColorRect] = []
const BAR_W := 120.0


func _build_params() -> void:
	var panel := Panel.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.08, 0.085, 0.15, 0.62)
	sb.border_color = Color(0.79, 0.64, 0.4, 0.45)
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(8)
	panel.add_theme_stylebox_override("panel", sb)
	var box: Rect2 = Rect2(layout.get("params", [1040, 16])[0], layout.get("params", [1040, 16])[1], 222, 150)
	panel.position = box.position
	panel.size = box.size
	$UI.add_child(panel)
	var fv := FontVariation.new()
	fv.base_font = load("res://fonts/Fraunces-var.ttf")
	fv.variation_opentype = {2003265652: 520, 1869640570: 12}
	var title := Label.new()
	title.text = "Live-Parameter"
	title.add_theme_font_override("font", fv)
	title.add_theme_font_size_override("font_size", 13)
	title.add_theme_color_override("font_color", Color(0.85, 0.76, 0.6, 0.95))
	title.position = Vector2(12, 6)
	panel.add_child(title)
	for i in PARAMS.size():
		var y := 30.0 + i * 19.0
		var l := Label.new()
		l.text = PARAMS[i][0]
		l.add_theme_font_override("font", fv)
		l.add_theme_font_size_override("font_size", 13)
		l.add_theme_color_override("font_color", Color(0.9, 0.87, 0.8, 0.9))
		l.position = Vector2(12, y - 3)
		panel.add_child(l)
		var track := ColorRect.new()
		track.color = Color(1, 1, 1, 0.12)
		track.position = Vector2(88, y + 6)
		track.size = Vector2(BAR_W, 5)
		panel.add_child(track)
		if PARAMS[i][2]:
			var mid := ColorRect.new()
			mid.color = Color(1, 1, 1, 0.35)
			mid.position = Vector2(88 + BAR_W * 0.5 - 0.5, y + 3)
			mid.size = Vector2(1, 11)
			panel.add_child(mid)
		var fill := ColorRect.new()
		fill.color = Color(0.96, 0.74, 0.4, 0.95)
		fill.position = track.position
		fill.size = Vector2(0, 5)
		panel.add_child(fill)
		param_bars.append(fill)


func _update_params() -> void:
	for i in PARAMS.size():
		var v: float = portrait.get(PARAMS[i][1])
		var fill := param_bars[i]
		if PARAMS[i][2]:
			v = clampf(v, -1.0, 1.0)
			var x0 := 88.0 + BAR_W * 0.5
			var w := BAR_W * 0.5 * v
			fill.position.x = roundf(x0 + minf(0.0, w))
			fill.size.x = roundf(absf(w))
		else:
			fill.position.x = 88.0
			fill.size.x = roundf(BAR_W * clampf(v, 0.0, 1.0))


func _place_fx() -> void:
	if layout.is_empty():
		return
	$FX/Beam.position = Vector2(layout["lamp"][0], layout["lamp"][1])
	$FX/LampGlow.position = $FX/Beam.position
	$FX/LanternGlow.position = Vector2(layout["lantern"][0], layout["lantern"][1])
	if layout.has("window"):
		$FX/WindowGlow.position = Vector2(layout["window"][0], layout["window"][1])
	else:
		$FX/WindowGlow.visible = false


# ------------------------------------------------------------------ Mundform aus dem Text
func _mouth_target(time: float) -> float:
	if time < TYPE_START or time > type_end + 0.05:
		return 0.0
	# aktuelles Zeichen (das zuletzt erschienene) bestimmt die Form; Vokale öffnen, Lippenlaute schließen
	var idx := -1
	for i in char_times.size():
		if char_times[i] <= time:
			idx = i
	if idx < 0:
		return 0.0
	var ch := LINE[idx].to_lower()
	var since := time - char_times[idx]
	if since > 1.6 / CPS:   # Pause nach Satzzeichen: Mund zu
		return 0.0
	match ch:
		"a", "ä":
			return 0.95
		"o", "ö":
			return 0.75
		"e":
			return 0.6
		"u", "ü":
			return 0.5
		"i":
			return 0.4
		"m", "b", "p":
			return 0.0
		" ", ".", ",":
			return 0.08
		_:
			return 0.22


# ------------------------------------------------------------------ Ablauf
func _smooth(a: float, b: float, x: float) -> float:
	return smoothstep(a, b, x)


func _blink(time: float, at: float) -> float:
	# 0,2 s: schnell zu (3 Bilder), kurz halten, langsamer auf
	var d := time - at
	if d < 0.0 or d > 0.24:
		return 1.0
	if d < 0.07:
		return 1.0 - d / 0.07
	if d < 0.10:
		return 0.0
	return clampf((d - 0.10) / 0.14, 0.0, 1.0)


func _apply_pose() -> void:
	match pose:
		"turn_l":
			portrait.angle_x = -1.0
		"turn_r":
			portrait.angle_x = 1.0
		"nod":
			portrait.angle_y = 1.0
		"tilt":
			portrait.angle_z = 1.0
		"blink":
			portrait.eye_l = 0.0
			portrait.eye_r = 0.0
		"half":
			portrait.eye_l = 0.5
			portrait.eye_r = 0.5
		"mouth":
			portrait.mouth = 1.0
		"mouth_half":
			portrait.mouth = 0.5
		"gaze_r":
			portrait.gaze = Vector2(1.0, 0.0)
		"gaze_dl":
			portrait.gaze = Vector2(-1.0, 1.0)


func _process(delta: float) -> void:
	t += delta
	if pose != "":
		_apply_pose()
		portrait.step(delta)
		return
	_animate_portrait(delta)
	_animate_ui()
	_animate_fx()
	if not param_bars.is_empty():
		_update_params()


func _animate_portrait(delta: float) -> void:
	var p = portrait
	# Kopf: schaut anfangs zum Leuchtturm (rechts), wendet sich beim Sprechen dem Gegenüber zu,
	# nickt auf betonten Silben, deutet bei „Am Kai“ kurz zur Seite, neigt am Ende freundlich den Kopf.
	var look := 0.55 * (1.0 - _smooth(0.15, 0.85, t))
	look += 0.32 * _smooth(2.05, 2.45, t) * (1.0 - _smooth(2.9, 3.5, t))
	look += 0.12 * _smooth(4.1, 4.7, t)
	p.angle_x = look + 0.05 * sin(t * 0.9)
	# Blick eilt dem Kopf voraus: erst zum Leuchtturm, dann zum Gegenüber, bei „Am Kai“ zur Seite, am Ende zu den Antworten
	var gx := 1.0 * (1.0 - _smooth(0.05, 0.45, t)) + 0.9 * _smooth(1.95, 2.15, t) * (1.0 - _smooth(2.75, 3.0, t))
	gx -= 0.35 * _smooth(4.15, 4.4, t)   # nach dem Satz wieder zum Gegenüber (Kopf leicht zur Seite geneigt)
	p.gaze = Vector2(gx, 0.25 * _smooth(4.15, 4.4, t))
	var nod := 0.0
	for at: float in [0.95, 1.55, 2.15, 2.95, 3.55]:
		var d: float = t - at
		if d > 0.0 and d < 0.45:
			nod += sin(d / 0.45 * PI) * 0.45
	p.angle_y = nod - 0.1 * _smooth(4.1, 4.6, t)
	p.angle_z = 0.18 * sin(t * 0.8 + 0.4) + 0.75 * _smooth(4.0, 4.7, t)
	p.body_x = 0.35 * sin(t * 0.95) + 0.25 * look
	p.breath = 0.5 - 0.5 * cos(t * TAU / 3.4)
	var e := minf(_blink(t, 1.98), _blink(t, 5.05))
	p.eye_l = e
	p.eye_r = e
	p.ear_l = 0.0
	p.ear_r = sin(clampf((t - 4.75) / 0.3, 0.0, 1.0) * PI) * 1.0
	p.wind = 3.0 + 3.5 * sin(t * 1.1) + 2.0 * sin(t * 2.7 + 1.0)
	# Mund: zweistufig geglättet zum Ziel (Öffnen schnell, Schließen etwas langsamer). Exponentielle Glättung
	# ist bei jedem Zeitschritt stabil; eine steife Feder mit explizitem Schritt schwang bei 30 fps Bild für Bild
	# zwischen 0 und 1 (gemessen mit --dump).
	var target := _mouth_target(t)
	var tau := 0.035 if target > mouth_vel else 0.06
	mouth_vel += (target - mouth_vel) * (1.0 - exp(-delta / tau))
	mouth_v += (mouth_vel - mouth_v) * (1.0 - exp(-delta / 0.03))
	mouth_v = clampf(mouth_v, 0.0, 1.0)
	p.mouth = 0.0 if no_mouth else mouth_v
	if no_blink:
		p.eye_l = 1.0
		p.eye_r = 1.0
	if not scarf_settled:
		# Schalende in der Windlage starten, sonst schwingt es aus der Senkrechten ein (Ruck zu Szenenbeginn)
		p.settle(p.wind)
		scarf_settled = true
	p.step(delta)
	if OS.get_cmdline_user_args().has("--dump"):
		print("P %d %.4f %.4f %.4f %.4f %.4f %.4f %.3f %.3f %.3f %.3f" % [Engine.get_frames_drawn(), p.angle_x, p.angle_y, p.angle_z, p.body_x, p.breath, p.mouth, p.s_ang[0], p.s_ang[1], p.s_ang[2], p.eye_l])


func _animate_ui() -> void:
	var n := 0
	for ct in char_times:
		if ct <= t:
			n += 1
	line_label.visible_characters = n
	# Antworten gleiten nacheinander von rechts herein (ganze Pixel)
	for i in choices_box.get_child_count():
		var at := type_end + 0.25 + i * 0.12
		var a := _smooth(at, at + 0.3, t)
		var ch: Control = choices_box.get_child(i)
		ch.modulate.a = a
		ch.position.x = roundf((1.0 - a) * 40.0)
	# Weiter-Pfeil blinkt kurz nach Ende der Zeile, bis die Antworten da sind
	var arrow_on := t > type_end + 0.05 and t < type_end + 0.3
	arrow.modulate.a = 1.0 if arrow_on else 0.0


func _animate_fx() -> void:
	if bg_mat:
		bg_mat.set_shader_parameter("time", t)
	# Leuchtturm: Strahl kreist (10 s je Umdrehung), Lampe blitzt auf, wenn er zur Kamera zeigt
	var phi := t * TAU / 10.0 + 1.9
	var beam: Node2D = $FX/Beam
	var side := sin(phi)
	var facing := cos(phi)
	beam.scale = Vector2(absf(side) * 1.0 + 0.04, 1.0)
	beam.modulate.a = clampf(0.25 + 0.75 * absf(side), 0.0, 1.0) * (1.0 if facing < 0.6 else 1.0 - (facing - 0.6) * 2.0)
	beam.rotation = 0.0 if side >= 0.0 else PI
	var lamp: Node2D = $FX/LampGlow
	var flash := pow(maxf(0.0, facing), 6.0)
	lamp.scale = Vector2.ONE * (0.8 + 1.4 * flash)
	lamp.modulate.a = 0.55 + 0.45 * flash
	# Laterne und Fenster flackern (geglättetes Rauschen aus fester Tabelle)
	var fl := 0.75 + 0.12 * sin(t * 13.0) + 0.08 * sin(t * 21.7 + 1.3) + 0.06 * sin(t * 37.1)
	$FX/LanternGlow.modulate.a = clampf(fl, 0.0, 1.0)
	$FX/LanternGlow.scale = Vector2.ONE * (0.95 + 0.08 * fl)
	$FX/WindowGlow.modulate.a = clampf(0.6 + 0.1 * sin(t * 9.0 + 0.5) + 0.06 * sin(t * 23.0), 0.0, 1.0)
	_animate_gulls()


# ------------------------------------------------------------------ Möwen (gezeichnete Silhouetten)
var gulls: Array[Polygon2D] = []
const GULLS := [
	# Start x, y, Geschwindigkeit px/s, Spannweite, Flügelschlag Hz, Phase
	[1310.0, 150.0, -62.0, 26.0, 2.6, 0.0],
	[1180.0, 92.0, -48.0, 18.0, 3.1, 1.7],
]


func _gull_shape(span: float, flap: float) -> PackedVector2Array:
	var tip := -span * 0.28 * flap
	var elb := span * 0.06 * flap - span * 0.05
	var h := span * 0.5
	return PackedVector2Array([
		Vector2(-h, tip), Vector2(-h * 0.45, elb), Vector2(0, 0), Vector2(h * 0.45, elb), Vector2(h, tip),
		Vector2(h * 0.45, elb + span * 0.07), Vector2(0, span * 0.08), Vector2(-h * 0.45, elb + span * 0.07),
	])


func _animate_gulls() -> void:
	if gulls.is_empty():
		for g in GULLS:
			var p := Polygon2D.new()
			p.color = Color(0.16, 0.13, 0.2, 0.92)
			p.antialiased = true
			$FX/Gulls.add_child(p)
			gulls.append(p)
	for i in GULLS.size():
		var g: Array = GULLS[i]
		var x: float = g[0] + g[2] * t
		var y: float = g[1] + 6.0 * sin(t * 0.7 + g[5])
		# Flügelschlag mit Gleitphasen
		var beat: float = sin(t * TAU * g[4] + g[5])
		var glide: float = smoothstep(0.2, 0.8, sin(t * 0.9 + g[5]))
		var flap: float = lerpf(beat, 0.25, glide)
		gulls[i].polygon = _gull_shape(g[3], flap)
		gulls[i].position = Vector2(roundf(x), roundf(y))
