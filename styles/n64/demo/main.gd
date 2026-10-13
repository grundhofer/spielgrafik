extends Node
## N64-Look (Katalogeintrag n64): Hafen von Lornholm mit dem Dachs-Kurier.
##
## 3D und Oberfläche entstehen im SubViewport "Game" (320×240, MSAA 4×); "Screen/TV" gibt das Bild über
## shaders/n64_vi.gdshader aus (16-Bit-Bildspeicher mit Dithering, Dither-Filter, weich ×3).
## Alle glTF-Materialien werden nach Namen durch eigene Shader ersetzt: Textur 32×32 mit 3-Punkt-Filter mal
## Licht je Eckpunkt (gebackene Vertexfarben + Laterne), Nebel je Eckpunkt. Der Dachs hat Materialfarben ohne
## Textur und Licht je Eckpunkt aus Richtungslichtern.
## Alles hängt an der aufsummierten Zeit t und an festen Seeds: tools/capture.py nimmt mit --fixed-fps auf.
##
## Vergleichs- und Messschalter (nach "--"): --no-3pt (bilinear mit 4 Texeln), --no-mip, --no-fog, --no-vc
## (Vertexlicht ohne gebackene Werte), --no-dither (24 Bit), --no-vifilter, --sharp (ohne weiches Vergrößern),
## --no-msaa, --nearest-tex (Texel ohne Filter), --no-ui, --figure-only (nur Dachs vor grauem Grund, für Fußmessung), --cam=fix (feste Messkamera),
## --feetmid=<m> (Drehpunkt), --stats (Dreiecke und Draw Calls je Bild ausgeben)

# --- Dachs (Werte aus shared/3d/badger_notes.md) ----------------------------------------------------------
const WALK_SPEED := 0.367        # m/s bei speed_scale 1, dann rutschen die Füße nicht
const WALK_RATE := 2.0           # Abspieltempo von Walk; Geschwindigkeit = WALK_SPEED * WALK_RATE
const START_X := -6.0
const BRAKE_T := 3.1             # ab hier bremst er (Tempo und Animation gemeinsam auf 0)
const BRAKE_TIME := 0.4
const IDLE_T := 3.45
const TURN_T := 3.55
const TURN_TIME := 0.45
const TURN_DEG := -98.0         # zur Kamera (−102° wäre genau frontal), Schnauze leicht nach links
const FEET_MID := 0.07           # m vor dem Ursprung: Mitte der Pfoten (Ferse 0, Zehen 0,12; mit --feetmid nachgemessen:
                                 # Mitte des Fußabdrucks vor und nach dem Drehen 276,5 / 277,2 px, mit 0,13 waren es 276,5 / 282,0)
const WAVE_T := 4.05
const WAVE_LEN := 1.5

# --- Umgebung ----------------------------------------------------------------------------------------------
const BEAM_PERIOD := 8.0
const BEAM_FACING_T := 2.4
const SMOKE_PUFFS := 7
const SMOKE_LIFE := 4.2
const SEED := 20261011

# Kamera: Fahrt von der Übersicht zur Halbnahen beim Dachs, wie die Verfolgerkameras der Zeit
# (Bézierkurve über einen Kontrollpunkt rechts, Winkel und Bildwinkel weich überblendet). Werte für das Ende
# aus scripts/frame_shot.py: Dachs links (gemessen: Füße bei y≈222, Kopf bei y≈124 in 320×240), Leuchtfeuer bei
# (127 | 42), Laterne bei (283 | 98), Dialogfenster rechts unten.
const CAM_T0 := 0.3
const CAM_T1 := 4.0
const CAM_P0 := Vector3(-1.4, 4.6, 15.5)
const CAM_P1 := Vector3(-1.6, 2.6, 8.0)         # Kontrollpunkt
const CAM_P2 := Vector3(-4.08, 1.1, 3.6)
const BADGER_END_X := -3.58                     # Dachs steht ab 3,45 s hier (gemessen)
const CAM_YAW := Vector2(-2.0, -37.5)            # Grad: Start, Ende
const CAM_PITCH := Vector2(-9.0, -1.0)
const CAM_FOV := Vector2(48.0, 60.0)

# Dialogfenster (320×240)
const BOX_BOTTOM := Rect2(16, 160, 288, 74)
const BOX_RIGHT := Rect2(104, 148, 212, 86)

