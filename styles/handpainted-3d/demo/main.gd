extends Node3D
## Handbemalte Texturen (stilisiert): Hafen von Lornholm mit dem Dachs-Kurier.
##
## Ersetzt alle glTF-Materialien nach Namen: Hafen -> hp_world.gdshader (gemalte Kacheltextur je Material,
## Projektion je Objekt, gebackene Verdeckung aus den Vertexfarben), Dachs -> hp_actor.gdshader (Farbe,
## Pinseltupfer, aufgemalter Höhenverlauf, Lichtkante), Meer -> hp_water.gdshader. Animiert über die
## aufsummierte Zeit t: Dachs (läuft von links ins Bild, biegt zur Kamera ab, bleibt stehen, winkt), Kamerafahrt,
## Boote, Laterne, Leuchtfeuer, Rauch, Möwen, Wolkendrift. Feste Seeds, deterministisch.
##
## Schalter nach "--": --no-paint (Texturen durch ihre Mittelfarbe ersetzen), --no-ao (ohne gebackene
## Verdeckung), --no-ui, --static-cam (Endeinstellung), --cam-start, --mask (Dachs weiß vor Schwarz),
## --measure (Fuß- und Kopfpunkte je Bild ausgeben), --t0=<s> (Startzeit vorspulen).

# --- Dachs (Werte aus shared/3d/badger_notes.md) -----------------------------------------------
const WALK_SPEED := 0.367            # m/s bei speed_scale 1
const WALK_RATE := 2.0
const START := Vector3(-3.3, 0.0, 2.75)   # bei t = 0 knapp links außerhalb der Anfangseinstellung
const TURN_T0 := 1.9
const TURN_T1 := 2.9
const TURN_DEG := -70.0              # Blick zur Endeinstellung der Kamera (plan_shot.py)
const MAX_TURN_STEP := deg_to_rad(3.0)
const BRAKE_T := 2.95                # Lauf endet in der Durchgangsphase (ein Fuß steht, einer schwingt)
const BRAKE_TIME := 0.4
const IDLE_T := 3.3
const IDLE_BLEND := 0.3              # Überblendung Walk -> Idle; der Standfuß wird dabei festgehalten
const WAVE_T := 3.85
const WAVE_LEN := 1.5

# --- Kamera: langsame Fahrt von der Halbtotalen zur Endeinstellung -----------------------------
# Anfang: Steg, Laterne, Boote, Leuchtturm (unter dem Gebietsnamen), der Dachs kommt von links ins Bild.
# Ende: Häuschen mit Seitenfenster und Schornstein links, Dachs halblinks, Leuchtturm rechts oben, Laterne
# rechts über dem Dialogfenster (scripts/plan_shot.py).
const CAM_A_POS := Vector3(1.5, 1.8, 11.0)
const CAM_A_LOOK := Vector3(4.0, 3.0, -4.0)
const CAM_A_FOV := 48.0
const CAM_B_POS := Vector3(0.8, 1.8, 8.6)
const CAM_B_LOOK := Vector3(-2.0, 2.6, -4.0)
const CAM_B_FOV := 52.0
const CAM_T0 := 0.0
const CAM_T1 := 4.2

# --- Umgebung -----------------------------------------------------------------------------------
const BEAM_PERIOD := 9.0
const BEAM_FACING_T := 2.55          # dann zeigt der Strahl zur Kamera (Lampe blitzt); dreht im Uhrzeigersinn
const FLASH_EXP := 56.0
const SMOKE_PUFFS := 7
const SMOKE_LIFE := 4.2
const SEED := 20261012
const SUN_TRAVEL := Vector3(0.78, -0.40, -0.48)
const KEY_TRAVEL := Vector3(0.45, -0.55, -0.7)   # Figurenlicht (nur Ebene 2)
const SKY_AZ_CENTER := 10.0
const SKY_AZ_SPAN := 104.0
const SKY_EL_TOP := 40.0
const SKY_DRIFT := 4.0               # Grad: Wolken pendeln langsam hin und her (Periode 120 s),
const SKY_DRIFT_PERIOD := 120.0      # damit auch lange Läufe nie den Bildrand des Himmels zeigen

