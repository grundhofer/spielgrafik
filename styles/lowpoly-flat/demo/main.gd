extends Node3D
## Katalogeintrag lowpoly-flat: Low-Poly mit Flat-Shading auf der gemeinsamen 3D-Grundlage (shared/3d).
##
## Hafen: Low-Poly-Fassung aus blender/build_lowpoly.py (Gelände und Felsen grob reduziert, flache
## Normalen, Farbabweichung je Facette als Vertexfarbe). Dachs: badger_low.glb (876 Dreiecke).
## Alle glTF-Materialien werden nach Namen durch shaders/lowpoly.gdshader mit einer Pastell-Palette
## ersetzt (eine Farbe je Material, keine Texturen, eine Normale je Facette). Wasser ist ein eigenes,
## unregelmäßiges Dreiecksnetz mit Wellen im Vertex-Shader; Wolken, Rauch, Möwen und Lichtkegel sind
## grobe Formen im selben Stil. Alles hängt an der aufsummierten Zeit t und an festen Seeds.
##
## Vergleichsschalter (nach --): --smooth (weiche Normalen, Original-Hafen aus shared/3d, keine
## Facettenfarbe), --no-jitter (keine Farbabweichung je Facette), --static-cam (immer Totale).
## Messen: --measure (Fuß- und Kopfpunkte je Bild), --mask (nur der Dachs, weiß auf Schwarz),
## --brake=<s> (anderer Bremsbeginn), --t0=<s> (Zeit startet später: Langzeitprüfung der Umgebung).

# --- Dachs (Werte aus shared/3d/badger_notes.md) ----------------------------------------------
const WALK_SPEED := 0.367        # m/s bei Abspieltempo 1
const WALK_RATE := 2.0
const START_X := -5.0
const TURN_T0 := 2.2             # biegt in den letzten Schritten zur Nahaufnahme-Kamera ab
const TURN_T1 := 3.2
@export var turn_deg := -67.0
const MAX_TURN_STEP := deg_to_rad(3.0)   # je Bild, nur bei einem Fuß am Boden, um dessen Bodenpunkt
@export var brake_t := 3.22
const BRAKE_TIME := 0.4
const BLEND_IDLE := 0.3          # Überblendung Walk -> Idle
const WAVE_T := 4.0
const WAVE_LEN := 1.5

# --- Kamera ------------------------------------------------------------------------------------
const CAM_T0 := 2.0              # bis hier Hauptkamera (Totale) wie shared/3d
const CAM_T1 := 3.9              # ab hier Nahaufnahme
@export var close_pos := Vector3(-1.25, 1.3, 5.25)
@export var close_target := Vector3(-1.25, 1.125, -4.75)
@export var close_fov := 50.0

# --- Umgebung ----------------------------------------------------------------------------------
const BEAM_PERIOD := 8.0
const BEAM_POSTER_T := 4.8       # zu dieser Zeit zeigt der Strahl schräg nach links vorn
const BEAM_POSTER_DIR := Vector2(-0.8, 0.6)
const SMOKE_PUFFS := 9
const SMOKE_LIFE := 4.2
const SEED := 20261012
const SUN_TRAVEL := Vector3(0.82, -0.3, -0.36)    # Abendsonne tief von links vorn
const FILL_TRAVEL := Vector3(-0.6, -0.55, 0.45)   # Fülllicht von rechts hinten oben

const LOWPOLY := preload("res://shaders/lowpoly.gdshader")
const CLOUD := preload("res://shaders/facet_cloud.gdshader")

## Pastell-Palette je glTF-Material (sRGB). Eine Farbe je Material; Abstufung nur durch Facetten und Licht.
const PALETTE := {
	"Stone": Color("d8c3b8"),
	"StoneDark": Color("9a8494"),
	"Wood": Color("d39a6a"),
	"WoodDark": Color("8a5a5e"),
	"WhitePaint": Color("f7efe6"),
	"RedPaint": Color("e8665e"),
	"Roof": Color("6f6fae"),
	"Rope": Color("c99a6a"),
	"Metal": Color("5d5876"),
	"Rock": Color("a8909e"),
	"Sand": Color("f0d2a2"),
	"Grass": Color("9ccf8e"),
	"Glass": Color("ffe1a6"),
}
const BADGER_PALETTE := {
	"FurDark": Color("4f4458"),
	"FurLight": Color("fdf3e6"),
	"Cap": Color("4f8a66"),
	"Brass": Color("f2c464"),
	"Vest": Color("74a86a"),
	"Shirt": Color("fbe9d0"),
	"Scarf": Color("ee5a62"),
	"Satchel": Color("a8673f"),
	"Parcel": Color("eeb57c"),
	"Nose": Color("2e2636"),
	"Eye": Color("2e2636"),
}

