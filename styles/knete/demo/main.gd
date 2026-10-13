extends Node3D
## Knetfigur & Stop-Motion: der Hafen von Lornholm als Knet-Set.
##
## - Materialien: alle glTF-Materialien von Hafen und Dachs per Name durch clay.gdshader ersetzt (Tabelle CLAY).
## - Dachs: Netz zur Laufzeit umgebaut: Ruhelage in CUSTOM0 (Muster bleibt beim Laufen fest), kleine
##   Beulen in der Ruhelage eingeknetet. Animation auf Zweien (15 Bilder/s): der AnimationPlayer läuft im
##   manuellen Modus und wird nur an Bildgrenzen weitergestellt; Formrauschen (boil_seed) je Animationsbild.
## - Umgebung auf Dreien (10 Bilder/s): Knetmeer, schaukelnde Boote, Leuchtfeuer. Laterne auf Zweien.
## - Zeit: aufsummiertes delta; Bildindex = floor(t * fps). Zufall nur mit festen Seeds.
## Prüfschalter nach "--": --t0=SEK, --no-boil, --no-ui, --no-detail (Knete ohne Abdrücke, Krümel, Marmorierung),
## --mask (Dachs weiß, alles andere schwarz),
## --measure (Knochen, Sohlenpunkte und Bildlage je Bild als JSON auf stdout).

const FPS_FIG := 15.0
const FPS_ENV := 10.0
const SEED := 20261013

# --- Dachs (Werte aus shared/3d/badger_notes.md) ----------------------------------------------
const WALK_SPEED := 0.367          # m je Sekunde Animationszeit (Füße rutschen dann nicht)
const WALK_DA := 0.125             # Animationszeit je Bild: Walk (1,0 s) in 8 Posen auf Zweien
const START_X := -2.75
const PATH_Z := 0.95               # Plattenreihe zwischen zwei Fugen (z 0,74–1,16), beide Füße darauf
const WALK_STEPS := 40             # bis Animationszeit 5,0 (linke Ferse setzt auf)
const DECEL := [0.1, 0.075, 0.05, 0.025]   # Abbremsen: endet bei x,25 (Durchgang, linker Fuß trägt)
const PIVOT_STEP := 45             # Überblenden auf Idle und Drehung um den linken Fuß zur Kamera
const PIVOT_STEPS := 6
const PIVOT_BLEND := 0.4
const WAVE_STEP := 56
const WAVE_BLEND := 0.2
const IDLE2_STEP := 77
const IDLE2_BLEND := 0.3

# --- Umgebung ------------------------------------------------------------------------------------
const BEAM_PERIOD := 9.0
const BEAM_FACING_T := 1.6

## Knetfarben je glTF-Material: Farbe (sRGB), Rauheit, Glanz, Art, weitere Uniforms
const CLAY := {
	"Stone": {"c": "a39b8e", "r": 0.66},
	"StoneDark": {"c": "6f6a64", "r": 0.66},
	"Wood": {"c": "b0703c", "r": 0.6},
	"WoodDark": {"c": "6a4428", "r": 0.62},
	"WhitePaint": {"c": "efe8d9", "r": 0.55},
	"RedPaint": {"c": "cc3a2c", "r": 0.52},
	"Roof": {"c": "566685", "r": 0.6},
	"Glass": {"c": "ffcf7a", "r": 0.5, "emit": "ffb24a", "e": 2.2},
	"Rope": {"c": "d4b984", "r": 0.7},
	"Metal": {"c": "45474f", "r": 0.42, "s": 0.7},
	"Rock": {"c": "776f66", "r": 0.7, "print_cell": 0.35, "print_depth": 0.012, "bump_amp": 0.02, "bump_wave": 0.45},
	"Sand": {"c": "c4ad84", "r": 0.75, "print_cell": 0.3, "print_depth": 0.008, "bump_amp": 0.012, "bump_wave": 0.4},
	"Grass": {"c": "6f9c47", "r": 0.72, "kind": 1},
	# Dachs
	"FurDark": {"c": "4a403c", "r": 0.6},
	"FurLight": {"c": "f2e8d2", "r": 0.58},
	"Cap": {"c": "3f6236", "r": 0.58},
	"Brass": {"c": "e0ad3e", "r": 0.4, "s": 0.8},
	"Vest": {"c": "5f8a3c", "r": 0.6},
	"Shirt": {"c": "f1e1bf", "r": 0.6},
	"Scarf": {"c": "d23a2e", "r": 0.62, "kind": 2},
	"Satchel": {"c": "8c4f2c", "r": 0.55},
	"Parcel": {"c": "cf9d62", "r": 0.66},
	"Nose": {"c": "231b18", "r": 0.2, "kind": 3},
	"Eye": {"c": "1a1210", "r": 0.14, "kind": 3},
}

