extends Node2D
## Hafen von Lornholm in 1 Bit (400×240): Ablauf der 6 s, Leuchtfeuer, Laterne, Rauch, Boote, Dachs.
## Alles hängt an der aufsummierten Zeit t (deterministisch). Benutzerargumente nach "--":
##   --t0=<s>    Startzeit (Dauerlauf-Prüfung)
##   --fx=1      ohne Licht, Rauch und Funkeln (Vergleichsschalter)
##   --solo      nur der Dachs auf Magenta, ohne Palette (Messung von Füßen und Kopf)

const WALK_FPS := 15.0
# Vorschub in Pixeln beim Wechsel von Laufbild k zu k+1, aus dem gemessenen Standfuß (scripts/measure_badger.py)
const ADV := [3, 1, 4, 3, 3, 2, 4, 3]
const WALK_X0 := -18          # Fußpunkt beim Start (knapp links außerhalb des Bildes)
const WALK_FRAMES := 56       # 7 Zyklen; letztes Bild 7 (Füße beisammen), dann Stand bei x = 140 vor freiem Wasser
const IDLE_DX := [-2, -2, 0, 0]   # Versatz der Stehbilder, damit die Füße stehen bleiben
const FEET_Y := 177           # Sohlenzeile auf dem Kai
const LIGHTHOUSE_PERIOD := 5.0

var t := 0.0
var fx_mode := 0
var solo := false
var info := {}
var lantern_seq: PackedFloat32Array

@onready var scene_mat: ShaderMaterial = $Scene.material
@onready var badger: Sprite2D = $Badger
@onready var boats := [$BoatA, $BoatB]
@onready var ui = $UI/Text
var tex_walk: Texture2D = preload("res://art/badger_walk.png")
var tex_idle: Texture2D = preload("res://art/badger_idle.png")
var boat_base := []


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t = float(a.substr(5))
		elif a.begins_with("--fx="):
			fx_mode = int(a.substr(5))
		elif a == "--solo":
			solo = true
	var f := FileAccess.open("res://art/bg.json", FileAccess.READ)
	info = JSON.parse_string(f.get_as_text())
	scene_mat.set_shader_parameter("horizon", float(info["horizon"]))
	scene_mat.set_shader_parameter("quay_top", float(info["quay_rows"][0]))
	scene_mat.set_shader_parameter("lamp_pos", Vector2(info["lamp"][0] + 0.5, info["lamp"][1] + 0.5))
	scene_mat.set_shader_parameter("lantern_pos", Vector2(info["lantern_glass"][0] + 0.5, info["lantern_glass"][1] + 0.5))
	scene_mat.set_shader_parameter("fx_mode", fx_mode)
	for i in 2:
		boat_base.append(Vector2(info["boats"][i]["pos"][0], info["boats"][i]["pos"][1]))
	# Flackerfolge der Laterne: Zielwerte alle 1/15 s aus festem Seed, zwei Böen
	var rng := RandomNumberGenerator.new()
	rng.seed = 4711
	lantern_seq = PackedFloat32Array()
	for i in 15 * 40:
		lantern_seq.append(rng.randf_range(0.55, 1.0))
	if solo:
		for n in [$Scene, $BoatA, $BoatB, $Gull1, $Gull2, $UI, $Palette]:
			n.visible = false
		RenderingServer.set_default_clear_color(Color(1, 0, 1))
	_update()


func _process(delta: float) -> void:
	t += delta
	_update()


func lantern_intensity(tt: float) -> float:
	var k := tt * 15.0
	var i0 := int(floor(k)) % lantern_seq.size()
	var v := lantern_seq[i0]
	# Böen: das Licht duckt sich kurz weg (Glas wird halb oder dunkel)
	for g in [1.6, 4.05]:
		var d: float = tt - g
		if d >= 0.0 and d < 0.35:
			v = 0.15 if d < 0.12 else 0.32
	return v


