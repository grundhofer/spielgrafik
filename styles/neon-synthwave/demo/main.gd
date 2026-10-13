extends Node2D
## Neon & Synthwave: der gemeinsame Hafen (shared/3d) als Neonzeichnung.
##
## Ablauf je Bild:
##   1. IdView rendert Hafen und Dachs mit id.gdshader in einen RGBA16F-Puffer (2560×1440):
##      Kennung, lineare Tiefe, Normale. Kein Licht, keine Farben.
##   2. ReflView rendert dieselbe Welt aus der an der Wasserfläche gespiegelten Kamera.
##   3. Composite (neon.gdshader) baut daraus Himmel, Streifensonne, Wasser mit Spiegelbild, Kai-Raster,
##      Neonröhren und dunkle Füllungen; Glow kommt aus der WorldEnvironment (HDR-2D).
## Alles hängt an der aufsummierten Zeit t und festen Seeds (tools/capture.py nimmt mit --fixed-fps auf).
##
## Schalter nach "--": --t0=<s> (Startzeit), --ids (Kennungen in Falschfarben), --no-post, --no-ui,
## --shot=<0..1> (feste Lage auf der Kamerafahrt), --badger-only (nur Dachs, Maske), --measure-cam[=bottom]
## (Messkamera von vorn bzw. von unten), --no-glow, --ss=1 (ID-Puffer in Bildgröße statt doppelt), --stats.

const SEED := 20261013
## Aussetzer der Laterne: [Beginn in s (innerhalb von 6 s), Dauer in s]
const LANTERN_DIPS := [[1.30, 0.067], [1.43, 0.034], [2.95, 0.1], [5.02, 0.067], [5.15, 0.034]]
const WATER_Y := -0.8

# --- Palette (sRGB) ---------------------------------------------------------------------------
const PINK := Color("ff2a9e")
const MAGENTA := Color("e23cff")
const CYAN := Color("1fe4ff")
const VIOLET := Color("8a55ff")
const BLUE := Color("4d7dff")
const AMBER := Color("ffb43c")
const ORANGE := Color("ff6a2c")
const RED := Color("ff2448")
const GREEN := Color("2dff9a")
const WHITE := Color("eef2ff")
const CREAM := Color("ffe2a6")
const PERI := Color("9aa6ff")
const NIGHT := Color("120724")

