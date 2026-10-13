extends Node3D
## HD-2D-Demo für den Katalog spielgrafik (Eintrag hd-2d).
##
## Die Umgebung ist die gemeinsame 3D-Szene (shared/3d/harbor.glb) mit Pixel-Texturen (shaders/world.gdshader,
## Texturen aus dem KI-Texturblatt), Figur und Requisiten sind Pixel-Sprites als Billboards
## (shaders/sprite.gdshader). Den Look machen Tiefenunschärfe (Tilt-Shift), Glühen, volumetrisches Licht,
## Vignette und eine langsam mitfahrende Kamera mit leichter Aufsicht.
## Alles hängt an der aufsummierten Zeit t und festen Seeds (Aufnahme mit --fixed-fps ist reproduzierbar).
##
## Benutzerargumente (nach "--"): --t0=<s> Startzeit, --solo (nur der Dachs vor Schwarz, zum Messen),
## --static-cam (Kamera steht), --nodof, --nofog (Vergleichsschalter).

const SPR := "res://sprites/"
const TEX := "res://textures/"
const WORLD := preload("res://shaders/world.gdshader")
const SPRITE := preload("res://shaders/sprite.gdshader")
const WATER := preload("res://shaders/water.gdshader")

# --- Sprite-Raster ----------------------------------------------------------------------------
const PX := 1.15 / 60.0          # Weltgröße eines Sprite-Pixels (Dachs 60 px = 1,15 m)
const SCREEN_PX := 2.0           # Dachs: ein Sprite-Pixel = genau 2×2 Bildpixel (siehe _pixel_perfect)

# --- Dachs ------------------------------------------------------------------------------------
const PATH_Z := 3.2              # Laufweg (näher an der Kamera als in shared/3d, siehe style.json)
const X_START := -6.3
const WALK_FPS := 15.0           # 8 Laufbilder, je 2 Aufnahmebilder
const WALK_ADV := 2.4         # Sprite-Pixel Vorschub je Laufbild (gemessener Rücklauf des Standfußes im Sprite)
const WALK_N := 44               # Anzahl gezeigter Laufbilder (endet auf einem Durchgangsbild)
const TURN_T := 3.2              # Seitenansicht -> Vorderansicht
const WAVE_T := 3.55
const WAVE_N := 6                # Winkbilder (je 0,2 s)
const BLINK_T := [5.25, 5.38]

# --- Kamera -----------------------------------------------------------------------------------
const CAM_Y := 2.75
const CAM_Z := 11.9
const CAM_PITCH := -4.2
const CAM_FOV := 44.0
const CAM_X0 := -3.6
const CAM_X1 := -1.9
const CAM_YAW0 := 2.0            # Grad; schwenkt beim Fahren leicht mit
const CAM_YAW1 := -1.0

# --- Umgebung ---------------------------------------------------------------------------------
const BEAM_PERIOD := 8.0
const BEAM_FACING_T := 4.6
const SEED := 20261012

var t := 0.0
var args := {}
var badger: MeshInstance3D
var badger_mat: ShaderMaterial
var badger_tex := {}
var gulls: Array = []
var smoke: Array = []
var dust: Array = []
var boats := {}
var lantern_mat: ShaderMaterial
var lamp_mat: ShaderMaterial
var window_mat: ShaderMaterial
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0
var _mat_cache := {}

@onready var harbor: Node3D = $Harbor
@onready var camera: Camera3D = $Camera
@onready var sun: DirectionalLight3D = $Sun
@onready var rotor: Node3D = $Attach/LighthouseLight/Rotor
@onready var lantern_omni: OmniLight3D = $Attach/LanternLight/Omni
@onready var lamp_omni: OmniLight3D = $Attach/LighthouseLight/Omni
@onready var window_omni: OmniLight3D = $Attach/CottageWindow/Omni


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=")
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	t = float(args.get("t0", "0"))
	_style_harbor()                      # vor dem Umhängen: nur die Flächen aus harbor.glb
	_attach_to_empties()
	sun.look_at_from_position(Vector3.ZERO, Vector3(0.42, -0.10, 0.90), Vector3.UP)
	_build_ground()
	_build_props()
	_build_badger()
	_build_gulls()
	_build_smoke()
	_build_dust()
	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform
	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	_place_camera()
	var to_cam := camera.global_position - rotor.global_position
	beam_yaw0 = atan2(-to_cam.x, -to_cam.z) - TAU * BEAM_FACING_T / BEAM_PERIOD
	_build_mist()
	if args.has("nodof"):
		($WorldEnvironment as WorldEnvironment).camera_attributes = null
	if args.has("nofog"):
		($WorldEnvironment as WorldEnvironment).environment.volumetric_fog_enabled = false
	if args.has("solo"):
		_solo()
	_update(0.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)


