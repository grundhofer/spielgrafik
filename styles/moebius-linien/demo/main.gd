extends Node3D
## Katalogeintrag moebius-linien: Linienzeichnung in 3D auf der gemeinsamen Grundlage (shared/3d).
##
## Ersetzt alle glTF-Materialien nach Namen durch shaders/ink.gdshader (flache Pastellfarbe, eine
## Schattenstufe, Schraffur im Schatten). Die schwarzen Linien zeichnet ein Nachbearbeitungs-Shader aus
## Tiefe, Normalen und Material-ID (ink_lines.gdshader). Himmel, Wasser, Lichtkegel und Lichtschein
## haben eigene Shader. Zwei feste Einstellungen: Totale mit der Hauptkamera aus shared/3d, dann ein
## Schnitt auf eine tiefe Nahaufnahme mit viel Himmel. Alles hängt an der aufsummierten Zeit t und an
## festen Seeds (deterministische Aufnahme).
##
## Schalter nach "--": --no-lines --no-ids --no-folds --no-hatch --no-shade --no-ui --shot=1|2 --t0=SEKUNDEN
## --debug-lines (Linienarten als Farben: rot Silhouette, grün Knick/Falte, blau Farbgrenze)
## Messen: --measure (Fuß- und Kopfpunkte je Bild), --mask (nur der Dachs, weiß auf Schwarz).

# --- Dachs (Werte aus shared/3d/badger_notes.md) -----------------------------------------------
const WALK_SPEED := 0.367        # m/s bei speed_scale 1, dann rutschen die Füße nicht
const WALK_RATE := 2.0
const START_X := -5.6
const TURN_T0 := 2.7             # biegt im Laufen zur Kamera der Nahaufnahme ab
const TURN_T1 := 3.5
const TURN_DEG := -55.0
const MAX_TURN_STEP := deg_to_rad(3.0)   # je Bild, nur bei einem Fuß am Boden, um dessen Bodenpunkt
# Bremsen so legen, dass der Lauf in der Durchgangsphase endet (Phase 2·BRAKE_T + 0,4 ≡ 0,8: linker
# Fuß schwingt neben dem rechten durch); die Überblendung auf Idle senkt dann nur den Schwungfuß ab
const BRAKE_T := 3.2
const BRAKE_TIME := 0.4
const IDLE_T := 3.6
const IDLE_BLEND := 0.45         # langsames Überblenden: der Schwungfuß setzt weich auf
const WAVE_T := 4.1
const WAVE_LEN := 1.5

# --- Kamera ------------------------------------------------------------------------------------
const CUT_T := 2.7               # Schnitt von der Totale auf die Nahaufnahme
# Nahaufnahme aus scripts/frame_shot.py: Füße bei (439, 538), Dachs 245 px hoch, Leuchtturm bei
# x 930 (Spitze y 44), Boot A bei x 787 über dem Textkasten, Horizont y 388 (54 % Himmel)
@export var close_pos := Vector3(-2.3, 0.62, 4.6)
@export var close_target := Vector3(-2.0, 1.0, -6.0)
@export var close_fov := 50.0

# --- Umgebung ----------------------------------------------------------------------------------
const BEAM_PERIOD := 9.0
const BEAM_POSTER_T := 4.85      # zu dieser Zeit zeigt der Strahl nach links vorn (quer über den Himmel);
const BEAM_POSTER_DIR := Vector2(-0.8, 0.6)   # (x, z); 0,75 s später zeigt er zur Kamera und blitzt
const SMOKE_PUFFS := 9
const SMOKE_LIFE := 5.0
const SEED := 20261013
const SUN_TRAVEL := Vector3(0.62, -0.38, -0.69)   # Abendsonne von links vorn, ≈22° hoch

const INK := preload("res://shaders/ink.gdshader")
const GLOW := preload("res://shaders/ink_glow.gdshader")

