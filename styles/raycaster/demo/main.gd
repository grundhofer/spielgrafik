extends Node2D
## Raycaster-Eintrag (2,5D-Sektor-Shooter 1993–1996): Hafen von Lornholm in Ego-Perspektive.
##
## Die Sektorkarte (map/lornholm.json, erzeugt von scripts/build_map.py) wird hier zu Meshes je Textur.
## Licht: Lichtstufe je Sektor in einer 256x1-Textur, jedes Bild neu (Flackern, Leuchtfeuer), dazu
## Abdunklung nach Entfernung über die Farbtabelle (shaders/rc_common.gdshaderinc).
## Figuren und Dekorationen sind Billboard-Sprites; der Dachs hat 8 Blickwinkel.
## Alles hängt an der aufsummierten Zeit t (deterministisch mit --fixed-fps 30).

const SECTOR_SHADER := preload("res://shaders/sector.gdshader")
const SPRITE_SHADER := preload("res://shaders/sprite.gdshader")
const COLORMAP := preload("res://colormap.png")
const PALETTE := preload("res://palette.png")
const TPM := 32.0
const EYE := 1.45                       # Augenhöhe über dem Boden (m)
const STEP := 0.0918                    # Vorschub je Laufbild: 0,367 m je Zyklus / 4 Bilder

@onready var view: SubViewport = $View
@onready var cam: Camera3D = $View/Camera
@onready var level_root: Node3D = $View/Level
@onready var things_root: Node3D = $View/Things
@onready var screen: TextureRect = $Screen

var t := 0.0
var frame := 0
var sectors: Array = []
var sector_id := {}
var base_light := PackedByteArray()
var cur_light := PackedByteArray()
var light_img: Image
var light_tex: ImageTexture
var water_mat: ShaderMaterial
var water_tex: Array = []
var sprite_info: Dictionary = {}
var sprite_mats := {}
var sprite_meshes := {}
var flicker := PackedInt32Array()
var badger: MeshInstance3D
var lantern_glow: MeshInstance3D
var parcel: MeshInstance3D
var smoke: Array = []
var gulls: Array = []
var flare: MeshInstance3D
const LAMP := Vector3(10.2, 12.05, -25.6)   # Mitte des Laternenhauses
var yaw_right := 0.0
var pickup_t := 4.9
var args := {}


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else ""
	var map: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://map/lornholm.json"))
	sectors = map["sectors"]
	for i in sectors.size():
		sector_id[sectors[i]["name"]] = i
		base_light.append(int(sectors[i]["light"]))
	cur_light = base_light.duplicate()
	cur_light.resize(256)
	light_img = Image.create_from_data(256, 1, false, Image.FORMAT_L8, cur_light)
	light_tex = ImageTexture.create_from_image(light_img)
	_build_level(map["surfaces"])
	sprite_info = JSON.parse_string(FileAccess.get_file_as_string("res://sprites/sprites.json"))
	_build_things(map["things"])
	# Feuerflackern wie die Sektoreffekte: alle 4 Tics (hier alle 3 Bilder = 0,1 s) neuer Zufallswert 0–3
	var rng := RandomNumberGenerator.new()
	rng.seed = 1993
	for i in 400:
		flicker.append(rng.randi() & 3)
	screen.texture = view.get_texture()
	if args.has("t0"):
		t = float(args["t0"])
	if args.has("measure"):
		# Messaufbau für scripts/measure_badger.py: nur der Dachs, feste Kamera seitlich vom Laufweg
		level_root.visible = false
		$HUD.visible = false
	_update(0.0)


func _process(delta: float) -> void:
	if args.has("still"):
		t = float(args["still"])
	else:
		t += delta
	frame += 1
	_update(delta)


# ---------------------------------------------------------------------------------------------
# Karte

