extends Node3D
## Realistisches PBR: Hafen und Dachs aus shared/3d mit CC0-PBR-Texturen, HDRI-Himmel, SDFGI,
## SSR, SSAO/SSIL, volumetrischem Nebel und eigenem Wasser.
##
## Alles hängt an der aufsummierten Zeit t und festen Seeds: tools/capture.py nimmt mit
## --fixed-fps auf, jede Aufnahme ist Bild für Bild gleich (bis auf die zeitliche Glättung von
## TAA, SDFGI und Nebel, die ebenfalls nur von der Bildfolge abhängt).
##
## Benutzerargumente (nach "--"):
##   --t0=SEK            Startzeit (Prüfung langer Läufe)
##   --cam=x,y,z,tx,ty,tz,fov   feste Kamera statt der Fahrt
##   --no-sdfgi --no-ssr --no-ssao --no-ssil --no-volfog --no-glow --no-pom --no-taa
##   --no-mist           Seenebel (FogVolume über dem Becken) aus
##   --no-haze           Dunst um Laterne und Fenster (FogVolumes auf dem Kai) aus
##   --no-flicker        Laterne ohne Flackern (Vergleich)
##   --ramp=a,b,…        sdfgi_energy der ersten Bilder (Abstimmung von SDFGI_RAMP)
##   --flat              Texturen aus (nur Farbe/Rauheit/Metall aus dem glTF), Vergleich
##   --no-fur            Fellschalen aus
##   --no-ui             Oberfläche aus
##   --bench=N           N Bilder ohne feste Bildrate messen (GPU-/CPU-Zeit je Bild), dann beenden
##   --measure           je Bild Ferse, Zehe und Kopf des Dachses (Welt und Bild) ausgeben
##   --mask              nur der Dachs, weiß auf Schwarz (Silhouette für scripts/measure_badger.py)
##   --start_x=X         Startpunkt des Laufs (Planung)
##   --stats             Zahl der Dreiecke der Fellschalen ausgeben

const TEX := "res://textures/"
const SURFACE := preload("res://shaders/surface.gdshader")
const FLOOR := preload("res://shaders/floor.gdshader")
const WATER := preload("res://shaders/water.gdshader")
const FUR := preload("res://shaders/fur_shell.gdshader")
const FUR_SHELLS := 14
const FUR_LEN := 0.014

# --- Dachs (Werte aus shared/3d/badger_notes.md) --------------------------------------------
const WALK_SPEED := 0.367        # m/s bei speed_scale 1, dann rutschen die Füße nicht
const WALK_RATE := 1.6           # Abspieltempo von Walk
const START_X := -3.10          # Ende des Laufs bei x ≈ -1,45, z ≈ 1,7 (scripts/plan_shot.py)
const BRAKE_T := 3.13            # Bremsen so, dass Walk beim Umschalten in der Durchgangsphase ist
const BRAKE_TIME := 0.4
const IDLE_T := 3.41             # (Phase ≈ 0,295: ein Fuß steht, der andere schwingt daneben, 7 cm hoch)
const TURN_T0 := 1.9             # im Laufen zur Kamera abbiegen (Drehung um den Standfuß)
const TURN_T1 := 3.2
const TURN_DEG := -78.0          # Blick fast zur Kamera der Endeinstellung
const BLEND_IDLE := 0.3
const WAVE_T := 4.0
const WAVE_LEN := 1.5
const FLOOR_Y := 0.012           # eigene Pflasterfläche liegt 12 mm über den Platten
## SDFGI sammelt in den ersten Bildern (frames_to_converge = 5 Bilder); ohne Ausgleich wäre das
## erste Bild der Aufnahme dunkel (Kai unten 15/32/37/44/52 statt 57). sdfgi_energy wird in diesen
## Bildern angehoben. Vorwärmen mit RenderingServer.force_draw() half nur halb und verdarb die
## SDFGI-Spiegelungen glatter Flächen (Wasser schwarz, Pfützen gelb), deshalb nicht genutzt.
## Werte mit --ramp=… gegen den Mittelwert des Bildes unter y = 600 abgestimmt (Ziel: Bild 0 bis 5
## so hell wie die eingeschwungenen Bilder; erste Fassung 5,5/2,4/1,9 ließ Bild 0 bis 3 um 17/9/4 %
## zu dunkel, das fiel bei jeder Wiederholung der GIF-Schleife als Aufhellen auf).
const SDFGI_RAMP := [7.6, 2.82, 1.84, 1.4, 1.12, 1.03, 1.0]

# --- Umgebung -------------------------------------------------------------------------------
const BEAM_PERIOD := 9.0
const BEAM_FACING_T := 2.2
const SMOKE_PUFFS := 18
const SMOKE_LIFE := 5.5
const SMOKE_Y0 := -0.18
const SEED := 20261013
const LANTERN_EMISSION := 4.5
const LANTERN_ENERGY := 3.0

