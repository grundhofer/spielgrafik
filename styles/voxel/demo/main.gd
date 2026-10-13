extends Node3D
## Katalogeintrag voxel: Hafen und Dachs aus Würfeln.
##
## Die Modelle kommen fertig voxelisiert aus scripts/voxelize_harbor.py (0,1-m-Voxel, Farbe je Voxel und
## Voxel-AO je Flächenecke in der Vertexfarbe) und scripts/voxelize_badger.py (1/32-m-Voxel, starre Teile je
## Knochen, Animationen aus shared/3d). Dieses Skript setzt das Voxel-Material, baut Wasser, Wolken und Rauch
## aus Würfeln (MultiMesh) und steuert den Ablauf: Totale, Fahrt zur Nahaufnahme, Dachs läuft, bremst, winkt.
## Alles hängt an der aufsummierten Zeit t und festen Seeds (deterministische Aufnahme).
##
## Schalter nach "--": --no-ao (gebackenes Voxel-AO aus), --no-edge (Voxelkanten aus), --no-shadow (Sonne
## ohne Schatten), --old-shadow (weiche Schatten der ersten Fassung), --static-cam, --close-cam, --mask (nur
## der Dachs weiß auf Schwarz), --measure (Fuß- und Kopfpunkte)

const VOXEL := preload("res://shaders/voxel.gdshader")
const WATER := preload("res://shaders/voxel_water.gdshader")
const CLOUD := preload("res://shaders/voxel_cloud.gdshader")

# --- Dachs (Werte aus shared/3d/badger_notes.md) -----------------------------------------------
const WALK_SPEED := 0.367
const WALK_RATE := 2.0
const TURN_T0 := 2.3
const TURN_T1 := 3.3
const TURN_DEG := -74.0
const MAX_TURN_STEP := deg_to_rad(3.0)
const BRAKE_T := 3.22
const BRAKE_TIME := 0.4
const IDLE_T := 3.57
const PIN_TIME := 0.4                  # Füße festhalten während der Überblendung Walk -> Idle (0,3 s)
const WAVE_T := 4.0
const WAVE_LEN := 1.5

# --- Kamera --------------------------------------------------------------------------------------
const CAM_T0 := 2.3
const CAM_T1 := 4.1
@export var close_pos := Vector3(-2.45, 1.4, 4.6)
@export var close_target := Vector3(0.75, 0.62, -4.9)
@export var close_fov := 53.0

# --- Umgebung ------------------------------------------------------------------------------------
const BEAM_PERIOD := 8.0
const BEAM_POSTER_T := 4.8
const BEAM_POSTER_DIR := Vector2(-0.8, 0.6)
const SEED := 20261011
const SUN_TRAVEL := Vector3(0.78, -0.5, -0.38)    # Abendsonne von links, etwa 30° hoch
const CHAR_FILL := Vector3(0.45, -0.35, -0.82)    # Figurenlicht von vorn links oben
const S := 0.1                                     # Voxelgröße der Welt (m)
const WATER_Y := -0.8

## Voxel-Material je glTF-Materialname: [Rauheit, Emission (Faktor auf die Voxelfarbe)]
const MAT := {
	"Stone": [0.92, 0.0], "StoneDark": [0.92, 0.0], "Wood": [0.85, 0.0], "WoodDark": [0.85, 0.0],
	"WhitePaint": [0.7, 0.0], "RedPaint": [0.6, 0.0], "Roof": [0.8, 0.0], "Glass": [0.3, 3.0],
	"Rope": [0.95, 0.0], "Metal": [0.5, 0.0], "Rock": [0.95, 0.0], "Sand": [1.0, 0.0],
	"Grass": [1.0, 0.0], "Earth": [1.0, 0.0],
	"FurDark": [0.9, 0.0], "FurLight": [0.9, 0.0], "Cap": [0.85, 0.0], "Brass": [0.4, 0.0],
	"Vest": [0.85, 0.0], "Shirt": [0.85, 0.0], "Scarf": [0.9, 0.0], "Satchel": [0.7, 0.0],
	"Parcel": [0.85, 0.0], "Nose": [0.4, 0.0], "Eye": [0.2, 0.0],
}