func _update(_delta: float) -> void:
	RenderingServer.global_shader_parameter_set("time_s", t)
	_place_camera()
	_update_badger()
	var k := 0
	for b in boats:
		var ph := 1.7 * k
		var roll := deg_to_rad(2.2) * sin(TAU * t / 3.4 + ph)
		var pitch := deg_to_rad(0.9) * sin(TAU * t / 4.6 + 0.8 + ph)
		var heave := 0.035 * sin(TAU * t / 3.9 + 2.1 + ph)
		var local := Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		(harbor.get_node(b) as Node3D).transform = boats[b] * local
		k += 1
	# Laterne flackert
	var f := 0.8 + 0.2 * lantern_noise.get_noise_1d(t * 7.0) + 0.07 * lantern_noise.get_noise_1d(t * 31.0 + 50.0)
	lantern_omni.light_energy = 2.6 * f
	lantern_omni.light_volumetric_fog_energy = 2.2 * f
	lantern_mat.set_shader_parameter("emission", Color(1.0, 0.58, 0.22) * 2.6 * f)
	# Fenster: leises Kaminfeuer-Flackern
	var fw := 0.92 + 0.08 * lantern_noise.get_noise_1d(t * 3.0 + 200.0)
	window_omni.light_energy = 1.2 * fw
	window_mat.set_shader_parameter("emission", Color(1.0, 0.6, 0.25) * 1.3 * fw)
	# Leuchtfeuer
	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position).normalized()
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), 24.0)
	lamp_mat.set_shader_parameter("emission", Color(1.0, 0.86, 0.6) * (3.0 + 16.0 * facing))
	lamp_omni.light_energy = 1.5 + 4.0 * facing
	_update_gulls()
	_update_smoke()
	_update_dust()


# --- Kamera -----------------------------------------------------------------------------------
func _place_camera() -> void:
	var u := 0.0 if args.has("static-cam") else smoothstep(0.0, 4.6, t)
	camera.fov = CAM_FOV
	camera.position = Vector3(lerpf(CAM_X0, CAM_X1, u), CAM_Y, CAM_Z)
	camera.rotation_degrees = Vector3(CAM_PITCH, lerpf(CAM_YAW0, CAM_YAW1, u), 0.0)
	RenderingServer.global_shader_parameter_set("view_cam_pos", camera.global_position)


# --- Dachs ------------------------------------------------------------------------------------
func _build_badger() -> void:
	var meta: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(SPR + "badger.json"))
	var cell: Array = meta["cell"]
	var cw := float(cell[0])
	var ch := float(cell[1])
	var base := float(meta["baseline"])
	badger_tex["walk"] = load(SPR + "badger_walk.png")
	badger_tex["front"] = load(SPR + "badger_front.png")
	badger_mat = _sprite_material(badger_tex["walk"], Vector2(cw, ch), 8)
	badger_mat.set_shader_parameter("ambient_boost", 0.22)
	badger_mat.set_shader_parameter("glint_energy", 0.9)
	badger = _sprite_mesh(badger_mat, Vector2(cw, ch), Vector2(float(meta["anchor_x"]), base + 1.0))
	badger.name = "Badger"
	badger.layers = 1 | 2                  # Ebene 2: Figurenlicht
	$Sprites.add_child(badger)