@export var water_material: ShaderMaterial

var t := 0.0
var walk_rate := WALK_RATE
var phase := 0
var boats := {}
var smoke: Array[MeshInstance3D] = []
var smoke_jitter: Array[Vector3] = []
var clouds: Array[Node3D] = []
var cloud_x0: Array[float] = []
var gulls: Array[Dictionary] = []
var lantern_mat: ShaderMaterial
var lamp_mat: ShaderMaterial
var window_mat: ShaderMaterial
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0
var cam_main: Transform3D
var lock_side := ""              # Fuß, der beim Überblenden auf Idle festgehalten wird
var lock_pos := Vector3.ZERO
var lock_until := -1.0
var opts := {}

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
		var kv := a.trim_prefix("--").split("=")
		opts[kv[0]] = kv[1] if kv.size() > 1 else true
	if opts.has("brake"):
		brake_t = float(opts["brake"])   # nur für Messläufe (scripts/measure_badger.py)
	if opts.has("t0"):
		t = float(opts["t0"])   # Langzeitprüfung der Umgebungsanimationen (Dachs bleibt am Start stehen)
	if opts.has("smooth"):
		# Vergleich: Original-Hafen aus shared/3d (weiche Normalen, volles Gelände) mit derselben Palette
		var orig := (load("res://models/harbor.glb") as PackedScene).instantiate() as Node3D
		harbor.replace_by(orig)
		harbor.queue_free()
		orig.name = "Harbor"
		harbor = orig
	cam_main = camera.global_transform
	($Sun as DirectionalLight3D).global_transform = Transform3D.IDENTITY.looking_at(SUN_TRAVEL, Vector3.UP)
	($Fill as DirectionalLight3D).global_transform = Transform3D.IDENTITY.looking_at(FILL_TRAVEL, Vector3.UP)

	_apply_palette(harbor, PALETTE, true)
	_apply_palette(badger, BADGER_PALETTE, false)
	_attach_to_empties()

	# Leuchtende Teile: je Objekt eigenes Material (einzeln flackern/blitzen), werfen keinen Schatten
	lantern_mat = _own_material(harbor.find_child("LanternGlass", true, false))
	lamp_mat = _own_material(harbor.find_child("LighthouseLamp", true, false))
	window_mat = _own_material(harbor.find_child("CottageWindow", true, false))
	for glass in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
		(harbor.find_child(glass, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	window_mat.set_shader_parameter("emission_energy", 0.9)

	# Meer: eigenes facettiertes Netz statt des glTF-Gitters
	(harbor.get_node("Sea") as Node3D).visible = false
	_build_water()

	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform

	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	# Tempo des Laufzyklus als eigenes Abspieltempo (play(..., custom_speed)) statt speed_scale:
	# speed_scale gilt auch für die ausgeblendete Animation und die Überblendung. So bleibt Walk beim
	# Überblenden auf Idle stehen, statt mit vollem Tempo weiterzulaufen (Füße rutschten sonst).
	player.play("Walk", -1, WALK_RATE)
	badger.position = Vector3(START_X, 0.012, 1.2)   # Pflaster liegt bis 8 mm über y = 0

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	# Strahlrichtung = -Z des Rotors = (-sin y, 0, -cos y)
	beam_yaw0 = atan2(-BEAM_POSTER_DIR.x, -BEAM_POSTER_DIR.y) - TAU * BEAM_POSTER_T / BEAM_PERIOD

	_build_smoke()
	_build_clouds()
	_build_gulls()
	if opts.has("mask"):
		_mask_mode()
	_setup_measure()
	if opts.has("measure"):
		RenderingServer.frame_pre_draw.connect(_measure)
	_update(0.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)


func _update(delta: float) -> void:
	RenderingServer.global_shader_parameter_set("lp_time", t)
	_update_badger(delta)
	_update_camera()

	var k := 0
	for b in boats:
		var ph := 1.7 * k
		var roll := deg_to_rad(2.4) * sin(TAU * t / 3.4 + ph)
		var pitch := deg_to_rad(1.0) * sin(TAU * t / 4.6 + 0.8 + ph)
		var heave := 0.04 * sin(TAU * t / 3.9 + 2.1 + ph)
		var local := Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		(harbor.get_node(b) as Node3D).transform = boats[b] * local
		k += 1

	# Laterne flackert (Rauschen mit festem Seed): Glas und Licht gemeinsam
	var f := 0.8 + 0.2 * lantern_noise.get_noise_1d(t * 7.0) + 0.08 * lantern_noise.get_noise_1d(t * 31.0 + 50.0)
	lantern_omni.light_energy = 1.8 * f
	lantern_mat.set_shader_parameter("emission_energy", 3.2 * f)

	# Leuchtfeuer dreht sich; die Lampe blitzt auf, wenn der Strahl zur Kamera zeigt
	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position).normalized()
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), 16.0)
	lamp_mat.set_shader_parameter("emission_energy", 3.0 + 9.0 * facing)
	lamp_omni.light_energy = 2.0 + 4.0 * facing

	_update_smoke()
	_update_clouds()
	_update_gulls()