# Farben (sRGB) und Stärken; main.gd übergibt sie linear an die globalen Shader-Uniforms.
const FOG_COLOR := Color("e8a27a")
const SKY_LIGHT := Color("9ca0c4")
const GROUND_LIGHT := Color("7a5a50")
const SUN_COLOR := Color("ffc080")
const SUN_ENERGY := 2.8
const WINDOW_COLOR := Color("ffb45a")
const LANTERN_COLOR := Color("ffb050")
const LANTERN_ENERGY := 2.6
const FOG_RANGE := Vector2(9.0, 75.0)

## Material -> [Textur, Kacheln je Meter]
const TEX := {
	"Paving": ["paving", 1.0 / 2.4], "Stone": ["stone", 1.0 / 1.6], "StoneDark": ["stonedark", 1.0 / 1.4],
	"Wood": ["wood", 1.0], "WoodDark": ["wooddark", 1.0], "WhitePaint": ["whitepaint", 1.0 / 1.5],
	"RedPaint": ["redpaint", 1.0 / 1.5], "Roof": ["roof", 1.0 / 1.2], "Rope": ["rope", 1.0 / 0.3],
	"Metal": ["metal", 1.0 / 0.8], "Rock": ["rock", 1.0 / 3.0], "Sand": ["sand", 1.0 / 2.0],
	"Grass": ["grass", 1.0 / 2.5], "BarrelSide": ["barrel", 1.0], "CrateSide": ["crate", 1.0],
}

const WORLD := preload("res://shaders/n64_world.gdshader")
const ACTOR := preload("res://shaders/n64_actor.gdshader")
const WATER := preload("res://shaders/n64_water.gdshader")
const SMOKE := preload("res://shaders/n64_smoke.gdshader")

var t := 0.0
var walk_rate := WALK_RATE
var walk_x := START_X           # Lage des Dachses vor dem Drehen (Ursprung)
var phase := 0
var boats := {}
var smoke: Array[MeshInstance3D] = []
var smoke_mats: Array[ShaderMaterial] = []
var smoke_jitter: Array[Vector3] = []
var lantern_noise := FastNoiseLite.new()
var flicker := 1.0
var noise_range := Vector2(-1.0, 1.0)  # Spannweite der Rauschsumme über die 6 s (in _ready gemessen)
var beam_yaw0 := 0.0
var glass_mats := {}             # Objektname -> ShaderMaterial (eigene Kopie je leuchtendem Objekt)
var args := {}
var turn_pivot := Vector3.ZERO

@onready var game: SubViewport = $Game
@onready var harbor: Node3D = $Game/Harbor
@onready var badger: Node3D = $Game/Badger
@onready var player: AnimationPlayer = $Game/Badger/AnimationPlayer
@onready var camera: Camera3D = $Game/Camera
@onready var rotor: Node3D = $Game/Attach/LighthouseLight/Rotor
@onready var lantern_glow: MeshInstance3D = $Game/Attach/LanternLight/Glow
@onready var lamp_glow: MeshInstance3D = $Game/Attach/LighthouseLight/Glow
@onready var shadow: MeshInstance3D = $Game/BlobShadow
@onready var tv: ColorRect = $Screen/TV
@onready var ui: Control = $Game/UI/Overlay


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=")
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	_attach_to_empties()
	_set_globals()
	_style_harbor()
	_style_badger()

	var vi := tv.material as ShaderMaterial
	vi.set_shader_parameter("src", game.get_texture())
	vi.set_shader_parameter("dither_on", 0.0 if args.has("no-dither") else 1.0)
	vi.set_shader_parameter("filter_on", 0.0 if args.has("no-vifilter") else 1.0)
	vi.set_shader_parameter("smooth_on", 0.0 if args.has("sharp") else 1.0)
	if args.has("no-msaa"):
		game.msaa_3d = Viewport.MSAA_DISABLED
	if args.has("no-ui") or args.has("figure-only"):
		$Game/UI.visible = false
	if args.has("no-shadow"):
		shadow.visible = false
	if args.has("figure-only"):
		# nur der Dachs vor grauem Grund (Messung von Füßen und Kopf, scripts/measure_feet.py)
		harbor.visible = false
		shadow.visible = false
		var env := ($Game/WorldEnvironment as WorldEnvironment).environment
		env.background_mode = Environment.BG_COLOR
		env.background_color = Color(0.5, 0.5, 0.5)
	ui.setup(BOX_BOTTOM if args.get("box", "right") == "bottom" else BOX_RIGHT)

	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform
	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.play("Walk")
	player.speed_scale = WALK_RATE
	walk_x = float(args.get("bx", str(START_X)))
	badger.position.x = walk_x

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	# Spannweite der Rauschsumme über die Laufzeit messen und auf 0,4–1,0 abbilden (sonst flackert es kaum sichtbar)
	noise_range = Vector2(INF, -INF)
	for i in 181:
		var nv := _lantern_noise(float(i) / 30.0)
		noise_range = Vector2(minf(noise_range.x, nv), maxf(noise_range.y, nv))
	var to_cam := camera.global_position - rotor.global_position
	beam_yaw0 = atan2(-to_cam.x, -to_cam.z) - TAU * BEAM_FACING_T / BEAM_PERIOD
	_build_smoke()
	_update(0.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)
	if args.has("stats"):
		# Messschalter: gezeichnete Dreiecke und Draw Calls des 320×240-Bildes (gilt für das vorige Bild)
		var f := int(round(t * 30.0))
		if f % 15 == 0:
			var tris := game.get_render_info(Viewport.RENDER_INFO_TYPE_VISIBLE, Viewport.RENDER_INFO_PRIMITIVES_IN_FRAME)
			var calls := game.get_render_info(Viewport.RENDER_INFO_TYPE_VISIBLE, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME)
			print("STATS Bild %d: %d Dreiecke, %d Draw Calls" % [f, tris, calls])


