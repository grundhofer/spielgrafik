extends Node
## Gemaltes 3D: Hafen von Lornholm mit dem Dachs-Kurier, als Echtzeit-3D gerendert und per
## Nachbearbeitung gemalt (post.gd: Strukturtensor, anisotroper Kuwahara-Filter, Pinselstriche per
## LIC, Randabdunklung, Papier).
##
## Die 3D-Szene (Modelle aus shared/3d) liegt im SubViewport "Color". Die Kamera "CtrlCam" im
## SubViewport "Ctrl" folgt der Bildkamera und rendert dieselbe Welt als Steuerkarte (Pinselgröße,
## Strichrauschen, Kantenstärke je Material; siehe shaders/paint_common.gdshaderinc).
## Animiert über die aufsummierte Zeit t mit festen Seeds: Dachs (läuft, biegt zur Kamera ab, bleibt
## stehen, winkt), langsame Kamerafahrt, Boote, Wasser, Laterne, Leuchtfeuer, Rauch, Wolkenzug.
##
## Schalter nach "--": --raw (ungemaltes 3D-Bild), --show-ctrl (Steuerkarte), --no-kuwahara, --no-lic,
## --no-edges, --no-paper, --screen-noise (Strichrauschen fest im Bild statt an den Oberflächen),
## --no-ui, --static-cam (Endeinstellung), --cam-start, --mask (Dachs weiß vor Schwarz, ohne Malen),
## --measure (Fuß- und Kopfpunkte je Bild ausgeben), --t0=<s> (Startzeit vorspulen), --no-shadow,
## --preset=aquarell (zweite Voreinstellung der Malart), --set=Durchgang.parameter=wert,… (post.gd),
## --bench (mittlere Bildzeit ohne VSync; braucht ein sichtbares Fenster).

# --- Dachs (Werte aus shared/3d/badger_notes.md) -----------------------------------------------
const WALK_SPEED := 0.367            # m/s bei speed_scale 1
const WALK_RATE := 2.0
const FLOOR_Y := 0.012               # eigener flacher Kaiboden über dem modellierten Pflaster (bis 8 mm)
const START := Vector3(-4.75, FLOOR_Y, 1.6)
const TURN_T0 := 2.2
const TURN_T1 := 3.2
const TURN_DEG := -62.0              # Dreiviertelansicht zur Endeinstellung (Winkarm sichtbar)
const MAX_TURN_STEP := deg_to_rad(3.0)
const BRAKE_T := 2.96
const BRAKE_TIME := 0.4
const IDLE_T := 3.31
const IDLE_BLEND := 0.3
const WAVE_T := 3.9
const WAVE_LEN := 1.5

# --- Kamera: langsame Fahrt von der Halbtotalen zur Nahaufnahme (scripts/plan_shot.py) ----------
const CAM_A_POS := Vector3(-2.5, 2.4, 12.5)
const CAM_A_LOOK := Vector3(-0.5, 2.4, -10.0)
const CAM_A_FOV := 46.0
const CAM_B_POS := Vector3(-1.0, 1.2, 8.5)
const CAM_B_LOOK := Vector3(0.0, 2.5, -8.0)
const CAM_B_FOV := 40.0
const CAM_T0 := 0.3
const CAM_T1 := 4.3

# --- Umgebung -----------------------------------------------------------------------------------
const BEAM_PERIOD := 8.0
const BEAM_FACING_T := 2.5           # dann zeigt der Strahl zur Kamera (Lampe blitzt)
const FLASH_EXP := 40.0
const SMOKE_PUFFS := 14
const SMOKE_LIFE := 5.0
const SEED := 20261013
const SUN_TRAVEL := Vector3(0.90, -0.33, -0.28)   # Abendsonne tief von links (Seitenlicht, etwas von vorn)
const KEY_TRAVEL := Vector3(-0.35, -0.45, -0.82)  # Figurenlicht von rechts vorn (aus Richtung der Laterne)

const WORLD := preload("res://shaders/world.gdshader")