## Ferne Teile als kleinere Modelle gedacht (erzwungene Perspektive wie im Studio): Muster je Objekt größer
const DETAIL_SCALE := {
	"Lighthouse": 2.6, "LighthouseLamp": 2.6, "Headland": 2.2, "WestHill": 1.8, "RocksSea": 1.5,
	"BoatA": 1.4, "BoatB": 1.5, "Jetty": 1.3,
}

const CLAY_SHADER := preload("res://shaders/clay.gdshader")
const SEA_SHADER := preload("res://shaders/clay_sea.gdshader")
const BACKDROP_SHADER := preload("res://shaders/backdrop.gdshader")

var t := 0.0
var fig_step := -1
var env_step := -1
var opt := {"t0": 0.0, "boil": true, "ui": true, "detail": true, "mask": false, "measure": false}

var path_h := {}                   # Laufweg-Höhen aus blender/build_clay_harbor.py
var boats := {}
var mats := {}                     # Name -> ShaderMaterial (Hafen)
var fig_mats: Array[ShaderMaterial] = []
var lantern_mat: ShaderMaterial
var lamp_mat: ShaderMaterial
var sea_mat: ShaderMaterial
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0
var heading := 0.0                 # Drehung des Dachses um y (0 = Blick nach +x)
var foot_l := -1
var foot_r := -1

@onready var harbor: Node3D = $Harbor
@onready var badger: Node3D = $Badger
@onready var player: AnimationPlayer = $Badger/AnimationPlayer
@onready var skeleton: Skeleton3D = $Badger/Armature/Skeleton3D
@onready var camera: Camera3D = $Camera
@onready var rotor: Node3D = $Attach/LighthouseLight/Rotor
@onready var lantern_omni: OmniLight3D = $Attach/LanternLight/Omni
@onready var lamp_omni: OmniLight3D = $Attach/LighthouseLight/Omni
@onready var ui: Control = $UI/Panel


func _ready() -> void:
	_parse_args()
	_load_path_heights()
	_apply_harbor_materials()
	_attach_to_empties()
	_build_badger()
	_build_sea()
	_build_backdrop()
	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform
	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	var to_cam := camera.global_position - rotor.global_position
	beam_yaw0 = atan2(-to_cam.x, -to_cam.z) - TAU * BEAM_FACING_T / BEAM_PERIOD
	$UI.visible = opt["ui"] and not opt["mask"]
	if opt["mask"]:
		_mask_mode()
	# Vorlauf bis t0 in denselben Schritten wie die Aufnahme
	var dt := 1.0 / 30.0
	var n := int(round(float(opt["t0"]) * 30.0))
	for i in n:
		t += dt
		_update()
	t = float(opt["t0"])
	_update()


func _process(delta: float) -> void:
	t += delta
	_update()


func _parse_args() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			opt["t0"] = a.substr(5).to_float()
		elif a == "--no-boil":
			opt["boil"] = false
		elif a == "--no-ui":
			opt["ui"] = false
		elif a == "--no-detail":
			opt["detail"] = false
		elif a == "--mask":
			opt["mask"] = true
		elif a == "--measure":
			opt["measure"] = true