# --- Dachs ------------------------------------------------------------------------------------
func _update_badger(delta: float) -> void:
	# AnimationPlayer von Hand (advance): erst Pose, dann Vorschub, dann Drehung um den Standfuß.
	if phase == 0:
		walk_rate = WALK_RATE * (1.0 - smoothstep(brake_t, brake_t + BRAKE_TIME, t))
		player.play("Walk", -1, walk_rate)
		player.advance(delta)
		var th := badger.rotation.y
		badger.position += Vector3(cos(th), 0.0, -sin(th)) * WALK_SPEED * walk_rate * delta
		var th_goal := deg_to_rad(turn_deg) * smoothstep(TURN_T0, TURN_T1, t)
		var pivot: Variant = _stance_point()
		var dth := clampf(th_goal - badger.rotation.y, -MAX_TURN_STEP, MAX_TURN_STEP)
		if absf(dth) > 0.0 and pivot != null:
			var pv: Vector3 = pivot
			pv.y = badger.position.y
			badger.position = pv + (badger.position - pv).rotated(Vector3.UP, dth)
			badger.rotation.y += dth
		if t >= brake_t + BRAKE_TIME - 0.05:
			phase = 1
			player.play("Walk", -1, 0.0)
			player.play("Idle", BLEND_IDLE)
			# Standfuß festhalten: Die Überblendung zieht ihn sonst zur Ruhepose (bis 17 mm je Bild)
			lock_side = _stance_side()
			if lock_side != "":
				lock_pos = _foot_ground(lock_side)
			lock_until = t + BLEND_IDLE
		return
	if phase == 1 and t >= WAVE_T:
		phase = 2
		player.play("Wave", 0.25)
	elif phase == 2 and t >= WAVE_T + WAVE_LEN - 0.1:
		phase = 3
		player.play("Idle", 0.3)
	player.advance(delta)
	if lock_side != "" and t <= lock_until + 0.001:
		var d := lock_pos - _foot_ground(lock_side)
		badger.position += Vector3(d.x, 0.0, d.z)


func _update_camera() -> void:
	if opts.has("static-cam"):
		return
	var k := smoothstep(CAM_T0, CAM_T1, t)
	k = k * k * (3.0 - 2.0 * k)
	var close := Transform3D.IDENTITY.translated(close_pos).looking_at(close_target, Vector3.UP)
	var q0 := cam_main.basis.get_rotation_quaternion()
	var q1 := close.basis.get_rotation_quaternion()
	camera.global_transform = Transform3D(Basis(q0.slerp(q1, k)), cam_main.origin.lerp(close_pos, k))
	camera.fov = lerpf(42.0, close_fov, k)


