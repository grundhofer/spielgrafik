extends Node3D
## Technik-Demo "3D-Figur riggen und animieren per Skript" (styles/blender-rig).
##
## Zeigt die Figur aus shared/3d (badger.glb: per Skript gebaut, 21 Knochen, Idle/Walk/Wave als
## gesampelte glTF-Animationen) so, wie ein Spiel sie benutzt:
##   - Schleifen im Code setzen (glTF kennt kein Loop-Flag),
##   - AnimationTree mit Blend2 (Idle <-> Walk), TimeScale für das Lauftempo und OneShot fürs Winken,
##   - Vorschub passend zum Lauftempo (0,367 m/s x Tempo x Gewicht von Walk), Kurve nur um den Standfuß,
##   - Knochen (2D-Overlay, rig_overlay.gd) und Drahtgitter (eigenes Mesh am selben Skin) kurz eingeblendet.
## Dazu die Umgebung aus der Probeszene von shared/3d (Wasser, Boote, Laterne, Leuchtfeuer; der Schornstein
## mit dem Rauch liegt außerhalb dieses Ausschnitts und ist weggelassen).
## Alles hängt an der aufsummierten Zeit t und festen Seeds; tools/capture.py nimmt mit --fixed-fps auf.
##
## Schalter nach "--" (z. B. godot --path demo -- --measure):
##   --measure   druckt je Bild Fuß- und Kopfpunkte (Welt und Bild) als "M ..." für scripts/measure_feet.py,
##               dazu Blickrichtung und Fußhalten in Grad als "F ..."
##   --mask      Dachs weiß auf Schwarz, ohne Oberfläche (für die Silhouettenmessung)
##   --no-rig    ohne Knochen und Drahtgitter (Vergleich)
##   --t0=S      Ablauf vorab bis S Sekunden rechnen (Standbilder zum Prüfen)
##   --cam=x,y,z,neigung,gieren,fov   andere Kamera (zum Ausprobieren von Bildausschnitten)

# --- Kamera (aus scripts/frame_shot.py) ------------------------------------------------------
const CAM_POS := Vector3(-1.2, 1.25, 4.6)
const CAM_ROT_DEG := Vector3(-3.0, -14.0, 0.0)
const CAM_FOV := 52.0

# --- Dachs: Werte aus shared/3d/badger_notes.md --------------------------------------------------
const WALK_SPEED := 0.367        # m/s bei Tempo 1: dann rutscht der Standfuß nicht
const WALK_RATE := 2.0           # Tempo von Walk (TimeScale); Geschwindigkeit = 0,734 m/s
const START_POS := Vector3(-3.5, 0.0, 0.8)
const HEADING0 := 0.0            # Grad zur Kamera hin (0 = Blick +X, Laufweg aus shared/3d)
const CURVE_T0 := 1.5            # ab hier biegt er zur Kamera ab ...
const CURVE_T1 := 3.1            # ... bis hierher (gedreht wird nur, wenn genau ein Fuß am Boden ist)
const HEADING_END := 80.0        # Grad: am Ende fast zur Kamera gewandt (Richtung zur Kamera etwa 84°)
const MAX_TURN := 2.8            # höchstens so viel Grad Drehung je Bild
const BRAKE_T := 3.15            # ab hier Tempo -> 0 (in BRAKE_D s) ...
const BRAKE_D := 0.5
const BLEND_T0 := 3.35           # ... und Überblenden Walk -> Idle (Blend2) von BLEND_T0 bis BLEND_T1
const BLEND_T1 := 3.77
const WAVE_T := 4.15             # OneShot "Wave" (1,5 s, Ein-/Ausblenden 0,25/0,3 s)

# --- Figurenlicht: nur für den Dachs (Ebene 2), damit er in der Nahaufnahme vor dem dunklen Wasser klar steht;
#     die Sonne beleuchtet ihn nicht mehr, wirft aber weiter seinen Schatten
const FIG_LAYER := 2
const KEY_FROM := Vector3(-1.6, 2.0, 2.4)     # Führungslicht: links vorn oben, relativ zum Endpunkt
const RIM_FROM := Vector3(1.4, 1.2, -2.6)     # Kantenlicht: rechts hinten (Abendglut)
const END_POS := Vector3(-1.53, 0.5, 1.68)    # Endpunkt aus scripts/frame_shot.py (Zielpunkt der Lichter)