const WORLD := preload("res://shaders/hp_world.gdshader")
const ACTOR := preload("res://shaders/hp_actor.gdshader")
const GLOW := preload("res://shaders/hp_glow.gdshader")
const SMOKE := preload("res://shaders/hp_smoke.gdshader")
const GULL := preload("res://shaders/hp_gull.gdshader")
const MARKER := preload("res://shaders/hp_marker.gdshader")
const BLOB := preload("res://shaders/hp_blob.gdshader")
const MARKER_T := 3.45               # goldenes Ausrufezeichen erscheint über dem stehenden Dachs

## Material -> [Textur, Meter je Kachel, Tönung, Projektion]; Projektion siehe hp_world.gdshader
const PALETTE := {
	"Paving": ["paving", 1.75, Color(1.0, 0.98, 0.95), 0],
	"Stone": ["wall", 1.7, Color(1.0, 0.98, 0.97), 0],
	"StoneDark": ["wall", 1.3, Color(0.66, 0.62, 0.72), 0],
	"Wood": ["planks", 1.15, Color(1.0, 1.0, 1.0), 0],
	"WoodDark": ["planks_dark", 1.15, Color(1.0, 1.0, 1.0), 0],
	"WhitePaint": ["plaster", 1.6, Color(1.0, 0.97, 0.93), 0],
	"RedPaint": ["plaster", 1.6, Color(0.86, 0.24, 0.2), 0],
	"Roof": ["roof", 1.35, Color(1.0, 1.0, 1.0), 0],
	"Rope": ["sand", 0.4, Color(0.92, 0.78, 0.58), 1],
	"Metal": ["plaster", 0.7, Color(0.30, 0.29, 0.37), 1],
	"Rock": ["rock", 4.5, Color(1.0, 0.97, 0.97), 1],
	"Sand": ["sand", 3.0, Color(1.0, 0.97, 0.94), 1],
	"Grass": ["grass", 3.2, Color(1.0, 1.0, 1.0), 1],
	"Glass": ["plaster", 1.0, Color(1.0, 0.82, 0.5), 0],
}
## Projektion je Objekt (überschreibt die Spalte oben): Fässer und Leuchtturm zylindrisch, Boote lokal
const OBJECT_MAPPING := {
	"Barrel1": [2, 0.31, true], "Barrel2": [2, 0.31, true],
	"Lighthouse": [2, 1.25, false],
	"BoatA": [3, 0.0, false], "BoatB": [3, 0.0, false],
	"Bollards": [1, 0.0, false], "RopeCoil": [1, 0.0, false],
	"Headland": [1, 0.0, false], "WestHill": [1, 0.0, false], "IslandsFar": [1, 0.0, false],
	"RocksSea": [1, 0.0, false],
}
## Steinflächen mit eigener Abbildung je Fläche (UV/UV2 aus build_harbor_hp.py): ein gemalter Stein je Fläche
const BLOCK_OBJECTS := ["Cottage", "Quay", "LanternPost"]
## Figur: kräftige, warme Farben, Glanzpunkt nur auf Messing, Nase und Augen
const BADGER_PALETTE := {
	"FurDark": [Color(0.20, 0.155, 0.17), 0.0],
	"FurLight": [Color(0.98, 0.92, 0.80), 0.0],
	"Cap": [Color(0.20, 0.42, 0.24), 0.0],
	"Brass": [Color(0.98, 0.74, 0.30), 0.45],
	"Vest": [Color(0.30, 0.52, 0.26), 0.0],
	"Shirt": [Color(0.98, 0.88, 0.70), 0.0],
	"Scarf": [Color(0.90, 0.18, 0.16), 0.0],
	"Satchel": [Color(0.58, 0.30, 0.16), 0.0],
	"Parcel": [Color(0.86, 0.60, 0.34), 0.0],
	"Nose": [Color(0.10, 0.07, 0.08), 0.6],
	"Eye": [Color(0.07, 0.04, 0.04), 0.7],
}

@export var water_material: ShaderMaterial
@export var sky_material: ShaderMaterial