var t := 0.0
var walk_rate := WALK_RATE
var phase := 0
var boats := {}
var opts := {}
var cam_main: Transform3D
var water_mat: ShaderMaterial
var sky_mat: ShaderMaterial
var lantern_mat: ShaderMaterial
var lamp_mat: ShaderMaterial
var window_mat: ShaderMaterial
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0
var smoke: Array[MeshInstance3D] = []
var smoke_jit: Array[Vector3] = []
var clouds: MultiMeshInstance3D
var cloud_x0: PackedFloat32Array

@onready var harbor: Node3D = $Harbor
@onready var badger: Node3D = $Badger
@onready var player: AnimationPlayer = $Badger/AnimationPlayer
@onready var camera: Camera3D = $Camera
@onready var rotor: Node3D = $Attach/LighthouseLight/Rotor
@onready var lantern_omni: OmniLight3D = $Attach/LanternLight/Omni
@onready var lamp_omni: OmniLight3D = $Attach/LighthouseLight/Omni
@onready var effects: Node3D = $Effects


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		opts[a.trim_prefix("--")] = true
	cam_main = camera.global_transform
	var sun := $Sun as DirectionalLight3D
	sun.global_transform = Transform3D.IDENTITY.looking_at(SUN_TRAVEL, Vector3.UP)
	# Schatten: fast hart (Winkel 0,2°, blur 0,5, Filter "high" in project.godot, bias 0,15 / normal_bias 4),
	# damit jede Würfelfläche flach bleibt; die erste Fassung (1,2°, blur 1,0, Filter "low", bias 0,03 / 1,2)
	# legte ein bildschirmfestes Körnungsmuster (Schattenakne, weich gefiltert) über Pflaster und große
	# Flächen. Vergleichsschalter: --old-shadow, --no-shadow
	if opts.has("old-shadow"):
		sun.light_angular_distance = 1.2
		sun.shadow_blur = 1.0
		sun.shadow_bias = 0.03
		sun.shadow_normal_bias = 1.2
		RenderingServer.directional_soft_shadow_filter_set_quality(RenderingServer.SHADOW_QUALITY_SOFT_LOW)
	if opts.has("no-shadow"):
		sun.shadow_enabled = false
	var env := ($WorldEnvironment as WorldEnvironment).environment
	sky_mat = env.sky.sky_material as ShaderMaterial

	_apply_voxel_material(harbor)
	_apply_voxel_material(badger)
	# Figurenlicht: weiches Fülllicht von vorn links nur für den Dachs (Ebene 2), damit Gesicht und
	# Kostüm in der Nahaufnahme lesbar bleiben; Sonne und Schatten gelten weiter
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		mi.layers = 1 | 2
	($CharFill as DirectionalLight3D).global_transform = Transform3D.IDENTITY.looking_at(CHAR_FILL, Vector3.UP)
	lantern_mat = _own_material(harbor.find_child("LanternGlass", true, false))
	lamp_mat = _own_material(harbor.find_child("LighthouseLamp", true, false))
	window_mat = _own_material(harbor.find_child("CottageWindow", true, false))
	for glass in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
		(harbor.find_child(glass, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_attach_to_empties()

	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform

	_build_water()
	_build_clouds()
	_build_smoke()

	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	player.play("Walk")
	player.speed_scale = WALK_RATE

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	beam_yaw0 = atan2(-BEAM_POSTER_DIR.x, -BEAM_POSTER_DIR.y) - TAU * BEAM_POSTER_T / BEAM_PERIOD

	_setup_measure()
	if opts.has("mask"):
		_mask_mode()
	if opts.has("measure"):
		RenderingServer.frame_pre_draw.connect(_measure)
	_update(0.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)


func _update(delta: float) -> void:
	_update_badger(delta)
	_update_camera()
	water_mat.set_shader_parameter("time_s", t)
	sky_mat.set_shader_parameter("time_s", t)

	# Boote schaukeln um die Wasserlinie (wie shared/3d); die Voxel drehen sich mit (starre Körper)
	var k := 0
	for b in boats:
		var ph := 1.7 * k
		var roll := deg_to_rad(2.4) * sin(TAU * t / 3.4 + ph)
		var pitch := deg_to_rad(0.9) * sin(TAU * t / 4.6 + 0.8 + ph)
		var heave := 0.04 * sin(TAU * t / 3.9 + 2.1 + ph)
		var local := Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		(harbor.get_node(b) as Node3D).transform = boats[b] * local
		k += 1

	# Laterne flackert in Stufen (10 je Sekunde), wie ein Voxel-Licht; Glas, Licht und Glitzern gemeinsam
	var tick := floorf(t * 10.0) / 10.0
	var f := 0.8 + 0.2 * lantern_noise.get_noise_1d(tick * 7.0) + 0.08 * lantern_noise.get_noise_1d(tick * 31.0 + 50.0)
	lantern_omni.light_energy = 2.4 * f
	lantern_mat.set_shader_parameter("emission_energy", 3.2 * f)
	water_mat.set_shader_parameter("glint_a_power", clampf((f - 0.6) * 2.5, 0.2, 1.0))

	# Leuchtfeuer dreht sich; Lampe blitzt, wenn der Strahl zur Kamera zeigt
	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position).normalized()
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), 16.0)
	lamp_mat.set_shader_parameter("emission_energy", 3.0 + 9.0 * facing)
	lamp_omni.light_energy = 2.0 + 4.0 * facing
	water_mat.set_shader_parameter("glint_b_power", 0.5 + 0.5 * facing)

	_update_smoke()
	_update_clouds()
	($UI/Panel as Control).call("set_time", t)


