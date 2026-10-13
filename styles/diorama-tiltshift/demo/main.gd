extends Node3D
## Diorama & Miniatur: der Hafen von Lornholm als Modell auf einem Holzsockel, der Dachs als Spielzeugfigur.
##
## Materialien werden per glTF-Materialname durch Modellbau-Shader ersetzt (Kunststoff, Filz mit Fasern,
## Holz, bemalter Gips, Streusand, Gießharz). Die Kamera beginnt mit einer Totale auf das ganze Modell und
## fährt dann schräg von oben an den Dachs heran; die Schärfentiefe folgt dem Dachs (Tilt-Shift-Eindruck).
## Alles hängt an der aufsummierten Zeit t und festen Seeds: Jede Aufnahme ist Bild für Bild gleich.
##
## Schalter nach "--" (nur für Prüfungen): --t0=SEK (Startzeit), --no-dof, --no-shells, --no-ui, --no-lamps,
## --no-gulls, --no-wires, --mask (Dachs weiß, alles andere schwarz; für die Fußmessung), --measure (Fuß- und
## Kopfpunkte je Bild ausgeben), --verbose, --cam=px,py,pz,tx,ty,tz,fov (feste Kamera).

const TOY := preload("res://shaders/toy.gdshader")
const SHELL := preload("res://shaders/felt_shell.gdshader")
const RESIN := preload("res://shaders/resin_water.gdshader")
const SECTION := preload("res://shaders/section_land.gdshader")
const BACKDROP := preload("res://shaders/backdrop.gdshader")
const COTTON := preload("res://shaders/cotton.gdshader")
const WIRE := preload("res://shaders/wire.gdshader")

