extends Node2D
## Hafen von Lornholm in moderner Hi-Bit-Pixel-Art (640×360, ganzzahlig ×2).
## Ablauf (6 s, 30 fps, deterministisch über aufsummiertes delta und feste Seeds):
##   0,0 s  Dachs-Kurier läuft von rechts heran (8 Laufbilder, 15 Bilder/s, Vorschub je Bild gemessen)
##   ~3,4 s bleibt er im Lichtkreis der Laterne stehen (Übergang im Durchgangsbild), atmet, blinzelt
##   Laterne und Fenster flackern (2D-Licht mit Normal Maps), Leuchtfeuer dreht sich (Kegel + Blitz +
##   Spiegelung), Wasser wellt sich zeilenweise, Rauch und Lichtstaub sind Partikel, Möwen, Sterne, Nebel.
## Benutzerargumente: --t0=<s> startet die Zeit später (Dauerlauf-Prüfung), --solo zeigt nur den Dachs
## auf Schwarz (Fußmessung), --nolight schaltet die 2D-Lichter aus (Vergleich).

const CW := 52
const CH := 68
const AX := 29             # Kopfanker-Spalte im nach rechts blickenden Bild
const BASE := 66           # Fußzeile in der Zelle
const FEET_Y := 284        # Fußlinie auf dem Kai
# Vorschub (px) beim Wechsel von Laufbild i nach i+1, aus dem Standfuß der verkleinerten Bilder gemessen
const WALK_ADV := [2, 5, 2, 2, 3, 3, 3, 4]
const WALK_FPS := 15.0
const START_X := 470
const STOP_X := 300        # ungefähres Ziel; gestoppt wird im nächsten Durchgangsbild (2 oder 6)

var t := 0.0
var frame_i := 0
var t0 := 0.0
var solo := false
var nolight := false
var only_light := ""
var flatnormals := false
var smooth := false

var walk_tex: CanvasTexture
var stand_tex: CanvasTexture
var bx := START_X          # Kopfanker in Bildschirm-x
var walk_f := 0
var walking := true
var stop_t := -1.0
var anim_tick := -1
var noise := FastNoiseLite.new()

@onready var badger: Sprite2D = $Badger
@onready var lantern: PointLight2D = $LanternLight
@onready var window_light: PointLight2D = $WindowLight
@onready var lamp_light: PointLight2D = $LampLight
@onready var beam: ColorRect = $Beam
@onready var water: Sprite2D = $Water
@onready var mist: Sprite2D = $Mist
@onready var ui: Control = $UI/Box


func _ct(diffuse: String, normal: String) -> CanvasTexture:
	var ct := CanvasTexture.new()
	ct.diffuse_texture = load(diffuse)
	ct.normal_texture = load(normal)
	ct.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	return ct


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a == "--solo":
			solo = true
		elif a == "--nolight":
			nolight = true
		elif a == "--flatnormals":
			flatnormals = true
		elif a == "--smooth":
			smooth = true
		elif a.begins_with("--only="):
			only_light = a.substr(7)
	noise.seed = 1803
	noise.frequency = 1.0
	noise.fractal_octaves = 2
	walk_tex = _ct("res://art/badger_walk_l.png", "res://art/badger_walk_l_n.png")
	stand_tex = _ct("res://art/badger_stand_l.png", "res://art/badger_stand_l_n.png")
	badger.texture = walk_tex
	badger.hframes = 8
	var sky_mask: Image = (load("res://art/layers.png") as Texture2D).get_image()
	$Stars.setup(sky_mask)
	# Wasserzeilen aus der Ebenenmaske (build_bg.py schreibt sie nach art/bg.json), nicht fest im Shader
	var bg_info: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/bg.json"))
	var wmat := water.material as ShaderMaterial
	wmat.set_shader_parameter("horizon", float(bg_info["first_water_row"]))
	wmat.set_shader_parameter("near_row", float(bg_info["quay_top"][0]))
	$Gulls.tex = load("res://art/gull.png")
	if solo:
		for n in get_children():
			if n is CanvasItem and n != badger:
				n.visible = false
		$UI.visible = false
		RenderingServer.set_default_clear_color(Color.BLACK)
	if nolight or only_light != "":
		for n in [lantern, window_light, lamp_light, $Rim]:
			n.enabled = (n.name == only_light)
	if flatnormals:   # Vergleich: dieselben Lichter ohne Normal Maps
		walk_tex.normal_texture = null
		stand_tex.normal_texture = null
		($Near.texture as CanvasTexture).normal_texture = null
		($Far.texture as CanvasTexture).normal_texture = null
	if smooth:        # Vergleich: Licht ohne Stufen
		for n in [$Near, $Far, badger]:
			(n.material as ShaderMaterial).set_shader_parameter("banded", false)
	# Dauerlauf: Zustand bis t0 durchrechnen (gleiche Schritte wie im Lauf)
	if t0 > 0.0:
		var steps := int(round(t0 * 30.0))
		for i in steps:
			_advance(1.0 / 30.0)


