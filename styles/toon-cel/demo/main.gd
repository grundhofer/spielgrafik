extends Node3D
## Katalogeintrag toon-cel: Cel-Shading mit Konturen auf der gemeinsamen 3D-Grundlage (shared/3d).
##
## Ersetzt alle glTF-Materialien nach Namen durch den Stufen-Shader (shaders/toon.gdshader) mit
## kräftigerer Toon-Palette, die Figur bekommt zusätzlich eine umgedrehte Hülle als Kontur. Wasser,
## Himmel, Wolken, Rauch und Lichtkegel haben eigene Toon-Shader; die Konturen der ganzen Szene
## zeichnet ein Nachbearbeitungs-Shader (outline_post.gdshader).
## Alles hängt an der aufsummierten Zeit t und an festen Seeds (deterministische Aufnahme).
##
## Vergleichsschalter: godot --path demo -- --no-post --no-hull --no-ids --no-toon --no-shadow --static-cam
## Messen: -- --measure (Fuß- und Kopfpunkte je Bild), -- --mask (nur der Dachs, weiß auf Schwarz);
## Auswertung in scripts/measure_badger.py und scripts/compare_switches.py.

# --- Dachs (Werte aus shared/3d/badger_notes.md) -----------------------------------------------
const WALK_SPEED := 0.367
const WALK_RATE := 2.0
# Er biegt in den letzten Schritten zur Nahaufnahme-Kamera ab (Drehen im Laufen statt auf der Stelle,
# sonst rutschen die Füße) und bremst so, dass der Lauf in der Durchgangsphase endet (Phase 0,81:
# linker Fuß schwingt neben dem rechten durch); die Überblendung auf Idle senkt dann nur den Fuß ab.
# Zeiten aus scripts/walk_timing.py; Endpunkt (-2.62 | 0 | 1.49).
const TURN_T0 := 2.3
const TURN_T1 := 3.3
const TURN_DEG := -60.0          # Blick zur Kamera der Nahaufnahme (Winkarm sichtbar; frame_close.py)
const MAX_TURN_STEP := deg_to_rad(3.0)   # je Bild; Ferse und Zehe des Standfußes drehen sich um ±4 mm
const BRAKE_T := 3.22
const BRAKE_TIME := 0.4
const IDLE_T := 3.57
const WAVE_T := 4.0
const WAVE_LEN := 1.5

# --- Kamera ------------------------------------------------------------------------------------
const CAM_T0 := 2.4              # bis hier Hauptkamera (Totale) wie shared/3d
const CAM_T1 := 4.3              # ab hier Nahaufnahme
# Nahaufnahme aus scripts/frame_close.py: Füße bei (255, 631), Dachs 205 px hoch, Leuchtfeuer bei
# (951, 67), Boot A bei (720, 484), Horizont y 349; Dialogkasten unten rechts frei vom Dachs
@export var close_pos := Vector3(-0.52, 1.4, 4.99)
@export var close_target := Vector3(-1.02, 1.25, -3.71)
@export var close_fov := 52.0

# --- Umgebung ----------------------------------------------------------------------------------
const BEAM_PERIOD := 8.0
const BEAM_POSTER_T := 4.8       # zu dieser Zeit zeigt der Strahl nach links vorn (quer über den Himmel)
const BEAM_POSTER_DIR := Vector2(-0.8, 0.6)   # (x, z)
const SMOKE_PUFFS := 6
const SMOKE_LIFE := 3.9
const SEED := 20261010
const SUN_TRAVEL := Vector3(0.85, -0.45, -0.28)   # Abendsonne von links (leicht von vorn), ≈27° hoch
const KEY_TRAVEL := Vector3(0.45, -0.55, -0.7)    # Figurenlicht von links vorn oben

const TOON := preload("res://shaders/toon.gdshader")
const HULL := preload("res://shaders/outline_hull.gdshader")
const CLOUD := preload("res://shaders/toon_cloud.gdshader")
const HALO := preload("res://shaders/toon_halo.gdshader")