# --- Materialtabelle: Name -> Art und Werte (siehe toy.gdshader) -------------------------------------
# kind: 0 Kunststoff, 1 Filz, 2 Holz, 3 bemalter Gips, 4 Streusand, 5 Fels, 6 Metall, 7 Leuchtdiode, 8 Papier
const HARBOR_MATS := {
	"Stone":       {"kind": 3, "albedo": Color("cdbb9e"), "roughness": 0.85},
	"StoneDark":   {"kind": 3, "albedo": Color("86786a"), "roughness": 0.85},
	"Wood":        {"kind": 2, "albedo": Color("d8ad78"), "albedo2": Color("a8743f"), "roughness": 0.7, "scale": 1.3},
	"WoodDark":    {"kind": 2, "albedo": Color("7a5236"), "albedo2": Color("4c3020"), "roughness": 0.65, "scale": 1.3},
	"WhitePaint":  {"kind": 0, "albedo": Color("f2ece0"), "roughness": 0.3, "clearcoat": 0.4, "sss": 0.15},
	"RedPaint":    {"kind": 0, "albedo": Color("d23a2c"), "roughness": 0.28, "clearcoat": 0.5, "sss": 0.15},
	"Roof":        {"kind": 1, "albedo": Color("4f5d80"), "albedo2": Color("38425e"), "rim": 0.5},
	"Glass":       {"kind": 7, "albedo": Color("ffe2b0"), "roughness": 0.1, "emission_color": Color("ffb85c"), "emission_energy": 3.0},
	"Rope":        {"kind": 1, "albedo": Color("d6bb88"), "albedo2": Color("a88a5a"), "rim": 0.3},
	"Metal":       {"kind": 6, "albedo": Color("44484f"), "albedo2": Color("8a8f98"), "roughness": 0.4, "metallic": 0.55},
	"Rock":        {"kind": 5, "albedo": Color("a59a8e"), "albedo2": Color("5a524d"), "roughness": 0.9},
	"Sand":        {"kind": 4, "albedo": Color("e0c792"), "roughness": 0.95},
	"Grass":       {"kind": 1, "albedo": Color("6e9a48"), "albedo2": Color("456e2e"), "rim": 0.6},
	"Seabed":      {"kind": 4, "albedo": Color("9e8a66"), "roughness": 1.0},
	"PlinthWood":  {"kind": 2, "albedo": Color("6a3f22"), "albedo2": Color("2f1a0d"), "roughness": 0.42, "clearcoat": 1.0, "clearcoat_gloss": 0.85, "scale": 0.7},
	"PlaqueBrass": {"kind": 6, "albedo": Color("f0c878"), "albedo2": Color("c89a48"), "roughness": 0.38, "metallic": 0.6},
	"GullWhite":   {"kind": 0, "albedo": Color("f4f2ec"), "roughness": 0.35, "sss": 0.2},
	"GullGrey":    {"kind": 0, "albedo": Color("8a95a3"), "roughness": 0.35},
	"GullBeak":    {"kind": 0, "albedo": Color("f2a838"), "roughness": 0.3},
}
const BADGER_MATS := {
	"FurDark":  {"kind": 0, "albedo": Color("4a3f3b"), "roughness": 0.36, "clearcoat": 0.25, "sss": 0.15},
	"FurLight": {"kind": 0, "albedo": Color("f4e8d2"), "roughness": 0.34, "clearcoat": 0.25, "sss": 0.3},
	"Cap":      {"kind": 0, "albedo": Color("4f6a36"), "roughness": 0.32, "clearcoat": 0.3, "sss": 0.1},
	"Brass":    {"kind": 6, "albedo": Color("e0b04e"), "albedo2": Color("e0b04e"), "roughness": 0.25, "metallic": 1.0},
	"Vest":     {"kind": 0, "albedo": Color("5f7a3a"), "roughness": 0.32, "clearcoat": 0.3, "sss": 0.1},
	"Shirt":    {"kind": 0, "albedo": Color("f2e2c2"), "roughness": 0.34, "clearcoat": 0.2, "sss": 0.25},
	"Scarf":    {"kind": 1, "albedo": Color("d0382f"), "albedo2": Color("9e2420"), "rim": 0.7},
	"Satchel":  {"kind": 0, "albedo": Color("85492c"), "roughness": 0.4, "clearcoat": 0.2},
	"Parcel":   {"kind": 8, "albedo": Color("cf9a62")},
	"Nose":     {"kind": 0, "albedo": Color("2a201d"), "roughness": 0.12, "clearcoat": 1.0},
	"Eye":      {"kind": 0, "albedo": Color("1c120c"), "roughness": 0.06, "clearcoat": 1.0},
}
const SHELLS := 8
## Ruderhaus von Boot A: Fenster und Positionslampe (im gemeinsamen Modell Material "Metal") als Leuchtdioden
const BOAT_LED := {"kind": 7, "albedo": Color("ffe2b0"), "roughness": 0.1, "emission_color": Color("ffbf6e"), "emission_energy": 2.6}

# --- Dachs (Werte aus shared/3d/badger_notes.md) ----------------------------------------------------
const WALK_SPEED := 0.367        # m/s bei speed_scale 1
const WALK_RATE := 2.0
const START := Vector3(-6.3, 0.0, 1.2)
const TURN_T0 := 1.95            # ab hier biegt er im Laufen zur Kamera ab
const TURN_T1 := 3.45
const TURN_TO := -100.0          # Gier am Ende (Grad; 0 = nach rechts, -90 = nach vorn zum Betrachter)
const BRAKE_T := 3.2
const BRAKE_TIME := 0.4
const IDLE_T := 3.58
const LOCK_TIME := 0.34            # so lange hält der Standfuß beim Überblenden fest (Überblendung 0,3 s)
const WAVE_T := 4.0
const WAVE_LEN := 1.5

# --- Kamera ---------------------------------------------------------------------------------------
const WIDE_A := [Vector3(-26.0, 23.5, 38.5), Vector3(0.8, 0.8, -12.0), 30.0]   # Position, Ziel, fov
const WIDE_B := [Vector3(-23.5, 21.5, 35.5), Vector3(0.3, 0.6, -11.0), 30.0]
const CLOSE_A := [Vector3(-7.6, 4.7, 9.8), Vector3(-3.272, 0.406, 2.246), 24.0]
const CLOSE_B := [Vector3(-7.25, 4.5, 9.45), Vector3(-3.38, 0.427, 2.168), 24.0]
const MOVE_T0 := 0.9
const MOVE_T1 := 2.9