# --- Dachs ---------------------------------------------------------------------------------------
func _update_badger(delta: float) -> void:
	# AnimationPlayer von Hand (advance): erst Pose, dann Vorschub, dann Drehung um den Standfuß.
	if phase == 0:
		walk_rate = WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, t))
		player.speed_scale = walk_rate
		player.advance(delta)
		var th := badger.rotation.y
		badger.position += Vector3(cos(th), 0.0, -sin(th)) * WALK_SPEED * walk_rate * delta
		# Drehung um den Standfuß (höchstens 3° je Bild); im Doppelstand mit halber Rate um die Mitte beider
		# Füße weiter (vorher hielt sie dort an und drehte in Schüben: 5 Bilder je 3°, dann 3 Bilder Pause)
		var th_goal := deg_to_rad(TURN_DEG) * smoothstep(TURN_T0, TURN_T1, t)
		var st := _stance()
		var max_step: float = MAX_TURN_STEP if st[1] == 1 else MAX_TURN_STEP * 0.5
		var dth := clampf(th_goal - badger.rotation.y, -max_step, max_step)
		if absf(dth) > 0.0 and st[1] > 0:
			var pv: Vector3 = st[0]
			pv.y = 0.0
			badger.position = pv + (badger.position - pv).rotated(Vector3.UP, dth)
			badger.rotation.y += dth
		if t >= IDLE_T:
			phase = 1
			player.speed_scale = 1.0
			player.play("Idle", 0.3)
		return
	if phase == 1 and t >= WAVE_T:
		phase = 2
		player.play("Wave", 0.25)
	elif phase == 2 and t >= WAVE_T + WAVE_LEN - 0.1:
		phase = 3
		player.play("Idle", 0.3)
	# Überblendung Walk -> Idle: Füße am Boden festhalten, indem die Figur um deren Verschiebung
	# zurückgesetzt wird (ein Fuß am Boden: dieser; zwei: ihre Mitte). Den Rest (die Füße rücken in der
	# Pose zusammen) fängt die Bein-IK unten ab: Jeder Fuß wird ab seinem ersten Bodenkontakt nach IDLE_T an
	# diesem Punkt festgehalten (Idle, Wave und Idle danach eingeschlossen). Waagerecht festgehalten wird
	# schon ab 2,5 cm Höhe, damit der aufsetzende Fuß die letzten Bilder senkrecht absetzt statt zu rutschen.
	var pin := {}
	if phase == 1 and t < IDLE_T + PIN_TIME:
		pin = _feet_on_ground()
	var down := _feet_on_ground(0.025)
	for side in down:
		if not foot_pin.has(side):
			foot_pin[side] = down[side]
	player.advance(delta)
	if not pin.is_empty():
		var now := _feet_on_ground()
		var d := Vector3.ZERO
		var n := 0
		for side in pin:
			if now.has(side):
				d += (now[side] as Vector3) - (pin[side] as Vector3)
				n += 1
		if n > 0:
			d /= n
			d.y = 0.0
			badger.position -= d
	for side in foot_pin:
		_pin_leg(side, foot_pin[side])