# --- Materialien -------------------------------------------------------------------------------
func _lowpoly_material(src: StandardMaterial3D, col: Color, jitter: bool) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = LOWPOLY
	m.set_shader_parameter("albedo", col)
	m.set_shader_parameter("use_jitter", 1.0 if jitter and not opts.has("no-jitter") and not opts.has("smooth") else 0.0)
	m.set_shader_parameter("flat_shading", 0.0 if opts.has("smooth") else 1.0)
	if src.emission_enabled:
		# Glas: Helligkeit nur aus der Emission, sonst überstrahlen Sonne und Punktlicht davor das Fenster
		m.set_shader_parameter("albedo", col * 0.2)
		m.set_shader_parameter("emission", col)
		m.set_shader_parameter("emission_energy", 3.0)
	return m


func _apply_palette(root: Node, palette: Dictionary, jitter: bool) -> void:
	var cache := {}
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(i) as StandardMaterial3D
			if src == null:
				push_error("%s: Fläche %d ohne glTF-Material" % [mi.name, i])
				continue
			var key := src.resource_name
			if key == "Water":
				continue
			if not palette.has(key):
				push_error("Material %s fehlt in der Palette" % key)
				continue
			if not cache.has(key):
				cache[key] = _lowpoly_material(src, palette[key], jitter)
			mi.set_surface_override_material(i, cache[key])


func _own_material(mi: MeshInstance3D) -> ShaderMaterial:
	var m := (mi.get_surface_override_material(0) as ShaderMaterial).duplicate() as ShaderMaterial
	mi.set_surface_override_material(0, m)
	return m


func _attach_to_empties() -> void:
	for holder in $Attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt in harbor.glb" % holder.name)
			continue
		for c in holder.get_children():
			c.reparent(target, false)


# --- Wasser: unregelmäßiges Dreiecksnetz, fein im Hafen, nach außen gröber -----------------------
func _axis(lo: float, hi: float, step: float, far_lo: float, far_hi: float) -> PackedFloat32Array:
	var v := PackedFloat32Array()
	var n := int(round((hi - lo) / step))
	for i in n + 1:
		v.append(lo + (hi - lo) * i / n)
	var s := step
	var x := hi
	while x < far_hi:
		s *= 1.4
		x = minf(x + s, far_hi)
		v.append(x)
	s = step
	x = lo
	while x > far_lo:
		s *= 1.4
		x = maxf(x - s, far_lo)
		v.insert(0, x)
	return v


func _build_water() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED + 7
	var xs := _axis(-42.0, 42.0, 1.75, -700.0, 700.0)
	var zs := _axis(-63.0, 12.0, 1.75, -900.0, 30.0)
	var nx := xs.size()
	var nz := zs.size()
	var pts := PackedVector3Array()
	pts.resize(nx * nz)
	for j in nz:
		for i in nx:
			var x := xs[i]
			var z := zs[j]
			if i > 0 and i < nx - 1 and j > 0 and j < nz - 1:
				var sx := minf(xs[i + 1] - x, x - xs[i - 1])
				var sz := minf(zs[j + 1] - z, z - zs[j - 1])
				x += rng.randf_range(-0.32, 0.32) * sx
				z += rng.randf_range(-0.32, 0.32) * sz
			pts[j * nx + i] = Vector3(x, 0.0, z)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	st.set_normal(Vector3.UP)
	for j in nz - 1:
		for i in nx - 1:
			var a := pts[j * nx + i]
			var b := pts[j * nx + i + 1]
			var c := pts[(j + 1) * nx + i + 1]
			var d := pts[(j + 1) * nx + i]
			var tris: Array
			if rng.randf() < 0.5:
				tris = [a, c, b, a, d, c]
			else:
				tris = [a, d, b, b, d, c]
			for p in tris:
				st.add_vertex(p)
	var mesh := st.commit()
	var mi := MeshInstance3D.new()
	mi.name = "Water"
	mi.mesh = mesh
	mi.material_override = water_material
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.extra_cull_margin = 1.0
	mi.position = Vector3(0.0, -0.8, 0.0)
	water_material.set_shader_parameter("flat_shading", 0.0 if opts.has("smooth") else 1.0)
	effects.add_child(mi)