# --- Einblenden von Knochen und Drahtgitter ----------------------------------------------------
const RIG_WINDOWS := [Vector2(0.7, 2.7), Vector2(4.3, 5.65)]   # Knochen (von, bis) in s
const WIRE_WINDOWS := [Vector2(0.7, 2.7)]                          # Drahtgitter nur im Laufen
const RIG_FADE := 0.25

# --- Umgebung (wie shared/3d/demo) ------------------------------------------------------------
const BEAM_PERIOD := 8.0
const BEAM_FACING_T := 5.2
const SEED := 20261011

# Spitzen der Knochen in der Ruhepose (Godot-Koordinaten, Figur-Raum), aus shared/3d/badger_notes.md.
# glTF speichert nur die Köpfe (Gelenke); für die Darstellung als Oktaeder braucht es auch die Spitzen.
const BONE_TAILS := {
	"root": Vector3(0.120, 0.000, 0.000), "hips": Vector3(0.000, 0.400, 0.000),
	"spine": Vector3(0.000, 0.520, 0.000), "chest": Vector3(0.000, 0.655, 0.000),
	"neck": Vector3(0.030, 0.750, 0.000), "head": Vector3(0.030, 0.950, 0.000),
	"upper_arm.L": Vector3(0.005, 0.453, -0.272), "forearm.L": Vector3(0.022, 0.310, -0.286),
	"hand.L": Vector3(0.030, 0.236, -0.288), "upper_arm.R": Vector3(-0.051, 0.482, 0.301),
	"forearm.R": Vector3(0.065, 0.395, 0.301), "hand.R": Vector3(0.114, 0.338, 0.297),
	"thigh.L": Vector3(0.022, 0.165, -0.120), "shin.L": Vector3(0.000, 0.065, -0.125),
	"foot.L": Vector3(0.120, 0.020, -0.125), "thigh.R": Vector3(0.022, 0.165, 0.120),
	"shin.R": Vector3(0.000, 0.065, 0.125), "foot.R": Vector3(0.120, 0.020, 0.125),
	"scarf_1": Vector3(-0.158, 0.551, 0.089), "scarf_2": Vector3(-0.170, 0.442, 0.097),
	"tail": Vector3(-0.180, 0.165, 0.000),
}

@export var water_material: ShaderMaterial
@export var wire_shader: Shader

var t := 0.0
var walk_time := 0.0             # Position in Walk (s), läuft mit dem Tempo
var walk_rate := WALK_RATE
var walk_weight := 1.0           # blend_amount von Blend2 (1 = Walk)
var heading := HEADING0          # tatsächlich gedreht (Grad)
var foot_lock := {"L": 0.0, "R": 0.0}      # Grad, um die der Fuß gegen die Körperdrehung gehalten wird
var lock_at_lift := {"L": 0.0, "R": 0.0}   # Wert beim Abheben, klingt in der Schwungphase ab
var wave_fired := false
var rig_amount := 0.0

var tree: AnimationTree
var wire_mats: Array[ShaderMaterial] = []
var bone_idx := {}               # Name -> Index
var bone_rest := {}              # Name -> globale Ruhetransformation (Skelettraum)
var bone_perp := {}              # Name -> Querachse in Ruhe (für die Oktaeder)

var boats := {}
var lantern_mat: StandardMaterial3D
var lamp_mat: StandardMaterial3D
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0

var measure := false
var mask := false
var no_rig := false