# --- Umgebung -------------------------------------------------------------------------------------
const BEAM_PERIOD := 7.0
const BEAM_FACING_T := 0.7       # Strahl zeigt in der Totale zur Kamera (Aufblitzen); in der Nahaufnahme ist der Leuchtturm nicht im Bild
const FLICKER_MIN := 0.55        # Laterne: Helligkeit schwankt zwischen 55 % und 100 %
const BEAM_INTENSITY := 0.12     # Lichtkegel (beam.gdshader); beim Aufblitzen bis zum Dreifachen
const SMOKE_PUFFS := 7
const SMOKE_LIFE := 4.2
const SEED := 20261013
const SUN_DIR := Vector3(0.62, -0.5, -0.6)    # Richtung des Lichts (von links vorn oben)
const FILL_DIR := Vector3(-0.55, -0.35, 0.75)

var t := 0.0
var walk_rate := WALK_RATE
var phase := 0
var yaw := 0.0
var lock_foot := -1
var lock_pos := Vector3.ZERO
var lock_both := false
var boats := {}
var gulls := {}
var smoke: Array[MeshInstance3D] = []
var smoke_jitter: Array[Vector3] = []
var lantern_mat: ShaderMaterial
var lamp_mat: ShaderMaterial
var resin_top: ShaderMaterial
var lantern_noise := FastNoiseLite.new()
var flicker_range := Vector2(-1.0, 1.0)     # Wertebereich des Rauschens in 0–6 s (für die Abbildung auf FLICKER_MIN..1)
var beam_yaw0 := 0.0
var cotton_mat: ShaderMaterial
var wire_mat: ShaderMaterial
var args := {}
var cam_override: Array = []