# --- Rauch: grobe Kugeln, die wachsen, aufsteigen und wieder schrumpfen --------------------------
func _cloud_material(top: Color, side: Color, bottom: Color) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = CLOUD
	m.set_shader_parameter("top_color", top)
	m.set_shader_parameter("side_color", side)
	m.set_shader_parameter("bottom_color", bottom)
	m.set_shader_parameter("sun_dir", -SUN_TRAVEL)
	m.set_shader_parameter("flat_shading", 0.0 if opts.has("smooth") else 1.0)
	return m


func _low_sphere(radial: int, rings: int) -> SphereMesh:
	var s := SphereMesh.new()
	s.radius = 0.5
	s.height = 1.0
	s.radial_segments = radial
	s.rings = rings
	return s


func _build_smoke() -> void:
	var mat := _cloud_material(Color("c9bfd8"), Color("a99bb8"), Color("f0c6b0"))
	var sphere := _low_sphere(7, 4)
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	var anchor := harbor.find_child("ChimneySmoke", true, false) as Node3D
	for i in SMOKE_PUFFS:
		var p := MeshInstance3D.new()
		p.mesh = sphere
		p.material_override = mat
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		anchor.add_child(p)
		smoke.append(p)
		smoke_jitter.append(Vector3(rng.randf_range(-0.2, 0.2), rng.randf_range(0.85, 1.2), rng.randf_range(-0.05, 0.05)))


func _update_smoke() -> void:
	for i in smoke.size():
		var j := smoke_jitter[i]
		var age := fposmod(t / SMOKE_LIFE + float(i) / SMOKE_PUFFS + j.z, 1.0)
		var p := smoke[i]
		var rise := 1.0 - pow(1.0 - age, 1.6)
		p.position = Vector3(2.0 * age * age + j.x * age, -0.1 + 2.3 * rise, 0.0)
		var s := (0.3 + 0.62 * rise) * (1.0 - smoothstep(0.7, 1.0, age)) * smoothstep(0.0, 0.08, age) * j.y
		p.scale = Vector3(s * 1.1, s * 0.9, s)
		p.rotation = Vector3(0.7 * i, 1.3 * i + 0.4 * age, 0.0)
		p.visible = s > 0.02


# --- Wolken: flache Gruppen grober Kugeln weit hinten, treiben langsam nach rechts ----------------
func _build_clouds() -> void:
	var mat := _cloud_material(Color("a993c9"), Color("e79ab0"), Color("ffc9a0"))
	var sphere := _low_sphere(7, 4)
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED + 1
	# (Mitte x, Höhe y, Entfernung z, Breite) in Metern
	var layout := [
		Vector4(-170.0, 62.0, -440.0, 120.0),
		Vector4(-30.0, 92.0, -520.0, 90.0),
		Vector4(170.0, 44.0, -430.0, 80.0),
		Vector4(60.0, 26.0, -640.0, 160.0),
	]
	for c in layout:
		var root := Node3D.new()
		effects.add_child(root)
		root.position = Vector3(c.x, c.y, c.z)
		var w: float = c.w
		# untere Reihe flach und breit, darüber zwei, drei runde Kuppen (Haufenwolke)
		var puffs := rng.randi_range(4, 5)
		var tops := rng.randi_range(2, 3)
		for i in puffs + tops:
			var top := i >= puffs
			var u: float
			var r: float
			var y: float
			if top:
				u = ((float(i - puffs) + 0.5) / float(tops) - 0.5) * 0.55 + rng.randf_range(-0.05, 0.05)
				r = w * rng.randf_range(0.16, 0.22)
				y = w * rng.randf_range(0.1, 0.16)
			else:
				u = (float(i) + 0.5) / float(puffs) - 0.5
				r = w * (0.1 + 0.07 * (1.0 - absf(u) * 2.0)) * rng.randf_range(0.85, 1.15)
				y = r * 0.15
			var p := MeshInstance3D.new()
			p.mesh = sphere
			p.material_override = mat
			p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			p.position = Vector3(u * w * 0.9, y, rng.randf_range(-0.1, 0.1) * w)
			p.scale = Vector3(r * 2.1, r * (1.45 if top else 1.0), r * 1.7)
			p.rotation = Vector3(0.0, rng.randf_range(0.0, TAU), 0.0)
			root.add_child(p)
		clouds.append(root)
		cloud_x0.append(c.x)