func _process(delta: float) -> void:
	_advance(delta)


func _advance(delta: float) -> void:
	t += delta
	frame_i += 1
	_badger_step()
	_lights()
	_ambient()
	ui.step(t, _badger_state())


func _badger_state() -> Dictionary:
	return {"walking": walking, "stop_t": stop_t}


# --- Dachs -----------------------------------------------------------------------------------------
func _badger_step() -> void:
	# 15 Bilder/s: neues Bild bei jedem zweiten Aufnahmebild (ganzzahlig, keine Rundungsdrift)
	var tick := int(floor((t + 0.0001) * WALK_FPS))
	if tick != anim_tick:
		var first := anim_tick < 0
		anim_tick = tick
		if walking and not first:
			bx -= WALK_ADV[walk_f]
			walk_f = (walk_f + 1) % 8
			if bx <= STOP_X and (walk_f == 2 or walk_f == 6):
				walking = false
				stop_t = t
	if walking:
		badger.texture = walk_tex
		badger.hframes = 8
		badger.frame = walk_f
	else:
		badger.texture = stand_tex
		badger.hframes = 5
		badger.frame = _stand_frame(t - stop_t)
	# Sprite ist gespiegelt (blickt nach links): Kopfanker liegt bei Spalte CW-1-AX
	badger.position = Vector2(bx - (CW - 1 - AX), FEET_Y - BASE)
	$Shadow.position = Vector2(bx - 14, FEET_Y - 2)


func _stand_frame(s: float) -> int:
	# 0 stehen, 1 blinzeln, 2 sprechen, 3 atmen (Oberkörper 1 px tiefer), 4 atmen + blinzeln;
	# Atmen im Wechsel alle 0,8 s. Blinzeln in der Atemphase nutzt Bild 4 (gleicher Versatz, kein Sprung).
	var breathing := int(floor(s / 0.8)) % 2 == 1
	for b in [0.9, 3.4, 6.1]:          # Blinzeln: 3 Aufnahmebilder lang
		if s >= b and s < b + 0.1:
			return 4 if breathing else 1
	return 3 if breathing else 0


# --- Licht -------------------------------------------------------------------------------------------
func _lights() -> void:
	# Laterne: Flackern aus Rauschen (fester Seed) plus zwei Windböen, in denen die Flamme einknickt
	var n1 := noise.get_noise_1d(t * 6.0)
	var n2 := noise.get_noise_1d(t * 17.0 + 40.0)
	var gust := 0.0
	for g in [[1.35, 0.35], [4.15, 0.3]]:
		var d: float = (t - g[0]) / g[1]
		if d > -1.0 and d < 1.0:
			gust = max(gust, 1.0 - d * d)
	var e := 1.85 + 0.2 * n1 + 0.08 * n2 - 0.55 * gust
	lantern.energy = e
	lantern.texture_scale = 1.9 + 0.05 * n1
	# Lichthöfe schwächer als in der ersten Fassung: Glas ist im Hintergrund jetzt nur mittelhell gemalt und gehört
	# zum Nahen (wird also selbst beleuchtet); Licht + Lichthof sollen es zum Leuchten bringen, nicht überstrahlen.
	$HaloLantern.modulate = Color(1.0, 0.72, 0.4, clamp(0.38 + 0.3 * (e - 1.65), 0.12, 0.7))
	# Fenster: ruhiges Kaminfeuer
	var w := 0.78 + 0.1 * noise.get_noise_1d(t * 3.0 + 100.0)
	window_light.energy = w
	$HaloWindow.modulate = Color(1.0, 0.7, 0.42, 0.2 + 0.2 * (w - 0.6))
	# Leuchtfeuer: Umdrehung in 6 s; Kegel nach cos, Blitz wenn er zur Kamera zeigt
	var phi := TAU * t / 6.0 - 1.74
	var dirx := cos(phi)
	var toward := sin(phi)
	var flash := clampf((toward - 0.82) / 0.18, 0.0, 1.0)
	flash = flash * flash
	var mat := beam.material as ShaderMaterial
	mat.set_shader_parameter("dirx", dirx)
	mat.set_shader_parameter("strength", 0.9 * clampf(abs(dirx) * 1.4, 0.0, 1.0) * (1.0 if toward > -0.2 else 0.55))
	$FlareLamp.modulate = Color(1.0, 0.9, 0.62, 0.75 * flash)
	$HaloLamp.modulate = Color(1.0, 0.9, 0.62, 0.45 + 0.5 * flash)
	lamp_light.energy = 0.25 + 1.6 * flash
	(water.material as ShaderMaterial).set_shader_parameter("lamp_flash", flash)


func _ambient() -> void:
	(water.material as ShaderMaterial).set_shader_parameter("time", t)
	# Nebel zieht nach links, um ganze Pixel (5 px/s)
	mist.region_rect = Rect2(floor(t * 5.0), 0, 640, 28)
	$Stars.step(t)
	$Gulls.step(t)