var opts := {}
var t := 0.0
var walk_rate := WALK_RATE
var phase := 0
var boats := {}
var textures := {}
var smoke: Array[MeshInstance3D] = []
var smoke_jitter: Array[Vector3] = []
var gulls: Array[MeshInstance3D] = []
var lantern_mat: ShaderMaterial
var lamp_mat: ShaderMaterial
var window_mat: ShaderMaterial
var lantern_glow: MeshInstance3D
var lamp_glow: MeshInstance3D
var window_glow: MeshInstance3D
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0
var flick_lo := 1.0
var flick_hi := 0.0
var marker: MeshInstance3D
var blob: MeshInstance3D
var _skel: Skeleton3D
var _hold_side := ""                 # Standfuß, der während der Überblendung zu Idle festgehalten wird
var _hold_until := 0.0
var _probe := {}

@onready var harbor: Node3D = $Harbor
@onready var badger: Node3D = $Badger
@onready var player: AnimationPlayer = $Badger/AnimationPlayer
@onready var camera: Camera3D = $Camera
@onready var effects: Node3D = $Effects
@onready var rotor: Node3D = $Attach/LighthouseLight/Rotor
@onready var lantern_omni: OmniLight3D = $Attach/LanternLight/Omni
@onready var lamp_omni: OmniLight3D = $Attach/LighthouseLight/Omni


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=")
		opts[kv[0]] = kv[1] if kv.size() > 1 else true
	($Sun as DirectionalLight3D).global_transform = Transform3D.IDENTITY.looking_at(SUN_TRAVEL, Vector3.UP)
	($CharKey as DirectionalLight3D).global_transform = Transform3D.IDENTITY.looking_at(KEY_TRAVEL, Vector3.UP)
	if opts.has("no-key"):
		($CharKey as DirectionalLight3D).visible = false
	for n in ["paving", "wall", "roof", "planks", "planks_dark", "rock", "grass", "sand", "plaster"]:
		textures[n] = load("res://textures/%s.png" % n)

	_apply_world(harbor)
	_apply_actor(badger)
	_attach_to_empties()   # erst nach den Materialien: der Lichtkegel hängt sonst im Hafen

	for m: ShaderMaterial in [water_material, sky_material]:
		m.set_shader_parameter("sky_az_center", SKY_AZ_CENTER)
		m.set_shader_parameter("sky_az_span", SKY_AZ_SPAN)
		m.set_shader_parameter("sky_el_top", SKY_EL_TOP)
	var n := replace_material(harbor, "Water", water_material)
	assert(n == 1, "Material Water nicht gefunden")
	(harbor.get_node("Sea") as MeshInstance3D).extra_cull_margin = 1.0

	lantern_mat = _glass(harbor.find_child("LanternGlass", true, false), Color(1.0, 0.72, 0.36), 3.0)
	lamp_mat = _glass(harbor.find_child("LighthouseLamp", true, false), Color(1.0, 0.86, 0.56), 3.0)
	window_mat = _glass(harbor.find_child("CottageWindow", true, false), Color(1.0, 0.6, 0.26), 1.5)
	for glass in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
		(harbor.find_child(glass, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform

	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	badger.position = START
	player.play("Walk")
	player.speed_scale = WALK_RATE

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	# Spannweite des Rauschens messen und später auf 0,45..1,0 abbilden (sonst flackert es kaum sichtbar)
	for i in 600:
		var v := _flicker_raw(i * 0.01)
		flick_lo = minf(flick_lo, v)
		flick_hi = maxf(flick_hi, v)

	# Leuchtfeuer: Drehwinkel so legen, dass der Strahl bei BEAM_FACING_T zur Endkamera zeigt
	var to_cam := CAM_B_POS - rotor.global_position
	beam_yaw0 = atan2(-to_cam.x, -to_cam.z) + TAU * BEAM_FACING_T / BEAM_PERIOD

	lantern_glow = _make_glow(harbor.find_child("LanternLight", true, false), Color(1.0, 0.7, 0.34), 1.0)
	lamp_glow = _make_glow(harbor.find_child("LighthouseLight", true, false), Color(1.0, 0.85, 0.55), 0.9)
	window_glow = _make_glow(harbor.find_child("CottageWindow", true, false), Color(1.0, 0.66, 0.32), 0.35)
	window_glow.position = Vector3(0.0, 0.0, 0.25)
	window_glow.scale = Vector3.ONE * 1.6
	_build_smoke()
	_build_gulls()
	_build_marker()
	_build_blob()
	if opts.has("no-ui"):
		$UI.visible = false
	if opts.has("mask"):
		_mask_mode()
	_setup_measure()
	if opts.has("measure"):
		RenderingServer.frame_pre_draw.connect(_measure)
	var t0 := float(opts.get("t0", "0.0"))
	while t < t0 - 0.0001:
		t += 1.0 / 30.0
		_update(1.0 / 30.0)
	_update(0.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)


func _update(delta: float) -> void:
	_update_badger(delta)
	_update_camera()
	var drift := SKY_DRIFT * sin(TAU * t / SKY_DRIFT_PERIOD)
	sky_material.set_shader_parameter("sky_drift", drift)
	water_material.set_shader_parameter("sky_drift", drift)
	water_material.set_shader_parameter("time_s", t)

	var k := 0
	for b in boats:
		var ph := 1.7 * k
		var roll := deg_to_rad(2.4) * sin(TAU * t / 3.4 + ph)
		var pitch := deg_to_rad(1.0) * sin(TAU * t / 4.6 + 0.8 + ph)
		var heave := 0.04 * sin(TAU * t / 3.9 + 2.1 + ph)
		var local := Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		(harbor.get_node(b) as Node3D).transform = boats[b] * local
		k += 1

	# Laterne flackert: Glas, Lichthof und Licht gemeinsam
	var f := 0.45 + 0.55 * clampf((_flicker_raw(t) - flick_lo) / maxf(flick_hi - flick_lo, 0.001), 0.0, 1.0)
	lantern_omni.light_energy = 2.4 * f
	lantern_mat.set_shader_parameter("emission_energy", 2.4 * f)
	lantern_glow.scale = Vector3.ONE * (0.9 + 0.7 * f)
	(lantern_glow.material_override as ShaderMaterial).set_shader_parameter("intensity", 0.6 + 0.6 * f)

	# Leuchtfeuer dreht sich; Lampe blitzt auf, wenn der Strahl zur Kamera zeigt
	rotor.rotation.y = beam_yaw0 - TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position).normalized()
	# Exponent 56: halbe Stärke nur, solange der Strahl auf ±9° zur Kamera zeigt (0,45 s je Umlauf von 9 s)
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), FLASH_EXP)
	lamp_mat.set_shader_parameter("emission_energy", 3.0 + 10.0 * facing)
	lamp_omni.light_energy = 2.0 + 4.0 * facing
	lamp_glow.scale = Vector3.ONE * (2.0 + 3.0 * facing)

	_update_smoke()
	_update_gulls()
	_update_marker()
	_update_blob()