## Gruppe -> [Röhrenfarbe, Röhrenhelligkeit, Füllfarbe, Füllhelligkeit, Knickwinkel in Grad (0 = keine
## Knicklinien), Linie an Materialgrenzen gleicher Tiefe]
var groups := {
	"water": [Color.BLACK, 0.0, Color.BLACK, 0.0, 0, false],
	"pavement": [CYAN, 0.0, NIGHT, 1.0, 0, false],
	"quay_wall": [CYAN, 1.7, NIGHT, 1.0, 50, true],
	"jetty": [ORANGE, 1.1, NIGHT, 1.0, 50, true],
	"bollard": [CYAN, 1.5, NIGHT, 1.0, 0, true],
	"boat_white": [CYAN, 1.7, NIGHT, 1.0, 55, true],
	"boat_red": [PINK, 1.8, NIGHT, 1.0, 55, true],
	"boat_wood": [ORANGE, 1.3, NIGHT, 1.0, 55, true],
	"boat_metal": [CYAN, 1.2, NIGHT, 1.0, 0, true],
	"boat_rope": [AMBER, 1.1, NIGHT, 1.0, 0, true],
	"barrel": [ORANGE, 1.6, NIGHT, 1.0, 0, true],
	"barrel_hoop": [AMBER, 1.6, NIGHT, 1.0, 0, true],
	"crate": [ORANGE, 1.6, NIGHT, 1.0, 40, true],
	"crate_frame": [AMBER, 1.5, NIGHT, 1.0, 40, true],
	"rope": [AMBER, 1.4, NIGHT, 1.0, 0, true],
	"cottage_wall": [VIOLET, 1.8, NIGHT, 1.0, 40, true],
	"cottage_dark": [VIOLET, 1.8, NIGHT, 1.0, 40, true],
	"roof": [PINK, 1.9, NIGHT, 1.0, 40, true],
	"door": [PINK, 1.5, NIGHT, 1.0, 40, true],
	"cottage_wood": [PINK, 1.5, NIGHT, 1.0, 40, true],
	"window_frame": [WHITE, 1.4, NIGHT, 1.0, 40, true],
	"shutter": [PINK, 1.6, NIGHT, 1.0, 40, true],
	"window_glass": [AMBER, 2.2, AMBER, 1.6, 0, true],
	"post_base": [VIOLET, 1.5, NIGHT, 1.0, 40, true],
	"post": [VIOLET, 1.6, NIGHT, 1.0, 40, true],
	"lantern_metal": [CYAN, 1.5, NIGHT, 1.0, 0, true],
	"lantern_glass": [AMBER, 2.4, AMBER, 2.2, 0, true],
	"lh_base": [VIOLET, 1.6, NIGHT, 1.0, 40, true],
	"lh_white": [WHITE, 1.9, NIGHT, 1.0, 0, true],
	"lh_red": [RED, 2.2, NIGHT, 1.0, 0, true],
	"lh_metal": [CYAN, 1.5, NIGHT, 1.0, 0, true],
	"lh_door": [PINK, 1.4, NIGHT, 1.0, 0, true],
	"lh_lamp": [WHITE, 2.5, WHITE, 2.5, 0, true],
	"head_rock": [VIOLET, 1.2, NIGHT, 0.8, 22, false, {"flat": true}],
	"head_sand": [VIOLET, 1.2, NIGHT, 0.8, 22, false, {"flat": true}],
	"head_grass": [BLUE, 1.2, NIGHT, 0.8, 22, false, {"flat": true}],
	"hill_rock": [VIOLET, 1.2, NIGHT, 0.8, 22, false, {"flat": true}],
	"hill_sand": [VIOLET, 1.2, NIGHT, 0.8, 22, false, {"flat": true}],
	"hill_grass": [BLUE, 1.2, NIGHT, 0.8, 22, false, {"flat": true}],
	"rocks_sea": [VIOLET, 1.3, NIGHT, 0.8, 30, false, {"flat": true}],
	"islands": [MAGENTA, 1.4, NIGHT, 0.7, 0, false],
	"fur_dark": [PERI, 1.8, Color("0b0a1d"), 1.0, 0, true],
	"fur_light": [WHITE, 1.7, Color("3a3058"), 1.0, 0, true],
	"cap": [GREEN, 1.9, Color("0e3b2c"), 1.0, 0, true],
	"vest": [GREEN, 1.7, Color("0e3b2c"), 1.0, 0, true],
	"shirt": [CREAM, 1.5, Color("4a3a32"), 1.0, 0, true],
	"scarf": [RED, 2.2, Color("5c0b22"), 1.0, 0, true],
	"satchel": [ORANGE, 1.7, Color("4a1d10"), 1.0, 0, true],
	"parcel": [AMBER, 2.0, Color("5a3512"), 1.0, 0, true],
	"brass": [AMBER, 2.0, AMBER, 1.5, 0, true],
	"nose": [WHITE, 1.2, Color("0b0a1d"), 1.0, 0, true],
	"eye": [WHITE, 1.4, Color("0b0a1d"), 1.0, 0, true],
	"smoke": [PINK, 1.6, NIGHT, 0.0, 0, false, {"clear": true}],
}

