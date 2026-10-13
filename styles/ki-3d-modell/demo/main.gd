extends Node3D
## KI-3D-Modell (lokal): Hafen aus shared/3d mit Modellen, die TripoSR auf dem Mac aus KI-Bildern gemacht hat.
##
## Dachs: Mesh aus TripoSR (Vorderansicht), in Blender dezimiert und gebacken, Gewichte von der Figur aus
## shared/3d übertragen; Rig und Animationen (Idle, Walk) sind die von shared/3d/badger.glb.
## Fässer, Laterne, Boot: TripoSR-Modelle statt der Originale (Barrel1/2, LanternPost, BoatB ausgeblendet).
## Ablauf 6 s: Der Dachs läuft schräg auf die Kamera zu, bremst und blendet auf Idle. Kein Drehen auf der
## Stelle: das ließ die Füße bis 1,8 px je Bild rutschen (gemessen), die Laufrichtung zeigt schon zur Kamera.
## Dazu Wasser, schaukelnde Boote, flackernde Laterne, Leuchtfeuer (Rauch läuft mit, der Schornstein liegt
## außerhalb des Ausschnitts), oben links die Drehteller.
## Alles hängt an der aufsummierten Zeit t und festen Seeds (tools/capture.py nimmt mit --fixed-fps auf).
##
## Schalter nach "--": --t0=S (Startzeit), --cam=x,y,z,neigung,gieren,fov, --measure (Fußpunkte je Bild
## auf stdout), --mask (nur der Dachs, weiß auf Schwarz, ohne Oberfläche), --no-ui.

# --- Kamera (feste Nahaufnahme) ----------------------------------------------------------------
var CAM_POS := Vector3(-0.5, 0.95, 6.0)
var CAM_ROT := Vector3(1.5, -6.0, 0.0)       # Grad: Neigung (x), Gieren (y); Werte aus scripts/frame_shot.py
var CAM_FOV := 46.0

# --- Dachs ----------------------------------------------------------------------------------
const WALK_SPEED := 0.367        # m/s bei speed_scale 1 (badger_notes.md), dann rutschen die Füße nicht
const WALK_RATE := 2.0
const HEADING := 70.0            # Grad: Laufrichtung gegen +X, zur Kamera hin gedreht (90 = auf die Kamera zu)
const STOP := Vector3(-0.55, 0.0, 2.65)
const BRAKE_T := 3.15
const BRAKE_TIME := 0.5
const IDLE_T := 3.65             # Walk steht (Tempo 0, Walk-Zeit 6,8 = Durchgang: rechter Fuß steht), Überblenden auf Idle
const BLEND_TIME := 0.45

# --- Requisiten (Godot-Koordinaten, Ursprung der Modelle unten Mitte, Blick nach +X) --------------
const BARREL_A := Vector3(0.45, 0.0, -0.2)
const BARREL_B := Vector3(1.1, 0.0, -0.65)
const LANTERN_POS := Vector3(2.9, 0.0, 0.4)
const LANTERN_YAW := -105.0      # Grad; -90 = Vorderseite zur Kamera
const BOAT_POS := Vector3(6.75, -0.8, -6.4)  # an der Stelle von BoatB, Ursprung auf der Wasserlinie
const BOAT_DRAFT := 0.42                      # m: Kiel unter der Wasserlinie

# --- Umgebung --------------------------------------------------------------------------------
const BEAM_PERIOD := 8.0
const BEAM_FACING_T := 4.6
const SMOKE_PUFFS := 9
const SMOKE_LIFE := 4.5
const SEED := 20261013

@export var water_material: ShaderMaterial

var t := 0.0
var walk_rate := WALK_RATE
var tree := AnimationTree.new()
var walk_dist := 0.0
var boats := {}
var smoke: Array[MeshInstance3D] = []
var smoke_jitter: Array[Vector3] = []
var lamp_mat: StandardMaterial3D
var glow_mat: StandardMaterial3D
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0
var measure := false
var mask := false
var t0 := 0.0
var frame := 0
var start := Vector3.ZERO
var dir := Vector3.RIGHT

