extends Node3D
## Stilneutrale Probeszene der gemeinsamen 3D-Grundlage (shared/3d/README.md).
##
## Lädt harbor.glb und badger.glb (Instanzen in main.tscn), hängt Lichter an die Empties,
## ersetzt das Wasser-Material per Name und animiert: Dachs (Walk -> bremsen -> zur Kamera
## drehen -> Wave -> Idle), Boote, Wasser, Laterne, Leuchtfeuer, Schornsteinrauch.
## Alles hängt an der aufsummierten Zeit t und an festen Seeds: tools/capture.py nimmt mit
## --fixed-fps auf, jede Aufnahme ist Bild für Bild gleich.

# --- Dachs (Werte aus badger_notes.md) -------------------------------------------------------
const WALK_SPEED := 0.367        # m/s bei speed_scale 1, dann rutschen die Füße nicht
const WALK_RATE := 2.0           # Abspieltempo von Walk; Geschwindigkeit = WALK_SPEED * WALK_RATE
const BRAKE_T := 3.1             # ab hier bremst er (Tempo und Animation gemeinsam auf 0)
const BRAKE_TIME := 0.4
const IDLE_T := 3.45             # Überblenden auf Idle
const TURN_T := 3.6              # dreht sich zur Kamera (rotation.y 0 -> -90°)
const TURN_TIME := 0.45
const WAVE_T := 4.05             # Wave dauert 1,5 s, beginnt und endet in der Ruhepose
const WAVE_LEN := 1.5

# --- Umgebung --------------------------------------------------------------------------------
const BEAM_PERIOD := 8.0         # s für eine Umdrehung des Leuchtfeuers
const BEAM_FACING_T := 2.4       # Zeitpunkt, zu dem der Strahl zur Kamera zeigt
const SMOKE_PUFFS := 9
const SMOKE_LIFE := 4.5
const SEED := 20261010

@export var water_material: ShaderMaterial

var t := 0.0
var walk_rate := WALK_RATE
var phase := 0                   # 0 Walk, 1 Idle, 2 Wave, 3 Idle
var boats := {}                  # Name -> Ausgangstransformation
var smoke: Array[MeshInstance3D] = []
var smoke_jitter: Array[Vector3] = []
var lantern_mat: StandardMaterial3D
var lamp_mat: StandardMaterial3D
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0

@onready var harbor: Node3D = $Harbor
@onready var badger: Node3D = $Badger
@onready var player: AnimationPlayer = $Badger/AnimationPlayer
@onready var camera: Camera3D = $Camera
@onready var rotor: Node3D = $Attach/LighthouseLight/Rotor
@onready var lantern_omni: OmniLight3D = $Attach/LanternLight/Omni
@onready var lamp_omni: OmniLight3D = $Attach/LighthouseLight/Omni


func _ready() -> void:
	_attach_to_empties()

	# Wasser: Material "Water" per Name ersetzen, Farbe und Rauheit aus dem glTF übernehmen.
	var water := find_material(harbor, "Water") as StandardMaterial3D
	water_material.set_shader_parameter("albedo", water.albedo_color)
	water_material.set_shader_parameter("roughness", water.roughness)
	var n := replace_material(harbor, "Water", water_material)
	assert(n == 1, "Material Water nicht gefunden")
	var sea := harbor.get_node("Sea") as MeshInstance3D
	sea.extra_cull_margin = 1.0  # Mesh ist flach (AABB-Höhe 0); der Shader hebt es an

	# Leuchtende Teile teilen sich das Material "Glass". Für eigenes Flackern je Objekt eine Kopie.
	lantern_mat = unique_material(harbor.find_child("LanternGlass", true, false))
	lamp_mat = unique_material(harbor.find_child("LighthouseLamp", true, false))
	for glass in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
		# Das Licht sitzt im Glaskörper; wirft das Glas Schatten, sperrt es eigene Lichter mit Schatten ein.
		(harbor.find_child(glass, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform

	# glTF kennt kein Loop-Flag: Godot importiert alle Animationen mit LOOP_NONE.
	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.play("Walk")
	player.speed_scale = WALK_RATE

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0

	# Leuchtfeuer: Drehwinkel so legen, dass der Strahl bei BEAM_FACING_T zur Kamera zeigt.
	var to_cam := camera.global_position - rotor.global_position
	beam_yaw0 = atan2(-to_cam.x, -to_cam.z) - TAU * BEAM_FACING_T / BEAM_PERIOD

	_build_smoke()
	_update(0.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)


func _update(delta: float) -> void:
	_update_badger(delta)

	# Boote schaukeln um ihren Ursprung (Wasserlinie); Bug zeigt lokal nach +X.
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

	# Laterne flackert (Rauschen mit festem Seed); Glas und Licht gemeinsam.
	var f := 0.82 + 0.18 * lantern_noise.get_noise_1d(t * 7.0) + 0.06 * lantern_noise.get_noise_1d(t * 31.0 + 50.0)
	lantern_omni.light_energy = 1.6 * f
	lantern_mat.emission_energy_multiplier = 4.0 * f

	# Leuchtfeuer dreht sich; Lampe blitzt auf, wenn der Strahl zur Kamera zeigt.
	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position).normalized()
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), 24.0)
	lamp_mat.emission_energy_multiplier = 4.0 + 26.0 * facing
	lamp_omni.light_energy = 2.0 + 4.0 * facing

	_update_smoke()