## Pastellpalette je glTF-Material: [Farbe, Material-ID (0..31; Figur ab 16), Zusatzparameter]
const PALETTE := {
	"Stone": [Color("ecd7ac"), 1, {"terminator": -0.25, "hatch_strength": 0.65}],   # Fasen der Pflastersteine bleiben hell
	"StoneDark": [Color("cfae8e"), 2, {"hatch_strength": 0.5}],   # Fugen und Mauern: leichtere Schraffur
	"Wood": [Color("dca274"), 3],
	"WoodDark": [Color("a7765c"), 4],
	"WhitePaint": [Color("f8f1e2"), 5],
	"RedPaint": [Color("e3755d"), 6],
	"Roof": [Color("79a6b4"), 7],
	"Rope": [Color("ead09a"), 8],
	"Metal": [Color("7d8794"), 9],
	"Rock": [Color("e0aa86"), 10],
	"Sand": [Color("f0dcae"), 11],
	"Grass": [Color("c4cf91"), 12],
	"Glass": [Color("fff0b0"), 13, {"glow": 1.0}],
}
const BADGER_PALETTE := {
	"FurDark": [Color("54515f"), 16],
	"FurLight": [Color("f7f1e6"), 17],
	"Cap": [Color("4f8670"), 18],
	"Brass": [Color("eac46a"), 19],
	"Vest": [Color("6fa070"), 20],
	"Shirt": [Color("f6e7c8"), 21],
	"Scarf": [Color("e65a42"), 22],
	"Satchel": [Color("b98053"), 23],
	"Parcel": [Color("e2c08e"), 24],
	"Nose": [Color("2e2a33"), 25],
	"Eye": [Color("1f1b22"), 26],
}

@export var water_material: ShaderMaterial
@export var lines_material: ShaderMaterial

var t := 0.0
var walk_rate := WALK_RATE
var phase := 0
var boats := {}
var smoke: Array[MeshInstance3D] = []
var smoke_jitter: Array[Vector3] = []
var lantern_mat: ShaderMaterial
var lamp_mat: ShaderMaterial
var lantern_glow: ShaderMaterial
var lamp_glow: ShaderMaterial
var lamp_glow_node: MeshInstance3D
var beam_mat: ShaderMaterial
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0
var cam_main: Transform3D
var cam_close: Transform3D
var shot := 0
var opts := {}