@onready var harbor: Node3D = $Harbor
@onready var badger: Node3D = $Badger
@onready var player: AnimationPlayer = $Badger/AnimationPlayer
@onready var camera: Camera3D = $Camera
@onready var cam_attr: CameraAttributesPractical = $Camera.attributes
@onready var rotor: Node3D = $Attach/LighthouseLight/Rotor
@onready var lantern_omni: OmniLight3D = $Attach/LanternLight/Omni
@onready var lamp_omni: OmniLight3D = $Attach/LighthouseLight/Omni
@onready var spot: SpotLight3D = $Attach/LighthouseLight/Rotor/Tilt/Spot
@onready var beam_mat: ShaderMaterial = ($Attach/LighthouseLight/Rotor/Tilt/Beam as MeshInstance3D).get_surface_override_material(0)
@onready var ui: Control = $UI/Card


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=")
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	if args.has("cam"):
		cam_override = Array(args["cam"].split(",")).map(func(s): return float(s))

	_place_light($Sun, SUN_DIR)
	_place_light($Fill, FILL_DIR)

	# Materialien vor dem Umhängen ersetzen, sonst bekäme der Lichtkegel ein Modellbau-Material
	_style(harbor, HARBOR_MATS, false)
	_style(badger, BADGER_MATS, true)
	_attach_to_empties()

	var sea := harbor.get_node("Sea") as MeshInstance3D
	resin_top = ShaderMaterial.new()
	resin_top.shader = RESIN
	sea.material_override = resin_top
	var side := ShaderMaterial.new()
	side.shader = RESIN
	side.set_shader_parameter("side", true)
	(harbor.get_node("SectionWater") as MeshInstance3D).material_override = side
	var sec := ShaderMaterial.new()
	sec.shader = SECTION
	(harbor.get_node("SectionLand") as MeshInstance3D).material_override = sec

	# Boot A: beleuchtetes Ruderhaus. In der Nahaufnahme liegt es im unscharfen Hintergrund (Lichtfleck, der mit
	# dem Boot schaukelt)
	var boat_a := harbor.get_node("BoatA") as MeshInstance3D
	var led := _toy_material(BOAT_LED, false)
	for i in boat_a.mesh.get_surface_count():
		if boat_a.mesh.surface_get_material(i).resource_name == "Metal":
			boat_a.set_surface_override_material(i, led)

	lantern_mat = _unique(harbor.find_child("LanternGlass", true, false))
	lamp_mat = _unique(harbor.find_child("LighthouseLamp", true, false))
	for glass in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
		(harbor.find_child(glass, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for w in ["Gull1Wire", "Gull2Wire"]:
		var wi := harbor.find_child(w, true, false) as GeometryInstance3D
		wi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		wi.lod_bias = 128.0

	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform
	for g in ["Gull1", "Gull2"]:
		gulls[g] = (harbor.get_node(g) as Node3D).transform

	badger.position = START
	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	player.play("Walk")
	player.speed_scale = WALK_RATE

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	var lo := 1e9
	var hi := -1e9
	for i in 181:
		var n := _flicker_noise(i / 30.0)
		lo = minf(lo, n)
		hi = maxf(hi, n)
	flicker_range = Vector2(lo, hi)
	# Startwinkel des Leuchtfeuers so, dass der Strahl bei BEAM_FACING_T zur Kamera der Totale zeigt
	var cam_at := Vector3(WIDE_A[0]).lerp(Vector3(WIDE_B[0]), clampf(BEAM_FACING_T / MOVE_T1, 0.0, 1.0))
	var to_cam := cam_at - rotor.global_position
	beam_yaw0 = atan2(-to_cam.x, -to_cam.z) - TAU * BEAM_FACING_T / BEAM_PERIOD

	_build_backdrop()
	_build_smoke()
	if args.has("no-dof"):
		cam_attr.dof_blur_far_enabled = false
		cam_attr.dof_blur_near_enabled = false
	if args.has("no-ui"):
		$UI.visible = false
	if args.has("mask"):
		_mask_mode()
	if args.has("no-wires"):
		for g in ["Gull1Wire", "Gull2Wire"]:
			(harbor.find_child(g, true, false) as Node3D).visible = false
	if args.has("no-gulls"):      # Prüfschalter: Möwen samt Fäden aus
		for g in ["Gull1", "Gull2"]:
			(harbor.get_node(g) as Node3D).visible = false
	if args.has("no-lamps"):      # Prüfschalter: Punkt- und Spotlichter aus
		for l in [lantern_omni, lamp_omni, spot, harbor.find_child("CottageWindow", true, false).get_node("Omni")]:
			l.visible = false

	# Startzeit (für Prüfungen ab einem späteren Zeitpunkt): Ablauf in 1/30-s-Schritten vorspulen
	var t0 := float(args.get("t0", "0"))
	_update(0.0)
	while t < t0 - 1e-6:
		var d := minf(1.0 / 30.0, t0 - t)
		t += d
		_update(d)


func _process(delta: float) -> void:
	t += delta
	_update(delta)


func _update(delta: float) -> void:
	RenderingServer.global_shader_parameter_set("dio_time", t)
	_update_badger(delta)
	_update_camera()

	var k := 0
	for b in boats:
		var ph := 1.9 * k
		var roll := deg_to_rad(1.6) * sin(TAU * t / 3.3 + ph)
		var pitch := deg_to_rad(0.7) * sin(TAU * t / 4.4 + 0.8 + ph)
		var heave := 0.025 * sin(TAU * t / 3.8 + 2.1 + ph)
		(harbor.get_node(b) as Node3D).transform = boats[b] * Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		k += 1

	# Spielzeugmöwen pendeln an ihren Fäden und drehen sich langsam
	k = 0
	for g in gulls:
		var ph := 2.3 * k
		var swing_x := deg_to_rad(0.35) * sin(TAU * t / 2.9 + ph)
		var swing_z := deg_to_rad(0.5) * sin(TAU * t / 3.7 + 1.0 + ph)
		var turn := deg_to_rad(14.0) * sin(TAU * t / 6.0 + ph)
		var bob := 0.04 * sin(TAU * t / 1.6 + ph)
		(harbor.get_node(g) as Node3D).transform = gulls[g] * Transform3D(Basis.from_euler(Vector3(swing_x, turn, swing_z)), Vector3(0.0, bob, 0.0))
		k += 1

	# Leuchtdiode in der Laterne flackert (Rauschen auf FLICKER_MIN..1 abgebildet, damit es sichtbar schwankt)
	var f := lerpf(FLICKER_MIN, 1.0, clampf(inverse_lerp(flicker_range.x, flicker_range.y, _flicker_noise(t)), 0.0, 1.0))
	lantern_omni.light_energy = 3.4 * f * f
	lantern_mat.set_shader_parameter("emission_energy", 6.0 * f * f)

	# Leuchtfeuer dreht sich; die Lampe blitzt, wenn der Strahl zur Kamera zeigt
	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := camera.global_position - rotor.global_position
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), 48.0)
	lamp_mat.set_shader_parameter("emission_energy", 3.0 + 40.0 * facing)
	lamp_omni.light_energy = 1.5 + 4.0 * facing
	beam_mat.set_shader_parameter("intensity", BEAM_INTENSITY * (1.0 + 2.0 * facing))
	if args.has("verbose") and facing > 0.05:
		print("Leuchtfeuer t=%.2f facing=%.2f" % [t, facing])

	_update_smoke()
	if args.has("measure"):
		_measure()
	if ui.has_method("set_time"):
		ui.set_time(t)