func _update_badger(delta: float) -> void:
	# Bremsen: Tempo und Animationstempo sinken gemeinsam, dann rutschen die Füße auch dabei nicht.
	if phase == 0:
		walk_rate = WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, t))
		player.speed_scale = walk_rate
		badger.position.x += WALK_SPEED * walk_rate * delta
		if t >= IDLE_T:
			phase = 1
			player.speed_scale = 1.0
			player.play("Idle", 0.3)
	elif phase == 1 and t >= WAVE_T:
		phase = 2
		player.play("Wave", 0.25)
	elif phase == 2 and t >= WAVE_T + WAVE_LEN - 0.1:
		phase = 3
		player.play("Idle", 0.3)
	# Zur Kamera drehen (Blick nach +Z), damit der Winkarm nicht hinter dem Kopf verschwindet.
	badger.rotation.y = -PI / 2.0 * smoothstep(TURN_T, TURN_T + TURN_TIME, t)


# --- Lichter und Hilfsknoten an die Empties hängen ----------------------------------------------
func _attach_to_empties() -> void:
	for holder in $Attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt in harbor.glb" % holder.name)
			continue
		for c in holder.get_children():
			c.reparent(target, false)


# --- Materialien nach Namen ------------------------------------------------------------------
## Erstes Material mit diesem resource_name unter root (oder null).
static func find_material(root: Node, mat_name: String) -> Material:
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i)
			if m and m.resource_name == mat_name:
				return m
	return null


## Setzt mat als Override auf alle Flächen, deren glTF-Material mat_name heißt. Gibt die Anzahl zurück.
static func replace_material(root: Node, mat_name: String, mat: Material) -> int:
	var count := 0
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i)
			if m and m.resource_name == mat_name:
				mi.set_surface_override_material(i, mat)
				count += 1
	return count


## Eigene Kopie des Materials der ersten Fläche (für Animation nur dieses Objekts).
static func unique_material(mi: MeshInstance3D) -> StandardMaterial3D:
	var m := (mi.mesh.surface_get_material(0) as StandardMaterial3D).duplicate() as StandardMaterial3D
	mi.set_surface_override_material(0, m)
	return m


# --- Rauch: Billboards mit festem Ablauf ------------------------------------------------------
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
		var age := fposmod(t + float(i) * SMOKE_LIFE / SMOKE_PUFFS, SMOKE_LIFE) / SMOKE_LIFE  # 0..1
		var j := smoke_jitter[i]
		var p := smoke[i]
		# steigt auf und treibt mit dem Wind nach rechts (+X)
		p.position = Vector3(1.4 * age * age + j.x * age, 2.2 * age * j.y, j.z * age)
		var s := lerpf(0.35, 1.5, sqrt(age))
		p.scale = Vector3(s, s, s)
		p.transparency = 1.0 - 0.55 * smoothstep(0.0, 0.12, age) * (1.0 - smoothstep(0.45, 1.0, age))