@onready var harbor: Node3D = $Harbor
@onready var badger: Node3D = $Badger
@onready var player: AnimationPlayer = $Badger/AnimationPlayer
@onready var camera: Camera3D = $Camera
@onready var rotor: Node3D = $Attach/LighthouseLight/Rotor
@onready var effects: Node3D = $Effects
@onready var ui: Control = $UILayer/UI
@onready var sky_mat: ShaderMaterial = ($WorldEnvironment as WorldEnvironment).environment.sky.sky_material


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=")
		opts[kv[0]] = kv[1] if kv.size() > 1 else "1"
	RenderingServer.global_shader_parameter_set("ink_hatch", 0.0 if opts.has("no-hatch") else 1.0)
	RenderingServer.global_shader_parameter_set("ink_shade", 0.0 if opts.has("no-shade") else 1.0)

	var sun := $Sun as DirectionalLight3D
	sun.global_transform = Transform3D.IDENTITY.looking_at(SUN_TRAVEL, Vector3.UP)

	_apply_palette(harbor, PALETTE)
	_apply_palette(badger, BADGER_PALETTE)
	beam_mat = ($Attach/LighthouseLight/Rotor/Tilt/Beam as MeshInstance3D).get_surface_override_material(0) as ShaderMaterial
	_attach_to_empties()

	# Wasser
	var n := replace_material(harbor, "Water", water_material)
	assert(n == 1, "Material Water nicht gefunden")
	(harbor.get_node("Sea") as MeshInstance3D).extra_cull_margin = 1.0

	# Leuchtende Teile: je Objekt eigenes Material (einzeln flackern/blitzen), keine Schatten
	lantern_mat = _own_material(harbor.find_child("LanternGlass", true, false))
	lamp_mat = _own_material(harbor.find_child("LighthouseLamp", true, false))
	for glass in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
		(harbor.find_child(glass, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform

	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	player.play("Walk")
	player.speed_scale = WALK_RATE
	badger.position = Vector3(START_X, 0.0, 1.2)

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0

	# Linien je Renderer: Normalen-/Rauheitspuffer gibt es nur in Forward+
	var fplus := RenderingServer.get_current_rendering_method() == "forward_plus"
	lines_material.shader = load("res://shaders/ink_lines.gdshader" if fplus else "res://shaders/ink_lines_depth.gdshader")
	lines_material.set_shader_parameter("grain_tex", _noise_tex(SEED + 7, 0.045, 512))
	lines_material.set_shader_parameter("wobble_tex", _noise_tex(SEED + 9, 0.012, 256))
	if opts.has("no-lines"):
		lines_material.set_shader_parameter("lines_on", 0.0)
		sky_mat.set_shader_parameter("lines_on", 0.0)
		beam_mat.set_shader_parameter("lines_on", 0.0)
	if opts.has("no-ids"):
		lines_material.set_shader_parameter("id_lines", 0.0)
	if opts.has("no-folds"):
		lines_material.set_shader_parameter("fold_lines", 0.0)
		lines_material.set_shader_parameter("figure_gap", 0.06)
	if opts.has("debug-lines"):
		lines_material.set_shader_parameter("debug", 1.0)

	cam_main = camera.global_transform
	cam_close = Transform3D.IDENTITY.translated(close_pos).looking_at(close_target, Vector3.UP)

	# Leuchtfeuer: Strahlrichtung = -Z des Rotors = (-sin y, 0, -cos y)
	var lamp := harbor.find_child("LighthouseLight", true, false) as Node3D
	beam_yaw0 = atan2(-BEAM_POSTER_DIR.x, -BEAM_POSTER_DIR.y) - TAU * BEAM_POSTER_T / BEAM_PERIOD

	lantern_glow = _make_glow(harbor.find_child("LanternLight", true, false), 1.3, 0.32).material_override
	lamp_glow_node = _make_glow(lamp, 4.2, 1.6)
	lamp_glow = lamp_glow_node.material_override
	lamp_glow.set_shader_parameter("rays", 16)
	_build_smoke()

	if opts.has("no-ui"):
		ui.visible = false
	if opts.has("mask"):
		_mask_mode()
	_setup_measure()

	_update(0.0)
	# --t0: Zeit vorspulen (für Prüfungen langer Läufe), gleiche Schritte wie die Aufnahme
	var t0 := float(opts.get("t0", "0"))
	while t < t0 - 0.0001:
		t += 1.0 / 30.0
		_update(1.0 / 30.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)
	if opts.has("measure"):
		_measure()


func _update(delta: float) -> void:
	RenderingServer.global_shader_parameter_set("ink_time", t)
	_update_badger(delta)
	_update_camera()
	ui.set("t", t)
	ui.set("shot", shot)

	# Boote schaukeln um ihren Ursprung (Wasserlinie); Bug zeigt lokal nach +X
	var k := 0
	for b in boats:
		var ph := 1.7 * k
		var roll := deg_to_rad(2.4) * sin(TAU * t / 3.4 + ph)
		var pitch := deg_to_rad(0.9) * sin(TAU * t / 4.6 + 0.8 + ph)
		var heave := 0.035 * sin(TAU * t / 3.9 + 2.1 + ph)
		var local := Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		(harbor.get_node(b) as Node3D).transform = boats[b] * local
		k += 1

	# Laterne flackert: Glasfarbe, Hof und Strahlenkranz gemeinsam
	var f := 0.5 + 0.5 * clampf(lantern_noise.get_noise_1d(t * 6.0) * 1.6 + 0.35 * lantern_noise.get_noise_1d(t * 29.0 + 50.0), -1.0, 1.0)
	lantern_mat.set_shader_parameter("albedo", Color("ffd27a").lerp(Color("fff6c8"), f))
	lantern_glow.set_shader_parameter("burst", f)
	lantern_glow.set_shader_parameter("spin", 0.15 * sin(t * 3.0))

	# Leuchtfeuer dreht sich; zeigt der Strahl zur Kamera, blitzt die Lampe mit großem Strahlenkranz
	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := camera.global_position - rotor.global_position
	var toward := clampf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0, 1.0)
	var facing := pow(toward, 10.0)
	# Zeigt der Kegel zur Kamera, wäre er nur ein heller Keil über der Lampe: dann tritt er zurück
	# und der Strahlenkranz übernimmt (so zeichnet man ein Licht, das den Betrachter trifft)
	beam_mat.set_shader_parameter("intensity", 1.0 - 0.9 * smoothstep(0.92, 0.985, toward))
	lamp_mat.set_shader_parameter("albedo", Color("fff0b0").lerp(Color("fffdf2"), facing))
	lamp_glow.set_shader_parameter("burst", facing)
	lamp_glow_node.visible = facing > 0.02

	_update_smoke()


func _update_badger(delta: float) -> void:
	# Der AnimationPlayer läuft von Hand (advance): erst Pose, dann Vorschub, dann Drehung um den
	# Standfuß (Muster aus toon-cel; dort gemessen: Standfuß höchstens 7,6 mm je Bild).
	if phase == 0:
		walk_rate = WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, t))
		player.speed_scale = walk_rate
		player.advance(delta)
		var th := badger.rotation.y
		badger.position += Vector3(cos(th), 0.0, -sin(th)) * WALK_SPEED * walk_rate * delta
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
			player.play("Idle", IDLE_BLEND)
			_plant_side = _grounded_side()
			if _plant_side != "":
				_plant_point = _foot_mid(_plant_side)
		return
	if phase == 1 and t >= WAVE_T:
		phase = 2
		player.play("Wave", 0.25)
	elif phase == 2 and t >= WAVE_T + WAVE_LEN - 0.1:
		phase = 3
		player.play("Idle", 0.3)
	player.advance(delta)
	# Überblendung Walk -> Idle: Die Ruhepose stellt die Füße etwas anders als der Lauf. Damit der
	# Standfuß dabei nicht rutscht, wird die Figur so nachgeschoben, dass er an seinem Platz bleibt.
	if phase == 1 and t < IDLE_T + IDLE_BLEND + 0.1 and _plant_side != "":
		var d := _plant_point - _foot_mid(_plant_side)
		badger.position += Vector3(d.x, 0.0, d.z)