## Objekt -> {Material -> Gruppe}; "*" gilt für alle übrigen Materialien des Objekts.
const ASSIGN := {
	"Sea": {"*": "water"},
	"Quay": {"*": "quay_wall"},
	"Jetty": {"*": "jetty"},
	"Bollards": {"*": "bollard"},
	"BoatA": {"WhitePaint": "boat_white", "RedPaint": "boat_red", "Metal": "boat_metal", "Rope": "boat_rope", "*": "boat_wood"},
	"BoatB": {"WhitePaint": "boat_white", "RedPaint": "boat_red", "Metal": "boat_metal", "Rope": "boat_rope", "*": "boat_wood"},
	"Barrel1": {"Metal": "barrel_hoop", "*": "barrel"},
	"Barrel2": {"Metal": "barrel_hoop", "*": "barrel"},
	"CrateStack": {"WoodDark": "crate_frame", "*": "crate"},
	"RopeCoil": {"*": "rope"},
	"Cottage": {"Stone": "cottage_wall", "StoneDark": "cottage_dark", "Roof": "roof", "WoodDark": "door",
		"Wood": "cottage_wood", "WhitePaint": "window_frame", "RedPaint": "shutter", "*": "cottage_wall"},
	"CottageWindow": {"*": "window_glass"},
	"LanternPost": {"StoneDark": "post_base", "Metal": "lantern_metal", "*": "post"},
	"LanternGlass": {"*": "lantern_glass"},
	"Lighthouse": {"StoneDark": "lh_base", "WhitePaint": "lh_white", "RedPaint": "lh_red", "Metal": "lh_metal",
		"WoodDark": "lh_door", "*": "lh_white"},
	"LighthouseLamp": {"*": "lh_lamp"},
	"Headland": {"Rock": "head_rock", "Sand": "head_sand", "Grass": "head_grass", "*": "head_rock"},
	"WestHill": {"Rock": "hill_rock", "Sand": "hill_sand", "Grass": "hill_grass", "*": "hill_rock"},
	"RocksSea": {"*": "rocks_sea"},
	"IslandsFar": {"*": "islands"},
	"Badger": {"FurDark": "fur_dark", "FurLight": "fur_light", "Cap": "cap", "Brass": "brass", "Vest": "vest",
		"Shirt": "shirt", "Scarf": "scarf", "Satchel": "satchel", "Nose": "nose", "Eye": "eye", "*": "fur_dark"},
	"Parcel": {"Parcel": "parcel", "Shirt": "shirt", "*": "parcel"},
}

const ID_SHADER := preload("res://shaders/id.gdshader")

# --- Kamera ----------------------------------------------------------------------------------
## Kamerafahrt: [Position, rotation_degrees (YXZ), fov, Zeitpunkt in s]; dazwischen weich überblendet
var shots := [
	[Vector3(-1.8, 2.8, 14.5), Vector3(-3.5, 0.0, 0.0), 42.0, 0.4],
	[Vector3(0.3, 0.88, 8.0), Vector3(1.5, -4.5, 0.0), 44.0, 3.7],
]

const MEASURE_CAM_POS := Vector3(-1.5, 0.6, 9.5)
const Walker := preload("res://walker.gd")
var walker: Walker

var t := 0.0
var t0 := 0.0
var args := {}
var group_id := {}             # Gruppe -> Kennung
var id_count := 3              # 0 Himmel, 1 Wasser, 2 Pflaster
var group_mats := {}           # Gruppe -> ShaderMaterial
var neon_arr := PackedVector4Array()
var fill_arr := PackedVector4Array()
var boats := {}
var smoke: Array[MeshInstance3D] = []
var smoke_mats: Array[ShaderMaterial] = []
var smoke_jitter: Array[Vector3] = []
var noise := FastNoiseLite.new()
var beam_yaw0 := 0.0