## Zwei-Knochen-IK für ein Bein nach advance(): verschiebt den Fuß (Lage und Drehung aus der Animation)
## waagerecht so, dass die Mitte aus Ferse und Zehe wieder auf dem festgehaltenen Punkt steht, und dreht
## Oberschenkel und Schienbein in ihrer bisherigen Beugeebene nach. Rechnet im Raum des Skeletts.
func _pin_leg(side: String, target_world: Vector3) -> void:
	var sk := _skel.global_transform
	var ski := sk.affine_inverse()
	var bt := _skel.find_bone("thigh." + side)
	var bs := _skel.find_bone("shin." + side)
	var bf := _skel.find_bone("foot." + side)
	var gt := _skel.get_bone_global_pose(bt)
	var gs := _skel.get_bone_global_pose(bs)
	var gf := _skel.get_bone_global_pose(bf)
	var mid := (_probe_world("heel." + side) + _probe_world("toe." + side)) * 0.5
	var dw := target_world - mid
	dw.y = 0.0
	if dw.length() < 1e-5:
		return
	var h := gt.origin
	var k := gs.origin
	var a := gf.origin
	var a2 := a + ski.basis * dw
	var l1 := (k - h).length()
	var l2 := (a - k).length()
	var to := a2 - h
	var d := clampf(to.length(), absf(l1 - l2) + 1e-4, l1 + l2 - 1e-4)
	var u := to.normalized()
	var n := (k - h).cross(a - h)
	if n.length() < 1e-6:
		n = gt.basis.x
	n = n.normalized()
	var v := n.cross(u).normalized()
	if v.dot(k - h) < 0.0:
		v = -v
	var ca := clampf((l1 * l1 + d * d - l2 * l2) / (2.0 * l1 * d), -1.0, 1.0)
	var k2 := h + l1 * (ca * u + sqrt(1.0 - ca * ca) * v)
	var a3 := h + u * d
	var q1 := Quaternion((k - h).normalized(), (k2 - h).normalized())
	var q2 := Quaternion((q1 * (a - k)).normalized(), (a3 - k2).normalized())
	_skel.set_bone_global_pose(bt, Transform3D(Basis(q1) * gt.basis, h))
	_skel.set_bone_global_pose(bs, Transform3D(Basis(q2 * q1) * gs.basis, k2))
	_skel.set_bone_global_pose(bf, Transform3D(gf.basis, a3))


func _update_camera() -> void:
	var close := Transform3D.IDENTITY.translated(close_pos).looking_at(close_target, Vector3.UP)
	if opts.has("close-cam"):
		camera.global_transform = close
		camera.fov = close_fov
		return
	if opts.has("static-cam"):
		return
	var k := smoothstep(CAM_T0, CAM_T1, t)
	k = k * k * (3.0 - 2.0 * k)
	var q0 := cam_main.basis.get_rotation_quaternion()
	var q1 := close.basis.get_rotation_quaternion()
	camera.global_transform = Transform3D(Basis(q0.slerp(q1, k)), cam_main.origin.lerp(close_pos, k))
	camera.fov = lerpf(42.0, close_fov, k)


# --- Materialien -----------------------------------------------------------------------------------
func _apply_voxel_material(root: Node) -> void:
	var cache := {}
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(i)
			if src == null:
				push_error("%s: Fläche %d ohne glTF-Material" % [mi.name, i])
				continue
			var key := src.resource_name
			if key == "Water":
				mi.visible = false      # das glatte Meer ersetzt das Voxelwasser (MultiMesh)
				continue
			if not MAT.has(key):
				push_error("Material %s fehlt in MAT" % key)
				continue
			if not cache.has(key):
				var m := ShaderMaterial.new()
				m.shader = VOXEL
				m.set_shader_parameter("roughness_v", MAT[key][0])
				m.set_shader_parameter("emission_energy", MAT[key][1])
				if opts.has("no-ao"):
					m.set_shader_parameter("ao_strength", 0.0)
				if opts.has("no-edge"):
					m.set_shader_parameter("edge_strength", 0.0)
				cache[key] = m
			mi.set_surface_override_material(i, cache[key])