func _update_badger() -> void:
	var n := mini(int(floor(t * WALK_FPS)), WALK_N)          # gezeigte Laufbilder bisher
	var x := X_START + float(n) * WALK_ADV * PX * badger.scale.x
	badger.position = Vector3(x, 0.012, PATH_Z)
	_pixel_perfect(badger, SCREEN_PX)
	$CharLight.position = badger.position + Vector3(-0.6, 1.6, 1.4)
	if t < TURN_T:
		badger_mat.set_shader_parameter("tex", badger_tex["walk"])
		badger_mat.set_shader_parameter("hframes", 8.0)
		var fr := (n % 8) if n < WALK_N else (WALK_N % 8)
		badger_mat.set_shader_parameter("frame", float(fr))
		return
	badger_mat.set_shader_parameter("tex", badger_tex["front"])
	badger_mat.set_shader_parameter("hframes", 6.0)
	var fr := 0
	if t >= WAVE_T and t < WAVE_T + 0.2 * WAVE_N:
		fr = 2 + (int(floor((t - WAVE_T) / 0.2)) % 2)
	else:
		# Atmen: im Takt von 0,6 s Oberkörper 1 px tiefer (6 Bilder/s-Raster: 18 Aufnahmebilder je Hälfte)
		var breath := int(floor((t - TURN_T) / 0.6)) % 2 == 1
		var blink: bool = t >= BLINK_T[0] and t < BLINK_T[1]
		fr = (5 if blink else 4) if breath else (1 if blink else 0)
	badger_mat.set_shader_parameter("frame", float(fr))


## Skaliert ein Billboard so, dass ein Sprite-Pixel auf seiner Tiefe genau `k` Bildschirmpixel breit und hoch
## ist (Abbildung über camera.unproject_position). Bei ganzzahligem k deckt jedes Sprite-Pixel bei jeder
## Unterpixellage genau k×k Bildpixel: keine ungleich breiten Pixel trotz Perspektive und Kamerafahrt.
func _pixel_perfect(mi: MeshInstance3D, k: float) -> void:
	var vp := get_viewport().get_visible_rect().size
	var sc := vp.y / 720.0                                     # Aufnahme 1280×720; andere Fenster skalieren mit
	var base := mi.global_position + Vector3(0.0, 0.5, 0.0)
	var right := camera.global_basis.x
	right.y = 0.0
	right = right.normalized()
	var p0 := camera.unproject_position(base)
	var p1 := camera.unproject_position(base + right * (10.0 * PX))
	var q0 := camera.unproject_position(mi.global_position)
	var q1 := camera.unproject_position(mi.global_position + Vector3(0.0, 30.0 * PX, 0.0))
	mi.scale = Vector3(10.0 * k * sc / p0.distance_to(p1), 30.0 * k * sc / absf(q1.y - q0.y), 1.0)


# --- Sprites allgemein ------------------------------------------------------------------------
func _sprite_material(tex: Texture2D, frame_px: Vector2, hframes: int) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = SPRITE
	m.set_shader_parameter("tex", tex)
	m.set_shader_parameter("tex_px", frame_px)
	m.set_shader_parameter("hframes", float(hframes))
	return m


## Quad in Sprite-Pixeln; anchor = Pixelkoordinate (von oben links), die auf dem Ursprung des Knotens liegt.
func _sprite_mesh(mat: ShaderMaterial, frame_px: Vector2, anchor: Vector2) -> MeshInstance3D:
	var q := QuadMesh.new()
	q.size = frame_px * PX
	q.center_offset = Vector3((frame_px.x * 0.5 - anchor.x) * PX, (anchor.y - frame_px.y * 0.5) * PX, 0.0)
	var mi := MeshInstance3D.new()
	mi.mesh = q
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	mi.extra_cull_margin = 2.0
	return mi


func _prop(name: String, pos: Vector3, flip := false, mod := Color.WHITE) -> MeshInstance3D:
	var tex: Texture2D = load(SPR + name + ".png")
	var sz := Vector2(tex.get_width(), tex.get_height())
	var m := _sprite_material(tex, sz, 1)
	m.set_shader_parameter("flip_h", flip)
	m.set_shader_parameter("modulate", mod)
	var mi := _sprite_mesh(m, sz, Vector2(sz.x * 0.5, sz.y - 1.0))
	mi.position = pos
	mi.name = name.capitalize().replace(" ", "")
	$Sprites.add_child(mi)
	return mi


func _build_props() -> void:
	# Ersetzt die 3D-Requisiten aus shared/3d durch Billboards an derselben Stelle
	for n in ["Barrel1", "Barrel2", "CrateStack", "RopeCoil"]:
		(harbor.find_child(n, true, false) as Node3D).visible = false
	_prop("barrel", Vector3(-5.25, 0.012, -0.15))
	_prop("barrel", Vector3(-4.55, 0.012, -0.62), true)
	_prop("crates", Vector3(6.55, 0.012, 0.2))
	_prop("crate", Vector3(5.75, 0.012, 0.75))
	_prop("rope", Vector3(1.05, 0.012, 0.05))
	_prop("net", Vector3(2.1, 0.012, -0.25))
	# Vordergrund nah an der Kamera (Tiefenunschärfe vorn)
	_prop("barrel", Vector3(-6.6, 0.012, 6.6), true)
	_prop("barrel", Vector3(-4.7, 0.012, 7.0))
	# Gras und Strandhafer an den Rändern von Insel und Felsnase
	_prop("seagrass", Vector3(-12.2, 0.4, -2.6))
	_prop("grass", Vector3(-11.4, 0.2, -1.2), true)
	_prop("seagrass", Vector3(8.6, 0.6, -4.2), true)
	_prop("grass", Vector3(9.3, 1.0, -6.5))
	# Möwe auf dem mittleren Poller
	_prop("gull_stand", Vector3(0.7, 0.63, -0.7), true)