func _flicker_noise(time: float) -> float:
	return lantern_noise.get_noise_1d(time * 7.0) + 0.35 * lantern_noise.get_noise_1d(time * 29.0 + 50.0)


# --- Dachs ---------------------------------------------------------------------------------------
func _update_badger(delta: float) -> void:
	if phase == 0:
		walk_rate = WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, t))
		player.speed_scale = walk_rate
		player.advance(delta)
		# Vorschub entlang der bisherigen Blickrichtung (Tempo passt zur Animation: Standfuß bleibt stehen)
		var fwd := Vector3(cos(yaw), 0.0, -sin(yaw))
		badger.position += fwd * WALK_SPEED * walk_rate * delta
		# im Laufen zur Kamera abbiegen: um den Bodenpunkt des Standfußes drehen, nicht um die Figurmitte,
		# sonst wandert der aufgesetzte Fuß auf einem Bogen über den Boden
		var new_yaw := deg_to_rad(TURN_TO) * smoothstep(TURN_T0, TURN_T1, t)
		var k := _stance_foot()
		var before := _heel(k) if k >= 0 else Vector3.ZERO
		badger.rotation.y = new_yaw
		yaw = new_yaw
		if k >= 0:
			var after := _heel(k)
			badger.position += Vector3(before.x - after.x, 0.0, before.z - after.z)
		if t >= IDLE_T:
			if args.has("verbose"):
				print("Dachs steht bei %s, Gier %.1f°" % [badger.position, rad_to_deg(yaw)])
			phase = 1
			player.speed_scale = 1.0
			player.play("Idle", 0.3)
			lock_foot = _stance_foot()
			if lock_foot >= 0:
				lock_pos = _heel(lock_foot)
	elif phase == 1:
		player.advance(delta)
		# Beim Überblenden Walk -> Idle bleibt der Standfuß stehen: die Figur wird so nachgeschoben, dass seine
		# Ferse am Bodenpunkt vom Ende des Laufens bleibt (sonst wandert er bis zu 4 cm hin und her)
		# Sobald auch der Schwungfuß aufsetzt, wird die Mitte beider Fersen festgehalten: Den Rest der
		# Überblendung teilen sich dann beide Füße (je etwa 1 cm statt 2,5 cm an einem Fuß).
		if lock_foot >= 0 and t < IDLE_T + LOCK_TIME:
			var h := _heel(lock_foot)
			var o := _heel(1 - lock_foot)
			if lock_both:
				h = (h + o) * 0.5
			elif o.y < 0.004:
				lock_both = true
				badger.position += Vector3(lock_pos.x - h.x, 0.0, lock_pos.z - h.z)
				lock_pos = (_heel(0) + _heel(1)) * 0.5
				h = lock_pos
			badger.position += Vector3(lock_pos.x - h.x, 0.0, lock_pos.z - h.z)
		if t >= WAVE_T:
			phase = 2
			player.play("Wave", 0.25)
	elif phase == 2:
		player.advance(delta)
		if t >= WAVE_T + WAVE_LEN - 0.1:
			phase = 3
			player.play("Idle", 0.3)
	else:
		player.advance(delta)