## Toon-Palette je glTF-Material: Farbe, Rim-Stärke, Glanz, Material-ID (0..15; nur Nachbarn
## mit verschiedener ID bekommen eine Linie). Farben kräftiger und wärmer als die neutralen glTF-Werte.
const PALETTE := {
	"Stone": [Color("c9b59c"), 0.0, 0.0, 1],
	"StoneDark": [Color("85777a"), 0.25, 0.0, 2],
	"Wood": [Color("c97c3c"), 0.35, 0.0, 3],
	"WoodDark": [Color("744329"), 0.35, 0.0, 4],
	"WhitePaint": [Color("f7f1e4"), 0.5, 0.0, 5],
	"RedPaint": [Color("e43b2d"), 0.5, 0.35, 6],
	"Roof": [Color("4f5f99"), 0.35, 0.0, 7],
	"Rope": [Color("ebcc8e"), 0.25, 0.0, 8],
	"Metal": [Color("4d4c63"), 0.45, 0.6, 9],
	"Rock": [Color("94828f"), 0.25, 0.0, 10],
	"Sand": [Color("efd49a"), 0.0, 0.0, 11],
	"Grass": [Color("76b24c"), 0.0, 0.0, 12],
	"Glass": [Color("ffd98a"), 0.0, 0.0, 13],
}
const BADGER_PALETTE := {
	"FurDark": [Color("54454e"), 1.0, 0.0, 1],
	"FurLight": [Color("fff4de"), 1.0, 0.0, 2],
	"Cap": [Color("4e7d3a"), 1.0, 0.0, 3],
	"Brass": [Color("f0b84c"), 0.6, 0.8, 4],
	"Vest": [Color("5f9140"), 1.0, 0.0, 5],
	"Shirt": [Color("fff0d4"), 1.0, 0.0, 6],
	"Scarf": [Color("ec3238"), 1.0, 0.25, 7],
	"Satchel": [Color("97502c"), 1.0, 0.3, 8],
	"Parcel": [Color("e0a865"), 1.0, 0.0, 9],
	"Nose": [Color("2a1d22"), 0.6, 0.9, 10, {"spec_size": 0.93}],
	"Eye": [Color("2b170d"), 0.0, 1.2, 11, {"spec_size": 0.9}],
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
var cloud_radii: Array[Vector3] = []
var lantern_mat: ShaderMaterial
var lamp_mat: ShaderMaterial
var window_mat: ShaderMaterial
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0
var lantern_halo: MeshInstance3D
var lamp_halo: MeshInstance3D
var cam_main: Transform3D
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
		opts[a.trim_prefix("--")] = true
	cam_main = camera.global_transform
	var sun := $Sun as DirectionalLight3D
	sun.global_transform = Transform3D.IDENTITY.looking_at(SUN_TRAVEL, Vector3.UP)
	($CharKey as DirectionalLight3D).global_transform = Transform3D.IDENTITY.looking_at(KEY_TRAVEL, Vector3.UP)
	if opts.has("no-shadow"):
		sun.shadow_enabled = false

	var hull := ShaderMaterial.new()
	hull.shader = HULL
	if opts.has("no-hull"):
		hull = null
	_apply_palette(harbor, PALETTE, null)
	_apply_palette(badger, BADGER_PALETTE, hull, 2)   # Ebene 2: nur Figurenlicht, keine Sonne
	_attach_to_empties()   # erst danach: der Lichtkegel hängt sonst im Hafen und bekäme ein Toon-Material

	# Wasser
	var n := replace_material(harbor, "Water", water_material)
	assert(n == 1, "Material Water nicht gefunden")
	var sea := harbor.get_node("Sea") as MeshInstance3D
	sea.extra_cull_margin = 1.0

	# Leuchtende Teile: je Objekt eigenes Material (einzeln flackern/blitzen)
	lantern_mat = _own_material(harbor.find_child("LanternGlass", true, false))
	lamp_mat = _own_material(harbor.find_child("LighthouseLamp", true, false))
	window_mat = _own_material(harbor.find_child("CottageWindow", true, false))
	for glass in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
		(harbor.find_child(glass, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	window_mat.set_shader_parameter("emission_energy", 2.2)

	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform

	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	player.play("Walk")
	player.speed_scale = WALK_RATE

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0

	# Strahlrichtung = -Z des Rotors = (-sin y, 0, -cos y)
	beam_yaw0 = atan2(-BEAM_POSTER_DIR.x, -BEAM_POSTER_DIR.y) - TAU * BEAM_POSTER_T / BEAM_PERIOD

	# Konturshader je Renderer: Normalen-/Rauheitspuffer gibt es nur in Forward+
	var outline_mat := ($Camera/Outline as MeshInstance3D).get_surface_override_material(0) as ShaderMaterial
	var fplus := RenderingServer.get_current_rendering_method() == "forward_plus"
	outline_mat.shader = load("res://shaders/outline_post.gdshader" if fplus else "res://shaders/outline_post_depth.gdshader")
	if opts.has("no-post"):
		($Camera/Outline as MeshInstance3D).visible = false
	if opts.has("no-ids"):
		outline_mat.set_shader_parameter("id_lines", 0.0)

	lantern_halo = _make_halo(harbor.find_child("LanternLight", true, false), Color(1.0, 0.72, 0.36), 0.55)
	lamp_halo = _make_halo(harbor.find_child("LighthouseLight", true, false), Color(1.0, 0.86, 0.55), 0.5)
	_build_smoke()
	_build_clouds()
	if opts.has("mask"):
		_mask_mode()
	_setup_measure()
	if opts.has("measure"):
		# kurz vor dem Zeichnen messen, wenn alle Änderungen dieses Bildes feststehen
		RenderingServer.frame_pre_draw.connect(_measure)
	_update(0.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)


func _update(delta: float) -> void:
	RenderingServer.global_shader_parameter_set("toon_time", t)
	_update_badger(delta)
	_update_camera()

	var k := 0
	for b in boats:
		var ph := 1.7 * k
		var roll := deg_to_rad(2.6) * sin(TAU * t / 3.4 + ph)
		var pitch := deg_to_rad(1.0) * sin(TAU * t / 4.6 + 0.8 + ph)
		var heave := 0.04 * sin(TAU * t / 3.9 + 2.1 + ph)
		var local := Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		(harbor.get_node(b) as Node3D).transform = boats[b] * local
		k += 1

	# Laterne flackert: Glas, Lichtring am Boden und Glitzern im Wasser gemeinsam
	var f := 0.8 + 0.2 * lantern_noise.get_noise_1d(t * 7.0) + 0.08 * lantern_noise.get_noise_1d(t * 31.0 + 50.0)
	lantern_omni.light_energy = 2.2 * f
	lantern_mat.set_shader_parameter("emission_energy", 3.0 * f)
	water_material.set_shader_parameter("lamp_b_power", clampf((f - 0.65) * 3.0, 0.0, 1.0))
	lantern_halo.scale = Vector3.ONE * (0.75 + 0.55 * f)

	# Leuchtfeuer dreht sich, Lampe blitzt, wenn der Strahl zur Kamera zeigt
	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position).normalized()
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), 16.0)
	lamp_mat.set_shader_parameter("emission_energy", 3.0 + 9.0 * facing)
	lamp_omni.light_energy = 2.0 + 4.0 * facing
	water_material.set_shader_parameter("lamp_a_power", 0.6 + 0.4 * facing)
	lamp_halo.scale = Vector3.ONE * (2.2 + 5.0 * facing)

	_update_smoke()
	_update_clouds()