## Material je "Objekt/Material" (Objekt "*" = alle, "Boat*" = Präfix). Schlüssel:
## tex (Präfix in textures/), map (Abbildung, siehe surface.gdshader), tile (m), detail (Farbe aus
## dem glTF × Graustufen-Textur), tint, rot, cyl, gain, rough_mul, rough_add, wet, algae, damp, top.
var MATS := {
	"Quay/Stone": {"tex": "quaywall", "map": 3, "tile": 1.7, "gain": 0.9},
	"Quay/StoneDark": {"tex": "quaywall", "map": 3, "tile": 1.7, "gain": 0.75, "top": "granite",
			"top_tile": 1.4, "wet": -0.2, "algae": -0.5, "damp": 0.6},
	"Cottage/Stone": {"tex": "slatewall", "map": 3, "tile": 2.5, "gain": 0.85},
	"Cottage/StoneDark": {"tex": "granite", "map": 3, "tile": 1.4, "gain": 0.7},
	"Cottage/Roof": {"tex": "roof", "map": 3, "tile": 3.0, "damp": 0.4},
	"Cottage/WoodDark": {"tex": "planks", "map": 3, "tile": 2.0, "gain": 0.8},
	"Cottage/Wood": {"tex": "planks", "map": 3, "tile": 2.0},
	"Cottage/WhitePaint": {"tex": "paintwood", "map": 3, "tile": 1.8, "detail": true},
	"Cottage/RedPaint": {"tex": "paintwood", "map": 3, "tile": 1.8, "detail": true},
	"Barrel*/Wood": {"tex": "planks", "map": 5, "tile": 2.0, "cyl": 0.31, "damp": 0.5},
	"Barrel*/Metal": {"tex": "rust", "map": 5, "tile": 1.2, "cyl": 0.32, "gain": 0.8},
	"CrateStack/Wood": {"tex": "greywood", "map": 3, "tile": 1.5, "rot": true, "damp": 0.4},
	"CrateStack/WoodDark": {"tex": "greywood", "map": 3, "tile": 1.5, "gain": 0.7, "rot": true},
	"Jetty/Wood": {"tex": "greywood", "map": 3, "tile": 1.5, "rot": true, "damp": 0.6},
	"Jetty/WoodDark": {"tex": "planks", "map": 3, "tile": 2.0, "gain": 0.75, "wet": -0.45, "algae": -0.7},
	"Boat*/WhitePaint": {"tex": "paintwood", "map": 2, "tile": 1.8, "detail": true, "rot": true},
	"Boat*/RedPaint": {"tex": "paintwood", "map": 2, "tile": 1.8, "detail": true, "rot": true},
	"Boat*/Wood": {"tex": "greywood", "map": 2, "tile": 1.5, "rot": true},
	"Boat*/WoodDark": {"tex": "planks", "map": 2, "tile": 2.0, "gain": 0.7},
	"Boat*/Metal": {"tex": "ironpaint", "map": 2, "tile": 1.0, "gain": 0.35},
	"*/Rope": {"tex": "rope", "map": 2, "tile": 0.3, "aspect": Vector2(2, 1), "detail": true},
	"Bollards/Metal": {"tex": "ironpaint", "map": 1, "tile": 1.0, "gain": 0.55, "damp": 0.5},
	"LanternPost/WoodDark": {"tex": "planks", "map": 3, "tile": 2.0, "gain": 0.75},
	"LanternPost/Metal": {"tex": "ironpaint", "map": 1, "tile": 1.0, "gain": 0.3},
	"LanternPost/StoneDark": {"tex": "granite", "map": 3, "tile": 1.4, "gain": 0.7},
	"Lighthouse/WhitePaint": {"tex": "plaster", "map": 5, "tile": 2.0, "detail": true, "cyl": 1.3},
	"Lighthouse/RedPaint": {"tex": "plaster", "map": 5, "tile": 2.0, "detail": true, "cyl": 1.3},
	"Lighthouse/StoneDark": {"tex": "granite", "map": 5, "tile": 1.6, "gain": 0.75, "cyl": 1.6},
	"Lighthouse/Metal": {"tex": "ironpaint", "map": 1, "tile": 1.0, "gain": 0.3},
	"Lighthouse/WoodDark": {"tex": "planks", "map": 3, "tile": 2.0, "gain": 0.7},
	"RocksSea/Rock": {"tex": "searock", "map": 1, "tile": 2.0, "wet": -0.45, "algae": -0.62},
	"*/Rock": {"tex": "rock", "map": 1, "tile": 4.0, "macro": 0.25, "wet": -0.5, "algae": -0.65, "nstr": 1.6, "gain": 0.9},
	"*/Sand": {"tex": "sand", "map": 1, "tile": 2.0, "macro": 0.2, "damp": 0.5},
	"*/Grass": {"tex": "grass", "map": 1, "tile": 2.0, "macro": 0.3},
	# Dachs: Mesh-UVs (1 UV = 1 m), Stoffe als Graustufen-Detail in der Farbe aus dem glTF
	"Badger/Cap": {"tex": "tweed", "map": 0, "tile": 0.3, "detail": true, "nstr": 1.8, "rim": 0.5},
	"Badger/Vest": {"tex": "tweed", "map": 0, "tile": 0.3, "detail": true, "nstr": 1.8, "rim": 0.5},
	"Badger/Shirt": {"tex": "linen", "map": 0, "tile": 0.25, "detail": true, "nstr": 1.5, "rim": 0.4},
	"Badger/Scarf": {"tex": "knit", "map": 0, "tile": 0.1, "detail": true, "nstr": 1.2, "rim": 0.25, "rough_add": 0.05},
	"Badger/Satchel": {"tex": "leather", "map": 0, "tile": 0.4, "detail": true, "nstr": 1.3},
	"Parcel/Parcel": {"tex": "cardboard", "map": 0, "tile": 0.5, "detail": true},
	"Parcel/Shirt": {"tex": "rope", "map": 0, "tile": 0.05, "aspect": Vector2(2, 1), "detail": true},
}

@export var water_material: ShaderMaterial

var t := 0.0
var args := {}
var walk_rate := WALK_RATE
var phase := 0                   # 0 Walk, 1 Idle, 2 Wave, 3 Idle
var lock_side := "L"
var lock_point := Vector3.ZERO
var boats := {}
var smoke: Array[MeshInstance3D] = []
var smoke_jitter: Array[Vector3] = []
var lantern_mat: StandardMaterial3D
var lamp_mat: StandardMaterial3D
var window_mat: StandardMaterial3D
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0
var _cache := {}
var _tex_cache := {}
var fixed_cam := false
var bench_frames := 0
var bench_samples: Array = []
var bench_last_us := 0