func _update_clouds() -> void:
	for i in clouds.size():
		# treiben nach rechts und kommen außerhalb des Bildes (±600 m) links wieder herein
		clouds[i].position.x = fposmod(cloud_x0[i] + (1.6 + 0.5 * i) * t + 600.0, 1200.0) - 600.0


# --- Möwen: Körper und zweiteilige Flügel aus wenigen Dreiecken ----------------------------------
func _tri_mesh(tris: PackedVector3Array, double_sided: bool) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in range(0, tris.size(), 3):
		st.add_vertex(tris[i])
		st.add_vertex(tris[i + 1])
		st.add_vertex(tris[i + 2])
		if double_sided:
			st.add_vertex(tris[i])
			st.add_vertex(tris[i + 2])
			st.add_vertex(tris[i + 1])
	st.generate_normals()
	return st.commit()


func _build_gulls() -> void:
	var white := ShaderMaterial.new()
	white.shader = LOWPOLY
	white.set_shader_parameter("albedo", Color("fbf6f2"))
	white.set_shader_parameter("use_jitter", 0.0)
	var grey := white.duplicate() as ShaderMaterial
	grey.set_shader_parameter("albedo", Color("6f6888"))
	# Körper: gestreckter Doppelkegel, Blick nach +X
	var n := Vector3(0.34, 0.0, 0.0)
	var tl := Vector3(-0.32, 0.02, 0.0)
	var up := Vector3(0.0, 0.08, 0.0)
	var dn := Vector3(0.0, -0.06, 0.0)
	var l := Vector3(0.0, 0.0, -0.08)
	var r := Vector3(0.0, 0.0, 0.08)
	var body := _tri_mesh(PackedVector3Array([
		n, up, r, n, r, dn, n, dn, l, n, l, up,
		tl, r, up, tl, dn, r, tl, l, dn, tl, up, l,
		tl, up, Vector3(-0.44, 0.03, 0.09), tl, Vector3(-0.44, 0.03, -0.09), up,
	]), true)
	# Flügel (rechts, +Z): Innenteil bis zum Gelenk, Spitze als eigener Knoten am Gelenk
	var inner := _tri_mesh(PackedVector3Array([
		Vector3(0.1, 0, 0), Vector3(-0.12, 0, 0), Vector3(-0.1, 0, 0.36),
		Vector3(0.1, 0, 0), Vector3(-0.1, 0, 0.36), Vector3(0.04, 0, 0.36),
	]), true)
	var tip := _tri_mesh(PackedVector3Array([
		Vector3(0.04, 0, 0), Vector3(-0.1, 0, 0), Vector3(-0.2, 0, 0.3),
	]), true)
	# (Mitte, Radius, Höhe, Winkelgeschwindigkeit, Phase, Flügelschlag/s)
	var paths := [
		[Vector3(-3.0, 0.0, -12.0), 7.0, 7.5, 0.32, 0.6, 2.6],
		[Vector3(4.0, 0.0, -18.0), 9.0, 10.0, -0.26, 2.4, 2.2],
		[Vector3(-11.0, 0.0, -26.0), 6.0, 12.5, 0.36, 4.0, 2.4],
	]
	for pth in paths:
		var g := Node3D.new()
		effects.add_child(g)
		var b := MeshInstance3D.new()
		b.mesh = body
		b.material_override = white
		g.add_child(b)
		var wings: Array[Node3D] = []
		var tips: Array[Node3D] = []
		for side in [1.0, -1.0]:
			var w := MeshInstance3D.new()
			w.mesh = inner
			w.material_override = white
			w.position = Vector3(0.02, 0.03, 0.06 * side)
			w.scale = Vector3(1.0, 1.0, side)
			g.add_child(w)
			var tp := MeshInstance3D.new()
			tp.mesh = tip
			tp.material_override = grey
			tp.position = Vector3(0.0, 0.0, 0.36)
			w.add_child(tp)
			wings.append(w)
			tips.append(tp)
		gulls.append({"node": g, "wings": wings, "tips": tips, "c": pth[0], "r": pth[1], "h": pth[2],
			"w": pth[3], "ph": pth[4], "flap": pth[5]})