# --- Zeitstufen ----------------------------------------------------------------------------------
func _update() -> void:
	var tf := t + 1e-4
	var s_fig := int(floor(tf * FPS_FIG))
	var s_env := int(floor(tf * FPS_ENV))
	while fig_step < s_fig:
		fig_step += 1
		_fig_step(fig_step)
	if s_env != env_step:
		env_step = s_env
		_env_update(float(s_env) / FPS_ENV, s_env)
	ui.set_time(t, s_fig)
	if opt["measure"]:
		_measure()


# --- Dachs ---------------------------------------------------------------------------------------
func _build_badger() -> void:
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		_clay_mesh(mi, 0.0035, 0.07)
		for i in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(i) as StandardMaterial3D
			var m := _make_clay(src.resource_name, true)
			mi.set_surface_override_material(i, m)
			fig_mats.append(m)
		mi.set_instance_shader_parameter("noise_offset", Vector3(3.7, 1.3, 8.9))
	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	foot_l = skeleton.find_bone("foot.L")
	foot_r = skeleton.find_bone("foot.R")
	badger.position = Vector3(START_X, 0.0, PATH_Z)


## Netz neu aufbauen: Ruhelage nach CUSTOM0 (für das Muster im Shader), kleine Beulen entlang der über
## alle Nahtkopien gemittelten Normale (sonst reißen die Nähte auf). Normalen um die Beulen geneigt.
func _clay_mesh(mi: MeshInstance3D, amp: float, wave: float) -> void:
	var src := mi.mesh as ArrayMesh
	var dst := ArrayMesh.new()
	var nz := FastNoiseLite.new()
	nz.seed = SEED + 7
	nz.noise_type = FastNoiseLite.TYPE_PERLIN
	nz.frequency = 1.0 / wave
	nz.fractal_type = FastNoiseLite.FRACTAL_FBM
	nz.fractal_octaves = 2
	for s in src.get_surface_count():
		var arrays := src.surface_get_arrays(s)
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var norms: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
		var acc := {}
		for i in verts.size():
			var key := Vector3i((verts[i] * 2000.0).round())
			acc[key] = acc.get(key, Vector3.ZERO) + norms[i]
		var custom := PackedFloat32Array()
		custom.resize(verts.size() * 4)
		var e := 0.004
		for i in verts.size():
			var p := verts[i]
			custom[i * 4] = p.x
			custom[i * 4 + 1] = p.y
			custom[i * 4 + 2] = p.z
			custom[i * 4 + 3] = 1.0
			var n: Vector3 = (acc[Vector3i((p * 2000.0).round())] as Vector3).normalized()
			var h := amp * nz.get_noise_3dv(p)
			# Gradient der Beulen für die Normale
			var g := Vector3(nz.get_noise_3dv(p + Vector3(e, 0, 0)), nz.get_noise_3dv(p + Vector3(0, e, 0)),
					nz.get_noise_3dv(p + Vector3(0, 0, e))) * amp / e - Vector3.ONE * (h / e)
			var gt := g - n * g.dot(n)
			verts[i] = p + n * h
			norms[i] = (norms[i] - gt).normalized()
		arrays[Mesh.ARRAY_VERTEX] = verts
		arrays[Mesh.ARRAY_NORMAL] = norms
		arrays[Mesh.ARRAY_TANGENT] = null
		arrays[Mesh.ARRAY_CUSTOM0] = custom
		var flags := Mesh.ARRAY_CUSTOM_RGBA_FLOAT << Mesh.ARRAY_FORMAT_CUSTOM0_SHIFT
		if src.surface_get_format(s) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS:
			flags |= Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS
		dst.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays, [], {}, flags)
		dst.surface_set_material(s, src.surface_get_material(s))
		dst.surface_set_name(s, src.surface_get_name(s))
	mi.mesh = dst