func _own_material(mi: MeshInstance3D) -> ShaderMaterial:
	var m := (mi.get_surface_override_material(0) as ShaderMaterial).duplicate() as ShaderMaterial
	mi.set_surface_override_material(0, m)
	return m


func _attach_to_empties() -> void:
	for holder in $Attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt in harbor_voxel.glb" % holder.name)
			continue
		for c in holder.get_children():
			c.reparent(target, false)


# --- Wasser: Säulen aus Würfeln (MultiMesh), Wellen im Shader -------------------------------------
func _column_mesh(depth: float) -> ArrayMesh:
	# Einheitswürfel 0..1 in x und z, Oberseite bei y = 0, Schürze bis -depth; ohne Unterseite und ohne
	# Rückseite (-z, nie zur Kamera)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var quads := [
		[Vector3(0, 0, 1), Vector3(1, 0, 1), Vector3(1, 0, 0), Vector3(0, 0, 0), Vector3.UP],
		[Vector3(0, -depth, 1), Vector3(1, -depth, 1), Vector3(1, 0, 1), Vector3(0, 0, 1), Vector3.BACK],
		[Vector3(1, -depth, 1), Vector3(1, -depth, 0), Vector3(1, 0, 0), Vector3(1, 0, 1), Vector3.RIGHT],
		[Vector3(0, -depth, 0), Vector3(0, -depth, 1), Vector3(0, 0, 1), Vector3(0, 0, 0), Vector3.LEFT],
	]
	# Godot sieht Dreiecke im Uhrzeigersinn als Vorderseite: die Ecken laufen von außen gesehen gegen den
	# Uhrzeigersinn, also 0-2-1 / 0-3-2. (Die erste Fassung hatte 0-1-2 / 0-2-3: Mit cull_back fielen Oberseiten
	# und Vorderflächen weg, man sah in die Säulen hinein auf die Innenseiten der Seitenwände, das ergab die
	# senkrechten Nadeln statt Stufen.)
	for q in quads:
		st.set_normal(q[4])
		for idx in [0, 2, 1, 0, 3, 2]:
			st.add_vertex(q[idx])
	return st.commit()


func _build_water() -> void:
	water_mat = ShaderMaterial.new()
	water_mat.shader = WATER
	water_mat.set_shader_parameter("step_h", S)
	var mask := (load("res://textures/water_mask.png") as Texture2D).get_image()   # verlustfrei importiert
	if mask == null:
		push_error("water_mask.png fehlt")
		return
	# Maske: x0 = -20, z0 = -35, 0,1 m je Pixel (scripts/voxelize_harbor.py)
	var mx0 := -20.0
	var mz0 := -35.0
	# Nähe: 0,1-m-Säulen im Hafen; Ferne: 0,4-m-Säulen bis 120 m; dahinter das glatte Meer (Sea) unsichtbar,
	# der Himmel unter dem Horizont hat Meeresfarbe
	var regions := [
		[Rect2(-16.0, -32.0, 46.0, 31.7), 0.1],
		[Rect2(-60.0, -120.0, 120.0, 88.0), 0.4],
	]
	for r in regions:
		var rect: Rect2 = r[0]
		var sc: float = r[1]
		var nx := int(round(rect.size.x / sc))
		var nz := int(round(rect.size.y / sc))
		var buf := PackedFloat32Array()
		buf.resize(nx * nz * 16)
		var n := 0
		for iz in nz:
			for ix in nx:
				var x := rect.position.x + ix * sc
				var z := rect.position.y + iz * sc
				var shore := 1.0
				var boat := 0.0
				if sc < 0.2:
					var px := int(round((x + 0.05 - mx0) / 0.1 - 0.5))
					var pz := int(round((z + 0.05 - mz0) / 0.1 - 0.5))
					if px >= 0 and pz >= 0 and px < mask.get_width() and pz < mask.get_height():
						var c := mask.get_pixel(px, pz)
						if c.r > 0.5:
							continue
						shore = c.g
						boat = c.b
				elif rect.has_point(Vector2(x, z)) and z > -32.0 and x > -16.0 and x < 30.0:
					continue
				var o := n * 16
				buf[o + 0] = sc; buf[o + 1] = 0.0; buf[o + 2] = 0.0; buf[o + 3] = x
				buf[o + 4] = 0.0; buf[o + 5] = sc; buf[o + 6] = 0.0; buf[o + 7] = WATER_Y
				buf[o + 8] = 0.0; buf[o + 9] = 0.0; buf[o + 10] = sc; buf[o + 11] = z
				buf[o + 12] = shore; buf[o + 13] = boat; buf[o + 14] = 0.0; buf[o + 15] = 0.0
				n += 1
		buf.resize(n * 16)
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_custom_data = true
		mm.mesh = _column_mesh(4.0 if sc < 0.2 else 1.5)
		mm.instance_count = n
		mm.buffer = buf
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.material_override = water_mat
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mmi.extra_cull_margin = 1.0
		effects.add_child(mmi)