@onready var harbor: Node3D = $Harbor
@onready var badger: Node3D = $Badger
@onready var player: AnimationPlayer = $Badger/AnimationPlayer
@onready var camera: Camera3D = $Camera
@onready var env: Environment = $WorldEnvironment.environment
@onready var sun: DirectionalLight3D = $Sun
@onready var rotor: Node3D = $Attach/LighthouseLight/Rotor
@onready var lantern_omni: OmniLight3D = $Attach/LanternLight/Omni
@onready var lamp_omni: OmniLight3D = $Attach/LighthouseLight/Omni
@onready var lamp_spot: SpotLight3D = $Attach/LighthouseLight/Rotor/Tilt/Spot
@onready var ui: Control = $UILayer/UI
@onready var mist_mat: ShaderMaterial = ($SeaMist as FogVolume).material
@onready var haze_vols: Array[FogVolume] = [$HazeLantern, $HazeWindow]


func _ready() -> void:
	_parse_args()
	_attach_to_empties()
	_apply_switches()
	_setup_sun()
	_build_floor()
	_style_materials(harbor)
	_style_materials(badger)
	if not args.has("no-fur") and not args.has("flat"):
		_build_fur()
	_setup_water()
	_setup_glass()
	for n in ["Barrel1", "Barrel2", "CrateStack", "RopeCoil"]:
		(harbor.get_node(n) as Node3D).position.y += FLOOR_Y
	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform
		# bewegte Objekte tragen nicht zur SDFGI-Szene bei, werden aber von ihr beleuchtet
		for mi: MeshInstance3D in harbor.get_node(b).find_children("*", "MeshInstance3D", true, false):
			mi.gi_mode = GeometryInstance3D.GI_MODE_DYNAMIC
		if harbor.get_node(b) is MeshInstance3D:
			(harbor.get_node(b) as MeshInstance3D).gi_mode = GeometryInstance3D.GI_MODE_DYNAMIC
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		mi.gi_mode = GeometryInstance3D.GI_MODE_DYNAMIC
		mi.layers = 1 | 2
	# Figurenlicht nur auf Ebene 2 (der Dachs), Ziel: Brust des Dachses in der Endeinstellung
	var ck := $CharKey as SpotLight3D
	ck.light_cull_mask = 2
	ck.look_at(Vector3(-1.45, 0.6, 1.7))

	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	player.play("Walk")
	player.speed_scale = WALK_RATE
	_setup_measure()
	badger.position = Vector3(float(args.get("start_x", str(START_X))), FLOOR_Y, 1.2)

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	var to_cam := camera.global_position - rotor.global_position
	beam_yaw0 = atan2(-to_cam.x, -to_cam.z) - TAU * BEAM_FACING_T / BEAM_PERIOD
	_build_smoke()

	if args.has("cam"):
		var v: PackedFloat64Array = PackedFloat64Array(Array(args["cam"].split(",")).map(func(s): return float(s)))
		camera.fov = v[6]
		camera.look_at_from_position(Vector3(v[0], v[1], v[2]), Vector3(v[3], v[4], v[5]))
		fixed_cam = true
	if args.has("no-ui"):
		$UILayer.visible = false
	if args.has("measure"):
		RenderingServer.frame_pre_draw.connect(_measure)
	if args.has("mask"):
		_mask_mode()
	if args.has("bench"):
		bench_frames = int(args["bench"])
		RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(), true)
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
		Engine.max_fps = 0
	var t0 := float(args.get("t0", "0"))
	if t0 > 0.0:
		_advance(t0)
	_update(0.0)


func _parse_args() -> void:
	for a in OS.get_cmdline_user_args():
		var s: String = a.trim_prefix("--")
		var i := s.find("=")
		if i >= 0:
			args[s.substr(0, i)] = s.substr(i + 1)
		else:
			args[s] = "1"


## Zeit vorspulen in festen Schritten (wie die Aufnahme), damit Lauf und Animation stimmen.
func _advance(t0: float) -> void:
	var dt := 1.0 / 30.0
	while t < t0 - 1e-6:
		t += dt
		_update_badger(dt)


func _process(delta: float) -> void:
	var fr := Engine.get_process_frames()
	if not args.has("no-ramp") and env.sdfgi_enabled:
		var ramp: Array = SDFGI_RAMP
		if args.has("ramp"):   # Abstimmung: --ramp=a,b,c,…
			ramp = Array(args["ramp"].split(",")).map(func(v): return float(v))
		env.sdfgi_energy = ramp[fr] if fr < ramp.size() else 1.0
	t += delta
	_update(delta)
	if bench_frames > 0:
		_bench_step()


func _update(delta: float) -> void:
	_update_badger(delta)
	if not fixed_cam:
		_update_camera()
	# Tiefenschärfe nur in der halbnahen Einstellung: Hintergrund (Leuchtturm 30 m) leicht weich
	var attr := $WorldEnvironment.camera_attributes as CameraAttributesPractical
	attr.dof_blur_amount = DOF_AMOUNT * smoothstep(2.8, 3.9, t)
	var k := 0
	for b in boats:
		var ph := 1.7 * k
		var roll := deg_to_rad(1.6) * sin(TAU * t / 3.8 + ph)
		var pitch := deg_to_rad(0.7) * sin(TAU * t / 5.1 + 0.8 + ph)
		var heave := 0.03 * sin(TAU * t / 4.3 + 2.1 + ph)
		var local := Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		(harbor.get_node(b) as Node3D).transform = boats[b] * local
		k += 1
	if water_material:
		water_material.set_shader_parameter("time_s", t)
	mist_mat.set_shader_parameter("time_s", t)
	for hv in haze_vols:
		(hv.material as ShaderMaterial).set_shader_parameter("time_s", t)

	# Flackern: Omni (Pfosten, Pflaster, Pfütze, Dunst) und Glas schwanken gemeinsam. Die Emission des
	# Glases bleibt unter der Sättigung von ACES, sonst schluckt die Tonwertkurve das Flackern.
	var f := clampf(0.72 + 0.45 * lantern_noise.get_noise_1d(t * 6.0) + 0.12 * lantern_noise.get_noise_1d(t * 29.0 + 50.0), 0.3, 1.15)
	if args.has("no-flicker"):
		f = 0.72
	f = f * f / 0.72   # quadratisch: doppelte relative Schwankung, etwa gleicher Mittelwert
	lantern_omni.light_energy = LANTERN_ENERGY * f
	lantern_mat.emission_energy_multiplier = LANTERN_EMISSION * f

	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position).normalized()
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), 24.0)
	lamp_mat.emission_energy_multiplier = 14.0 + 60.0 * facing
	lamp_omni.light_energy = 3.0 + 5.0 * facing

	_update_smoke()
	if ui.has_method("set_time"):
		ui.set_time(t)