func _update_badger(delta: float) -> void:
	# Der AnimationPlayer läuft von Hand (advance), damit Pose, Verschiebung und Drehung in jedem
	# Bild in fester Reihenfolge entstehen: erst Pose, dann Vorschub, dann Drehung um den Standfuß.
	if phase == 0:
		walk_rate = WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, t))
		player.speed_scale = walk_rate
		player.advance(delta)
		var th := badger.rotation.y
		badger.position += Vector3(cos(th), 0.0, -sin(th)) * WALK_SPEED * walk_rate * delta
		# Drehen nur, solange genau ein Fuß am Boden steht, und um dessen Bodenpunkt: der Standfuß
		# bleibt stehen. In der Doppelstütze wartet die Drehung (holt danach auf).
		var th_goal := deg_to_rad(TURN_DEG) * smoothstep(TURN_T0, TURN_T1, t)
		var pivot: Variant = _stance_point()
		var dth := clampf(th_goal - badger.rotation.y, -MAX_TURN_STEP, MAX_TURN_STEP)
		if absf(dth) > 0.0 and pivot != null:
			var pv: Vector3 = pivot
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
	player.advance(delta)


func _update_camera() -> void:
	if opts.has("static-cam"):
		return
	var k := smoothstep(CAM_T0, CAM_T1, t)
	k = k * k * (3.0 - 2.0 * k)   # doppelt geglättet: weicher Anfang und Auslauf
	var close := Transform3D.IDENTITY.translated(close_pos).looking_at(close_target, Vector3.UP)
	var q0 := cam_main.basis.get_rotation_quaternion()
	var q1 := close.basis.get_rotation_quaternion()
	camera.global_transform = Transform3D(Basis(q0.slerp(q1, k)), cam_main.origin.lerp(close_pos, k))
	camera.fov = lerpf(42.0, close_fov, k)