const FEET := ["foot.L", "foot.R"]


## Weltposition der Ferse (Kopf des Fußknochens liegt 6,5 cm über der Sohle)
func _heel(k: int) -> Vector3:
	var skel := badger.get_node("Armature/Skeleton3D") as Skeleton3D
	var pose := skel.global_transform * skel.get_bone_global_pose(skel.find_bone(FEET[k]))
	return pose.origin - Vector3(0, 0.062, 0)


## Index des aufgesetzten Fußes (tiefere Ferse unter 1,2 cm) oder -1
func _stance_foot() -> int:
	var a := _heel(0)
	var b := _heel(1)
	var k := 0 if a.y <= b.y else 1
	return k if minf(a.y, b.y) < 0.012 else -1


# --- Kamera und Schärfentiefe ----------------------------------------------------------------------
func _shot(a: Array, b: Array, s: float) -> Array:
	return [Vector3(a[0]).lerp(b[0], s), Vector3(a[1]).lerp(b[1], s), lerpf(a[2], b[2], s)]


func _update_camera() -> void:
	var pos: Vector3
	var tgt: Vector3
	var fov: float
	if cam_override.size() == 7:
		pos = Vector3(cam_override[0], cam_override[1], cam_override[2])
		tgt = Vector3(cam_override[3], cam_override[4], cam_override[5])
		fov = cam_override[6]
	else:
		var wide := _shot(WIDE_A, WIDE_B, clampf(t / MOVE_T1, 0.0, 1.0))
		var close := _shot(CLOSE_A, CLOSE_B, clampf((t - MOVE_T0) / (6.0 - MOVE_T0), 0.0, 1.0))
		var s := smoothstep(MOVE_T0, MOVE_T1, t)
		s = s * s * (3.0 - 2.0 * s)        # doppelt geglättet: sanftes Anfahren und Abbremsen
		# Position auf einem Bogen (kugelförmig um das Ziel interpoliert), damit die Fahrt nicht durch das Modell schneidet
		tgt = Vector3(wide[1]).lerp(close[1], s)
		var r0: Vector3 = Vector3(wide[0]) - Vector3(wide[1])
		var r1: Vector3 = Vector3(close[0]) - Vector3(close[1])
		var dist := exp(lerpf(log(r0.length()), log(r1.length()), s))
		var dir := r0.normalized().slerp(r1.normalized(), s)
		pos = tgt + dir * dist
		fov = lerpf(wide[2], close[2], s)
	camera.fov = fov
	camera.look_at_from_position(pos, tgt, Vector3.UP)
	if wire_mat:
		wire_mat.set_shader_parameter("m_per_px", 2.0 * tan(deg_to_rad(fov) / 2.0) / get_viewport().get_visible_rect().size.y)

	# Schärfe liegt auf dem Dachs; Tiefenbereich wächst mit dem Abstand (wie beim Blick auf ein Modell)
	var focus := camera.global_position.distance_to(badger.global_position + Vector3(0, 0.55, 0))
	cam_attr.dof_blur_far_distance = focus * 1.05 + 0.25
	cam_attr.dof_blur_far_transition = focus * 0.45
	cam_attr.dof_blur_near_distance = focus * 0.92 - 0.2
	cam_attr.dof_blur_near_transition = focus * 0.2