## Material -> [Farbe (sRGB), Schwankung, Fleckgröße m, Pinselgröße, Kantenstärke, weitere Parameter]
## Farben als Malerpalette: warme Erdtöne, kühles Grauviolett im Stein, kräftiges Rot und Weiß am Turm.
const PALETTE := {
	"Stone": [Color("a69886"), 0.16, 0.9, 0.55, 0.6, {}],
	"StoneDark": [Color("6e6470"), 0.16, 0.7, 0.5, 0.6, {}],
	"Wood": [Color("a26a3c"), 0.16, 0.6, 0.45, 0.6, {}],
	"WoodDark": [Color("5c3b29"), 0.14, 0.6, 0.45, 0.6, {}],
	"WhitePaint": [Color("ece4d4"), 0.06, 1.0, 0.4, 0.5, {}],
	"RedPaint": [Color("bf3427"), 0.10, 0.8, 0.4, 0.6, {}],
	"Roof": [Color("4d5874"), 0.16, 0.9, 0.5, 0.6, {}],
	"Rope": [Color("c9ad7a"), 0.10, 0.4, 0.35, 0.5, {}],
	"Metal": [Color("3e3a48"), 0.10, 0.5, 0.35, 0.5, {}],
	"Rock": [Color("7f7277"), 0.20, 2.5, 0.75, 0.6, {}],
	"Sand": [Color("cbb187"), 0.14, 2.0, 0.7, 0.5, {}],
	"Grass": [Color("6f8a4a"), 0.20, 2.5, 0.75, 0.5, {}],
	"Glass": [Color("3a2a18"), 0.0, 1.0, 0.3, 0.2, {"emission_energy": 3.0, "emission_color": Color("ffc870")}],
}
## Abweichungen je Objekt: Objektname -> {Material -> [Farbe oder null, Zusatzparameter]}
## Kai: Pflaster flach beleuchtet und als lockere Steine angedeutet, Fugenfläche fast in Steinfarbe
const OBJECT_OVERRIDES := {
	"Quay": {
		"Stone": [null, {"paving": 1.0, "dab_amount": 0.12, "wrap": 0.45}],
		"StoneDark": [Color("8f8276"), {"paving": 1.0, "dab_amount": 0.12, "wrap": 0.45}],
	},
}
## Figur: feinere Pinsel (Steuerwert klein), damit Gesicht und Kostüm lesbar bleiben
const BADGER_PALETTE := {
	"FurDark": [Color("3a3036"), 0.10, 0.12, 0.06, 0.7, {}],
	"FurLight": [Color("f2e6d0"), 0.06, 0.12, 0.06, 0.7, {}],
	"Cap": [Color("3d6a3a"), 0.10, 0.12, 0.06, 0.7, {}],
	"Brass": [Color("e8b04c"), 0.05, 0.12, 0.04, 0.5, {}],
	"Vest": [Color("4f7d3a"), 0.10, 0.12, 0.06, 0.7, {}],
	"Shirt": [Color("f2e2c4"), 0.06, 0.12, 0.06, 0.7, {}],
	"Scarf": [Color("d4322b"), 0.10, 0.12, 0.06, 0.7, {}],
	"Satchel": [Color("8a4e2c"), 0.10, 0.12, 0.06, 0.7, {}],
	"Parcel": [Color("cf9a5c"), 0.08, 0.12, 0.06, 0.7, {}],
	"Nose": [Color("1c1416"), 0.0, 0.12, 0.0, 0.5, {}],
	"Eye": [Color("1a1010"), 0.0, 0.12, 0.0, 0.5, {}],
}

@export var water_material: ShaderMaterial

var opts := {}
var t := 0.0
var walk_rate := WALK_RATE
var phase := 0
var boats := {}
var smoke: Array[MeshInstance3D] = []
var smoke_jitter: Array[Vector3] = []
var smoke_origin := Vector3.ZERO
var lantern_mat: ShaderMaterial
var lamp_mat: ShaderMaterial
var window_mat: ShaderMaterial
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0
var _skel: Skeleton3D
var _hold_side := ""
var _hold_until := 0.0
var _probe := {}