@onready var id_view: SubViewport = $IdView
@onready var refl_view: SubViewport = $ReflView
@onready var cam: Camera3D = $IdView/Cam
@onready var refl_cam: Camera3D = $ReflView/ReflCam
@onready var harbor: Node3D = $IdView/Harbor
@onready var badger: Node3D = $IdView/Badger
@onready var player: AnimationPlayer = $IdView/Badger/AnimationPlayer
@onready var composite: ColorRect = $Composite
@onready var neon_mat: ShaderMaterial = $Composite.material
@onready var ui: Control = $UI/Panel
@onready var gulls: Node2D = $FX


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv: PackedStringArray = a.trim_prefix("--").split("=")
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	t0 = float(args.get("t0", "0"))
	t = t0

	if args.get("ss", "2") == "1":
		# Sparfassung (z. B. Telefon): ID-Puffer in Bildgröße, eine Abtastung je Pixel, schmalere Röhren
		id_view.size = Vector2i(1280, 720)
		neon_mat.set_shader_parameter("ss", 1)
		neon_mat.set_shader_parameter("line_w", 1.25)
		gulls.scale_px = 1.0
	refl_view.world_3d = id_view.find_world_3d()
	neon_mat.set_shader_parameter("id_tex", id_view.get_texture())
	neon_mat.set_shader_parameter("refl_tex", refl_view.get_texture())
	group_id = {"water": 1, "pavement": 2}
	neon_arr.resize(64)
	fill_arr.resize(64)
	_apply_ids(harbor)
	_apply_ids(badger)
	var quay_mat := group_mats["quay_wall"] as ShaderMaterial
	quay_mat.set_shader_parameter("alt_id", 2.0)
	_build_smoke()
	_build_group_arrays()

	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform
	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	walker = Walker.new(badger)

	noise.seed = SEED
	noise.frequency = 1.0

	if args.has("ids"):
		neon_mat.set_shader_parameter("debug_view", 1)
	if args.has("badger-only"):
		# Messlauf: nur der Dachs im ID-Puffer, Maske weiß auf schwarz, feste Messkamera, ohne Glow/Oberfläche
		harbor.visible = false
		$IdView/Smoke.visible = false
		$FX.visible = false
		neon_mat.set_shader_parameter("debug_view", 3 if args.get("measure-cam", "") == "bottom" else 2)
		args["no-post"] = "1"
		args["no-ui"] = "1"
		args["no-glow"] = "1"
	if args.has("no-post"):
		($Post/Screen.material as ShaderMaterial).set_shader_parameter("enabled", 0)
	if args.has("no-ui"):
		$UI.visible = false
	if args.has("no-glow"):
		($WorldEnvironment.environment as Environment).glow_enabled = false
	_update(0.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)
	if args.has("stats"):
		_stats()


# --- Messung der Bildzeit (Schalter --stats): ohne VSync, Wanduhr über 300 Bilder ----------------
var _stat_n := 0
var _stat_t0 := 0

func _stats() -> void:
	if _stat_n == 0:
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	elif _stat_n == 60:
		_stat_t0 = Time.get_ticks_usec()
	elif _stat_n == 360:
		var ms := float(Time.get_ticks_usec() - _stat_t0) / 300.0 / 1000.0
		print("Bildzeit (Mittel über 300 Bilder, ohne VSync): %.2f ms (%s)" % [ms,
			RenderingServer.get_video_adapter_name()])
		get_tree().quit()
	_stat_n += 1


# --- Kennungen -------------------------------------------------------------------------------
func _group_material(g: String) -> ShaderMaterial:
	if not group_mats.has(g):
		if not group_id.has(g):
			group_id[g] = id_count
			id_count += 1
		var m := ShaderMaterial.new()
		m.shader = ID_SHADER
		m.set_shader_parameter("obj_id", float(group_id[g]))
		m.set_shader_parameter("water_y", WATER_Y)
		var d: Array = groups[g]
		if d.size() > 6 and (d[6] as Dictionary).get("flat", false):
			m.set_shader_parameter("flat_normals", true)
		group_mats[g] = m
	return group_mats[g]


func _apply_ids(root: Node) -> void:
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		var table: Dictionary = ASSIGN.get(String(mi.name), {})
		if table.is_empty():
			push_error("keine Zuordnung für %s" % mi.name)
			continue
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		for i in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(i)
			var mname := src.resource_name if src else ""
			var g: String = table.get(mname, table.get("*", ""))
			if g == "":
				push_error("%s/%s ohne Gruppe" % [mi.name, mname])
				continue
			mi.set_surface_override_material(i, _group_material(g))


func _build_group_arrays() -> void:
	for g in groups:
		if not group_id.has(g):
			continue
		_set_group_color(g)
	neon_mat.set_shader_parameter("neon", neon_arr)
	neon_mat.set_shader_parameter("fill", fill_arr)