func _update_gulls() -> void:
	for i in gulls.size():
		var g: Dictionary = gulls[i]
		var a: float = g.ph + g.w * t
		var c: Vector3 = g.c
		var r: float = g.r
		var node: Node3D = g.node
		node.position = c + Vector3(r * cos(a), g.h + 0.4 * sin(0.9 * t + i), r * sin(a))
		# Flugrichtung = Ableitung der Kreisbahn; Neigung in die Kurve
		var dir := Vector3(-sin(a), 0.0, cos(a)) * signf(g.w)
		var yaw := atan2(-dir.z, dir.x)
		node.rotation = Vector3(0.0, yaw, 0.0)
		node.rotate_object_local(Vector3.RIGHT, -0.35 * signf(g.w))
		# Flügelschlag im Wechsel mit Gleitphasen
		var cyc := fposmod(t * 0.35 + i * 0.37, 1.0)
		var flapping := smoothstep(0.0, 0.08, cyc) * (1.0 - smoothstep(0.5, 0.6, cyc))
		var s := sin(TAU * g.flap * t + i)
		var ang := deg_to_rad(8.0) + flapping * deg_to_rad(32.0) * s
		var tip_ang := flapping * deg_to_rad(18.0) * sin(TAU * g.flap * t + i - 0.9) - deg_to_rad(6.0)
		for k in 2:
			var side := 1.0 if k == 0 else -1.0
			(g.wings[k] as Node3D).rotation = Vector3(-ang * side, 0.0, 0.0)
			(g.tips[k] as Node3D).rotation = Vector3(-tip_ang * side, 0.0, 0.0)


# --- Messen (scripts/measure_badger.py) ----------------------------------------------------------
var _skel: Skeleton3D
var _probe := {}


func _mask_mode() -> void:
	harbor.visible = false
	effects.visible = false
	$UI.visible = false
	var env := ($WorldEnvironment as WorldEnvironment).environment
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color.BLACK
	env.glow_enabled = false
	env.fog_enabled = false
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color.WHITE
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			mi.set_surface_override_material(i, white)


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


## Bodenpunkt des Standfußes: Mittel seiner Punkte unter 1 cm über dem Boden der Figur.
## null, wenn beide Füße oder keiner am Boden stehen.
func _stance_point() -> Variant:
	var down := {}
	var floor_y := badger.position.y
	for side in ["L", "R"]:
		var pts: Array[Vector3] = []
		for k in ["heel.", "toe."]:
			var w := _probe_world(k + side)
			if w.y - floor_y < 0.01:
				pts.append(w)
		if not pts.is_empty():
			var m := Vector3.ZERO
			for w in pts:
				m += w
			down[side] = m / pts.size()
	if down.size() != 1:
		return null
	return down.values()[0]


## Seite ("L"/"R") des einzigen Fußes am Boden, sonst "".
func _stance_side() -> String:
	var down: Array[String] = []
	for side in ["L", "R"]:
		if _probe_world("heel." + side).y - badger.position.y < 0.01 or _probe_world("toe." + side).y - badger.position.y < 0.01:
			down.append(side)
	return down[0] if down.size() == 1 else ""


## Bodenpunkt eines Fußes: Mitte von Ferse und Zehe.
func _foot_ground(side: String) -> Vector3:
	return (_probe_world("heel." + side) + _probe_world("toe." + side)) * 0.5


func _measure() -> void:
	var line := "M %.4f rot %.2f %.4f %.4f" % [t, rad_to_deg(badger.rotation.y), badger.position.x, badger.position.z]
	for k in ["heel.L", "toe.L", "heel.R", "toe.R", "head"]:
		var w := _probe_world(k)
		var sp := camera.unproject_position(w)
		line += " %s %.4f %.4f %.4f %.2f %.2f" % [k, w.x, w.y, w.z, sp.x, sp.y]
	print(line)