@onready var world: Node3D = $Color/World
@onready var harbor: Node3D = $Color/World/Harbor
@onready var badger: Node3D = $Color/World/Badger
@onready var player: AnimationPlayer = $Color/World/Badger/AnimationPlayer
@onready var camera: Camera3D = $Color/World/Camera
@onready var ctrl_cam: Camera3D = $Ctrl/CtrlCam
@onready var rotor: Node3D = $Color/World/Attach/LighthouseLight/Rotor
@onready var lantern_omni: OmniLight3D = $Color/World/Attach/LanternLight/Omni
@onready var lamp_omni: OmniLight3D = $Color/World/Attach/LighthouseLight/Omni
@onready var effects: Node3D = $Color/World/Effects


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		opts[kv[0]] = kv[1] if kv.size() > 1 else true
	var sun := $Color/World/Sun as DirectionalLight3D
	sun.global_transform = Transform3D.IDENTITY.looking_at(SUN_TRAVEL, Vector3.UP)
	if opts.has("no-shadow"):
		sun.shadow_enabled = false
	($Color/World/CharKey as DirectionalLight3D).global_transform = Transform3D.IDENTITY.looking_at(KEY_TRAVEL, Vector3.UP)

	_apply_palette(harbor, PALETTE, 1)
	_build_floor()
	_apply_palette(badger, BADGER_PALETTE, 2)    # Ebene 2: Sonne und Figurenlicht
	_attach_to_empties()

	var n := replace_material(harbor, "Water", water_material)
	assert(n == 1, "Material Water nicht gefunden")
	var sea := harbor.get_node("Sea") as MeshInstance3D
	sea.extra_cull_margin = 1.0

	lantern_mat = _own_material(harbor.find_child("LanternGlass", true, false))
	lamp_mat = _own_material(harbor.find_child("LighthouseLamp", true, false))
	window_mat = _own_material(harbor.find_child("CottageWindow", true, false))
	for glass in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
		(harbor.find_child(glass, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	window_mat.set_shader_parameter("emission_energy", 1.4)
	window_mat.set_shader_parameter("emission_color", Color("ffa548"))

	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform

	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	player.play("Walk")
	player.speed_scale = WALK_RATE
	badger.position = START

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0

	_build_smoke()
	_setup_measure()
	if opts.has("mask"):
		_mask_mode()
	if opts.has("no-ui") or opts.has("mask"):
		$UI.visible = false
	if opts.has("measure"):
		RenderingServer.frame_pre_draw.connect(_measure)

	# Leuchtfeuer: Winkel so legen, dass der Strahl bei BEAM_FACING_T zur Kamera zeigt (Endeinstellung)
	var to_cam := CAM_B_POS - rotor.global_position
	beam_yaw0 = atan2(-to_cam.x, -to_cam.z) - TAU * BEAM_FACING_T / BEAM_PERIOD

	var t0: float = float(opts.get("t0", "0"))
	if t0 > 0.0:
		var step := 1.0 / 30.0
		while t < t0 - 1e-6:
			t += step
			_update(step)
	else:
		_update(0.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)
	if opts.has("bench"):
		_bench()


func _update(delta: float) -> void:
	RenderingServer.global_shader_parameter_set("paint_time", t)
	_update_badger(delta)
	_update_camera()

	# Boote schaukeln um ihren Ursprung (Wasserlinie); Bug zeigt lokal nach +X
	var k := 0
	for b in boats:
		var ph := 1.7 * k
		var roll := deg_to_rad(2.4) * sin(TAU * t / 3.4 + ph)
		var pitch := deg_to_rad(1.0) * sin(TAU * t / 4.6 + 0.8 + ph)
		var heave := 0.04 * sin(TAU * t / 3.9 + 2.1 + ph)
		var local := Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		(harbor.get_node(b) as Node3D).transform = boats[b] * local
		k += 1

	# Laterne flackert (Rauschen mit festem Seed); Glas, Licht und Glitzern im Wasser gemeinsam
	var f := 0.78 + 0.22 * lantern_noise.get_noise_1d(t * 6.0) + 0.08 * lantern_noise.get_noise_1d(t * 23.0 + 50.0)
	lantern_omni.light_energy = 3.0 * f
	lantern_mat.set_shader_parameter("emission_energy", 3.2 * f)
	water_material.set_shader_parameter("light_a", Vector4(4.1, 1.79, -0.12, 1.1 * f))

	# Leuchtfeuer dreht sich; Lampe blitzt auf, wenn der Strahl zur Kamera zeigt
	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position).normalized()
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), FLASH_EXP)
	lamp_mat.set_shader_parameter("emission_energy", 3.0 + 9.0 * facing)
	lamp_omni.light_energy = 2.0 + 4.0 * facing
	water_material.set_shader_parameter("light_b", Vector4(10.2, 12.58, -25.6, 0.6 + 0.8 * facing))

	_update_smoke()


# --- Leistung: mittlere Bildzeit ohne VSync (die CPU wartet auf die GPU, sobald diese der Engpass ist) --
var _bench_frames := 0
var _bench_t0 := 0