@onready var harbor: Node3D = $Harbor
@onready var badger: Node3D = $Badger
@onready var player: AnimationPlayer = $Badger/AnimationPlayer
@onready var camera: Camera3D = $Camera
@onready var rotor: Node3D = $Attach/LighthouseLight/Rotor
@onready var lamp_omni: OmniLight3D = $Attach/LighthouseLight/Omni
@onready var lantern: Node3D = $Props/Lantern
@onready var lantern_omni: OmniLight3D = $Props/Lantern/LanternLight
@onready var ui: Control = $UI/Panel


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a.begins_with("--cam="):
			var v := a.substr(6).split_floats(",")
			CAM_POS = Vector3(v[0], v[1], v[2])
			CAM_ROT = Vector3(v[3], v[4], 0.0)
			CAM_FOV = v[5]
		elif a == "--measure":
			measure = true
		elif a == "--mask":
			mask = true
		elif a == "--no-ui":
			ui.visible = false
	camera.position = CAM_POS
	camera.rotation_degrees = CAM_ROT
	camera.fov = CAM_FOV

	_attach_to_empties()
	var water := find_material(harbor, "Water") as StandardMaterial3D
	water_material.set_shader_parameter("albedo", water.albedo_color)
	water_material.set_shader_parameter("roughness", water.roughness)
	assert(replace_material(harbor, "Water", water_material) == 1, "Material Water nicht gefunden")
	(harbor.get_node("Sea") as MeshInstance3D).extra_cull_margin = 1.0
	lamp_mat = unique_material(harbor.find_child("LighthouseLamp", true, false))
	for glass in ["LighthouseLamp", "CottageWindow"]:
		(harbor.find_child(glass, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	# Originale, die durch KI-Modelle ersetzt sind, ausblenden
	for n in ["Barrel1", "Barrel2", "LanternPost", "BoatB"]:
		(harbor.get_node(n) as Node3D).visible = false
	_place_props()
	# BoatA um 180° gedreht (gleicher Liegeplatz): sonst steht sein Mast in der Nahaufnahme genau über dem
	# Kopf des Dachses. Verschieben ging nicht, rechts liegt der Steg (x 2,65 bis 4,25).
	(harbor.get_node("BoatA") as Node3D).rotate_y(PI)
	boats["BoatA"] = (harbor.get_node("BoatA") as Node3D).transform
	boats["TSR"] = ($Props/BoatPivot as Node3D).transform

	# Dachs: glTF kennt kein Loop-Flag
	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	_build_tree()
	dir = Vector3(cos(deg_to_rad(HEADING)), 0.0, sin(deg_to_rad(HEADING)))
	# Laufweg rückwärts vom Haltepunkt: Strecke bis IDLE_T aus Tempo und Bremsrampe (numerisch, 1/300 s)
	var d := 0.0
	var tt := 0.0
	while tt < IDLE_T:
		d += WALK_SPEED * WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, tt)) / 300.0
		tt += 1.0 / 300.0
	start = STOP - dir * d
	badger.position = start
	badger.rotation.y = -deg_to_rad(HEADING)

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	var to_cam := camera.global_position - rotor.global_position
	beam_yaw0 = atan2(-to_cam.x, -to_cam.z) - TAU * BEAM_FACING_T / BEAM_PERIOD
	_build_smoke()
	if mask:
		_setup_mask()
	# Vorspulen für Standbilder ab t0 (gleiche Schritte wie die Aufnahme)
	while t < t0 - 1e-6:
		var dt := minf(1.0 / 30.0, t0 - t)
		t += dt
		_update(dt)
	_update(0.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)
	frame += 1