func _update_camera() -> void:
	var s := 1 if t < CUT_T else 2
	if opts.has("shot"):
		s = int(opts["shot"])
	if s == shot:
		return
	shot = s
	camera.global_transform = cam_main if s == 1 else cam_close
	camera.fov = 42.0 if s == 1 else close_fov
	sky_mat.set_shader_parameter("px_deg", camera.fov / 720.0)


# --- Materialien -------------------------------------------------------------------------------
func _ink_material(entry: Array) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = INK
	m.set_shader_parameter("albedo", entry[0])
	m.set_shader_parameter("material_id", entry[1])
	if entry.size() > 2:
		for k in entry[2]:
			m.set_shader_parameter(k, entry[2][k])
	return m


func _apply_palette(root: Node, palette: Dictionary) -> void:
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
				cache[key] = _ink_material(palette[key])
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


func _noise_tex(seed_: int, freq: float, size: int) -> NoiseTexture2D:
	var nz := FastNoiseLite.new()
	nz.seed = seed_
	nz.frequency = freq
	nz.fractal_octaves = 3
	var tex := NoiseTexture2D.new()
	tex.width = size
	tex.height = size
	tex.seamless = true
	tex.noise = nz
	return tex


# --- Lichtschein: Billboard mit Hof und Strahlenkranz an einem Empty ---------------------------
func _make_glow(anchor: Node3D, size_m: float, offset_m: float) -> MeshInstance3D:
	var mat := ShaderMaterial.new()
	mat.shader = GLOW
	mat.render_priority = 120   # nach den Linien (100): die Nachbearbeitung übermalt sonst Durchsichtiges
	mat.set_shader_parameter("offset_m", offset_m)
	if opts.has("no-lines"):
		mat.set_shader_parameter("lines_on", 0.0)
	var q := QuadMesh.new()
	q.size = Vector2.ONE
	var mi := MeshInstance3D.new()
	mi.mesh = q
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.extra_cull_margin = 8.0
	mi.scale = Vector3.ONE * size_m
	anchor.add_child(mi)
	return mi