func _set_group_color(g: String, line_gain := 1.0, fill_gain := 1.0) -> void:
	var d: Array = groups[g]
	var id: int = group_id[g]
	var lc: Color = (d[0] as Color).srgb_to_linear()
	var fc: Color = (d[2] as Color).srgb_to_linear()
	var lk: float = d[1] * line_gain
	var fk: float = d[3] * fill_gain
	var facet: float = cos(deg_to_rad(d[4])) if d[4] > 0 else -2.0
	neon_arr[id] = Vector4(lc.r * lk, lc.g * lk, lc.b * lk, facet)
	var opt: Dictionary = d[6] if d.size() > 6 else {}
	var flags := (1.0 if d[5] else 0.0) + (2.0 if opt.get("clear", false) else 0.0)
	fill_arr[id] = Vector4(fc.r * fk, fc.g * fk, fc.b * fk, flags)


# --- Ablauf ----------------------------------------------------------------------------------
func _update(delta: float) -> void:
	_update_camera()
	_update_badger(delta)

	var k := 0
	for b in boats:
		var ph := 1.7 * k
		var roll := deg_to_rad(2.4) * sin(TAU * t / 3.4 + ph)
		var pitch := deg_to_rad(1.0) * sin(TAU * t / 4.6 + 0.8 + ph)
		var heave := 0.04 * sin(TAU * t / 3.9 + 2.1 + ph)
		(harbor.get_node(b) as Node3D).transform = boats[b] * Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		k += 1

	_update_smoke()

	# Leuchtfeuer: Strahl dreht sich (8 s je Umdrehung), 5° nach unten geneigt
	var lamp := (harbor.find_child("LighthouseLight", true, false) as Node3D).global_position
	var yaw := beam_yaw0 + TAU * t / 8.0
	var bdir := Vector3(sin(yaw), -0.087, -cos(yaw)).normalized()
	neon_mat.set_shader_parameter("lamp_pos", lamp)
	neon_mat.set_shader_parameter("beam_dir", bdir)

	# Laterne flackert
	var f := 0.8 + 0.2 * noise.get_noise_1d(t * 7.0) + 0.08 * noise.get_noise_1d(t * 29.0 + 50.0)
	# Neon-Aussetzer: kurze Einbrüche zu festen Zeiten (wiederholt alle 6 s)
	var tm := fposmod(t, 6.0)
	for d in LANTERN_DIPS:
		if tm >= d[0] and tm < d[0] + d[1]:
			f *= 0.3
	_set_group_color("lantern_glass", f, f)
	var to_cam := (cam.global_position - lamp)
	var facing := pow(maxf(bdir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), 16.0)
	_set_group_color("lh_lamp", 1.0 + facing * 0.8, 1.0 + facing * 1.5)
	neon_mat.set_shader_parameter("neon", neon_arr)
	neon_mat.set_shader_parameter("fill", fill_arr)

	var lantern := (harbor.find_child("LanternLight", true, false) as Node3D).global_position
	var window := (harbor.find_child("CottageWindow", true, false) as Node3D).global_position
	var amber := AMBER.srgb_to_linear()
	neon_mat.set_shader_parameter("halo_pos", PackedVector3Array([lantern, window + Vector3(0.0, 0.0, 0.3), lamp]))
	neon_mat.set_shader_parameter("halo_col", PackedVector4Array([
		Vector4(amber.r * 0.5 * f, amber.g * 0.5 * f, amber.b * 0.5 * f, 46.0),
		Vector4(amber.r * 0.25, amber.g * 0.25, amber.b * 0.25, 40.0),
		Vector4(0.6 + facing * 1.2, 0.8 + facing * 1.2, 1.0 + facing * 1.2, 12.0 + facing * 16.0)]))
	neon_mat.set_shader_parameter("halo_count", 3)
	neon_mat.set_shader_parameter("t", t)
	ui.t = t
	ui.queue_redraw()
	gulls.t = t
	gulls.cam = cam
	gulls.queue_redraw()