@onready var harbor: Node3D = $Harbor
@onready var badger: Node3D = $Badger
@onready var player: AnimationPlayer = $Badger/AnimationPlayer
@onready var skeleton: Skeleton3D = $Badger/Armature/Skeleton3D
@onready var camera: Camera3D = $Camera
@onready var rotor: Node3D = $Attach/LighthouseLight/Rotor
@onready var lantern_omni: OmniLight3D = $Attach/LanternLight/Omni
@onready var lamp_omni: OmniLight3D = $Attach/LighthouseLight/Omni
@onready var overlay: Control = $Overlay/Rig
@onready var ui: Control = $Overlay/UI


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	measure = "--measure" in args
	mask = "--mask" in args
	no_rig = "--no-rig" in args

	camera.position = CAM_POS
	camera.rotation_degrees = CAM_ROT_DEG
	camera.fov = CAM_FOV
	var t0 := 0.0
	for a in args:
		if a.begins_with("--cam="):
			var c := a.substr(6).split_floats(",")
			camera.position = Vector3(c[0], c[1], c[2])
			camera.rotation_degrees = Vector3(c[3], c[4], 0.0)
			camera.fov = c[5]
		elif a.begins_with("--t0="):
			t0 = a.substr(5).to_float()

	_attach_to_empties()
	_setup_water()
	_setup_glass()
	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform
	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	var to_cam := camera.global_position - rotor.global_position
	beam_yaw0 = atan2(-to_cam.x, -to_cam.z) - TAU * BEAM_FACING_T / BEAM_PERIOD

	_setup_badger()
	_setup_figure_lights()
	if mask:
		_apply_mask()
	_update(0.0)
	while t0 > 0.0 and t < t0 - 0.001:
		t += 1.0 / 30.0
		_update(1.0 / 30.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)


func _update(delta: float) -> void:
	_update_badger(delta)
	_update_ambient()
	_update_rig_view()
	if measure:
		_print_measure()


# =============================================================================================
# Dachs: Schleifen, AnimationTree, Vorschub
# =============================================================================================
func _setup_badger() -> void:
	# 1) glTF kennt kein Loop-Flag: Godot importiert Idle, Walk und Wave mit LOOP_NONE.
	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR

	# 2) AnimationTree: (Idle | Walk x Tempo) -> Blend2 -> OneShot(Wave) -> Ausgang
	var bt := AnimationNodeBlendTree.new()
	var idle := AnimationNodeAnimation.new()
	idle.animation = &"Idle"
	var walk := AnimationNodeAnimation.new()
	walk.animation = &"Walk"
	var wave := AnimationNodeAnimation.new()
	wave.animation = &"Wave"
	var speed := AnimationNodeTimeScale.new()
	var blend := AnimationNodeBlend2.new()
	var shot := AnimationNodeOneShot.new()
	shot.fadein_time = 0.25
	shot.fadeout_time = 0.3
	bt.add_node(&"Idle", idle, Vector2(0, 0))
	bt.add_node(&"Walk", walk, Vector2(0, 160))
	bt.add_node(&"WalkSpeed", speed, Vector2(200, 160))
	bt.add_node(&"Blend", blend, Vector2(400, 60))
	bt.add_node(&"WaveAnim", wave, Vector2(400, 240))
	bt.add_node(&"Wave", shot, Vector2(600, 100))
	bt.connect_node(&"WalkSpeed", 0, &"Walk")
	bt.connect_node(&"Blend", 0, &"Idle")
	bt.connect_node(&"Blend", 1, &"WalkSpeed")
	bt.connect_node(&"Wave", 0, &"Blend")
	bt.connect_node(&"Wave", 1, &"WaveAnim")
	bt.connect_node(&"output", 0, &"Wave")

	tree = AnimationTree.new()
	tree.name = "AnimationTree"
	badger.add_child(tree)
	tree.anim_player = tree.get_path_to(player)
	tree.tree_root = bt
	# Manuell weiterschalten: feste Reihenfolge Pose -> Vorschub -> Drehung -> Overlay in einem Bild
	tree.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	tree.active = true
	player.stop()
	tree.set("parameters/WalkSpeed/scale", WALK_RATE)
	tree.set("parameters/Blend/blend_amount", 1.0)

	badger.position = START_POS
	badger.rotation.y = deg_to_rad(-heading)

	for i in skeleton.get_bone_count():
		var n := skeleton.get_bone_name(i)
		bone_idx[n] = i
		bone_rest[n] = skeleton.get_bone_global_rest(i)
		var d: Vector3 = BONE_TAILS[n] - bone_rest[n].origin
		var ref := Vector3.UP if absf(d.normalized().y) < 0.8 else Vector3.RIGHT
		bone_perp[n] = d.cross(ref).normalized()

	_build_wire()
	tree.advance(0.0)
	if measure:
		for n in bone_idx:
			print("R %s %s" % [n, (bone_rest[n] as Transform3D).origin])
		for mi: MeshInstance3D in skeleton.get_children().filter(func(c): return c.name.ends_with("Wire")):
			print("W %s Dreiecke %d, ausgeblendete Diagonalen %d" % [mi.name, mi.mesh.get_meta("triangles"),
				mi.mesh.get_meta("hidden_diagonals")])