func _bench() -> void:
	_bench_frames += 1
	if _bench_frames == 1:
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
		Engine.max_fps = 0
	elif _bench_frames == 60:
		_bench_t0 = Time.get_ticks_usec()
	elif _bench_frames == 360:
		var ms := float(Time.get_ticks_usec() - _bench_t0) / 300.0 / 1000.0
		print("BENCH %.2f ms je Bild (%.0f Bilder/s)" % [ms, 1000.0 / ms])
		get_tree().quit()


# --- Dachs ---------------------------------------------------------------------------------------
func _update_badger(delta: float) -> void:
	# AnimationPlayer von Hand (advance): erst Pose, dann Vorschub entlang der Blickrichtung, dann Drehung
	# um den Bodenpunkt des Standfußes (nur bei genau einem Fuß am Boden), so bleibt der Standfuß stehen.
	# Vorgehen aus styles/toon-cel und styles/handpainted-3d übernommen.
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
			# Walk in der Pose einfrieren, sonst läuft der Schwungfuß während der Überblendung weiter
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
	k = k * k * (3.0 - 2.0 * k)     # doppelt geglättet: weicher Anfang und Auslauf
	var a := Transform3D.IDENTITY.translated(CAM_A_POS).looking_at(CAM_A_LOOK, Vector3.UP)
	var b := Transform3D.IDENTITY.translated(CAM_B_POS).looking_at(CAM_B_LOOK, Vector3.UP)
	var q := a.basis.get_rotation_quaternion().slerp(b.basis.get_rotation_quaternion(), k)
	camera.global_transform = Transform3D(Basis(q), CAM_A_POS.lerp(CAM_B_POS, k))
	camera.fov = lerpf(CAM_A_FOV, CAM_B_FOV, k)
	# Steuerkamera folgt der Bildkamera exakt; das Endbild braucht die Blickrichtung für die Sterne
	ctrl_cam.global_transform = camera.global_transform
	ctrl_cam.fov = camera.fov
	var pm := ($Post as Node).get("mats").get("Paint") as ShaderMaterial
	if pm:
		pm.set_shader_parameter("cam_basis", camera.global_basis)
		pm.set_shader_parameter("tan_half_fov", tan(deg_to_rad(camera.fov) * 0.5))


# --- Materialien ---------------------------------------------------------------------------------
func _paint_material(entry: Array, src: StandardMaterial3D) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = WORLD
	var c: Color = entry[0]
	m.set_shader_parameter("albedo", c)
	m.set_shader_parameter("variation", entry[1])
	m.set_shader_parameter("var_scale", entry[2])
	m.set_shader_parameter("ctrl_size", entry[3])
	m.set_shader_parameter("ctrl_edge", entry[4])
	if src.emission_enabled:
		m.set_shader_parameter("emission_color", c)
	for key in entry[5]:
		m.set_shader_parameter(key, entry[5][key])
	return m


func _apply_palette(root: Node, palette: Dictionary, layers: int) -> void:
	var cache := {}
	var extra: Dictionary = {}
	if root == badger:
		extra = {"wrap": 0.45, "terminator": 0.25, "rim": 0.55, "stroke_cell_px": 2.0}
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		mi.layers = layers
		for i in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(i) as StandardMaterial3D
			if src == null:
				push_error("%s: Fläche %d ohne glTF-Material" % [mi.name, i])
				continue
			var mat_name := src.resource_name
			if mat_name == "Water":
				continue
			if not palette.has(mat_name):
				push_error("Material %s fehlt in der Palette" % mat_name)
				continue
			var ov: Array = OBJECT_OVERRIDES.get(String(mi.name), {}).get(mat_name, [])
			var key := mat_name if ov.is_empty() else String(mi.name) + "/" + mat_name
			if not cache.has(key):
				var entry: Array = (palette[mat_name] as Array).duplicate()
				if not ov.is_empty() and ov[0] != null:
					entry[0] = ov[0]
				var m := _paint_material(entry, src)
				for e in extra:
					m.set_shader_parameter(e, extra[e])
				if not ov.is_empty():
					for e in ov[1]:
						m.set_shader_parameter(e, ov[1][e])
				cache[key] = m
			mi.set_surface_override_material(i, cache[key])