func _flicker_raw(x: float) -> float:
	return lantern_noise.get_noise_1d(x * 6.0) + 0.35 * lantern_noise.get_noise_1d(x * 23.0 + 50.0)


# --- Dachs ---------------------------------------------------------------------------------------
func _update_badger(delta: float) -> void:
	# AnimationPlayer von Hand (advance): erst Pose, dann Vorschub entlang der Blickrichtung, dann Drehung
	# um den Bodenpunkt des Standfußes (nur bei genau einem Fuß am Boden), so bleibt der Standfuß stehen.
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
			# Walk in der Pose einfrieren (eigenes Tempo 0), sonst läuft der Schwungfuß während der
			# Überblendung weiter nach vorn und rutscht nach dem Aufsetzen zurück
			player.play("Walk", 0.0, 0.0)
			player.play("Idle", IDLE_BLEND)
			_hold_side = _lower_foot()
			_hold_until = t + IDLE_BLEND
		return
	if phase == 1 and t >= WAVE_T:
		phase = 2
		player.play("Wave", 0.25)
	elif phase == 2 and t >= WAVE_T + WAVE_LEN - 0.1:
		phase = 3
		player.play("Idle", 0.3)
	# Überblendung Walk -> Idle: den Standfuß am Boden festhalten (Körper statt Fuß verschieben)
	var hold := phase == 1 and t <= _hold_until + 0.0001 and _hold_side != ""
	var before := _foot_point(_hold_side) if hold else Vector3.ZERO
	player.advance(delta)
	if hold:
		var after := _foot_point(_hold_side)
		badger.position += Vector3(before.x - after.x, 0.0, before.z - after.z)