func _setup_figure_lights() -> void:
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		mi.layers = FIG_LAYER
	var sun := $Sun as DirectionalLight3D
	sun.light_cull_mask = 0xFFFFF & ~FIG_LAYER      # wirft weiter den Schatten des Dachses
	var key := DirectionalLight3D.new()
	key.name = "FigureKey"
	key.light_color = Color(1.0, 0.86, 0.72)
	key.light_energy = 1.25
	key.light_cull_mask = FIG_LAYER
	key.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY   # keine zweite Sonne im Himmel
	add_child(key)
	key.look_at_from_position(END_POS + KEY_FROM, END_POS)
	var rim := DirectionalLight3D.new()
	rim.name = "FigureRim"
	rim.light_color = Color(1.0, 0.62, 0.38)
	rim.light_energy = 2.2
	rim.light_cull_mask = FIG_LAYER
	rim.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY
	add_child(rim)
	rim.look_at_from_position(END_POS + RIM_FROM, END_POS)


func _update_badger(delta: float) -> void:
	# Tempo und Gewicht für dieses Bild
	walk_rate = WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_D, t))
	walk_weight = 1.0 - smoothstep(BLEND_T0, BLEND_T1, t)
	tree.set("parameters/WalkSpeed/scale", walk_rate)
	tree.set("parameters/Blend/blend_amount", walk_weight)
	if not wave_fired and t >= WAVE_T:
		wave_fired = true
		tree.set("parameters/Wave/request", AnimationNodeOneShot.ONE_SHOT_REQUEST_FIRE)
	if delta <= 0.0:
		return
	walk_time += walk_rate * delta
	tree.advance(delta)

	# Vorschub entlang der Blickrichtung (+X der Figur): so schnell, wie der Standfuß nach hinten wandert
	var fwd := badger.global_basis.x.normalized()
	badger.global_position += fwd * WALK_SPEED * walk_rate * walk_weight * delta

	# Abbiegen: nur bei genau einem Fuß am Boden, um dessen Knöchel (senkrechte Achse). Der Fuß selbst wird
	# zurückgedreht (foot_lock), damit Ferse und Ballen am Boden stehen bleiben, während sich Bein und
	# Körper über ihm drehen; in der folgenden Schwungphase dreht er sich in die neue Richtung.
	var target := lerpf(HEADING0, HEADING_END, clampf((t - CURVE_T0) / (CURVE_T1 - CURVE_T0), 0.0, 1.0))
	var pending := target - heading
	var stance := _single_stance()
	if absf(pending) > 0.001 and stance != "" and walk_weight > 0.999:
		var step := clampf(pending, -MAX_TURN, MAX_TURN)
		var pivot := _bone_point("foot." + stance, Vector3.ZERO, true)
		pivot.y = 0.0
		var r := Transform3D(Basis(Vector3.UP, deg_to_rad(-step)), Vector3.ZERO)
		var gt := badger.global_transform
		gt.origin -= pivot
		gt = r * gt
		gt.origin += pivot
		badger.global_transform = gt
		heading += step
		foot_lock[stance] += step
	for side in ["L", "R"]:
		var p := fposmod(walk_time + (0.0 if side == "L" else 0.5), 1.0)   # 0 = Ferse dieses Fußes setzt auf
		if p < 0.6:
			lock_at_lift[side] = foot_lock[side]
		else:
			foot_lock[side] = lock_at_lift[side] * (1.0 - smoothstep(0.0, 0.6, (p - 0.6) / 0.4))
	_apply_foot_lock()