func _fig_step(step: int) -> void:
	var dt := 1.0 / FPS_FIG             # Sekunden Animationszeit bei Tempo 1
	if step == 0:
		player.play("Walk")
		player.advance(0.0)
	elif step <= WALK_STEPS:
		_walk(WALK_DA)
	elif step <= WALK_STEPS + DECEL.size():
		_walk(DECEL[step - WALK_STEPS - 1])
	elif step < PIVOT_STEP + PIVOT_STEPS:
		if step == PIVOT_STEP:
			player.play("Idle", PIVOT_BLEND)
		# Drehung um den tragenden linken Fuß, während der rechte (in der Luft) auf Idle niedergeht
		var k := float(step - PIVOT_STEP + 1) / PIVOT_STEPS
		var target := -PI / 2.0 * smoothstep(0.0, 1.0, k)
		var p0 := _foot_world(foot_l)
		player.advance(dt)
		heading = target
		badger.rotation.y = heading
		var p1 := _foot_world(foot_l)
		badger.position += Vector3(p0.x - p1.x, 0.0, p0.z - p1.z)
	elif step == WAVE_STEP:
		player.play("Wave", WAVE_BLEND)
		player.advance(dt)
	elif step == IDLE2_STEP:
		player.play("Idle", IDLE2_BLEND)
		player.advance(dt)
	else:
		player.advance(dt)
	_set_height()
	var boil := float(step) if opt["boil"] else 0.0
	for m in fig_mats:
		m.set_shader_parameter("boil_seed", boil)
	# Laterne flackert auf Zweien (eine Lampe im Set, je Aufnahme neu eingestellt)
	var f := 0.8 + 0.2 * lantern_noise.get_noise_1d(float(step) * 0.55) + 0.08 * lantern_noise.get_noise_1d(float(step) * 2.3 + 40.0)
	lantern_omni.light_energy = 2.2 * f * f
	lantern_mat.set_shader_parameter("emission_energy", 3.2 * f * f)


func _walk(da: float) -> void:
	player.advance(da)
	badger.position += Vector3(cos(heading), 0.0, -sin(heading)) * WALK_SPEED * da


func _foot_world(bone: int) -> Vector3:
	return (skeleton.global_transform * skeleton.get_bone_global_pose(bone)).origin


## Höhe: Der tragende Fuß ruht auf den höchsten Stellen der unebenen Knet-Oberfläche unter seiner Sohle
## (Ferse, Mitte, Zehen; sonst sackt er in eine Fuge). Im Stehen trägt der höhere der beiden Füße.
func _set_height() -> void:
	var anim_pos := player.current_animation_position
	var sl := _support(foot_l)
	var sr := _support(foot_r)
	var h: float
	if player.current_animation == "Walk":
		h = sl if fposmod(anim_pos, 1.0) < 0.5 else sr
	else:
		h = maxf(sl, sr)
	badger.position.y = h


## Sohlenpunkte eines Fußes (Ferse, Mitte, Zehen) in Weltkoordinaten: in der Ruhelage auf Sohlenhöhe
## festgelegt und mit der aktuellen Knochenlage mitbewegt.
func _sole_points(bone: int) -> Array[Vector3]:
	var side := -0.125 if bone == foot_l else 0.125
	var rest := skeleton.get_bone_global_rest(bone)
	var pose := skeleton.global_transform * skeleton.get_bone_global_pose(bone)
	var out: Array[Vector3] = []
	for x in [-0.03, 0.04, 0.11]:
		out.append(pose * (rest.affine_inverse() * Vector3(x, 0.003, side)))
	return out


func _support(bone: int) -> float:
	var h := -1.0
	for p in _sole_points(bone):
		h = maxf(h, _surface(p.x, p.z))
	return h


func _load_path_heights() -> void:
	var f := FileAccess.open("res://models/harbor_knete_path.json", FileAccess.READ)
	if f == null:
		push_error("harbor_knete_path.json fehlt")
		return
	path_h = JSON.parse_string(f.get_as_text())