# --- Kamera ----------------------------------------------------------------------------------
## Totale (Häuschen, Hafenbecken, Leuchtturm) mit langsamer Fahrt, dann Kranfahrt hinunter zur
## halbnahen Einstellung auf Augenhöhe des Dachses. Werte mit scripts/plan_shot.py gerechnet.
const DOF_AMOUNT := 0.035
const CAM_KEYS := [
	# t, Position, Ziel, fov
	[0.0, Vector3(-3.0, 2.4, 11.2), Vector3(-1.2, 1.9, -6.0), 52.0],
	[1.5, Vector3(-2.8, 2.25, 10.4), Vector3(-1.1, 1.85, -6.0), 52.0],
	[3.9, Vector3(-0.95, 1.2, 5.0), Vector3(-0.1, 1.04, -0.4), 52.0],
	[6.0, Vector3(-0.87, 1.2, 4.85), Vector3(-0.03, 1.05, -0.4), 52.0],
]


func _update_camera() -> void:
	var k := 0
	while k < CAM_KEYS.size() - 2 and t >= CAM_KEYS[k + 1][0]:
		k += 1
	var a: Array = CAM_KEYS[k]
	var b: Array = CAM_KEYS[k + 1]
	var u := clampf((t - a[0]) / (b[0] - a[0]), 0.0, 1.0)
	var e := u
	if k == 1:
		e = u * u * u * (u * (u * 6.0 - 15.0) + 10.0)   # Kranfahrt weich an- und ausfahren
	else:
		e = u * (2.0 - u) if k == 0 else u * u * (3.0 - 2.0 * u)
	var pa: Vector3 = a[1]
	var pb: Vector3 = b[1]
	var pos := pa.lerp(pb, e)
	if k == 1:
		pos.y += 0.35 * sin(PI * e)   # leichter Bogen: erst vor, dann hinunter
	var qa := Basis.looking_at(a[2] - a[1], Vector3.UP).get_rotation_quaternion()
	var qb := Basis.looking_at(b[2] - b[1], Vector3.UP).get_rotation_quaternion()
	camera.global_transform = Transform3D(Basis(qa.slerp(qb, e)), pos)
	camera.fov = lerpf(a[3], b[3], e)


# --- Dachs ------------------------------------------------------------------------------------
func _update_badger(delta: float) -> void:
	# Der AnimationPlayer läuft von Hand (callback manual): erst die Pose dieses Bildes, dann die
	# Wurzel so setzen, dass der Standfuß stehen bleibt.
	if phase == 0:
		walk_rate = WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, t))
		player.speed_scale = walk_rate
	player.advance(delta)
	if phase == 0:
		# Vorschub in Blickrichtung mit 0,367 m/s × Abspieltempo (die Pose läuft auf der Stelle)
		var fwd := Vector3(cos(badger.rotation.y), 0.0, -sin(badger.rotation.y))
		badger.position += fwd * WALK_SPEED * walk_rate * delta
		# Abbiegen im Laufen: Drehung um den Bodenpunkt des Standfußes
		var r_new := deg_to_rad(TURN_DEG) * smoothstep(TURN_T0, TURN_T1, t)
		var dr := r_new - badger.rotation.y
		if absf(dr) > 0.0:
			var pivot = _stance_point()
			if pivot != null:
				var off: Vector3 = badger.position - pivot
				badger.position = (pivot as Vector3) + off.rotated(Vector3.UP, dr)
			badger.rotation.y = r_new
		if t >= IDLE_T:
			phase = 1
			# Walk einfrieren, bevor er ausgeblendet wird: Lief er in der Überblendung weiter, schwang
			# der Fuß noch 9 cm nach vorn, setzte auf und rutschte zurück in die Idle-Stellung. In der
			# Durchgangsphase steht der Schwungfuß schon fast über seinem Idle-Platz (5 mm daneben)
			# und senkt sich in der Überblendung nur noch ab.
			player.play("Walk", 0.0, 0.0)
			player.speed_scale = 1.0
			player.play("Idle", BLEND_IDLE)
			player.advance(0.0)   # Start verbuchen
			player.advance(delta) # erster Schritt der Überblendung schon in diesem Bild (sonst ein Standbild)
			# Fuß festhalten, der beim Umschalten aufsteht (sonst rutscht er in die Idle-Stellung)
			lock_side = "L" if _foot_height("L") <= _foot_height("R") else "R"
			lock_point = _foot_point(lock_side)
	else:
		if phase == 1 and t < IDLE_T + BLEND_IDLE + 0.05:
			var cur := _foot_point(lock_side)
			badger.position += Vector3(lock_point.x - cur.x, 0.0, lock_point.z - cur.z)
		if phase == 1 and t >= WAVE_T:
			phase = 2
			player.play("Wave", 0.25)
		elif phase == 2 and t >= WAVE_T + WAVE_LEN - 0.1:
			phase = 3
			player.play("Idle", 0.3)


func _foot_point(side: String) -> Vector3:
	return (_probe_world("heel." + side) + _probe_world("toe." + side)) * 0.5


func _foot_height(side: String) -> float:
	return maxf(_probe_world("heel." + side).y, _probe_world("toe." + side).y)


## Bodenpunkt des Standfußes (Welt): Mittel der Fußpunkte unter 1 cm; null, wenn kein Fuß aufsteht.
func _stance_point() -> Variant:
	if _skel == null:
		return null
	var pts: Array[Vector3] = []
	for k in ["heel.L", "toe.L", "heel.R", "toe.R"]:
		var w := _probe_world(k)
		if w.y - FLOOR_Y < 0.01:
			pts.append(w)
	if pts.is_empty():
		return null
	var m := Vector3.ZERO
	for w in pts:
		m += w
	m /= float(pts.size())
	m.y = badger.position.y
	return m