func _build_gulls() -> void:
	var tex: Texture2D = load(SPR + "gull_fly.png")
	var meta: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(SPR + "props.json"))
	var g: Dictionary = meta["sprites"]["gull_fly"]
	var sz := Vector2(float(g["size"][0]), float(g["size"][1]))
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	for i in 3:
		var m := _sprite_material(tex, sz, 4)
		m.set_shader_parameter("ambient_boost", 0.3)
		var mi := _sprite_mesh(m, sz, Vector2(sz.x * 0.5, sz.y * 0.5))
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		$Sprites.add_child(mi)
		gulls.append({"mi": mi, "mat": m, "c": Vector3(rng.randf_range(-2.0, 6.0), rng.randf_range(5.5, 8.0),
			rng.randf_range(-12.0, -6.0)), "r": rng.randf_range(2.5, 4.5), "w": rng.randf_range(0.25, 0.4)
			* (1.0 if i % 2 == 0 else -1.0), "ph": rng.randf_range(0.0, TAU), "fp": rng.randi_range(0, 3)})


func _update_gulls() -> void:
	for g in gulls:
		var a: float = g["ph"] + t * g["w"]
		var c: Vector3 = g["c"]
		var r: float = g["r"]
		(g["mi"] as MeshInstance3D).position = c + Vector3(cos(a) * r, 0.35 * sin(a * 2.0), sin(a) * r * 0.5)
		var vx := -sin(a) * float(g["w"])                      # Flugrichtung im Bild (x)
		var mat: ShaderMaterial = g["mat"]
		mat.set_shader_parameter("flip_h", vx < 0.0)
		mat.set_shader_parameter("frame", float((int(floor(t * 10.0)) + int(g["fp"])) % 4))


# --- Rauch (Pixel-Wölkchen) und Lichtstaub ----------------------------------------------------
func _build_smoke() -> void:
	var tex: Texture2D = load(SPR + "smoke.png")
	var fw := float(tex.get_height())
	var anchor := harbor.find_child("ChimneySmoke", true, false) as Node3D
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED + 1
	for i in 10:
		var m := _sprite_material(tex, Vector2(fw, fw), 4)
		m.set_shader_parameter("wrap", 1.0)
		m.set_shader_parameter("ambient_boost", 0.35)
		var mi := _sprite_mesh(m, Vector2(fw, fw), Vector2(fw * 0.5, fw * 0.5))
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		anchor.add_child(mi)
		smoke.append({"mi": mi, "mat": m, "j": Vector3(rng.randf_range(-0.12, 0.12), rng.randf_range(0.85, 1.15), 0.0)})


func _update_smoke() -> void:
	var life := 4.2
	for i in smoke.size():
		var s: Dictionary = smoke[i]
		var age := fposmod(t + float(i) * life / smoke.size(), life) / life
		var j: Vector3 = s["j"]
		(s["mi"] as MeshInstance3D).position = Vector3(1.4 * age * age + j.x * age, 2.4 * age * j.y, 0.0)
		var st := clampi(int(floor(age * 4.0)), 0, 3)            # Wölkchen wächst in vier Stufen
		(s["mat"] as ShaderMaterial).set_shader_parameter("frame", float(st))