func _update() -> void:
	# Leuchtfeuer: Winkel phi, 0 = nach rechts, pi/2 = zur Kamera, pi = nach links
	var phi := PI + TAU * (t - 4.6) / LIGHTHOUSE_PERIOD
	var c := cos(phi)
	var s := sin(phi)
	scene_mat.set_shader_parameter("beam_side", -1.0 if c < 0.0 else 1.0)
	scene_mat.set_shader_parameter("beam_len", floor(240.0 * abs(c)) if s < 0.55 else 0.0)
	scene_mat.set_shader_parameter("flash_r", floor(clamp((s - 0.86) / 0.14, 0.0, 1.0) * 11.0))
	scene_mat.set_shader_parameter("t", t)
	scene_mat.set_shader_parameter("lantern_i", lantern_intensity(t))
	_update_smoke()
	# Boote heben sich abwechselnd um 1 px
	for i in 2:
		var ph := sin(TAU * t / (2.6 + 0.7 * i) + 1.9 * i)
		boats[i].position = boat_base[i] + Vector2(0, -1 if ph > 0.35 else 0)
	_update_gulls()
	_update_badger()
	ui.t = t
	ui.queue_redraw()


func _update_smoke() -> void:
	var chim := Vector2(info["chimney"][0], info["chimney"][1])
	var arr := PackedVector4Array()
	var period := 0.6
	var life := 4.2
	var first := int(floor((t - life) / period)) + 1
	var last := int(floor(t / period))
	for n in range(first, last + 1):
		var age := t - n * period
		if age < 0.0 or age > life:
			continue
		var j := fposmod(sin(n * 12.9898) * 43758.5453, 1.0)
		var u := age / life
		# Wind treibt die Wölkchen fast waagrecht und leicht sinkend über das Dach nach rechts (Start 2 px über
		# dem Schornsteinrand, Radius 2 → 6): so bleiben sie ganz im Bild statt am oberen Rand abgeschnitten
		var pos := chim + Vector2(age * (11.0 + 4.0 * j), -2.0 + age * (0.6 + 0.4 * j))
		pos = pos.round()
		var r := roundf(2.0 + 4.0 * u)
		arr.append(Vector4(pos.x + 0.5, pos.y + 0.5, r, 1.0 - u * u))
		if arr.size() >= 10:
			break
	scene_mat.set_shader_parameter("puffs", arr)
	scene_mat.set_shader_parameter("puff_count", arr.size())


func _update_gulls() -> void:
	# Zwei Möwen: Flügelschlag oben, Mitte, unten, Mitte mit 10 Bildern/s, Flug in ganzen Pixeln
	var flap := [0, 1, 2, 1]
	var g1: Sprite2D = $Gull1
	var g2: Sprite2D = $Gull2
	var x1 := fposmod(60.0 + t * 17.0, 480.0) - 40.0
	g1.position = Vector2(roundf(x1), roundf(34.0 + 3.0 * sin(t * 1.3)))
	g1.frame = flap[int(floor(t * 10.0)) % 4]
	var x2 := 430.0 - fposmod(150.0 + t * 12.0, 480.0)
	g2.position = Vector2(roundf(x2), roundf(48.0 + 2.0 * sin(t * 1.7 + 1.0)))
	g2.frame = flap[(int(floor(t * 10.0)) + 2) % 4]


func walk_x(frames_done: int) -> int:
	var x := WALK_X0
	for k in frames_done:
		x += ADV[k % 8]
	return x


func _update_badger() -> void:
	var n := int(floor(t * WALK_FPS))
	if n < WALK_FRAMES:
		badger.texture = tex_walk
		badger.hframes = 8
		badger.frame = n % 8
		badger.position = Vector2(walk_x(n), FEET_Y)
		return
	var x_stop := walk_x(WALK_FRAMES - 1)
	var fr := 0
	if (t >= 4.05 and t < 4.15) or (t >= 5.75 and t < 5.85):
		fr = 1
	elif t >= 4.4 and t < 5.4:
		fr = 2 if int(floor((t - 4.4) / 0.2)) % 2 == 0 else 3
	badger.texture = tex_idle
	badger.hframes = 4
	badger.frame = fr
	badger.position = Vector2(x_stop + IDLE_DX[fr], FEET_Y)