func _update(delta: float) -> void:
	_update_badger(delta)
	var k := 0
	for b in boats:
		var ph := 1.7 * k
		var roll := deg_to_rad(2.2) * sin(TAU * t / 3.4 + ph)
		var pitch := deg_to_rad(0.9) * sin(TAU * t / 4.6 + 0.8 + ph)
		var heave := 0.035 * sin(TAU * t / 3.9 + 2.1 + ph)
		var local := Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		var node: Node3D = harbor.get_node("BoatA") if b == "BoatA" else $Props/BoatPivot
		node.transform = boats[b] * local
		k += 1
	water_material.set_shader_parameter("time_s", t)

	var f := 0.82 + 0.18 * lantern_noise.get_noise_1d(t * 7.0) + 0.06 * lantern_noise.get_noise_1d(t * 31.0 + 50.0)
	lantern_omni.light_energy = 1.8 * f
	glow_mat.albedo_color = Color(1.5, 0.98, 0.5, 0.5 * f)

	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position).normalized()
	var facing := pow(clampf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0, 1.0), 24.0)
	lamp_mat.emission_energy_multiplier = 4.0 + 26.0 * facing
	lamp_omni.light_energy = 2.0 + 4.0 * facing
	_update_smoke()
	if ui.visible:
		ui.call("set_time", t)
	if measure:
		_measure()


func _update_badger(delta: float) -> void:
	# Bremsen: Vorschub und Walk-Tempo sinken gemeinsam (TimeScale), danach Walk eingefroren nach Idle
	# überblenden (Blend2). Mit AnimationPlayer.play("Idle", x) liefe Walk beim Überblenden weiter, während der
	# Dachs steht: der Standfuß rutschte dann bis 1,35 px je Bild (gemessen).
	walk_rate = WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, t))
	walk_dist += WALK_SPEED * walk_rate * delta
	badger.position = start + dir * walk_dist
	tree.set("parameters/WalkSpeed/scale", walk_rate)
	tree.set("parameters/Blend/blend_amount", 1.0 - smoothstep(IDLE_T, IDLE_T + BLEND_TIME, t))
	tree.advance(delta)


func _build_tree() -> void:
	var bt := AnimationNodeBlendTree.new()
	var idle := AnimationNodeAnimation.new()
	idle.animation = "Idle"
	var walk := AnimationNodeAnimation.new()
	walk.animation = "Walk"
	bt.add_node("Idle", idle)
	bt.add_node("Walk", walk)
	bt.add_node("WalkSpeed", AnimationNodeTimeScale.new())
	bt.add_node("Blend", AnimationNodeBlend2.new())
	bt.connect_node("WalkSpeed", 0, "Walk")
	bt.connect_node("Blend", 0, "Idle")
	bt.connect_node("Blend", 1, "WalkSpeed")
	bt.connect_node("output", 0, "Blend")
	tree.tree_root = bt
	tree.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	badger.add_child(tree)
	tree.anim_player = tree.get_path_to(player)
	tree.active = true


# --- Requisiten -------------------------------------------------------------------------------
func _place_props() -> void:
	$Props/BarrelA.position = BARREL_A
	$Props/BarrelA.rotation_degrees.y = -70.0
	$Props/BarrelB.position = BARREL_B
	$Props/BarrelB.rotation_degrees.y = 25.0
	lantern.position = LANTERN_POS
	lantern.rotation_degrees.y = LANTERN_YAW
	($Props/BoatPivot as Node3D).position = BOAT_POS
	($Props/BoatPivot as Node3D).rotation_degrees.y = 160.0
	$Props/BoatPivot/Boat.position = Vector3(0.0, -BOAT_DRAFT, 0.0)
	# Laternenkörper im KI-Modell suchen: Eckpunkte weit vom Pfosten und unterhalb des Auslegers
	var c := _lantern_center(lantern)
	lantern_omni.position = c
	glow_mat = StandardMaterial3D.new()
	glow_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	glow_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	glow_mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	glow_mat.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	glow_mat.no_depth_test = true
	var grad := Gradient.new()
	grad.offsets = PackedFloat32Array([0.0, 0.25, 1.0])
	grad.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 0.45), Color(1, 1, 1, 0)])
	var tex := GradientTexture2D.new()
	tex.gradient = grad
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	glow_mat.albedo_texture = tex
	var q := QuadMesh.new()
	q.size = Vector2(0.55, 0.55)
	var glow := MeshInstance3D.new()
	glow.mesh = q
	glow.material_override = glow_mat
	glow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	glow.position = c
	lantern.add_child(glow)