## Dreht die Fußknochen um die Senkrechte durch den Knöchel zurück (nach dem AnimationTree, vor dem Zeichnen).
func _apply_foot_lock() -> void:
	var sb := skeleton.global_basis.orthonormalized()
	for side in ["L", "R"]:
		var lk: float = foot_lock[side] * walk_weight
		if absf(lk) < 0.01:
			continue
		var fi: int = bone_idx["foot." + side]
		var pg := skeleton.get_bone_global_pose(skeleton.get_bone_parent(fi)).basis.orthonormalized()
		var r := sb.inverse() * Basis(Vector3.UP, deg_to_rad(lk)) * sb      # Weltsenkrechte im Skelettraum
		var local := Basis(skeleton.get_bone_pose_rotation(fi))
		skeleton.set_bone_pose_rotation(fi, (pg.inverse() * r * pg * local).get_rotation_quaternion())


## "L" oder "R", wenn im Laufzyklus genau dieser Fuß am Boden steht, sonst "".
## Walk (badger_notes.md): 0,0 s linke Ferse setzt auf, 0,5 s rechte Ferse, Standphase je 0,6 s;
## dazwischen 0,1 bis 0,5 (nur links) und 0,6 bis 1,0 (nur rechts), mit 0,005 Abstand zu den Wechseln.
func _single_stance() -> String:
	var p := fposmod(walk_time, 1.0)
	if p >= 0.105 and p < 0.495:
		return "L"
	if p >= 0.605 and p < 0.995:
		return "R"
	return ""


## Punkt im Knochenraum (Versatz zum Gelenk in Ruhe-Achsen der Figur) in Weltkoordinaten.
func _bone_point(bone: String, rest_offset: Vector3, world := true) -> Vector3:
	var i: int = bone_idx[bone]
	var rest: Transform3D = bone_rest[bone]
	var p := skeleton.get_bone_global_pose(i) * rest.affine_inverse() * (rest.origin + rest_offset)
	return skeleton.global_transform * p if world else p


# =============================================================================================
# Knochen und Drahtgitter
# =============================================================================================
## Liefert für jeden Knochen Kopf, Spitze und Querachsen in Weltkoordinaten (für rig_overlay.gd).
func bone_frames() -> Array:
	var out := []
	var sk := skeleton.global_transform
	for n in bone_idx:
		var i: int = bone_idx[n]
		var rest: Transform3D = bone_rest[n]
		var m := skeleton.get_bone_global_pose(i) * rest.affine_inverse()
		var head := sk * (m * rest.origin)
		var tail: Vector3 = sk * (m * (BONE_TAILS[n] as Vector3))
		var p: Vector3 = (sk.basis * (m.basis * bone_perp[n])).normalized()
		out.append({"name": n, "head": head, "tail": tail, "perp": p})
	return out


func _build_wire() -> void:
	var mat := ShaderMaterial.new()
	mat.shader = wire_shader
	mat.set_shader_parameter("amount", 0.0)
	wire_mats.append(mat)
	for src_name in ["Badger", "Parcel"]:
		var src := skeleton.get_node(src_name) as MeshInstance3D
		var mi := MeshInstance3D.new()
		mi.name = src_name + "Wire"
		mi.mesh = WireMesh.build(src.mesh as ArrayMesh)
		mi.skin = src.skin
		mi.material_override = mat
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.extra_cull_margin = 0.5
		skeleton.add_child(mi)
		mi.skeleton = mi.get_path_to(skeleton)


func _window(windows: Array) -> float:
	var a := 0.0
	for w: Vector2 in windows:
		a = maxf(a, smoothstep(w.x, w.x + RIG_FADE, t) * (1.0 - smoothstep(w.y - RIG_FADE, w.y, t)))
	return 0.0 if no_rig or mask else a


func _update_rig_view() -> void:
	rig_amount = _window(RIG_WINDOWS)
	var wire := _window(WIRE_WINDOWS)
	for m in wire_mats:
		m.set_shader_parameter("amount", wire)
	overlay.set_frame(bone_frames(), camera, rig_amount)
	ui.set_state(t, {
		"blend": walk_weight, "speed": walk_rate, "walk_time": walk_time,
		"wave_active": bool(tree.get("parameters/Wave/active")),
		"wave_t": t - WAVE_T, "rig": rig_amount, "wire": wire,
	})