func _update_camera() -> void:
	var k := 1.0 if opts.has("static-cam") else smoothstep(CAM_T0, CAM_T1, t)
	if opts.has("cam-start"):
		k = 0.0
	var a := Transform3D.IDENTITY.translated(CAM_A_POS).looking_at(CAM_A_LOOK, Vector3.UP)
	var b := Transform3D.IDENTITY.translated(CAM_B_POS).looking_at(CAM_B_LOOK, Vector3.UP)
	var q := a.basis.get_rotation_quaternion().slerp(b.basis.get_rotation_quaternion(), k)
	camera.global_transform = Transform3D(Basis(q), CAM_A_POS.lerp(CAM_B_POS, k))
	camera.fov = lerpf(CAM_A_FOV, CAM_B_FOV, k)


# --- Materialien ---------------------------------------------------------------------------------
func _mean_color(tex: Texture2D) -> Color:
	var img := tex.get_image()
	img.decompress()
	img.resize(1, 1, Image.INTERPOLATE_BILINEAR)
	return img.get_pixel(0, 0)


func _world_material(obj: String, mat_name: String) -> ShaderMaterial:
	var e: Array = PALETTE[mat_name]
	var m := ShaderMaterial.new()
	m.shader = WORLD
	var tex: Texture2D = textures[e[0]]
	m.set_shader_parameter("tex", tex)
	m.set_shader_parameter("tile_m", e[1])
	var tint: Color = e[2]
	m.set_shader_parameter("tint", Vector3(tint.r, tint.g, tint.b))
	var mapping: int = e[3]
	if OBJECT_MAPPING.has(obj):
		var om: Array = OBJECT_MAPPING[obj]
		mapping = om[0]
		if mapping == 2:
			m.set_shader_parameter("cyl_radius", om[1])
			m.set_shader_parameter("rotate90", om[2] and mat_name in ["Wood", "WoodDark"])
	m.set_shader_parameter("mapping", mapping)
	if opts.has("no-ao"):
		m.set_shader_parameter("has_ao", false)
	if opts.has("no-paint"):
		# Vergleich: gleiche Mittelfarbe ohne gemalte Struktur
		var img := Image.create(4, 4, false, Image.FORMAT_RGB8)
		img.fill(_mean_color(tex))
		m.set_shader_parameter("tex", ImageTexture.create_from_image(img))
	if obj in ["IslandsFar"]:
		m.set_shader_parameter("ao_far", 0.0)
	if mat_name == "StoneDark" and obj in BLOCK_OBJECTS and not opts.has("no-paint"):
		var wc := _mean_color(textures["wall"]).srgb_to_linear()
		var pc := _mean_color(textures["plaster"]).srgb_to_linear()
		m.set_shader_parameter("use_block", true)
		m.set_shader_parameter("block_tex", textures["plaster"])
		m.set_shader_parameter("block_color", Vector3(wc.r * tint.r, wc.g * tint.g, wc.b * tint.b))
		m.set_shader_parameter("block_det_mean", Vector3(pc.r, pc.g, pc.b))
	return m


func _apply_world(root: Node) -> void:
	var cache := {}
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(i)
			if src == null:
				push_error("%s: Fläche %d ohne glTF-Material" % [mi.name, i])
				continue
			var mat_name := src.resource_name
			if mat_name == "Water":
				continue
			if not PALETTE.has(mat_name):
				push_error("Material %s fehlt in PALETTE" % mat_name)
				continue
			var mapping_key := String(mi.name) if OBJECT_MAPPING.has(String(mi.name)) else ""
			var key := mapping_key + "/" + mat_name
			if not cache.has(key):
				cache[key] = _world_material(String(mi.name), mat_name)
			mi.set_surface_override_material(i, cache[key])