# --- Materialien ---------------------------------------------------------------------------------
func _style(root: Node, table: Dictionary, uv_space: bool) -> void:
	var cache := {}
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(i)
			if src == null:
				push_error("%s: Fläche %d ohne glTF-Material" % [mi.name, i])
				continue
			var key := src.resource_name
			if key in ["Water", "SectionLand", "SectionWater"]:
				continue
			if key == "GullWire":
				if not cache.has(key):
					wire_mat = ShaderMaterial.new()
					wire_mat.shader = WIRE
					cache[key] = wire_mat
				mi.set_surface_override_material(i, cache[key])
				continue
			if not table.has(key):
				push_error("Material %s fehlt in der Tabelle" % key)
				continue
			if not cache.has(key):
				cache[key] = _toy_material(table[key], uv_space)
				if key == "Grass" and not args.has("no-shells"):
					_add_shells(cache[key], table[key])
			mi.set_surface_override_material(i, cache[key])


func _toy_material(def: Dictionary, uv_space: bool) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = TOY
	m.set_shader_parameter("use_uv", uv_space)
	for p in def:
		m.set_shader_parameter(p, def[p])
	return m


func _add_shells(base: ShaderMaterial, def: Dictionary) -> void:
	var prev: Material = base
	for i in SHELLS:
		var s := ShaderMaterial.new()
		s.shader = SHELL
		s.set_shader_parameter("layer", float(i + 1) / SHELLS)
		s.set_shader_parameter("albedo", def["albedo2"])
		s.set_shader_parameter("tip", Color(def["albedo"]).lightened(0.25))
		prev.next_pass = s
		prev = s


func _unique(mi: MeshInstance3D) -> ShaderMaterial:
	var m := (mi.get_surface_override_material(0) as ShaderMaterial).duplicate() as ShaderMaterial
	mi.set_surface_override_material(0, m)
	return m


func _place_light(light: DirectionalLight3D, dir: Vector3) -> void:
	var d := dir.normalized()
	light.look_at_from_position(Vector3.ZERO, d, Vector3.UP if absf(d.y) < 0.99 else Vector3.FORWARD)


func _attach_to_empties() -> void:
	for holder in $Attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt im Hafen" % holder.name)
			continue
		for c in holder.get_children():
			c.reparent(target, false)


# --- Himmelsprospekt hinter dem Sockel ----------------------------------------------------------------
func _build_backdrop() -> void:
	# Profil (Radius, Höhe): 8 m auf dem Tisch, Hohlkehle mit 9 m Radius, dann senkrecht bis 30 m über dem Tisch
	var center := Vector3(1.0, -3.79, -12.5)
	var R := 62.0
	var rc := 10.0
	var prof: Array[Vector2] = [Vector2(R - rc - 8.0, 0.0)]
	for i in 13:
		var a := deg_to_rad(-90.0 + 90.0 * i / 12.0)
		prof.append(Vector2(R - rc + rc * cos(a), rc + rc * sin(a)))
	prof.append(Vector2(R, 42.0))
	var plen: Array[float] = [0.0]
	for i in range(1, prof.size()):
		plen.append(plen[i - 1] + prof[i].distance_to(prof[i - 1]))
	var total: float = plen[-1]
	var a0 := deg_to_rad(-168.0)    # Bogen hinter dem Sockel (Winkel um die Y-Achse, 0 = +X)
	var a1 := deg_to_rad(15.0)
	var seg := 96
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in seg:
		var u := [float(i) / seg, float(i + 1) / seg]
		for j in prof.size() - 1:
			var q := []
			for c in [[0, j], [1, j], [1, j + 1], [0, j + 1]]:
				var ang := lerpf(a0, a1, u[c[0]])
				var p := prof[c[1]]
				q.append([center + Vector3(cos(ang) * p.x, p.y, sin(ang) * p.x), Vector2(u[c[0]], plen[c[1]] / total)])
			for idx in [0, 2, 1, 0, 3, 2]:
				st.set_uv(q[idx][1])
				st.add_vertex(q[idx][0])
	st.generate_normals()
	var mi := MeshInstance3D.new()
	mi.name = "Backdrop"
	mi.mesh = st.commit()
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var m := ShaderMaterial.new()
	m.shader = BACKDROP
	m.set_shader_parameter("aspect", (a1 - a0) * R / total)
	mi.material_override = m
	add_child(mi)