# --- Wolken: flache Quader-Gruppen weit hinten, treiben langsam nach rechts -----------------------
func _build_clouds() -> void:
	var mat := ShaderMaterial.new()
	mat.shader = CLOUD
	var box := BoxMesh.new()
	box.size = Vector3.ONE
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED + 1
	var cell := 9.0
	# (Mitte x, Höhe y, Entfernung z, Breite in Zellen, Tiefe in Zellen)
	var layout := [
		Vector4(-170.0, 64.0, -430.0, 15.0), Vector4(-40.0, 92.0, -520.0, 11.0),
		Vector4(120.0, 52.0, -440.0, 9.0), Vector4(30.0, 30.0, -640.0, 19.0),
		Vector4(250.0, 80.0, -560.0, 12.0),
	]
	var xf: Array[Transform3D] = []
	for c in layout:
		var w := int(c.w)
		var d := 4 + rng.randi_range(0, 2)
		for ix in w:
			for iz in d:
				# runde Form: Rand ausdünnen, oben eine zweite Lage in der Mitte
				var u := (ix + 0.5) / w * 2.0 - 1.0
				var v := (iz + 0.5) / d * 2.0 - 1.0
				var r := u * u + v * v * 0.8
				if r > 1.0 or rng.randf() < r * 0.45:
					continue
				var p := Vector3(c.x + (ix - w * 0.5) * cell, c.y, c.z + (iz - d * 0.5) * cell)
				xf.append(Transform3D(Basis.from_scale(Vector3(cell, cell * 0.7, cell)), p))
				if r < 0.45 and rng.randf() < 0.8:
					xf.append(Transform3D(Basis.from_scale(Vector3(cell, cell * 0.7, cell)), p + Vector3(0, cell * 0.7, 0)))
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = box
	mm.instance_count = xf.size()
	cloud_x0 = PackedFloat32Array()
	for i in xf.size():
		mm.set_instance_transform(i, xf[i])
		cloud_x0.append(xf[i].origin.x)
	clouds = MultiMeshInstance3D.new()
	clouds.multimesh = mm
	clouds.material_override = mat
	clouds.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	effects.add_child(clouds)


func _update_clouds() -> void:
	clouds.position.x = 2.5 * t


# --- Rauch: Würfel, die aufsteigen, wachsen und wieder schrumpfen ------------------------------------
const SMOKE_PUFFS := 8
const SMOKE_LIFE := 4.0


func _build_smoke() -> void:
	var m := ShaderMaterial.new()
	m.shader = VOXEL
	m.set_shader_parameter("ao_strength", 0.0)
	m.set_shader_parameter("use_color", 1.0)
	m.set_shader_parameter("flat_color", Color(0.80, 0.78, 0.80))
	var box := BoxMesh.new()
	box.size = Vector3.ONE
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	var anchor := harbor.find_child("ChimneySmoke", true, false) as Node3D
	for i in SMOKE_PUFFS:
		var p := MeshInstance3D.new()
		p.mesh = box
		p.material_override = m
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		anchor.add_child(p)
		smoke.append(p)
		smoke_jit.append(Vector3(rng.randf_range(-0.2, 0.2), rng.randf_range(0.85, 1.2), rng.randf_range(-0.06, 0.06)))