# =============================================================================================
# Umgebung (aus shared/3d/demo/main.gd übernommen)
# =============================================================================================
func _setup_water() -> void:
	var water := find_material(harbor, "Water") as StandardMaterial3D
	water_material.set_shader_parameter("albedo", water.albedo_color)
	water_material.set_shader_parameter("roughness", water.roughness)
	var n := replace_material(harbor, "Water", water_material)
	assert(n == 1, "Material Water nicht gefunden")
	(harbor.get_node("Sea") as MeshInstance3D).extra_cull_margin = 1.0


func _setup_glass() -> void:
	lantern_mat = unique_material(harbor.find_child("LanternGlass", true, false))
	lamp_mat = unique_material(harbor.find_child("LighthouseLamp", true, false))
	for glass in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
		(harbor.find_child(glass, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


func _update_ambient() -> void:
	var k := 0
	for b in boats:
		var ph := 1.7 * k
		var roll := deg_to_rad(2.2) * sin(TAU * t / 3.4 + ph)
		var pitch := deg_to_rad(0.9) * sin(TAU * t / 4.6 + 0.8 + ph)
		var heave := 0.035 * sin(TAU * t / 3.9 + 2.1 + ph)
		var local := Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		(harbor.get_node(b) as Node3D).transform = boats[b] * local
		k += 1
	water_material.set_shader_parameter("time_s", t)

	var f := 0.82 + 0.18 * lantern_noise.get_noise_1d(t * 7.0) + 0.06 * lantern_noise.get_noise_1d(t * 31.0 + 50.0)
	lantern_omni.light_energy = 1.6 * f
	lantern_mat.emission_energy_multiplier = 4.0 * f

	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position).normalized()
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), 24.0)
	lamp_mat.emission_energy_multiplier = 4.0 + 26.0 * facing
	lamp_omni.light_energy = 2.0 + 4.0 * facing


func _attach_to_empties() -> void:
	for holder in $Attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt in harbor.glb" % holder.name)
			continue
		for c in holder.get_children():
			c.reparent(target, false)


static func find_material(root: Node, mat_name: String) -> Material:
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i)
			if m and m.resource_name == mat_name:
				return m
	return null


static func replace_material(root: Node, mat_name: String, mat: Material) -> int:
	var count := 0
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i)
			if m and m.resource_name == mat_name:
				mi.set_surface_override_material(i, mat)
				count += 1
	return count


static func unique_material(mi: MeshInstance3D) -> StandardMaterial3D:
	var m := (mi.mesh.surface_get_material(0) as StandardMaterial3D).duplicate() as StandardMaterial3D
	mi.set_surface_override_material(0, m)
	return m


# =============================================================================================
# Messen
# =============================================================================================
func _apply_mask() -> void:
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color.WHITE
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		if not mi.name.ends_with("Wire"):
			mi.material_override = white
	harbor.visible = false
	$Attach.visible = false
	$WorldEnvironment.environment = Environment.new()
	$WorldEnvironment.environment.background_mode = Environment.BG_COLOR
	$WorldEnvironment.environment.background_color = Color.BLACK
	$Overlay.visible = false


func _print_measure() -> void:
	# Ferse (5,5 cm hinter dem Knöchel), Ballen (Spitze des Fußknochens), Kopf (Mützendeckel)
	var vals := []
	for side in ["L", "R"]:
		for off in [Vector3(-0.055, -0.062, 0.0), Vector3(0.10, -0.062, 0.0)]:
			var p := _bone_point("foot." + side, off)
			var s := camera.unproject_position(p)
			vals.append("%.4f %.4f %.4f %.2f %.2f" % [p.x, p.y, p.z, s.x, s.y])
	var hp := _bone_point("head", Vector3(0.0, 0.26, 0.0))
	var hs := camera.unproject_position(hp)
	vals.append("%.4f %.4f %.4f %.2f %.2f" % [hp.x, hp.y, hp.z, hs.x, hs.y])
	print("F %d %.2f %.2f %.2f" % [roundi(t * 30.0), heading, foot_lock["L"], foot_lock["R"]])
	print("M %d %.4f %.4f %.4f %s %s" % [roundi(t * 30.0), walk_rate, walk_weight, fposmod(walk_time, 1.0),
		(_single_stance() if _single_stance() != "" else "D") if walk_weight > 0.999 else "-", " ".join(vals)])