# --- Rauch aus Watte ------------------------------------------------------------------------------
func _build_smoke() -> void:
	cotton_mat = ShaderMaterial.new()
	cotton_mat.shader = COTTON
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	var anchor := harbor.find_child("ChimneySmoke", true, false) as Node3D
	for i in SMOKE_PUFFS:
		var p := MeshInstance3D.new()
		p.mesh = quad
		p.material_override = cotton_mat
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		p.set_instance_shader_parameter("seed", rng.randf_range(0.0, 100.0))
		anchor.add_child(p)
		smoke.append(p)
		smoke_jitter.append(Vector3(rng.randf_range(-0.12, 0.12), rng.randf_range(0.85, 1.15), rng.randf_range(-0.1, 0.1)))


func _update_smoke() -> void:
	var sun_view := (camera.global_transform.basis.inverse() * -SUN_DIR.normalized())
	cotton_mat.set_shader_parameter("sun_view", sun_view)
	for i in smoke.size():
		var age := fposmod(t + float(i) * SMOKE_LIFE / SMOKE_PUFFS, SMOKE_LIFE) / SMOKE_LIFE
		var j := smoke_jitter[i]
		var p := smoke[i]
		p.position = Vector3(0.9 * age * age + j.x * age, 0.15 + 2.0 * age * j.y, j.z * age)
		var s := lerpf(0.45, 1.25, sqrt(age))
		p.scale = Vector3(s, s, s)
		p.set_instance_shader_parameter("fade", smoothstep(0.0, 0.1, age) * (1.0 - smoothstep(0.6, 1.0, age)))


# --- Messwerte je Bild (für scripts/measure_badger.py) ---------------------------------------------
func _measure() -> void:
	var skel := badger.find_child("Skeleton3D", true, false) as Skeleton3D
	var out := PackedStringArray(["M", "%.4f" % t])
	for b in ["foot.L", "foot.R"]:
		var pose := skel.global_transform * skel.get_bone_global_pose(skel.find_bone(b))
		var heel := pose.origin - Vector3(0, 0.062, 0)          # Ferse am Boden (Kopf des Fußknochens 6,5 cm hoch)
		var toe := pose * Vector3(0, 0.128, 0)                     # Spitze des Fußknochens (Zehen)
		out.append("%.5f,%.5f,%.5f,%.5f,%.5f,%.5f" % [heel.x, heel.y, heel.z, toe.x, toe.y, toe.z])
	var head := skel.global_transform * skel.get_bone_global_pose(skel.find_bone("head"))
	var top := head * Vector3(0, 0.2, 0)
	out.append("%.5f,%.5f,%.5f" % [top.x, top.y, top.z])
	var cam := camera.unproject_position(top)
	out.append("%.2f,%.2f" % [cam.x, cam.y])
	print(" ".join(out))
	# Möwe am Faden in der Schärfeebene: Bildlage der Körpermitte
	var gull := harbor.get_node("Gull1") as MeshInstance3D
	var gp := gull.global_transform * gull.get_aabb().get_center()
	var gs := camera.unproject_position(gp)
	print("G %.4f %.2f,%.2f %.3f" % [t, gs.x, gs.y, camera.global_position.distance_to(gp)])


# --- Maske für die Fußmessung: Dachs weiß, Rest schwarz ------------------------------------------------
func _mask_mode() -> void:
	var black := StandardMaterial3D.new()
	black.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	black.albedo_color = Color.BLACK
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color.WHITE
	for mi: GeometryInstance3D in find_children("*", "GeometryInstance3D", true, false):
		mi.material_override = black
	for mi: GeometryInstance3D in badger.find_children("*", "GeometryInstance3D", true, false):
		mi.material_override = white
	for s in smoke:
		s.visible = false
	var env := ($WorldEnvironment as WorldEnvironment).environment
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color.BLACK
	env.glow_enabled = false
	env.ssao_enabled = false
	env.ssil_enabled = false
	env.adjustment_enabled = false
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	cam_attr.dof_blur_far_enabled = false
	cam_attr.dof_blur_near_enabled = false
	$UI.visible = false