func _surface(x: float, z: float) -> float:
	if path_h.is_empty():
		return 0.0
	var xs: Array = path_h["x"]
	var fi := clampf((x - float(xs[0])) / 0.02, 0.0, xs.size() - 1.001)
	var i := int(fi)
	var fr := fi - i
	var lines := [0.825, 0.95, 1.075]
	var vals := []
	for zl in lines:
		var row: Array = path_h["z_lines"][str(zl)]
		var a: float = row[i] if row[i] != null else 0.0
		var b: float = row[i + 1] if row[i + 1] != null else a
		vals.append(lerpf(a, b, fr))
	var zc := clampf(z, 0.825, 1.075)
	if zc <= 0.95:
		return lerpf(vals[0], vals[1], (zc - 0.825) / 0.125)
	return lerpf(vals[1], vals[2], (zc - 0.95) / 0.125)


# --- Umgebung auf Dreien -------------------------------------------------------------------------
func _env_update(te: float, s: int) -> void:
	sea_mat.set_shader_parameter("sea_t", te)
	sea_mat.set_shader_parameter("sea_seed", float(s))
	var k := 0
	for b in boats:
		var ph := 1.9 * k
		var roll := deg_to_rad(2.0) * sin(TAU * te / 3.2 + ph)
		var pitch := deg_to_rad(0.8) * sin(TAU * te / 4.4 + 0.8 + ph)
		var heave := 0.025 * sin(TAU * te / 3.7 + 2.1 + ph)
		(harbor.get_node(b) as Node3D).transform = boats[b] * Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		k += 1
	rotor.rotation.y = beam_yaw0 + TAU * te / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position)
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), 20.0)
	lamp_mat.set_shader_parameter("emission_energy", 3.0 + 22.0 * facing)
	lamp_omni.light_energy = 2.0 + 4.0 * facing


# --- Materialien ---------------------------------------------------------------------------------
func _make_clay(mat_name: String, figure: bool) -> ShaderMaterial:
	var d: Dictionary = CLAY.get(mat_name, {})
	if d.is_empty():
		push_error("Material %s fehlt in CLAY" % mat_name)
	var m := ShaderMaterial.new()
	m.shader = CLAY_SHADER
	m.set_shader_parameter("albedo", Color(d.get("c", "808080")))
	m.set_shader_parameter("roughness", d.get("r", 0.62))
	m.set_shader_parameter("spec", d.get("s", 0.45))
	m.set_shader_parameter("kind", d.get("kind", 0))
	# Set: Eine Fingerkuppe wäre bei Puppenmaßstab 1:5 etwa 8 cm breit; hier 10–17 cm und tiefer
	# übertrieben, damit die Abdrücke bei streifendem Blick auf das Pflaster noch lesbar sind
	m.set_shader_parameter("print_cell", 0.17)
	m.set_shader_parameter("print_depth", 0.009)
	m.set_shader_parameter("print_density", 0.7)
	m.set_shader_parameter("bump_amp", 0.003)
	m.set_shader_parameter("bump_wave", 0.08)
	m.set_shader_parameter("cavity_dark", 0.45)
	for key in ["print_cell", "print_depth", "bump_amp", "bump_wave"]:
		if d.has(key):
			m.set_shader_parameter(key, d[key])
	if d.has("emit"):
		m.set_shader_parameter("emission_color", Color(d["emit"]))
		m.set_shader_parameter("emission_energy", d["e"])
	if figure:
		# Figur: Puppe etwa 20 cm, also feinere Abdrücke; Formrauschen je Animationsbild
		m.set_shader_parameter("use_rest", true)
		m.set_shader_parameter("print_cell", 0.095)
		m.set_shader_parameter("print_depth", 0.0034)
		m.set_shader_parameter("ridge_len", 0.0105)
		m.set_shader_parameter("ridge_amp", 0.0004)
		m.set_shader_parameter("bump_amp", 0.0009)
		m.set_shader_parameter("bump_wave", 0.035)
		m.set_shader_parameter("pore_cell", 0.03)
		m.set_shader_parameter("pore_depth", 0.0008)
		m.set_shader_parameter("speck_cell", 0.022)
		if opt["boil"] and opt["detail"]:
			m.set_shader_parameter("boil_amp", 0.006)
			m.set_shader_parameter("boil_shift", 0.004)
			m.set_shader_parameter("boil_prints", 0.12)
	if not opt["detail"]:
		for key in ["bump_scale", "speck_amount", "mottle", "streak", "cavity_dark"]:
			m.set_shader_parameter(key, 0.0)
	return m