func _update(delta: float) -> void:
	RenderingServer.global_shader_parameter_set("n64_time", t)
	ui.set_time(t)
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

	# Laterne flackert (Rauschen mit festem Seed): Glas, Lichthof und Licht je Eckpunkt gemeinsam
	var n := inverse_lerp(noise_range.x, noise_range.y, _lantern_noise(t))
	flicker = lerpf(0.4, 1.0, clampf(n, 0.0, 1.0))
	RenderingServer.global_shader_parameter_set("n64_lantern_energy", LANTERN_ENERGY * flicker)
	(glass_mats["LanternGlass"] as ShaderMaterial).set_shader_parameter("emission", _lin(Color("ffc870")) * (0.3 + 0.8 * flicker))
	(lantern_glow.get_surface_override_material(0) as ShaderMaterial).set_shader_parameter("strength", 0.2 + 2.6 * flicker)
	lantern_glow.scale = Vector3.ONE * (0.8 + 1.1 * flicker)

	# Leuchtfeuer dreht sich; Lampe und Lichthof blitzen auf, wenn der Strahl zur Kamera zeigt
	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position)
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), 16.0)
	(glass_mats["LighthouseLamp"] as ShaderMaterial).set_shader_parameter("emission", _lin(Color("ffe0a0")) * (1.0 + 1.5 * facing))
	(lamp_glow.get_surface_override_material(0) as ShaderMaterial).set_shader_parameter("strength", 0.55 + 1.2 * facing)
	lamp_glow.scale = Vector3.ONE * (4.0 + 5.0 * facing)

	_update_smoke()


func _lantern_noise(time: float) -> float:
	return lantern_noise.get_noise_1d(time * 6.0) * 0.75 + lantern_noise.get_noise_1d(time * 23.0 + 40.0) * 0.25


# --- Dachs ---------------------------------------------------------------------------------------------------
func _update_badger(delta: float) -> void:
	if phase == 0:
		walk_rate = WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, t))
		player.speed_scale = walk_rate
		walk_x += WALK_SPEED * walk_rate * delta
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
	# Drehen auf der Stelle um die Mitte der Pfoten (FEET_MID vor dem Ursprung), nicht um den Ursprung
	var th := deg_to_rad(float(args.get("turn", str(TURN_DEG)))) * smoothstep(TURN_T, TURN_T + TURN_TIME, t)
	var fm := float(args.get("feetmid", str(FEET_MID)))
	badger.rotation.y = th
	badger.position = Vector3(walk_x + fm, 0.0, 1.2) - fm * Vector3(cos(th), 0.0, -sin(th))
	shadow.position = Vector3(walk_x + fm, 0.015, 1.2)