# --- Schalter ---------------------------------------------------------------------------------
func _apply_switches() -> void:
	if args.has("no-sdfgi"):
		env.sdfgi_enabled = false
	if args.has("no-ssr"):
		env.ssr_enabled = false
	if args.has("no-ssao"):
		env.ssao_enabled = false
	if args.has("no-ssil"):
		env.ssil_enabled = false
	if args.has("no-volfog"):
		env.volumetric_fog_enabled = false
	if args.has("no-mist") or args.has("no-volfog"):
		$SeaMist.visible = false
	if args.has("no-haze") or args.has("no-volfog"):
		for hv in haze_vols:
			hv.visible = false
	if args.has("no-dof"):
		($WorldEnvironment.camera_attributes as CameraAttributesPractical).dof_blur_far_enabled = false
	if args.has("no-glow"):
		env.glow_enabled = false
	if args.has("no-taa"):
		get_viewport().use_taa = false


func _setup_sun() -> void:
	# Richtung zur Sonne aus dem HDRI (build_textures.py: 20° links der Blickrichtung, 2° hoch);
	# etwas höher gelegt, damit Schatten nicht endlos werden.
	var to_sun := Vector3(-0.342, 0.0, -0.939).normalized()
	to_sun.y = tan(deg_to_rad(6.0))
	to_sun = to_sun.normalized()
	sun.look_at_from_position(Vector3.ZERO, -to_sun, Vector3.UP)


# --- Boden ------------------------------------------------------------------------------------
func _build_floor() -> void:
	var mat: Material
	var fm := ShaderMaterial.new()
	fm.shader = FLOOR
	mat = fm
	fm.set_shader_parameter("tex_a", _tex("cobble_a"))
	fm.set_shader_parameter("tex_n", _tex("cobble_n"))
	fm.set_shader_parameter("tex_orm", _tex("cobble_orm"))
	fm.set_shader_parameter("tex_h", _tex("cobble_h"))
	fm.set_shader_parameter("puddle_noise", _noise_texture(256, 7, 0.02, false))
	fm.set_shader_parameter("use_pom", not args.has("no-pom"))
	if args.has("flat"):
		var sm := StandardMaterial3D.new()
		sm.albedo_color = Color("#8C877D")
		sm.roughness = 0.9
		mat = sm
	# Kaifläche: Hauptfläche und der Teil links hinter dem Häuschen (Maße aus harbor.glb)
	var rects := [Rect2(-12.94, -0.41, 20.35, 8.35), Rect2(-12.94, -3.54, 7.35, 3.13)]
	for ri in rects.size():
		var r: Rect2 = rects[ri]
		var pm := PlaneMesh.new()
		pm.size = r.size
		var mi := MeshInstance3D.new()
		mi.mesh = pm
		mi.material_override = mat
		mi.position = Vector3(r.position.x + r.size.x / 2.0, FLOOR_Y, r.position.y + r.size.y / 2.0)
		mi.name = "Floor%d" % ri
		add_child(mi)


# --- Materialien ------------------------------------------------------------------------------
func _style_materials(root: Node) -> void:
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		var owner_name := _owner_name(mi)
		for i in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(i) as StandardMaterial3D
			if src == null:
				continue
			var cfg = _lookup(owner_name, src.resource_name)
			if cfg == null:
				continue
			mi.set_surface_override_material(i, _make_material(owner_name, src, cfg))


## Objektname für die Tabelle: Kinder (Fenster, Laternenglas) zählen zum eigenen Namen.
func _owner_name(mi: MeshInstance3D) -> String:
	return String(mi.name)


func _lookup(obj: String, mat: String):
	if MATS.has(obj + "/" + mat):
		return MATS[obj + "/" + mat]
	for key in MATS:
		var parts: PackedStringArray = key.split("/")
		if parts[1] == mat and parts[0].ends_with("*") and obj.begins_with(parts[0].trim_suffix("*")) and parts[0] != "*":
			return MATS[key]
	if MATS.has("*/" + mat):
		return MATS["*/" + mat]
	return null


func _make_material(obj: String, src: StandardMaterial3D, cfg: Dictionary) -> Material:
	var key := obj + "/" + src.resource_name
	if _cache.has(key):
		return _cache[key]
	if args.has("flat"):
		var m0 := src.duplicate() as StandardMaterial3D
		_cache[key] = m0
		return m0
	var m := ShaderMaterial.new()
	m.shader = SURFACE
	var tex: String = cfg["tex"]
	m.set_shader_parameter("tex_a", _tex(tex + "_a"))
	m.set_shader_parameter("tex_n", _tex(tex + "_n"))
	m.set_shader_parameter("tex_orm", _tex(tex + "_orm"))
	m.set_shader_parameter("mapping", cfg.get("map", 3))
	m.set_shader_parameter("tile_m", cfg.get("tile", 2.0))
	m.set_shader_parameter("tile_aspect", cfg.get("aspect", Vector2.ONE))
	m.set_shader_parameter("rot90", cfg.get("rot", false))
	m.set_shader_parameter("cyl_radius", cfg.get("cyl", 0.3))
	m.set_shader_parameter("albedo_gain", cfg.get("gain", 1.0))
	m.set_shader_parameter("rough_mul", cfg.get("rough_mul", 1.0))
	m.set_shader_parameter("rough_add", cfg.get("rough_add", 0.0))
	m.set_shader_parameter("macro_amount", cfg.get("macro", 0.0))
	m.set_shader_parameter("damp_top", cfg.get("damp", 0.0))
	m.set_shader_parameter("normal_strength", cfg.get("nstr", 1.0))
	m.set_shader_parameter("rim_amount", cfg.get("rim", 0.0))
	if cfg.has("wet"):
		m.set_shader_parameter("wet_top", cfg["wet"])
	if cfg.has("algae"):
		m.set_shader_parameter("algae_top", cfg["algae"])
	if cfg.get("detail", false):
		m.set_shader_parameter("detail_mode", true)
		m.set_shader_parameter("tint", cfg.get("tint", src.albedo_color))
	else:
		m.set_shader_parameter("tint", cfg.get("tint", Color.WHITE))
	if cfg.has("top"):
		m.set_shader_parameter("use_top", true)
		m.set_shader_parameter("top_a", _tex(cfg["top"] + "_a"))
		m.set_shader_parameter("top_n", _tex(cfg["top"] + "_n"))
		m.set_shader_parameter("top_orm", _tex(cfg["top"] + "_orm"))
		m.set_shader_parameter("top_tile_m", cfg.get("top_tile", 1.5))
		m.set_shader_parameter("top_tint", Color(0.8, 0.8, 0.82))
	_cache[key] = m
	return m