func _update_smoke() -> void:
	for i in smoke.size():
		var j := smoke_jit[i]
		var age := fposmod(t / SMOKE_LIFE + float(i) / SMOKE_PUFFS + j.z, 1.0)
		var rise := 1.0 - pow(1.0 - age, 1.6)
		# Steighöhe 1,9 m und Drift 2,6 m nach rechts: In der Totale endet der Rauch so frei vor dem Himmel,
		# etwa 12 px unter dem Ortsschild (mit 2,8 m stieg er bis an dessen Unterkante und wirkte angeschnitten)
		var pos := Vector3(2.6 * age * age + j.x * age, -0.1 + 1.9 * rise, 0.0)
		# Würfelgröße in ganzen Voxeln (0,1 m), Position auf dem Voxelraster
		var sz := (0.2 + 0.45 * rise) * (1.0 - smoothstep(0.75, 1.0, age)) * smoothstep(0.0, 0.08, age) * j.y
		sz = roundf(sz / S) * S
		p_set(smoke[i], (pos / S).round() * S, sz)


func p_set(p: MeshInstance3D, pos: Vector3, sz: float) -> void:
	p.position = pos
	p.scale = Vector3.ONE * maxf(sz, 0.001)
	p.visible = sz > 0.05


# --- Messen ---------------------------------------------------------------------------------------
var _skel: Skeleton3D
var _probe := {}
var foot_pin := {}       # Seite -> festgehaltener Bodenpunkt (Welt) ab IDLE_T


func _setup_measure() -> void:
	_skel = badger.find_child("Skeleton3D", true, false) as Skeleton3D
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


## Bodenpunkt für die Drehung: [Punkt, Zahl der Füße am Boden]. Ein Fuß: Mitte seiner Punkte am Boden
## (Ferse und/oder Zehe unter 1 cm); zwei Füße: Mitte beider.
func _stance() -> Array:
	var down := {}
	for side in ["L", "R"]:
		var pts: Array[Vector3] = []
		for k in ["heel.", "toe."]:
			var w := _probe_world(k + side)
			if w.y < 0.01:
				pts.append(w)
		if not pts.is_empty():
			var m := Vector3.ZERO
			for w in pts:
				m += w
			down[side] = m / pts.size()
	var c := Vector3.ZERO
	for side in down:
		c += down[side]
	return [c / maxf(down.size(), 1), down.size()]


## Füße, deren Ferse und Zehe beide am Boden sind (y < limit, Standard 1,2 cm): Seite -> Mitte aus Ferse
## und Zehe (Welt)
func _feet_on_ground(limit := 0.012) -> Dictionary:
	var out := {}
	for side in ["L", "R"]:
		var h := _probe_world("heel." + side)
		var o := _probe_world("toe." + side)
		if maxf(h.y, o.y) < limit:
			out[side] = (h + o) * 0.5
	return out


func _measure() -> void:
	var line := "M %.4f rot %.2f %.4f %.4f" % [t, rad_to_deg(badger.rotation.y), badger.position.x, badger.position.z]
	for k in ["heel.L", "toe.L", "heel.R", "toe.R", "head"]:
		var w := _probe_world(k)
		var sp := camera.unproject_position(w)
		line += " %s %.4f %.4f %.4f %.2f %.2f" % [k, w.x, w.y, w.z, sp.x, sp.y]
	print(line)


func _mask_mode() -> void:
	harbor.visible = false
	effects.visible = false
	$UI.visible = false
	$Attach.visible = false
	var env := ($WorldEnvironment as WorldEnvironment).environment
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color.BLACK
	env.glow_enabled = false
	env.fog_enabled = false
	env.ssao_enabled = false
	env.adjustment_enabled = false
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color.WHITE
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			mi.set_surface_override_material(i, white)