## Flacher Kaiboden auf 12 mm über den beiden Pflasterflächen aus build_harbor.py (Kantensteine bleiben
## frei): Das modellierte Fugenraster zeichnete im gemalten Bild ein regelmäßiges Gitter aus Linien
## (Fasen im Seitenlicht, Schatten in den Fugen); der Boden malt stattdessen locker angedeutete Steine.
func _build_floor() -> void:
	var src := find_material(harbor, "Stone") as StandardMaterial3D
	var entry: Array = (PALETTE["Stone"] as Array).duplicate()
	var m := _paint_material(entry, src)
	for e in OBJECT_OVERRIDES["Quay"]["Stone"][1]:
		m.set_shader_parameter(e, OBJECT_OVERRIDES["Quay"]["Stone"][1][e])
	# (x0, x1, z0, z1): vorderer Kai bis zu den Kantensteinen, hinterer Teil links neben dem Häuschen
	for r in [Vector4(-13.0, 7.38, -0.38, 8.0), Vector4(-13.0, -5.62, -3.6, -0.38)]:
		var pm := PlaneMesh.new()
		pm.size = Vector2(r.y - r.x, r.w - r.z)
		pm.subdivide_width = 8
		pm.subdivide_depth = 4
		var mi := MeshInstance3D.new()
		mi.name = "PavingFloor"
		mi.mesh = pm
		mi.material_override = m
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.position = Vector3((r.x + r.y) * 0.5, FLOOR_Y, (r.z + r.w) * 0.5)
		harbor.add_child(mi)


static func find_material(root: Node, mat_name: String) -> Material:
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var mm := mi.mesh.surface_get_material(i)
			if mm and mm.resource_name == mat_name:
				return mm
	return null


func _own_material(mi: MeshInstance3D) -> ShaderMaterial:
	var m := (mi.get_surface_override_material(0) as ShaderMaterial).duplicate() as ShaderMaterial
	mi.set_surface_override_material(0, m)
	return m


func _attach_to_empties() -> void:
	for holder in $Color/World/Attach.get_children():
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


# --- Rauch: Ballen, die aufsteigen, wachsen, nach rechts treiben und vergehen (shaders/smoke.gdshader) --
func _build_smoke() -> void:
	var mat := ShaderMaterial.new()
	mat.shader = preload("res://shaders/smoke.gdshader")
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	var anchor := harbor.find_child("ChimneySmoke", true, false) as Node3D
	for i in SMOKE_PUFFS:
		var p := MeshInstance3D.new()
		p.mesh = quad
		p.material_override = mat
		p.layers = 4                  # Ebene 3: nur Bildkamera
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		p.extra_cull_margin = 2.0
		p.set_instance_shader_parameter("seed", rng.randf_range(0.0, 10.0))
		effects.add_child(p)
		smoke.append(p)
		smoke_jitter.append(Vector3(rng.randf_range(-0.12, 0.12), rng.randf_range(0.9, 1.15), rng.randf_range(0.0, 0.06)))
	smoke_origin = anchor.global_position


func _update_smoke() -> void:
	for i in smoke.size():
		var j := smoke_jitter[i]
		var age := fposmod(t / SMOKE_LIFE + float(i) / SMOKE_PUFFS + j.z, 1.0)
		var p := smoke[i]
		var rise := 1.0 - pow(1.0 - age, 1.4)
		p.position = smoke_origin + Vector3(1.9 * age * age + j.x * age, -0.15 + 3.2 * rise * j.y, -0.2 * age)
		var s := lerpf(0.35, 2.0, sqrt(age)) * j.y
		p.scale = Vector3(s, s, s)
		p.set_instance_shader_parameter("opacity", 0.62 * smoothstep(0.0, 0.04, age) * (1.0 - smoothstep(0.35, 1.0, age)))
		# ältere Ballen hinter jüngeren (näher am Schornstein) zeichnen
		p.sorting_offset = -age


# --- Messen (scripts/measure_badger.py) ----------------------------------------------------------
func _mask_mode() -> void:
	harbor.visible = false
	effects.visible = false
	var env := ($Color/World/WorldEnvironment as WorldEnvironment).environment
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


func _foot_point(side: String) -> Vector3:
	_skel.force_update_all_bone_transforms()
	return (_probe_world("heel." + side) + _probe_world("toe." + side)) * 0.5


func _lower_foot() -> String:
	return "L" if _foot_point("L").y <= _foot_point("R").y else "R"


func _stance_point() -> Variant:
	var down := {}
	for side in ["L", "R"]:
		var pts: Array[Vector3] = []
		for k in ["heel.", "toe."]:
			var w := _probe_world(k + side)
			if w.y - FLOOR_Y < 0.01:
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