func _apply_actor(root: Node) -> void:
	var brush: Texture2D = load("res://textures/brush.png")
	var cache := {}
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(i)
			var mat_name := src.resource_name
			if not BADGER_PALETTE.has(mat_name):
				push_error("Material %s fehlt in BADGER_PALETTE" % mat_name)
				continue
			if not cache.has(mat_name):
				var e: Array = BADGER_PALETTE[mat_name]
				var m := ShaderMaterial.new()
				m.shader = ACTOR
				var c: Color = e[0]
				m.set_shader_parameter("albedo", Vector3(c.r, c.g, c.b))
				m.set_shader_parameter("gloss", e[1])
				m.set_shader_parameter("brush", brush)
				if opts.has("no-paint"):
					m.set_shader_parameter("brush_amount", 0.0)
				if opts.has("no-ao"):
					m.set_shader_parameter("has_ao", false)
				cache[mat_name] = m
			mi.set_surface_override_material(i, cache[mat_name])
		mi.layers = 1 | 2   # Ebene 2: Figurenlicht


## Glas: eigenes Material je Objekt (einzeln flackern), leuchtet in warmer Farbe
func _glass(mi: MeshInstance3D, col: Color, energy: float) -> ShaderMaterial:
	var m := (mi.get_surface_override_material(0) as ShaderMaterial).duplicate() as ShaderMaterial
	m.set_shader_parameter("emission_color", Vector3(col.r, col.g, col.b))
	m.set_shader_parameter("emission_energy", energy)
	m.set_shader_parameter("has_ao", false)
	m.set_shader_parameter("tint", Vector3(0.45, 0.3, 0.16))   # Grundfarbe dunkel: das Leuchten bestimmt den Ton
	mi.set_surface_override_material(0, m)
	return m


func _attach_to_empties() -> void:
	for holder in $Attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt im Hafen" % holder.name)
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


# --- Effekte -------------------------------------------------------------------------------------
func _make_glow(anchor: Node3D, col: Color, intensity: float) -> MeshInstance3D:
	var q := QuadMesh.new()
	q.size = Vector2.ONE
	var m := ShaderMaterial.new()
	m.shader = GLOW
	m.set_shader_parameter("color", Vector3(col.r, col.g, col.b))
	m.set_shader_parameter("intensity", intensity)
	var mi := MeshInstance3D.new()
	mi.mesh = q
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	anchor.add_child(mi)
	return mi


func _build_smoke() -> void:
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	var mat := ShaderMaterial.new()
	mat.shader = SMOKE
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	var anchor := harbor.find_child("ChimneySmoke", true, false) as Node3D
	for i in SMOKE_PUFFS:
		var p := MeshInstance3D.new()
		p.mesh = quad
		p.material_override = mat
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		p.sorting_offset = float(i) * 0.01
		anchor.add_child(p)
		p.set_instance_shader_parameter("seed", rng.randf())
		smoke.append(p)
		smoke_jitter.append(Vector3(rng.randf_range(-0.12, 0.12), rng.randf_range(0.85, 1.15), rng.randf_range(-0.1, 0.1)))


func _update_smoke() -> void:
	for i in smoke.size():
		var age := fposmod(t + float(i) * SMOKE_LIFE / SMOKE_PUFFS, SMOKE_LIFE) / SMOKE_LIFE
		var j := smoke_jitter[i]
		var p := smoke[i]
		# steigt auf, treibt mit dem Wind nach rechts, wächst; ältere Ballen liegen hinten
		p.position = Vector3(1.6 * age * age + j.x * age, 2.4 * age * j.y + 0.1, j.z * age - 0.05 * age)
		var s := lerpf(0.4, 1.7, sqrt(age))
		p.scale = Vector3(s, s, s)
		p.set_instance_shader_parameter("opacity", smoothstep(0.0, 0.1, age) * (1.0 - smoothstep(0.45, 1.0, age)) * 0.8)
		p.sorting_offset = -age


func _build_gulls() -> void:
	var quad := QuadMesh.new()
	quad.size = Vector2(1.0, 0.5)
	var mat := ShaderMaterial.new()
	mat.shader = GULL
	for i in 2:
		var g := MeshInstance3D.new()
		g.mesh = quad
		g.material_override = mat
		g.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		effects.add_child(g)
		gulls.append(g)