func _build_dust() -> void:
	# Lichtstaub im Schein der Laterne: einzelne Pixel, die langsam treiben und nur im Licht leuchten
	var img := Image.create(2, 2, false, Image.FORMAT_RGBA8)
	img.fill(Color(1, 0.85, 0.6, 1))
	var tex := ImageTexture.create_from_image(img)
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED + 2
	var lantern := harbor.find_child("LanternLight", true, false) as Node3D
	for i in 26:
		var m := _sprite_material(tex, Vector2(2, 2), 1)
		m.set_shader_parameter("emission_color", Color(1.0, 0.7, 0.35))
		var mi := _sprite_mesh(m, Vector2(2, 2), Vector2(1, 1))
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		$Sprites.add_child(mi)
		dust.append({"mi": mi, "mat": m, "c": lantern.global_position + Vector3(rng.randf_range(-1.6, 1.6),
			rng.randf_range(-1.6, 0.8), rng.randf_range(-0.8, 1.6)), "ph": rng.randf_range(0.0, TAU),
			"sp": rng.randf_range(0.15, 0.4)})


func _update_dust() -> void:
	var lp := (harbor.find_child("LanternLight", true, false) as Node3D).global_position
	for d in dust:
		var ph: float = d["ph"]
		var sp: float = d["sp"]
		var c: Vector3 = d["c"]
		# steigt langsam und beginnt nach 2,4 m wieder unten (läuft beliebig lange gleichmäßig)
		var rise := fposmod(0.05 * t + ph * 0.38, 2.4) - 1.2
		var p := c + Vector3(0.3 * sin(t * sp + ph), 0.25 * sin(t * sp * 1.3 + ph * 2.0) + rise, 0.2 * cos(t * sp + ph))
		(d["mi"] as MeshInstance3D).position = p
		var dist := p.distance_to(lp)
		var glow := clampf(1.0 - dist / 2.2, 0.0, 1.0) * (0.6 + 0.4 * sin(t * 3.0 + ph * 5.0))
		(d["mat"] as ShaderMaterial).set_shader_parameter("emission_color", Color(1.0, 0.7, 0.35) * 4.0 * glow)
		(d["mat"] as ShaderMaterial).set_shader_parameter("modulate", Color(1, 1, 1, 1.0 if glow > 0.05 else 0.0))


# --- Bodennebel ------------------------------------------------------------------------------
func _build_mist() -> void:
	# Dichterer Nebel nur über Kai und Hafenkante: hier werden Sonnenstrahlen (Schattenkeil hinter dem
	# Häuschen), Laternen- und Fensterlicht sichtbar, die Ferne bleibt klar. FogVolume gibt es nur in
	# Forward+; im Compatibility-Renderer meldet schon das Laden eines FogMaterial einen Fehler.
	if RenderingServer.get_current_rendering_method() != "forward_plus" or args.has("nofog"):
		return
	var fm := FogMaterial.new()
	fm.density = 0.02
	fm.albedo = Color(0.95, 0.85, 0.8)
	fm.height_falloff = 0.35
	fm.edge_fade = 0.4
	var fv := FogVolume.new()
	fv.name = "Mist"
	fv.size = Vector3(24, 5, 9)
	fv.material = fm
	fv.position = Vector3(-3.0, 1.5, 1.2)
	add_child(fv)


# --- Boden über dem modellierten Pflaster -----------------------------------------------------
func _build_ground() -> void:
	# Die modellierten Pflasterplatten aus shared/3d tragen keine Pixel-Textur sinnvoll (Fugen aus Geometrie
	# und Textur doppelt). Ein flacher Boden 12 mm über dem Pflaster (README shared/3d) trägt die
	# Pflastertextur; Kantensteine, Poller und Mauern bleiben aus dem Modell.
	var mat := _world_material("paving", Color(1, 1, 1), 0.85)
	for r in [Rect2(-13.0, -0.38, 20.38, 8.38), Rect2(-13.0, -3.6, 7.38, 3.22)]:
		var pm := PlaneMesh.new()
		pm.size = r.size
		var mi := MeshInstance3D.new()
		mi.mesh = pm
		mi.material_override = mat
		mi.position = Vector3(r.position.x + r.size.x * 0.5, 0.012, r.position.y + r.size.y * 0.5)
		add_child(mi)


# --- Materialien nach Namen -------------------------------------------------------------------
const MAT_TEX := {
	"Stone": ["fieldstone", 0.92], "StoneDark": ["stone_dark", 0.9], "Wood": ["wood", 0.85],
	"WoodDark": ["wood_dark", 0.85], "WhitePaint": ["white_boards", 0.6], "RedPaint": ["red_boards", 0.6],
	"Roof": ["slate", 0.75], "Rope": ["rope", 0.95], "Metal": ["iron", 0.5], "Rock": ["rock", 0.95],
	"Sand": ["sand", 1.0], "Grass": ["grass", 1.0],
}