func _make_terrain() -> ShaderMaterial:
	var m := _make_clay("Rock", false)
	m.set_shader_parameter("kind", 4)
	m.set_shader_parameter("rock_color", Color(CLAY["Rock"]["c"]))
	m.set_shader_parameter("sand_color", Color(CLAY["Sand"]["c"]))
	m.set_shader_parameter("grass_color", Color(CLAY["Grass"]["c"]))
	m.set_shader_parameter("roughness", 0.72)
	return m


func _apply_harbor_materials() -> void:
	for mi: MeshInstance3D in harbor.find_children("*", "MeshInstance3D", true, false):
		for s in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(s)
			if src == null:
				push_error("%s: Fläche %d ohne Material" % [mi.name, s])
				continue
			var key := src.resource_name
			var m: ShaderMaterial
			if mi.name in ["Headland", "WestHill"] and key in ["Rock", "Sand", "Grass"]:
				# Gelände: ein Material für alle drei Flächen, Grenzen im Shader (keine Polygonzacken)
				if not mats.has("Terrain"):
					mats["Terrain"] = _make_terrain()
				m = mats["Terrain"]
			elif mi.name in ["LanternGlass", "LighthouseLamp"]:
				m = _make_clay(key, false)            # eigene Kopie: flackert bzw. blitzt einzeln
				if mi.name == "LanternGlass":
					lantern_mat = m
				else:
					lamp_mat = m
			else:
				if not mats.has(key):
					mats[key] = _make_clay(key, false)
				m = mats[key]
			mi.set_surface_override_material(s, m)
		# jedes Objekt mit eigenem Musterversatz (sonst tragen gleiche Fässer gleiche Abdrücke)
		var h := float(hash(String(mi.name)) % 1000)
		mi.set_instance_shader_parameter("noise_offset", Vector3(h * 0.137, h * 0.071, h * 0.193))
		mi.set_instance_shader_parameter("detail_scale", DETAIL_SCALE.get(String(mi.name), 1.0))
		if mi.name in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


func _attach_to_empties() -> void:
	for holder in $Attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt im Hafen" % holder.name)
			continue
		for c in holder.get_children():
			c.reparent(target, false)


# --- Knetmeer und Himmelsprospekt ----------------------------------------------------------------
## Gitter im Kamerakegel: Zeilenabstand wächst mit dem Quadrat der Entfernung (gleichmäßige Dichte im Bild
## bei streifendem Blick), jede Zeile gleich viele Spalten (keine T-Stöße).
func _build_sea() -> void:
	var cam := camera.global_position
	var rows := PackedFloat32Array()
	var z := 0.4
	while z > -56.0:
		rows.append(z)
		var dz := cam.z - z
		z -= clampf(dz * dz / 1100.0, 0.035, 2.5)
	rows.append(-56.0)
	var ncol := 420
	var verts := PackedVector3Array()
	var norms := PackedVector3Array()
	var idx := PackedInt32Array()
	for r in rows.size():
		var zz := rows[r]
		var dz := cam.z - zz
		var x0 := cam.x - dz * 0.56 - 3.0
		var x1 := cam.x + dz * 1.12 + 3.0
		for c in ncol:
			verts.append(Vector3(lerpf(x0, x1, float(c) / (ncol - 1)), 0.0, zz))
			norms.append(Vector3.UP)
	for r in rows.size() - 1:
		for c in ncol - 1:
			var a := r * ncol + c
			var b := a + 1
			var cc := a + ncol
			var d := cc + 1
			idx.append_array(PackedInt32Array([a, cc, b, b, cc, d]))
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = norms
	arrays[Mesh.ARRAY_INDEX] = idx
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	sea_mat = ShaderMaterial.new()
	sea_mat.shader = SEA_SHADER
	var sea := MeshInstance3D.new()
	sea.name = "ClaySea"
	sea.mesh = mesh
	sea.material_override = sea_mat
	sea.position = Vector3(0.0, -0.8, 0.0)
	sea.extra_cull_margin = 0.5
	sea.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(sea)