# --- Kamera --------------------------------------------------------------------------------------------------
func _update_camera() -> void:
	# Position auf der Bézierkurve; Blickziel gleitet vom Hafen (Übersicht) zum Ziel der Schlusseinstellung
	var u := clampf((t - CAM_T0) / (CAM_T1 - CAM_T0), 0.0, 1.0)
	u = u * u * u * (u * (u * 6.0 - 15.0) + 10.0)          # weich anfahren und auslaufen
	var a := CAM_P0.lerp(CAM_P1, u)
	var b := CAM_P1.lerp(CAM_P2, u)
	camera.position = a.lerp(b, u)
	# Das Ziel der Schlusseinstellung wandert mit dem Dachs mit (wie eine Verfolgerkamera), bis er steht.
	var follow := Vector3(walk_x - BADGER_END_X, 0.0, 0.0)
	var target := _cam_target(CAM_P0, CAM_YAW.x, CAM_PITCH.x, 20.0).lerp(_cam_target(CAM_P2, CAM_YAW.y, CAM_PITCH.y, 10.0) + follow, u)
	camera.look_at(target, Vector3.UP)
	camera.fov = lerpf(CAM_FOV.x, CAM_FOV.y, u)
	if args.get("cam", "") == "fix":
		# feste Messkamera von vorn auf den Laufweg (Seitenansicht der laufenden Figur)
		camera.position = Vector3(-4.75, 0.5, 5.6)
		camera.rotation = Vector3.ZERO
		camera.fov = 32.0
	elif args.has("cam"):
		var v := (args["cam"] as String).split(",")
		camera.position = Vector3(float(v[0]), float(v[1]), float(v[2]))
		camera.rotation = Vector3(deg_to_rad(float(v[4])), deg_to_rad(float(v[3])), 0.0)
		camera.fov = float(v[5])


static func _cam_target(p: Vector3, yaw_deg: float, pitch_deg: float, dist: float) -> Vector3:
	var basis := Basis.from_euler(Vector3(deg_to_rad(pitch_deg), deg_to_rad(yaw_deg), 0.0))
	return p - basis.z * dist


# --- Materialien -----------------------------------------------------------------------------------------------
static func _lin(c: Color) -> Vector3:
	var l := c.srgb_to_linear()
	return Vector3(l.r, l.g, l.b)


static func _lin4(c: Color) -> Vector4:
	var l := c.srgb_to_linear()
	return Vector4(l.r, l.g, l.b, 1.0)


func _set_globals() -> void:
	var rs := RenderingServer
	# Abstimmschalter (nur zum Ausprobieren): --fogc=hex --sky=hex --ground=hex --sunc=hex --sun=f --fogr=a,b
	var fog_c := Color(args.get("fogc", FOG_COLOR.to_html(false)))
	var fr := FOG_RANGE
	if args.has("fogr"):
		var v := (args["fogr"] as String).split(",")
		fr = Vector2(float(v[0]), float(v[1]))
	rs.global_shader_parameter_set("n64_fog_color", _lin4(fog_c))
	rs.global_shader_parameter_set("n64_fog_range", fr)
	rs.global_shader_parameter_set("n64_sky_light", _lin4(Color(args.get("sky", SKY_LIGHT.to_html(false)))))
	rs.global_shader_parameter_set("n64_ground_light", _lin4(Color(args.get("ground", GROUND_LIGHT.to_html(false)))))
	rs.global_shader_parameter_set("n64_sun_color", _lin4(Color(args.get("sunc", SUN_COLOR.to_html(false)))))
	rs.global_shader_parameter_set("n64_sun_energy", float(args.get("sun", str(SUN_ENERGY))))
	rs.global_shader_parameter_set("n64_window_color", _lin4(WINDOW_COLOR) * 1.4)
	rs.global_shader_parameter_set("n64_lantern_color", _lin4(LANTERN_COLOR))
	rs.global_shader_parameter_set("n64_lantern_pos", harbor.find_child("LanternLight", true, false).global_position)
	rs.global_shader_parameter_set("n64_three_point", 0.0 if args.has("no-3pt") else 1.0)
	rs.global_shader_parameter_set("n64_mip", 0.0 if args.has("no-mip") else 1.0)
	rs.global_shader_parameter_set("n64_fog_on", 0.0 if args.has("no-fog") else 1.0)
	rs.global_shader_parameter_set("n64_vc_on", 0.0 if args.has("no-vc") else 1.0)
	rs.global_shader_parameter_set("n64_debug", float(args.get("debug-bake", "0")))
	rs.global_shader_parameter_set("n64_tex_nearest", 1.0 if args.has("nearest-tex") else 0.0)