func _world_material(tex_name: String, tint: Color, rough: float, object_space := false) -> ShaderMaterial:
	var key := "%s|%s|%s" % [tex_name, tint, object_space]
	if _mat_cache.has(key):
		return _mat_cache[key]
	var m := ShaderMaterial.new()
	m.shader = WORLD
	var tex: Texture2D = load(TEX + tex_name + ".png")
	m.set_shader_parameter("albedo_tex", tex)
	m.set_shader_parameter("has_tex", true)
	m.set_shader_parameter("tex_px", float(tex.get_width()))
	if ResourceLoader.exists(TEX + tex_name + "_n.png"):
		m.set_shader_parameter("normal_tex", load(TEX + tex_name + "_n.png"))
		m.set_shader_parameter("has_normal", true)
	m.set_shader_parameter("albedo", tint)
	m.set_shader_parameter("roughness", rough)
	m.set_shader_parameter("object_space", object_space)
	if tex_name == "rope":
		m.set_shader_parameter("density", 2.0)
	_mat_cache[key] = m
	return m


func _glass_material(c: Color) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = WORLD
	m.set_shader_parameter("albedo", Color(1.0, 0.85, 0.55))
	m.set_shader_parameter("roughness", 1.0)
	m.set_shader_parameter("specular", 0.0)
	m.set_shader_parameter("emission", c)
	return m


func _style_harbor() -> void:
	window_mat = _glass_material(Color(1.0, 0.66, 0.32) * 3.2)
	lantern_mat = _glass_material(Color(1.0, 0.62, 0.28) * 5.0)
	lamp_mat = _glass_material(Color(1.0, 0.86, 0.6) * 5.0)
	var water := ShaderMaterial.new()
	water.shader = WATER
	for mi: MeshInstance3D in harbor.find_children("*", "MeshInstance3D", true, false):
		var on := mi.name as String
		var boat := on.begins_with("Boat")
		var lighthouse := on == "Lighthouse"
		if on in ["CottageWindow", "LanternGlass", "LighthouseLamp"]:
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mi.material_override = {"CottageWindow": window_mat, "LanternGlass": lantern_mat,
				"LighthouseLamp": lamp_mat}[on]
			continue
		if on == "Sea":
			mi.material_override = water
			mi.extra_cull_margin = 1.0
			continue
		for i in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(i) as StandardMaterial3D
			if src == null:
				push_error("%s: Fläche %d ohne glTF-Material" % [on, i])
				continue
			var key := src.resource_name
			var m: Material
			if lighthouse and key == "WhitePaint":
				m = _world_material("plaster", Color(1, 1, 1), 0.8)
			elif lighthouse and key == "RedPaint":
				m = _world_material("plaster", Color(0.78, 0.2, 0.17), 0.8)
			elif MAT_TEX.has(key):
				var d: Array = MAT_TEX[key]
				m = _world_material(d[0], Color(1, 1, 1), d[1], boat)
			else:
				push_error("unbekanntes Material %s an %s" % [key, on])
				continue
			mi.set_surface_override_material(i, m)


func _attach_to_empties() -> void:
	for holder in $Attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt in harbor.glb" % holder.name)
			continue
		for c in holder.get_children():
			c.reparent(target, false)


# --- Messlauf: nur der Dachs vor Schwarz ------------------------------------------------------
func _solo() -> void:
	harbor.visible = false
	for c in $Sprites.get_children():
		if c != badger:
			(c as Node3D).visible = false
	for c in get_children():
		if c is MeshInstance3D:
			(c as Node3D).visible = false
	var env := ($WorldEnvironment as WorldEnvironment).environment
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color.BLACK
	env.volumetric_fog_enabled = false
	env.glow_enabled = false
	env.fog_enabled = false
	env.ssao_enabled = false
	env.ssr_enabled = false
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color.WHITE
	env.ambient_light_energy = 1.0
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	env.adjustment_enabled = false
	($WorldEnvironment as WorldEnvironment).camera_attributes = null
	sun.visible = false
	$Post.visible = false
	$UI.visible = false
	badger_mat.set_shader_parameter("silhouette", true)
	# Messbilder: Laufbilder als Maske (weiß Körper, grün nahes Bein, blau fernes Bein); Stehbilder in Farbe
	badger_tex["walk"] = load(SPR + "badger_walk_legs.png")
	$CharLight.visible = false
	$Fill.visible = false