func _build_backdrop() -> void:
	var plane := PlaneMesh.new()
	plane.size = Vector2(170.0, 72.0)
	plane.orientation = PlaneMesh.FACE_Z
	var m := ShaderMaterial.new()
	m.shader = BACKDROP_SHADER
	var bd := MeshInstance3D.new()
	bd.name = "Backdrop"
	bd.mesh = plane
	bd.material_override = m
	bd.position = Vector3(14.0, 34.5, -55.0)
	bd.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(bd)


# --- Prüfhilfen ----------------------------------------------------------------------------------
func _mask_mode() -> void:
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color.WHITE
	var black := StandardMaterial3D.new()
	black.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	black.albedo_color = Color.BLACK
	for mi: MeshInstance3D in harbor.find_children("*", "MeshInstance3D", true, false):
		mi.material_override = black
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		# Formrauschen bleibt (Shader mit Weiß), damit die Messung den echten Umriss sieht
		for s in mi.mesh.get_surface_count():
			var m := mi.get_surface_override_material(s) as ShaderMaterial
			m.set_shader_parameter("albedo", Color.WHITE)
			m.set_shader_parameter("emission_color", Color.WHITE)
			m.set_shader_parameter("emission_energy", 50.0)
	for n in ["ClaySea", "Backdrop"]:
		(get_node(n) as MeshInstance3D).material_override = black
	$WorldEnvironment.environment = Environment.new()
	$Key.visible = false
	$Rim.visible = false
	camera.attributes = null
	for l in [lantern_omni, lamp_omni]:
		l.visible = false
	harbor.find_child("Beam", true, false).visible = false


func _measure() -> void:
	# Knochen (Welt und Bild) und je Fuß drei Sohlenpunkte (Ferse, Mitte, Zehen; siehe _sole_points):
	# Der tragende Fuß muss mit einem davon stillstehen. "drawn" ordnet die Zeile dem Bild der Aufnahme zu.
	var out := {"t": snappedf(t, 0.0001), "fig_step": fig_step, "env_step": env_step,
		"drawn": Engine.get_frames_drawn(), "anim": player.current_animation,
		"anim_pos": snappedf(player.current_animation_position, 0.0001)}
	for b in ["foot.L", "foot.R", "head"]:
		var bi := skeleton.find_bone(b)
		var p := _foot_world(bi)
		var sp := camera.unproject_position(p)
		out[b] = [snappedf(p.x, 0.0001), snappedf(p.y, 0.0001), snappedf(p.z, 0.0001), snappedf(sp.x, 0.01), snappedf(sp.y, 0.01)]
		if b.begins_with("foot"):
			var sp3 := _sole_points(bi)
			for k in 3:
				var w: Vector3 = sp3[k]
				var sw := camera.unproject_position(w)
				out[b + "." + ["heel", "mid", "toe"][k]] = [snappedf(w.x, 0.0001), snappedf(w.y, 0.0001), snappedf(w.z, 0.0001), snappedf(sw.x, 0.01), snappedf(sw.y, 0.01)]
			out[b + ".support"] = snappedf(_support(bi), 0.0001)
	print("MEASURE ", JSON.stringify(out))