# --- Materialien -------------------------------------------------------------------------------
func _toon_material(src: StandardMaterial3D, entry: Array, hull: Material) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = TOON
	m.set_shader_parameter("albedo", entry[0])
	m.set_shader_parameter("rim_strength", entry[1])
	m.set_shader_parameter("spec_strength", entry[2])
	m.set_shader_parameter("material_id", entry[3])
	if src.emission_enabled:
		m.set_shader_parameter("emission", entry[0])
		m.set_shader_parameter("emission_energy", 3.0)
	if entry.size() > 4:
		for k in entry[4]:
			m.set_shader_parameter(k, entry[4][k])
	if opts.has("no-toon"):
		m.set_shader_parameter("smooth_shading", 1.0)
	m.next_pass = hull
	return m


func _apply_palette(root: Node, palette: Dictionary, hull: Material, layer := 1) -> void:
	var cache := {}
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		mi.layers = layer
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
				cache[key] = _toon_material(src, palette[key], hull)
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


static func replace_material(root: Node, mat_name: String, mat: Material) -> int:
	var count := 0
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i)
			if m and m.resource_name == mat_name:
				mi.set_surface_override_material(i, mat)
				count += 1
	return count


# --- Lichthöfe: Billboard mit zwei harten Ringen an einem Empty ---------------------------------
func _make_halo(anchor: Node3D, col: Color, intensity: float) -> MeshInstance3D:
	var mat := ShaderMaterial.new()
	mat.shader = HALO
	mat.render_priority = 20
	mat.set_shader_parameter("color", col)
	mat.set_shader_parameter("intensity", intensity)
	var q := QuadMesh.new()
	q.size = Vector2.ONE
	var mi := MeshInstance3D.new()
	mi.mesh = q
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.extra_cull_margin = 4.0
	anchor.add_child(mi)
	return mi


# --- Rauch: Toon-Bällchen, die wachsen, aufsteigen und wieder schrumpfen ------------------------
func _build_smoke() -> void:
	var mat := ShaderMaterial.new()
	mat.shader = TOON
	mat.set_shader_parameter("albedo", Color("f4eff2"))
	mat.set_shader_parameter("rim_strength", 0.6)
	mat.set_shader_parameter("band_shadow", -0.25)
	mat.set_shader_parameter("material_id", 14)
	var sphere := SphereMesh.new()
	sphere.radius = 0.5
	sphere.height = 1.0
	sphere.radial_segments = 24
	sphere.rings = 12
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
		smoke_jitter.append(Vector3(rng.randf_range(-0.2, 0.2), rng.randf_range(0.8, 1.25), rng.randf_range(-0.05, 0.05)))


func _update_smoke() -> void:
	for i in smoke.size():
		var j := smoke_jitter[i]
		# Phase je Bällchen leicht verschoben (j.z), damit keine gleichmäßige Kette entsteht
		var age := fposmod(t / SMOKE_LIFE + float(i) / SMOKE_PUFFS + j.z, 1.0)
		var p := smoke[i]
		var rise := 1.0 - pow(1.0 - age, 1.6)
		p.position = Vector3(1.9 * age * age + j.x * age, -0.12 + 2.9 * rise, 0.0)
		var s := (0.26 + 0.42 * rise) * (1.0 - smoothstep(0.72, 1.0, age)) * smoothstep(0.0, 0.08, age) * j.y
		p.scale = Vector3(s * 1.12, s * 0.92, s)
		p.visible = s > 0.02