func _style_harbor() -> void:
	var cache := {}
	for mi: MeshInstance3D in harbor.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			if mi.get_surface_override_material(i) != null:
				continue                           # eigene Effekte unter Attach (Lichthof, Kegel)
			var src := mi.mesh.surface_get_material(i) as StandardMaterial3D
			if src == null:
				push_error("%s: Fläche %d ohne glTF-Material" % [mi.name, i])
				continue
			var key := src.resource_name
			if key == "Glass":
				var g := ShaderMaterial.new()      # je Objekt eigene Kopie (Laterne flackert, Lampe blitzt)
				g.shader = WORLD
				g.set_shader_parameter("use_tex", 0.0)
				# Grundfarbe gedämpft, sonst läuft das Glas mit Sonne und Fensterlicht in Weißgelb über (255/255/160);
				# die Farbe kommt aus der Emission (warmes Orangegelb, Laterne und Lampe setzt _update() je Bild)
				g.set_shader_parameter("tint", src.albedo_color * Color(0.2, 0.2, 0.2, 1.0))
				g.set_shader_parameter("emission", _lin(Color("ffc060")) * 0.9)
				glass_mats[mi.name] = g
				mi.set_surface_override_material(i, g)
				mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
				continue
			if not cache.has(key):
				var m := ShaderMaterial.new()
				if key == "Water":
					m.shader = WATER
					m.set_shader_parameter("tex", load("res://textures/water.png"))
					m.set_shader_parameter("sheen", Color("e8a090"))
					m.set_shader_parameter("sheen_strength", 0.3)
				elif TEX.has(key):
					m.shader = WORLD
					m.set_shader_parameter("tex", load("res://textures/%s.png" % TEX[key][0]))
					m.set_shader_parameter("uv_scale", Vector2.ONE * float(TEX[key][1]))
				else:
					push_error("Material %s ohne Textur-Zuordnung" % key)
					m.shader = WORLD
					m.set_shader_parameter("use_tex", 0.0)
					m.set_shader_parameter("tint", src.albedo_color)
				cache[key] = m
			mi.set_surface_override_material(i, cache[key])
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	(harbor.get_node("Sea") as MeshInstance3D).extra_cull_margin = 1.0


func _style_badger() -> void:
	var cache := {}
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		for i in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(i) as StandardMaterial3D
			var key := src.resource_name
			if not cache.has(key):
				var m := ShaderMaterial.new()
				m.shader = ACTOR
				m.set_shader_parameter("albedo", src.albedo_color)
				if key in ["Eye", "Nose", "Brass"]:
					m.set_shader_parameter("shine", 0.6)
				cache[key] = m
			mi.set_surface_override_material(i, cache[key])


func _attach_to_empties() -> void:
	for holder in $Game/Attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt in harbor_n64.glb" % holder.name)
			continue
		for c in holder.get_children():
			c.reparent(target, false)


# --- Rauch -----------------------------------------------------------------------------------------------------
func _build_smoke() -> void:
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	var tex := load("res://textures/smoke.png")
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	var anchor := harbor.find_child("ChimneySmoke", true, false) as Node3D
	for i in SMOKE_PUFFS:
		var p := MeshInstance3D.new()
		p.mesh = quad
		var m := ShaderMaterial.new()
		m.shader = SMOKE
		m.set_shader_parameter("tex", tex)
		m.render_priority = 1 + i
		p.material_override = m
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		anchor.add_child(p)
		smoke.append(p)
		smoke_mats.append(m)
		smoke_jitter.append(Vector3(rng.randf_range(-0.15, 0.15), rng.randf_range(0.85, 1.15), rng.randf_range(-0.1, 0.1)))


func _update_smoke() -> void:
	for i in smoke.size():
		var age := fposmod(t + float(i) * SMOKE_LIFE / SMOKE_PUFFS, SMOKE_LIFE) / SMOKE_LIFE
		var j := smoke_jitter[i]
		smoke[i].position = Vector3(1.5 * age * age + j.x * age, 2.4 * age * j.y, j.z * age)
		var s := lerpf(0.45, 1.7, sqrt(age))
		smoke[i].scale = Vector3.ONE * s
		smoke_mats[i].set_shader_parameter("opacity", 0.85 * smoothstep(0.0, 0.1, age) * (1.0 - smoothstep(0.4, 1.0, age)))