func _update_camera() -> void:
	var a: Array = shots[0]
	var b: Array = shots[1]
	var k := clampf((t - a[3]) / (b[3] - a[3]), 0.0, 1.0)
	k = k * k * k * (k * (k * 6.0 - 15.0) + 10.0)
	if args.has("shot"):
		k = float(args["shot"])
	cam.position = (a[0] as Vector3).lerp(b[0], k)
	cam.rotation_degrees = (a[1] as Vector3).lerp(b[1], k)
	cam.fov = lerpf(a[2], b[2], k)
	if args.get("measure-cam", "") == "bottom":
		# Messkamera von unten (durch den Boden, der Hafen ist ausgeblendet), orthografisch, 2,0 m Bildhöhe:
		# Bild-x = Welt-x, die Sohlen beider Füße liegen getrennt (z ±0,125); 1 px = 2,78 mm
		cam.projection = Camera3D.PROJECTION_ORTHOGONAL
		cam.size = 2.0
		cam.position = Vector3(-1.95, -4.0, walker.PATH_Z)
		cam.rotation_degrees = Vector3(90.0, 0.0, 0.0)
	elif args.has("measure-cam"):
		# Messkamera: sieht den ganzen Laufweg (x -3,2 … -0,75 auf z 2,2) von vorn, ohne Fahrt
		cam.position = MEASURE_CAM_POS
		cam.rotation_degrees = Vector3.ZERO
		cam.fov = 44.0
	refl_cam.fov = cam.fov
	# Spiegelkamera: Lage an der Wasserfläche gespiegelt, Drehung S·R·S (S spiegelt y)
	var sm := Basis(Vector3(1, 0, 0), Vector3(0, -1, 0), Vector3(0, 0, 1))
	refl_cam.global_transform = Transform3D(sm * cam.global_basis * sm,
		Vector3(cam.global_position.x, 2.0 * WATER_Y - cam.global_position.y, cam.global_position.z))
	var th := tan(deg_to_rad(cam.fov) * 0.5)
	neon_mat.set_shader_parameter("cam_xform", Projection(cam.global_transform))
	neon_mat.set_shader_parameter("view_mat", Projection(cam.global_transform.affine_inverse()))
	neon_mat.set_shader_parameter("tan_half_fov", th)
	neon_mat.set_shader_parameter("px_rad", 2.0 * th / 720.0)


func _update_badger(_delta: float) -> void:
	walker.update(t)


# --- Rauch: Neonringe aus dem Schornstein ------------------------------------------------------
const SMOKE_PUFFS := 6
const SMOKE_LIFE := 4.2

func _build_smoke() -> void:
	var sphere := SphereMesh.new()
	sphere.radius = 0.5
	sphere.height = 1.0
	sphere.radial_segments = 24
	sphere.rings = 12
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	var anchor := harbor.find_child("ChimneySmoke", true, false) as Node3D
	_group_material("smoke")
	for i in SMOKE_PUFFS:
		var p := MeshInstance3D.new()
		p.mesh = sphere
		var m := (group_mats["smoke"] as ShaderMaterial).duplicate() as ShaderMaterial
		p.material_override = m
		$IdView/Smoke.add_child(p)
		p.global_position = anchor.global_position
		smoke.append(p)
		smoke_mats.append(m)
		smoke_jitter.append(Vector3(rng.randf_range(-0.12, 0.12), rng.randf_range(0.85, 1.15), rng.randf_range(-0.1, 0.1)))


func _update_smoke() -> void:
	var anchor := (harbor.find_child("ChimneySmoke", true, false) as Node3D).global_position
	for i in smoke.size():
		var age := fposmod(t + float(i) * SMOKE_LIFE / SMOKE_PUFFS, SMOKE_LIFE) / SMOKE_LIFE
		var j := smoke_jitter[i]
		smoke[i].global_position = anchor + Vector3(1.3 * age * age + j.x * age, 1.7 * age * j.y, j.z * age)
		var s := lerpf(0.2, 0.85, sqrt(age))
		smoke[i].scale = Vector3(s, s * 0.85, s)
		var vis := smoothstep(0.0, 0.1, age) * (1.0 - smoothstep(0.5, 1.0, age))
		smoke_mats[i].set_shader_parameter("fade", clampf(0.9 * (1.0 - vis), 0.0, 0.9))
		smoke[i].visible = vis > 0.05