# --- Wolken: Gruppen gestauchter Kugeln weit hinten, treiben langsam nach rechts ----------------
func _build_clouds() -> void:
	var mat := ShaderMaterial.new()
	mat.shader = CLOUD
	var sphere := SphereMesh.new()
	sphere.radius = 0.5
	sphere.height = 1.0
	sphere.radial_segments = 32
	sphere.rings = 16
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED + 1
	# (Mitte x, Höhe y, Entfernung z, Breite) in Metern; frei von Leuchtturm und Schornstein
	var layout := [
		Vector4(-150.0, 58.0, -430.0, 110.0),
		Vector4(-20.0, 84.0, -500.0, 80.0),
		Vector4(150.0, 40.0, -420.0, 70.0),
		Vector4(40.0, 22.0, -620.0, 150.0),
	]
	for c in layout:
		var root := Node3D.new()
		effects.add_child(root)
		root.position = Vector3(c.x, c.y, c.z)
		var w: float = c.w
		var radii := Vector3(w * 0.55, w * 0.3, w * 0.3)
		# untere Reihe flach und breit, darüber zwei bis drei größere Kuppen (Haufenwolke)
		var puffs := rng.randi_range(5, 7)
		var tops := rng.randi_range(2, 3)
		for i in puffs + tops:
			var top := i >= puffs
			var u: float
			var r: float
			var y: float
			if top:
				u = ((float(i - puffs) + 0.5) / float(tops) - 0.5) * 0.6 + rng.randf_range(-0.06, 0.06)
				r = w * rng.randf_range(0.17, 0.23)
				y = w * rng.randf_range(0.12, 0.2)
			else:
				u = (float(i) + 0.5) / float(puffs) - 0.5
				r = w * (0.1 + 0.08 * (1.0 - absf(u) * 2.0)) * rng.randf_range(0.85, 1.15)
				y = r * 0.2
			var p := MeshInstance3D.new()
			p.mesh = sphere
			p.material_override = mat
			p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			p.position = Vector3(u * w * 0.9, y, rng.randf_range(-0.1, 0.1) * w)
			p.scale = Vector3(r * 2.1, r * (1.5 if top else 1.1), r * 1.6)
			root.add_child(p)
		clouds.append(root)
		cloud_x0.append(c.x)
		cloud_radii.append(radii)


func _update_clouds() -> void:
	for i in clouds.size():
		clouds[i].position.x = cloud_x0[i] + (2.0 + 0.5 * i) * t
		for p: GeometryInstance3D in clouds[i].get_children():
			p.set_instance_shader_parameter("cloud_center", clouds[i].position)
			p.set_instance_shader_parameter("cloud_radii", cloud_radii[i])


# --- Messen (scripts/measure_badger.py) ----------------------------------------------------------
# --mask: nur der Dachs, weiß und unbeleuchtet auf Schwarz (Silhouette für die Bildmessung)
# --measure: je Bild Ferse und Zehe beider Füße sowie Kopf in Welt- und Bildkoordinaten ausgeben
var _skel: Skeleton3D
var _probe := {}   # Name -> [Knochenindex, lokaler Punkt]


func _mask_mode() -> void:
	harbor.visible = false
	effects.visible = false
	$Camera/Outline.visible = false
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
	# Punkte in Ruhepose (Godot-Koordinaten der Figur, aus badger_notes.md): Ferse unter dem
	# Fußknochen, Zehe an seiner Spitze, beide 3 mm über dem Boden; Kopf = Mützendeckel
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


## Bodenpunkt des Standfußes (Pose des letzten Bildes): Mittel seiner Punkte unter 1 cm.
## null, wenn beide Füße oder keiner am Boden stehen.
func _stance_point() -> Variant:
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
	if down.size() != 1:
		return null
	return down.values()[0]


func _measure() -> void:
	var line := "M %.4f rot %.2f %.4f %.4f 0 0" % [t, rad_to_deg(badger.rotation.y), badger.position.x, badger.position.z]
	for k in ["heel.L", "toe.L", "heel.R", "toe.R", "head"]:
		var w := _probe_world(k)
		var sp := camera.unproject_position(w)
		line += " %s %.4f %.4f %.4f %.2f %.2f" % [k, w.x, w.y, w.z, sp.x, sp.y]
	print(line)