# --- Rauch: umrissene Bällchen, die wachsen, aufsteigen, abtreiben und wieder schrumpfen ----------
func _build_smoke() -> void:
	var mat := _ink_material([Color("f3eef0"), 14, {"hatch_strength": 0.0, "shade_mul": Vector3(1.25, 1.25, 1.12)}])
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
		smoke_jitter.append(Vector3(rng.randf_range(-0.2, 0.2), rng.randf_range(0.85, 1.2), rng.randf_range(-0.04, 0.04)))


func _update_smoke() -> void:
	for i in smoke.size():
		var j := smoke_jitter[i]
		var age := fposmod(t / SMOKE_LIFE + float(i) / SMOKE_PUFFS + j.z, 1.0)
		var p := smoke[i]
		var rise := 1.0 - pow(1.0 - age, 1.6)
		# Wind von links: die Säule biegt sich nach rechts, die Bällchen pendeln leicht
		var sway := 0.12 * sin(TAU * (age * 1.3 + float(i) * 0.37))
		p.position = Vector3(2.6 * pow(age, 1.5) + j.x * age + sway, -0.1 + 2.6 * rise, j.x * 0.6)
		var s := (0.26 + 0.78 * rise) * (1.0 - smoothstep(0.72, 1.0, age)) * smoothstep(0.0, 0.08, age) * j.y
		p.scale = Vector3(s * 1.1, s * 0.92, s)
		p.visible = s > 0.1   # winzige Bällchen wären nur noch Tuschepunkte


# --- Messen ------------------------------------------------------------------------------------
# --mask: nur der Dachs, weiß und unbeleuchtet auf Schwarz (Silhouette für die Bildmessung)
# --measure: je Bild Ferse und Zehe beider Füße sowie Kopf in Welt- und Bildkoordinaten
var _skel: Skeleton3D
var _probe := {}   # Name -> [Knochenindex, Punkt im Knochenraum]


func _mask_mode() -> void:
	harbor.visible = false
	effects.visible = false
	$Camera/Lines.visible = false
	ui.visible = false
	var env := ($WorldEnvironment as WorldEnvironment).environment
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color.BLACK
	env.fog_enabled = false
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color.WHITE
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			mi.set_surface_override_material(i, white)


func _setup_measure() -> void:
	_skel = badger.find_child("Skeleton3D", true, false) as Skeleton3D
	# Punkte in Ruhepose (Figurenkoordinaten aus badger_notes.md): Ferse und Zehe 3 mm über dem
	# Boden, Kopf = Mützendeckel
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


## Bodenpunkt des Standfußes: Mittel seiner Punkte unter 1 cm; null bei zwei oder keinem Fuß am Boden.
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


var _plant_side := ""
var _plant_point := Vector3.ZERO


## Seite des einzigen Fußes, dessen Ferse und Zehe am Boden stehen ("" bei keinem oder beiden).
func _grounded_side() -> String:
	var down: Array[String] = []
	for side in ["L", "R"]:
		if _probe_world("heel." + side).y < 0.01 and _probe_world("toe." + side).y < 0.01:
			down.append(side)
	return down[0] if down.size() == 1 else ""


func _foot_mid(side: String) -> Vector3:
	return (_probe_world("heel." + side) + _probe_world("toe." + side)) * 0.5


func _measure() -> void:
	var line := "M %.4f shot %d rot %.2f pos %.4f %.4f" % [t, shot, rad_to_deg(badger.rotation.y), badger.position.x, badger.position.z]
	for k in ["heel.L", "toe.L", "heel.R", "toe.R", "head"]:
		var w := _probe_world(k)
		var sp := camera.unproject_position(w)
		line += " %s %.4f %.4f %.4f %.2f %.2f" % [k, w.x, w.y, w.z, sp.x, sp.y]
	print(line)