func _tex(name: String) -> Texture2D:
	if not _tex_cache.has(name):
		var path := TEX + name + ".jpg"
		if not ResourceLoader.exists(path):
			path = TEX + name + ".png"   # aus Code erzeugt (scripts/make_knit.py)
		_tex_cache[name] = load(path)
	return _tex_cache[name]


## Nahtlose Rauschtextur (synchron erzeugt, damit das erste Bild schon stimmt).
func _noise_texture(size: int, seed_: int, freq: float, normal_map: bool, strength := 4.0) -> ImageTexture:
	var n := FastNoiseLite.new()
	n.seed = seed_
	n.noise_type = FastNoiseLite.TYPE_PERLIN
	n.frequency = freq
	n.fractal_type = FastNoiseLite.FRACTAL_FBM
	n.fractal_octaves = 4
	var img := n.get_seamless_image(size, size, false, false, 0.1, true)
	img.convert(Image.FORMAT_RGBA8)
	if normal_map:
		img.bump_map_to_normal_map(strength)
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func _setup_water() -> void:
	water_material = ShaderMaterial.new()
	water_material.shader = WATER
	water_material.set_shader_parameter("wave_n1", _noise_texture(512, 11, 0.012, true, 5.0))
	water_material.set_shader_parameter("wave_n2", _noise_texture(512, 23, 0.02, true, 3.0))
	var sea := harbor.get_node("Sea") as MeshInstance3D
	sea.set_surface_override_material(0, water_material)
	sea.extra_cull_margin = 1.0