func _update_gulls() -> void:
	# zwei Möwen ziehen in weiten Bögen über dem Hafenbecken nach links; Flügelschlag mit Gleitphasen
	for i in gulls.size():
		var g := gulls[i]
		var u := t * (0.055 + 0.012 * i) + 0.25 + 0.05 * i
		var x := lerpf(26.0, -34.0, fposmod(u, 1.0))   # Wendepunkte außerhalb des Bildes
		# Höhe und Tiefe so, dass sie in beiden Einstellungen bei y = 190–290 px fliegen (unter dem Gebietsnamen)
		var y := 7.4 + 1.2 * i + 0.5 * sin(t * 0.9 + i * 2.0)
		var z := -14.0 - 4.0 * i + 1.5 * sin(t * 0.5 + i)
		g.position = Vector3(x, y, z)
		g.scale = Vector3.ONE * (2.4 - 0.2 * i)
		var flap := sin(t * 7.5 + i * 1.3)
		var glide := smoothstep(0.2, 0.6, sin(t * 0.8 + i * 2.2))
		g.set_instance_shader_parameter("flap", lerpf(flap, 0.25, glide))


func _build_marker() -> void:
	var q := QuadMesh.new()
	q.size = Vector2(0.22, 0.44)
	var m := ShaderMaterial.new()
	m.shader = MARKER
	marker = MeshInstance3D.new()
	marker.mesh = q
	marker.material_override = m
	marker.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	effects.add_child(marker)


func _update_marker() -> void:
	var k := smoothstep(MARKER_T, MARKER_T + 0.25, t)
	marker.visible = k > 0.0
	# kurzes Überschwingen beim Erscheinen, dann sanftes Auf und Ab
	var pop := k + 0.25 * sin(PI * k) * (1.0 - k)
	marker.scale = Vector3.ONE * maxf(pop, 0.001)
	var head := badger.position
	marker.position = Vector3(head.x, 1.42 + 0.04 * sin(TAU * (t - MARKER_T) / 1.6), head.z)


func _build_blob() -> void:
	var q := PlaneMesh.new()   # liegt in x/z (QuadMesh blieb trotz orientation senkrecht)
	q.size = Vector2(0.78, 0.62)
	var m := ShaderMaterial.new()
	m.shader = BLOB
	if opts.has("no-blob"):
		m.set_shader_parameter("strength", 0.0)
	blob = MeshInstance3D.new()
	blob.mesh = q
	blob.material_override = m
	blob.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	effects.add_child(blob)


func _update_blob() -> void:
	# liegt 12 mm über dem Kaiboden unter dem Körper (Mitte zwischen den Füßen), dreht mit der Figur
	blob.position = Vector3(badger.position.x, 0.012, badger.position.z)
	blob.rotation.y = badger.rotation.y


# --- Prüfmodi ------------------------------------------------------------------------------------
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
	env.adjustment_enabled = false
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color.WHITE
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			mi.set_surface_override_material(i, white)


func _setup_measure() -> void:
	_skel = badger.find_child("Skeleton3D", true, false) as Skeleton3D
	# Punkte in Ruhepose (Godot-Koordinaten der Figur, badger_notes.md): Ferse und Zehe 3 mm über dem
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


## Mitte von Ferse und Zehe eines Fußes ("L"/"R") in Weltkoordinaten, nach der aktuellen Pose
func _foot_point(side: String) -> Vector3:
	_skel.force_update_all_bone_transforms()
	return (_probe_world("heel." + side) + _probe_world("toe." + side)) * 0.5


## Fuß, der tiefer steht (Standfuß beim Anhalten)
func _lower_foot() -> String:
	return "L" if _foot_point("L").y <= _foot_point("R").y else "R"


## Bodenpunkt des Standfußes (Pose des letzten Bildes): Mittel seiner Punkte unter 1 cm; null, wenn
## beide oder keiner am Boden stehen.
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
	var line := "M %.4f rot %.2f %.4f %.4f" % [t, rad_to_deg(badger.rotation.y), badger.position.x, badger.position.z]
	for k in ["heel.L", "toe.L", "heel.R", "toe.R", "head"]:
		var w := _probe_world(k)
		var sp := camera.unproject_position(w)
		line += " %s %.4f %.4f %.4f %.2f %.2f" % [k, w.x, w.y, w.z, sp.x, sp.y]
	print(line)