func _build_level(surfaces: Dictionary) -> void:
	for tex_name in surfaces:
		var s: Dictionary = surfaces[tex_name]
		var v: Array = s["v"]
		var uv: Array = s["uv"]
		var uv2: Array = s["uv2"]
		var verts := PackedVector3Array()
		var uvs := PackedVector2Array()
		var uv2s := PackedVector2Array()
		for i in range(0, v.size(), 3):
			verts.append(Vector3(v[i], v[i + 1], v[i + 2]))
		for i in range(0, uv.size(), 2):
			uvs.append(Vector2(uv[i], uv[i + 1]))
			uv2s.append(Vector2(uv2[i], uv2[i + 1]))
		var arr := []
		arr.resize(Mesh.ARRAY_MAX)
		arr[Mesh.ARRAY_VERTEX] = verts
		arr[Mesh.ARRAY_TEX_UV] = uvs
		arr[Mesh.ARRAY_TEX_UV2] = uv2s
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
		var mat := ShaderMaterial.new()
		mat.shader = SECTOR_SHADER
		mat.set_shader_parameter("tex", load("res://textures/%s.png" % tex_name))
		mat.set_shader_parameter("colormap", COLORMAP)
		mat.set_shader_parameter("palette", PALETTE)
		mat.set_shader_parameter("sector_light", light_tex)
		var mi := MeshInstance3D.new()
		mi.name = "S_" + tex_name
		mi.mesh = mesh
		mi.material_override = mat
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.extra_cull_margin = 2.0
		level_root.add_child(mi)
		if tex_name == "water0":
			water_mat = mat
	for i in 4:
		water_tex.append(load("res://textures/water%d.png" % i))


func floor_at(sec: int, x: float, z: float) -> float:
	var f: Array = sectors[sec]["floor"]
	return f[0] + f[1] * x + f[2] * z