func _setup_glass() -> void:
	lantern_mat = _glass(harbor.find_child("LanternGlass", true, false), Color(1.0, 0.62, 0.3), 9.0)
	lamp_mat = _glass(harbor.find_child("LighthouseLamp", true, false), Color(1.0, 0.85, 0.6), 14.0)
	window_mat = _glass(harbor.find_child("CottageWindow", true, false), Color(1.0, 0.6, 0.3), 5.0)
	for g in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
		(harbor.find_child(g, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


func _glass(mi: MeshInstance3D, col: Color, energy: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.05, 0.04, 0.03)
	m.roughness = 0.08
	m.metallic_specular = 0.6
	m.emission_enabled = true
	m.emission = col
	m.emission_energy_multiplier = energy
	mi.set_surface_override_material(0, m)
	return m


# --- Fell (Schalen) ---------------------------------------------------------------------------
## Kopiert die Fellflächen (FurDark, FurLight) FUR_SHELLS-mal in ein eigenes Mesh mit derselben
## Haut (Skin) wie die Figur. Winzige Teile (Glanzpunkte der Augen nutzen FurLight) bleiben ohne
## Fell; um die Augen und im Gesicht wird das Fell kürzer (COLOR.g).
func _build_fur() -> void:
	var src := badger.find_child("Badger", true, false) as MeshInstance3D
	var mesh := src.mesh
	var eyes: Array[Vector3] = []
	for i in mesh.get_surface_count():
		var m := mesh.surface_get_material(i)
		if m and m.resource_name == "Eye":
			var v: PackedVector3Array = mesh.surface_get_arrays(i)[Mesh.ARRAY_VERTEX]
			var acc := {-1: [Vector3.ZERO, 0], 1: [Vector3.ZERO, 0]}
			for p in v:
				var k := 1 if p.z > 0.0 else -1
				acc[k][0] += p
				acc[k][1] += 1
			for k in acc:
				if acc[k][1] > 0:
					eyes.append(acc[k][0] / float(acc[k][1]))
	var fur_mesh := ArrayMesh.new()
	var mats: Array[Material] = []
	for i in mesh.get_surface_count():
		var m := mesh.surface_get_material(i) as StandardMaterial3D
		if m == null or not (m.resource_name in ["FurDark", "FurLight", "Scarf"]):
			continue
		var is_scarf := m.resource_name == "Scarf"
		var arr := mesh.surface_get_arrays(i)
		var pos: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
		var keep := _big_components(pos, idx, 0.035)
		var lenf := PackedFloat32Array()
		lenf.resize(pos.size())
		for j in pos.size():
			lenf[j] = 1.0 if is_scarf else _fur_length(pos[j], eyes)
		var out := []
		out.resize(Mesh.ARRAY_MAX)
		var n := pos.size()
		var colors := PackedColorArray()
		var new_idx := PackedInt32Array()
		for key in [Mesh.ARRAY_VERTEX, Mesh.ARRAY_NORMAL, Mesh.ARRAY_TANGENT, Mesh.ARRAY_TEX_UV,
				Mesh.ARRAY_TEX_UV2, Mesh.ARRAY_BONES, Mesh.ARRAY_WEIGHTS]:
			if arr[key] == null:
				continue
			var base = arr[key]
			var acc = base.duplicate()
			for s_ in FUR_SHELLS - 1:
				acc.append_array(base)
			out[key] = acc
		for s_ in FUR_SHELLS:
			var h := float(s_ + 1) / float(FUR_SHELLS)
			for j in n:
				colors.append(Color(h, lenf[j], 0.0, 1.0))
			for t_ in range(0, idx.size(), 3):
				if keep[idx[t_]]:
					new_idx.append(idx[t_] + s_ * n)
					new_idx.append(idx[t_ + 1] + s_ * n)
					new_idx.append(idx[t_ + 2] + s_ * n)
		out[Mesh.ARRAY_COLOR] = colors
		out[Mesh.ARRAY_INDEX] = new_idx
		fur_mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, out)
		var fm := ShaderMaterial.new()
		fm.shader = FUR
		var base_col := m.albedo_color
		var dark := m.resource_name == "FurDark"
		fm.set_shader_parameter("fur_color", base_col * (0.85 if dark else 0.92))
		fm.set_shader_parameter("tip_color", Color(0.56, 0.53, 0.5) if dark else Color(1.0, 0.97, 0.9))
		fm.set_shader_parameter("fur_len", FUR_LEN)
		mats.append(fm)
		if is_scarf:
			# Wollflaum auf dem Strickschal: kurz, dicht, dünn; die Strickfläche darunter bleibt
			fm.set_shader_parameter("fur_color", base_col * 0.9)
			fm.set_shader_parameter("tip_color", Color(0.85, 0.42, 0.4))
			fm.set_shader_parameter("fur_len", 0.006)
			fm.set_shader_parameter("density", 420.0)
			fm.set_shader_parameter("thickness", 0.7)
			fm.set_shader_parameter("gravity", 0.2)
			fm.set_shader_parameter("root_dark", 0.75)
			continue
		# Grundfläche unter dem Fell: dunkler (Verdeckung zwischen den Haaren), matt
		var bm := StandardMaterial3D.new()
		bm.albedo_color = base_col * (0.5 if dark else 0.62)
		bm.roughness = 0.95
		bm.rim_enabled = true
		bm.rim = 0.3
		bm.rim_tint = 0.6
		src.set_surface_override_material(i, bm)
	if args.has("stats"):
		var tris := 0
		for k in fur_mesh.get_surface_count():
			tris += (fur_mesh.surface_get_arrays(k)[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3
		print("STATS fur_triangles=%d shells=%d" % [tris, FUR_SHELLS])
	var fur := MeshInstance3D.new()
	fur.name = "Fur"
	fur.mesh = fur_mesh
	for k in mats.size():
		fur.set_surface_override_material(k, mats[k])
	src.get_parent().add_child(fur)
	fur.skin = src.skin
	fur.skeleton = NodePath("..")
	fur.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	fur.gi_mode = GeometryInstance3D.GI_MODE_DYNAMIC
	fur.layers = src.layers


## true für Punkte in zusammenhängenden Teilen, deren Ausdehnung größer als min_size ist.
func _big_components(pos: PackedVector3Array, idx: PackedInt32Array, min_size: float) -> PackedByteArray:
	# Array (Referenz), damit das Lambda und die Schleifen dieselben Daten ändern
	var parent: Array[int] = []
	parent.resize(pos.size())
	for j in pos.size():
		parent[j] = j
	var find := func(a: int) -> int:
		while parent[a] != a:
			parent[a] = parent[parent[a]]
			a = parent[a]
		return a
	for t_ in range(0, idx.size(), 3):
		var r0: int = find.call(idx[t_])
		for e in [1, 2]:
			var r1: int = find.call(idx[t_ + e])
			if r1 != r0:
				parent[r1] = r0
	# gleiche Position (UV-Nähte) ebenfalls verbinden
	var by_pos := {}
	for j in pos.size():
		var key := Vector3i(roundi(pos[j].x * 10000.0), roundi(pos[j].y * 10000.0), roundi(pos[j].z * 10000.0))
		if by_pos.has(key):
			var a: int = find.call(j)
			var b: int = find.call(by_pos[key])
			if a != b:
				parent[a] = b
		else:
			by_pos[key] = j
	var lo := {}
	var hi := {}
	for j in pos.size():
		var r: int = find.call(j)
		if not lo.has(r):
			lo[r] = pos[j]
			hi[r] = pos[j]
		else:
			lo[r] = (lo[r] as Vector3).min(pos[j])
			hi[r] = (hi[r] as Vector3).max(pos[j])
	var keep := PackedByteArray()
	keep.resize(pos.size())
	for j in pos.size():
		var r: int = find.call(j)
		keep[j] = 1 if ((hi[r] as Vector3) - (lo[r] as Vector3)).length() > min_size else 0
	return keep


## Fellänge 0..1 an einem Punkt der Ruhepose: Körper voll, Kopf kurz, um die Augen fast null.
func _fur_length(p: Vector3, eyes: Array[Vector3]) -> float:
	var f := 1.0
	f = minf(f, lerpf(1.0, 0.45, smoothstep(0.62, 0.70, p.y)))
	for e in eyes:
		f = minf(f, lerpf(0.0, 0.45, smoothstep(0.022, 0.06, p.distance_to(e))))
	f = minf(f, lerpf(0.5, 1.0, smoothstep(0.03, 0.09, p.y)))
	return f


# --- Lichter an die Empties hängen ------------------------------------------------------------
func _attach_to_empties() -> void:
	for holder in $Attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt in harbor.glb" % holder.name)
			continue
		for c in holder.get_children():
			c.reparent(target, false)


# --- Rauch ------------------------------------------------------------------------------------
func _build_smoke() -> void:
	var img := Image.create(128, 128, false, Image.FORMAT_RGBA8)
	var n := FastNoiseLite.new()
	n.seed = SEED
	n.frequency = 0.05
	n.fractal_octaves = 4
	for y in 128:
		for x in 128:
			var d := Vector2(x - 63.5, y - 63.5).length() / 63.5
			var fall := clampf(1.0 - d, 0.0, 1.0)
			var a := fall * fall * (0.55 + 0.45 * n.get_noise_2d(x, y))
			img.set_pixel(x, y, Color(1, 1, 1, clampf(a, 0.0, 1.0)))
	img.generate_mipmaps()
	var tex := ImageTexture.create_from_image(img)
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = tex
	mat.albedo_color = Color(0.36, 0.36, 0.4)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	mat.roughness = 1.0
	mat.proximity_fade_enabled = true
	mat.proximity_fade_distance = 0.15   # weich am Schornsteinkopf, ohne den Ansatz zu verschlucken
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	var anchor := harbor.find_child("ChimneySmoke", true, false) as Node3D
	for i in SMOKE_PUFFS:
		var p := MeshInstance3D.new()
		p.mesh = quad
		p.material_override = mat
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		anchor.add_child(p)
		smoke.append(p)
		smoke_jitter.append(Vector3(rng.randf_range(-0.15, 0.15), rng.randf_range(0.8, 1.2), rng.randf_range(-0.1, 0.1)))


func _update_smoke() -> void:
	for i in smoke.size():
		var age := fposmod(t + float(i) * SMOKE_LIFE / SMOKE_PUFFS, SMOKE_LIFE) / SMOKE_LIFE
		var j := smoke_jitter[i]
		var p := smoke[i]
		# Start im Schornsteinkopf (Austritt 4,9 m, Kopf bis etwa 4,8 m), damit der Rauch sichtbar aus
		# der Öffnung steigt; kurzes Einblenden, der Kopf verdeckt den unteren Teil des ersten Ballens.
		p.position = Vector3(1.6 * age * age + j.x * age, SMOKE_Y0 + 2.4 * age * j.y, j.z * age)
		var s := lerpf(0.45, 1.9, sqrt(age))
		p.scale = Vector3(s, s, s)
		p.transparency = 1.0 - 0.7 * smoothstep(0.0, 0.03, age) * (1.0 - smoothstep(0.4, 1.0, age))


# --- Leistungsmessung -------------------------------------------------------------------------
func _bench_step() -> void:
	var vp := get_viewport().get_viewport_rid()
	var gpu := RenderingServer.viewport_get_measured_render_time_gpu(vp)
	var cpu := RenderingServer.viewport_get_measured_render_time_cpu(vp) + RenderingServer.get_frame_setup_time_cpu()
	if Engine.get_process_frames() > 90:
		var now := Time.get_ticks_usec()
		bench_samples.append([gpu, cpu, (now - bench_last_us) / 1000.0])
	bench_last_us = Time.get_ticks_usec()
	if bench_samples.size() >= bench_frames:
		var g: Array = bench_samples.map(func(s): return s[0])
		var c: Array = bench_samples.map(func(s): return s[1])
		g.sort()
		c.sort()
		var fr: Array = bench_samples.map(func(s): return s[2])
		fr.sort()
		var res := {"gpu_ms_median": g[g.size() / 2], "gpu_ms_p90": g[int(g.size() * 0.9)],
				"cpu_ms_median": c[c.size() / 2], "frame_ms_median": fr[fr.size() / 2], "frames": g.size(),
				"switches": args.keys(), "renderer": RenderingServer.get_current_rendering_method(),
				"adapter": RenderingServer.get_video_adapter_name()}
		print("BENCH " + JSON.stringify(res))
		get_tree().quit()


# --- Messen (scripts/measure_badger.py) -------------------------------------------------------
var _skel: Skeleton3D
var _probe := {}   # Name -> [Knochenindex, lokaler Punkt]


func _setup_measure() -> void:
	_skel = badger.find_child("Skeleton3D", true, false) as Skeleton3D
	# Punkte in Ruhepose (aus badger_notes.md): Ferse unter dem Fußknochen, Zehe an seiner Spitze,
	# beide 3 mm über dem Boden; Kopf = Mützendeckel
	var pts := {
		"heel.L": ["foot.L", Vector3(-0.02, 0.003, -0.125)], "toe.L": ["foot.L", Vector3(0.13, 0.003, -0.125)],
		"heel.R": ["foot.R", Vector3(-0.02, 0.003, 0.125)], "toe.R": ["foot.R", Vector3(0.13, 0.003, 0.125)],
		"head": ["head", Vector3(0.0, 1.011, 0.0)],
	}
	for k in pts:
		var bi := _skel.find_bone(pts[k][0])
		var rest := _skel.get_bone_global_rest(bi)
		_probe[k] = [bi, rest.affine_inverse() * (pts[k][1] as Vector3)]


func _probe_world(k: String) -> Vector3:
	return _skel.global_transform * _skel.get_bone_global_pose(_probe[k][0]) * (_probe[k][1] as Vector3)


func _measure() -> void:
	var line := "M %.4f rot %.2f %.4f %.4f 0 0" % [t, rad_to_deg(badger.rotation.y), badger.position.x, badger.position.z]
	line += " ph %.4f %d 0 0 0" % [player.current_animation_position, phase]
	for k in ["heel.L", "toe.L", "heel.R", "toe.R", "head"]:
		var w := _probe_world(k)
		var sp := camera.unproject_position(w)
		line += " %s %.4f %.4f %.4f %.2f %.2f" % [k, w.x, w.y - FLOOR_Y, w.z, sp.x, sp.y]
	print(line)


func _mask_mode() -> void:
	harbor.visible = false
	$SeaMist.visible = false
	for hv in haze_vols:
		hv.visible = false
	$UILayer.visible = false
	for n in get_children():
		if n.name.begins_with("Floor"):
			n.visible = false
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color.BLACK
	for prop in ["glow_enabled", "fog_enabled", "volumetric_fog_enabled", "sdfgi_enabled", "ssr_enabled",
			"ssao_enabled", "ssil_enabled"]:
		env.set(prop, false)
	($WorldEnvironment.camera_attributes as CameraAttributesPractical).dof_blur_far_enabled = false
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color.WHITE
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		if mi.name == "Fur":
			mi.visible = false
			continue
		for i in mi.mesh.get_surface_count():
			mi.set_surface_override_material(i, white)
	for p in smoke:
		p.visible = false