func _lantern_center(root: Node3D) -> Vector3:
	var mi := root.find_children("*", "MeshInstance3D", true, false)[0] as MeshInstance3D
	var verts: PackedVector3Array = mi.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	var to_root := root.global_transform.affine_inverse() * mi.global_transform
	# Pfosten: Eckpunkte unter 0,5 m Höhe -> Mitte in xz
	var post := Vector3.ZERO
	var n := 0
	for v in verts:
		if v.y < 0.5:
			post += v
			n += 1
	post /= maxf(n, 1)
	var sum := Vector3.ZERO
	var m := 0
	for v in verts:
		var h := Vector2(v.x - post.x, v.z - post.z).length()
		if h > 0.55 and v.y > 0.5 and v.y < 1.7:
			sum += v
			m += 1
	return to_root * (sum / maxf(m, 1))


# --- Messen: Fuß- und Kopfpunkte im Bild ---------------------------------------------------------
func _measure() -> void:
	var sk := badger.find_child("Skeleton3D", true, false) as Skeleton3D
	var out := "M %d %.4f" % [frame, t]
	for bn in ["foot.L", "foot.R", "head"]:
		var i := sk.find_bone(bn)
		var p := sk.global_transform * sk.get_bone_global_pose(i).origin
		var tip := p
		if bn.begins_with("foot"):
			# Ballen = Knochenspitze: 12,8 cm entlang der Knochenachse (Kopf/Spitze aus badger_notes.md)
			tip = sk.global_transform * (sk.get_bone_global_pose(i) * Vector3(0.0, 0.128, 0.0))
		var s := camera.unproject_position(tip)
		out += " %s %.3f %.3f %.4f" % [bn, s.x, s.y, tip.y]
	print(out)


func _setup_mask() -> void:
	ui.visible = false
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color.WHITE
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		mi.material_override = white
	for n in [harbor, $Props]:
		n.visible = false
	$Attach.visible = false
	var env := ($WorldEnvironment as WorldEnvironment).environment.duplicate() as Environment
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color.BLACK
	env.fog_enabled = false
	env.glow_enabled = false
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	($WorldEnvironment as WorldEnvironment).environment = env


# --- Lichter an die Empties ------------------------------------------------------------------------
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


# --- Rauch ---------------------------------------------------------------------------------------
func _build_smoke() -> void:
	var grad := Gradient.new()
	grad.offsets = PackedFloat32Array([0.0, 0.55, 1.0])
	grad.colors = PackedColorArray([Color(1, 1, 1, 0.9), Color(1, 1, 1, 0.45), Color(1, 1, 1, 0)])
	var tex := GradientTexture2D.new()
	tex.gradient = grad
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	tex.width = 64
	tex.height = 64
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = tex
	mat.albedo_color = Color(0.72, 0.72, 0.76)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	mat.roughness = 1.0
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
		p.position = Vector3(1.4 * age * age + j.x * age, 2.2 * age * j.y, j.z * age)
		var s := lerpf(0.35, 1.5, sqrt(age))
		p.scale = Vector3(s, s, s)
		p.transparency = 1.0 - 0.55 * smoothstep(0.0, 0.12, age) * (1.0 - smoothstep(0.45, 1.0, age))