func _point_in(loop: Array, x: float, z: float) -> bool:
	var c := false
	var n := loop.size()
	for i in n:
		var a: Array = loop[i]
		var b: Array = loop[(i + 1) % n]
		if (a[1] > z) != (b[1] > z) and x < a[0] + (z - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
			c = not c
	return c


func sector_at(x: float, z: float) -> int:
	var best := -1
	var bh := -1e9
	for i in sectors.size():
		var s: Dictionary = sectors[i]
		if not _point_in(s["loop"], x, z):
			continue
		var hole := false
		for h in s["holes"]:
			if _point_in(h, x, z):
				hole = true
				break
		if hole:
			continue
		var fh := floor_at(i, x, z)
		if fh > bh:
			bh = fh
			best = i
	return best


# ---------------------------------------------------------------------------------------------
# Sprites

func _sprite_mesh(w: float, h: float, ox: float, oy: float) -> ArrayMesh:
	var l := -ox / TPM
	var r := (w - ox) / TPM
	var top := oy / TPM
	var bot := -(h - oy) / TPM
	var verts := PackedVector3Array([Vector3(l, top, 0), Vector3(r, top, 0), Vector3(r, bot, 0),
		Vector3(l, top, 0), Vector3(r, bot, 0), Vector3(l, bot, 0)])
	var uvs := PackedVector2Array([Vector2(0, 0), Vector2(1, 0), Vector2(1, 1), Vector2(0, 0), Vector2(1, 1), Vector2(0, 1)])
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = verts
	arr[Mesh.ARRAY_TEX_UV] = uvs
	var m := ArrayMesh.new()
	m.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	return m


func _sprite_mat(tex_name: String) -> ShaderMaterial:
	if not sprite_mats.has(tex_name):
		var m := ShaderMaterial.new()
		m.shader = SPRITE_SHADER
		m.set_shader_parameter("atlas", load("res://sprites/%s.png" % tex_name))
		m.set_shader_parameter("colormap", COLORMAP)
		m.set_shader_parameter("palette", PALETTE)
		sprite_mats[tex_name] = m
	return sprite_mats[tex_name]


func make_sprite(kind: String, tex_name: String, pos: Vector3, full := false) -> MeshInstance3D:
	var info: Dictionary = sprite_info[kind]
	var w: float
	var h: float
	if info.has("cell"):
		w = info["cell"][0]
		h = info["cell"][1]
	else:
		w = info["size"][0]
		h = info["size"][1]
	var key := "%s_%d_%d" % [kind, w, h]
	if not sprite_meshes.has(key):
		sprite_meshes[key] = _sprite_mesh(w, h, info["origin"][0], info["origin"][1])
	var mi := MeshInstance3D.new()
	mi.name = kind
	mi.mesh = sprite_meshes[key]
	mi.material_override = _sprite_mat(tex_name)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.position = pos
	mi.set_instance_shader_parameter("frame_rect", Vector4(0, 0, w, h))
	mi.set_instance_shader_parameter("fullbright", 1.0 if full else 0.0)
	things_root.add_child(mi)
	return mi


func _build_things(list: Array) -> void:
	for th in list:
		var kind: String = th["kind"]
		var pos := Vector3(th["x"], th["y"], th["z"])
		var mi := make_sprite(kind, kind, pos)
		mi.set_meta("sector", int(th["sector"]))
		if kind == "lanternpost":
			# Glas als Vollhell-Sprite eine Handbreit vor dem Pfahl (zur Kamera hin, siehe _update)
			lantern_glow = make_sprite("lanternglow", "lanternglow0", pos, true)
			lantern_glow.set_meta("sector", int(th["sector"]))
			lantern_glow.set_meta("base", pos)
		if kind == "parcel":
			parcel = mi
	badger = make_sprite("badger", "badger_atlas", Vector3(3.0, 0, 2.2))
	for i in 6:
		var s := make_sprite("smoke0", "smoke0", Vector3.ZERO)
		s.set_meta("sector", sector_id["quay"])
		smoke.append(s)
	for i in 2:
		var g := make_sprite("gull0", "gull0", Vector3.ZERO)
		g.set_meta("sector", sector_id["plateau"])    # helleres Licht als das Meer: Möwen vor dem Abendhimmel
		gulls.append(g)
	# Lichtschein des Leuchtfeuers (vollhell), nur wenn der Strahl zur Kamera zeigt
	flare = make_sprite("flare", "flare", LAMP, true)


# ---------------------------------------------------------------------------------------------
# Zeitablauf

func _smooth(a: float, b: float, x: float) -> float:
	var u := clampf((x - a) / (b - a), 0.0, 1.0)
	return u * u * (3.0 - 2.0 * u)


## Weg der Kamera: Beschleunigen 0–0,4 s, gleichmäßig bis 3,0 s, Bremsen bis 3,6 s (geschlossene Formel)
func walk_dist(x: float) -> float:
	var a := 0.4
	var b := 3.0
	var c := 3.6
	if x <= 0.0:
		return 0.0
	if x < a:
		return 0.5 * x * x / a
	if x < b:
		return 0.5 * a + (x - a)
	if x < c:
		var u := x - b
		return 0.5 * a + (b - a) + u - 0.5 * u * u / (c - b)
	return 0.5 * a + (b - a) + 0.5 * (c - b)


func walk_speed(x: float) -> float:
	if x <= 0.0 or x >= 3.6:
		return 0.0
	if x < 0.4:
		return x / 0.4
	if x < 3.0:
		return 1.0
	return (3.6 - x) / 0.6


const CAM_A := Vector2(-1.6, 10.6)
const CAM_B := Vector2(-0.8, 5.4)


func camera_at(x: float) -> Dictionary:
	var d := walk_dist(x) / walk_dist(10.0)
	var p := CAM_A.lerp(CAM_B, d)
	var yaw := lerpf(-14.0, 4.0, _smooth(0.2, 3.9, x))
	# Wippen beim Gehen nur senkrecht, Stärke mit dem Quadrat der Geschwindigkeit (wie in den Shootern)
	var v := walk_speed(x)
	var bob := 0.04 * v * v * sin(TAU * x / 0.571)
	return {"pos": Vector3(p.x, EYE + bob, p.y), "yaw": yaw}


func _update(_delta: float) -> void:
	var n := int(round(t * 30.0))
	# Kamera
	var c := camera_at(t)
	if args.has("measure"):
		c = {"pos": Vector3(1.6, 0.5, 3.8), "yaw": 0.0}
	cam.position = c["pos"]
	yaw_right = deg_to_rad(c["yaw"])
	cam.rotation = Vector3(0.0, -yaw_right, 0.0)
	(screen.material as ShaderMaterial).set_shader_parameter("yaw", yaw_right)
	# Licht je Sektor
	cur_light = base_light.duplicate()
	cur_light.resize(256)
	var fl := flicker[int(n / 3) % flicker.size()]
	var lp: int = sector_id["lanternpool"]
	cur_light[lp] = maxi(base_light[lp] - 16 * fl, base_light[sector_id["quay"]])
	# Leuchtfeuer: Kennung "Blitz alle 3 s"; die Lampenwände gehören zum Sektor lh_tower
	var lh: int = sector_id["lh_tower"]
	var ph := fmod(t + 0.9, 3.0)
	var flash := ph < 0.2
	cur_light[lh] = 255 if flash else base_light[lh]
	flare.visible = flash
	var to_cam: Vector3 = (cam.position - LAMP) * Vector3(1, 0, 1)
	flare.position = LAMP + to_cam.normalized() * 1.0
	light_img.set_data(256, 1, false, Image.FORMAT_L8, cur_light)
	light_tex.update(light_img)
	# Wasser: 4 Bilder, 6 Bilder/s
	water_mat.set_shader_parameter("tex", water_tex[int(n / 5) % 4])
	# Laterne: Glasbild folgt dem Flackern
	lantern_glow.material_override = _sprite_mat("lanternglow%d" % fl)
	var glow_base: Vector3 = lantern_glow.get_meta("base")
	var cam_dir: Vector3 = (cam.position - glow_base) * Vector3(1, 0, 1)
	lantern_glow.position = glow_base + cam_dir.normalized() * 0.03
	_update_badger(n)
	_update_smoke()
	_update_gulls()
	if parcel:
		parcel.visible = t < pickup_t
	# Aufblitzen beim Aufheben: 5 Bilder (Doom: 6 Tics) Palettenzeile 1 über das ganze Bild
	$Flash.visible = t >= pickup_t and t < pickup_t + 0.17 and not args.has("measure")
	if args.has("measure"):
		for th in things_root.get_children():
			th.visible = th == badger
	for th in things_root.get_children():
		if th.has_meta("sector"):
			(th as MeshInstance3D).set_instance_shader_parameter("light", float(cur_light[int(th.get_meta("sector"))]))


func rot_index(pos: Vector3, facing_deg: float) -> int:
	var d := cam.position - pos
	var yaw_to_cam := rad_to_deg(atan2(-d.z, d.x))
	var rel := fposmod(yaw_to_cam - facing_deg + 22.5, 360.0)
	return int(rel / 45.0) % 8


func _update_badger(n: int) -> void:
	var poses: Array = sprite_info["badger"]["poses"]
	var cw: int = sprite_info["badger"]["cell"][0]
	var ch: int = sprite_info["badger"]["cell"][1]
	var step := int(floor(t * 10.0))            # 10 Laufbilder je Sekunde (je 3 Bilder bei 30 fps)
	var pose := "idle0"
	var facing := 180.0
	var x := 3.0
	if step < 30:
		pose = "walk%d" % (step % 4)
		x = 3.0 - STEP * step
	else:
		x = 3.0 - STEP * 30
		if t >= 3.4:
			facing = 270.0
		elif t >= 3.2:
			facing = 225.0
		if t >= 3.6 and t < 5.6:
			pose = "wave%d" % (int(floor((t - 3.6) * 3.0)) % 2)
	var pos := Vector3(x, 0.0, 2.2)
	var sec := sector_at(pos.x, pos.z)
	pos.y = floor_at(sec, pos.x, pos.z)
	badger.position = pos
	badger.set_meta("sector", sec)
	var r := rot_index(pos, facing)
	var row := poses.find(pose)
	badger.set_instance_shader_parameter("frame_rect", Vector4(r * cw, row * ch, cw, ch))


func _update_smoke() -> void:
	# Rauchwolken: alle 0,5 s eine neue, steigt 0,5 m/s, treibt nach Osten, 4 Bilder je 0,6 s
	var origin := Vector3(-6.5, 5.15, -3.55)
	var k := 0
	var newest := int(floor(t / 0.5))
	for i in range(newest - 5, newest + 1):      # Wolken der letzten 2,4 s, beliebig lange
		var born := 0.5 * i
		var age := t - born
		if age < 0.0 or age >= 2.4 or k >= smoke.size():
			continue
		var s: MeshInstance3D = smoke[k]
		k += 1
		s.visible = true
		s.position = origin + Vector3(0.28 * age + 0.05 * sin(i * 1.7), 0.5 * age, -0.1 * age)
		var f := mini(int(age / 0.6), 3)
		s.material_override = _sprite_mat("smoke%d" % f)
	for j in range(k, smoke.size()):
		smoke[j].visible = false


func _update_gulls() -> void:
	for i in gulls.size():
		var g: MeshInstance3D = gulls[i]
		var a := t * (0.35 + 0.08 * i) + i * 2.4
		g.position = Vector3(1.0 + 5.0 * cos(a) + 3.0 * i, 5.2 + 1.0 * i + 0.3 * sin(a * 2.0), -10.0 + 3.0 * sin(a))
		g.material_override = _sprite_mat("gull%d" % (int(floor(t * 5.0 + i)) % 2))    # 5 Bilder/s
