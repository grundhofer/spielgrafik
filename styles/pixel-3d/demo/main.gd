extends Node
## Pixel-3D: echtes 3D in niedriger Auflösung (428×242, sichtbar 426⅔×240), Nearest ×3 auf 1280×720.
##
## - Materialien des Hafens und des Dachses werden per Name durch p3d_toon (drei harte Töne) ersetzt,
##   das Wasser durch p3d_water; Konturen, Kantenlicht und Nebel macht p3d_post in Renderauflösung.
## - Kamera: Projektion FRUSTUM. Der Schwenk ist eine Objektivverschiebung (frustum_offset) um ganze
##   Renderpixel; der Rest (Drittelpixel) wird beim Hochskalieren als Versatz des Sprite2D gezeigt.
##   So verschiebt sich das Bild beim Schwenken nur als Ganzes, statt an allen Kanten zu flimmern.
## - Palette: palette.gdshader rastet jedes Pixel auf palette.png ein (scripts/build_palette.py).
## - Alles hängt an der aufsummierten Zeit t und an festen Seeds (zwei Aufnahmen: Bilder 1–179 bitgleich,
##   Bild 0 in 0,02 % der Pixel anders).
##
## Schalter (nach "--" an Godot): --no-snap --no-outline --no-highlight --no-fog --no-palette
## --no-toon --freeze (nur die Kamera fährt) --debug-edges (Konturen rot, Kantenlicht grün)
## --dump=<Ordner> (Render- und Fensterbilder als PNG) --measure (Pan und Fußknochen des Dachses je Bild)
## --mask (Dachs weiß, Rest schwarz, für die Messung).

# --- Bild ---------------------------------------------------------------------------------------
const RW := 428
const RH := 242
const SCALE := 3
const BASE_OX := 1.0 / 3.0       # Restversatz 0: sichtbare Spalte 0 = Renderspalte 1/3
const BASE_OY := 1.0

# --- Kamera (Werte aus scripts/frame.py) -------------------------------------------------------
const CAM_POS := Vector3(-0.9, 1.5, 6.5)
const CAM_PITCH := -1.8          # Grad
const CAM_YAW := 0.0
const CAM_FOV := 52.0            # vertikal, für die 242 Renderzeilen
const PAN_FOLLOW := 0.7          # Anteil der Dachsbewegung, dem der Schwenk folgt
const PAN_END := 12.0            # Objektivverschiebung am Ende (Renderpixel): Laterne ganz im Bild

# --- Dachs ---------------------------------------------------------------------------------------
const WALK_SPEED := 0.367        # m/s bei speed_scale 1 (badger_notes.md)
const WALK_RATE := 2.0
const START_X := -4.9
const BADGER_Z := 1.2
const BRAKE_T := 2.85
const BRAKE_TIME := 0.4
const IDLE_T := 3.2
const TURN_T := 3.3
const TURN_TIME := 0.45
const WAVE_T := 3.85
const WAVE_LEN := 1.5

# --- Umgebung --------------------------------------------------------------------------------------
const BEAM_PERIOD := 8.0
const BEAM_FACING_T := 6.3       # Strahl zeigt zur Kamera (nach der Aufnahme; im Poster quer über den Himmel)
const SEED := 20261011

## Materialien mit Flächennormalen (Gelände: Facetten statt runder Verläufe)
const FLAT := ["Rock", "Sand", "Grass"]

var t := 0.0
var walk_rate := WALK_RATE
var phase := 0
var boats := {}
var toon_mats := {}
var lantern_mat: ShaderMaterial
var lamp_mat: ShaderMaterial
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0
var water_mat: ShaderMaterial
var post_mat: ShaderMaterial
var halo_lantern: ShaderMaterial
var halo_lamp: ShaderMaterial
var badger_x_end := 0.0
var px_near := 0.0
var pan := 0.0

# Schalter
var opt := {"snap": true, "outline": true, "highlight": true, "fog": true, "palette": true, "toon": true,
	"freeze": false, "dump": "", "measure": false, "mask": false, "debug_edges": false}

@onready var world: SubViewport = $World
@onready var harbor: Node3D = $World/Harbor
@onready var badger: Node3D = $World/Badger
@onready var player: AnimationPlayer = $World/Badger/AnimationPlayer
@onready var camera: Camera3D = $World/Camera
@onready var rotor: Node3D = $World/Attach/LighthouseLight/Rotor
@onready var lantern_omni: OmniLight3D = $World/Attach/LanternLight/Omni
@onready var lamp_omni: OmniLight3D = $World/Attach/LighthouseLight/Omni
@onready var screen: Sprite2D = $Screen
@onready var ui_screen: Sprite2D = $UIScreen
@onready var ui: Control = $UIView/UI


func _ready() -> void:
	_parse_args()
	screen.texture = world.get_texture()
	ui_screen.texture = ($UIView as SubViewport).get_texture()
	ui_screen.position = Vector2(0, 0)

	var pal_mat := ShaderMaterial.new()
	pal_mat.shader = preload("res://shaders/palette.gdshader")
	var pal_tex: Texture2D = load("res://palette.png") if ResourceLoader.exists("res://palette.png") else null
	if pal_tex:
		pal_mat.set_shader_parameter("palette", pal_tex)
		pal_mat.set_shader_parameter("count", pal_tex.get_width())
	pal_mat.set_shader_parameter("enabled", 1.0 if (opt.palette and pal_tex != null) else 0.0)
	screen.material = pal_mat

	# Konturen: Forward+ mit Normalenpuffer (Kantenlicht), sonst nur aus der Tiefe. Der Shader steht nicht
	# in der .tscn, weil hint_normal_roughness_texture in Mobile/Compatibility nicht kompiliert.
	post_mat = ShaderMaterial.new()
	post_mat.render_priority = -10
	if RenderingServer.get_current_rendering_method() == "forward_plus":
		post_mat.shader = load("res://shaders/p3d_post.gdshader")
	else:
		post_mat.shader = load("res://shaders/p3d_post_depth.gdshader")
	($World/Camera/Post as MeshInstance3D).set_surface_override_material(0, post_mat)
	post_mat.set_shader_parameter("outlines", 1.0 if opt.outline else 0.0)
	post_mat.set_shader_parameter("highlights", 1.0 if opt.highlight else 0.0)
	post_mat.set_shader_parameter("fog", 1.0 if opt.fog else 0.0)
	post_mat.set_shader_parameter("debug_edges", 1.0 if opt.debug_edges else 0.0)

	_setup_camera()
	_apply_styles()
	_attach_to_empties()
	_build_halos()

	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform

	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.play("Walk")
	player.speed_scale = WALK_RATE
	if opt.freeze:
		player.speed_scale = 0.0
	badger.position = Vector3(START_X, 0.012, BADGER_Z)
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		mi.layers = 2
	var to_light := Vector3(-0.55, 0.5, 0.67).normalized()
	($World/FigureLight as DirectionalLight3D).transform = Transform3D(Basis.looking_at(-to_light, Vector3.UP), Vector3.ZERO)
	badger_x_end = _walk_x(IDLE_T)

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0

	var to_cam := camera.global_position - rotor.global_position
	beam_yaw0 = atan2(-to_cam.x, -to_cam.z) - TAU * BEAM_FACING_T / BEAM_PERIOD

	if opt.mask:
		_apply_mask()
	if opt.dump != "":
		DirAccess.make_dir_recursive_absolute(opt.dump)
		RenderingServer.frame_post_draw.connect(_dump_frame)
	if opt.measure:
		# nach dem Zeichnen messen: dann gelten Pose und Lage, die im Bild zu sehen sind
		RenderingServer.frame_post_draw.connect(_measure)
	_update(0.0)


func _parse_args() -> void:
	for a in OS.get_cmdline_user_args():
		match a:
			"--no-snap": opt.snap = false
			"--no-outline": opt.outline = false
			"--no-highlight": opt.highlight = false
			"--no-fog": opt.fog = false
			"--no-palette": opt.palette = false
			"--no-toon": opt.toon = false
			"--freeze": opt.freeze = true
			"--measure": opt.measure = true
			"--debug-edges": opt.debug_edges = true
			"--mask": opt.mask = true
			_:
				if a.begins_with("--dump="):
					opt.dump = a.substr(7)


func _process(delta: float) -> void:
	t += delta
	_update(delta)


func _update(delta: float) -> void:
	var ta := 0.0 if opt.freeze else t       # Zeit für Umgebung und Figur
	var da := 0.0 if opt.freeze else delta
	RenderingServer.global_shader_parameter_set("p3d_time", ta)
	_update_badger(da)
	_update_camera()

	var k := 0
	for b in boats:
		var ph := 1.7 * k
		var roll := deg_to_rad(2.4) * sin(TAU * ta / 3.4 + ph)
		var pitch := deg_to_rad(1.0) * sin(TAU * ta / 4.6 + 0.8 + ph)
		var heave := 0.035 * sin(TAU * ta / 3.9 + 2.1 + ph)
		var local := Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		(harbor.get_node(b) as Node3D).transform = boats[b] * local
		k += 1

	# Laterne flackert in Stufen (Rauschen mit festem Seed, 10 Werte pro Sekunde)
	var tf := floorf(ta * 10.0) / 10.0
	var f := 0.82 + 0.2 * lantern_noise.get_noise_1d(tf * 7.0) + 0.08 * lantern_noise.get_noise_1d(tf * 31.0 + 50.0)
	lantern_omni.light_energy = 1.8 * f
	lantern_mat.set_shader_parameter("emission_energy", 0.8 + 0.25 * f)
	halo_lantern.set_shader_parameter("pulse", clampf((f - 0.75) * 2.5, 0.0, 1.0))
	water_mat.set_shader_parameter("lamp0_gain", 1.0 if f > 0.7 else 0.0)

	# Leuchtfeuer dreht sich; Lampe blitzt, wenn der Strahl zur Kamera zeigt.
	rotor.rotation.y = beam_yaw0 + TAU * ta / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position).normalized()
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), 16.0)
	lamp_mat.set_shader_parameter("emission_energy", 1.0 + 0.8 * facing)
	lamp_omni.light_energy = 2.0 + 4.0 * facing
	halo_lamp.set_shader_parameter("pulse", facing)

	ui.set_time(t)


# --- Kamera ------------------------------------------------------------------------------------------
func _setup_camera() -> void:
	camera.projection = Camera3D.PROJECTION_FRUSTUM
	camera.keep_aspect = Camera3D.KEEP_HEIGHT
	camera.size = 2.0 * camera.near * tan(deg_to_rad(CAM_FOV) / 2.0)
	px_near = camera.size / RH
	camera.transform = Transform3D(Basis.from_euler(Vector3(deg_to_rad(CAM_PITCH), deg_to_rad(CAM_YAW), 0.0)), CAM_POS)
	var lv: Vector3 = camera.global_basis.inverse() * (-($World/Sun as Node3D).global_basis.z)
	post_mat.set_shader_parameter("light_view", -lv.normalized())


## Objektivverschiebung in Renderpixeln: positiv = Bildinhalt wandert nach links.
func _pan_for(x: float) -> float:
	var f := (RH / 2.0) / tan(deg_to_rad(CAM_FOV) / 2.0)
	var depth := CAM_POS.z - BADGER_Z
	return PAN_END + (x - badger_x_end) * f / depth * PAN_FOLLOW


func _update_camera() -> void:
	pan = _pan_for(_walk_x(t))
	var ip := floorf(pan)
	var sub := floorf((pan - ip) * SCALE) / SCALE
	if opt.snap:
		camera.frustum_offset = Vector2(ip * px_near, 0.0)
		screen.position = Vector2(-SCALE * (BASE_OX + sub), -SCALE * BASE_OY)
		RenderingServer.global_shader_parameter_set("p3d_pan", Vector2(ip, 0.0))
	else:
		# Vergleich: Verschiebung stufenlos in der Projektion, kein Restversatz
		camera.frustum_offset = Vector2(pan * px_near, 0.0)
		screen.position = Vector2(-SCALE * BASE_OX, -SCALE * BASE_OY)
		RenderingServer.global_shader_parameter_set("p3d_pan", Vector2(roundf(pan), 0.0))


# --- Dachs -------------------------------------------------------------------------------------------
func _brake_factor(tt: float) -> float:
	return 1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, tt)


## Weg des Dachses bis Zeit tt (Integral von Tempo × Bremsfaktor; smoothstep integriert sich zu u - u³ + u⁴/2).
## Die Kamera folgt diesem Wert, damit sie auch mit --freeze dieselbe Fahrt macht.
func _walk_x(tt: float) -> float:
	var v := WALK_SPEED * WALK_RATE
	if tt <= BRAKE_T:
		return START_X + v * tt
	var u := clampf((tt - BRAKE_T) / BRAKE_TIME, 0.0, 1.0)
	return START_X + v * (BRAKE_T + BRAKE_TIME * (u - u * u * u + 0.5 * u * u * u * u))


func _update_badger(delta: float) -> void:
	if opt.freeze:
		return
	if phase == 0:
		walk_rate = WALK_RATE * _brake_factor(t)
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
	badger.rotation.y = -PI / 2.0 * smoothstep(TURN_T, TURN_T + TURN_TIME, t)


# --- Materialien ---------------------------------------------------------------------------------
func _apply_styles() -> void:
	water_mat = ShaderMaterial.new()
	water_mat.shader = preload("res://shaders/p3d_water.gdshader")
	water_mat.render_priority = 0
	var sky_mat := (($World/WorldEnvironment as WorldEnvironment).environment.sky.sky_material) as ShaderMaterial
	for p in ["c0", "c1", "c2", "c3", "c4", "c5", "c6", "bands_deg", "bands_deg2"]:
		var v: Variant = sky_mat.get_shader_parameter(p)
		if v != null:
			water_mat.set_shader_parameter(p, v)
	for root in [harbor, badger]:
		for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
			for i in mi.mesh.get_surface_count():
				var src := mi.mesh.surface_get_material(i) as StandardMaterial3D
				if src == null:
					push_error("%s: Fläche %d ohne glTF-Material" % [mi.name, i])
					continue
				if src.resource_name == "Water":
					mi.set_surface_override_material(i, water_mat)
				else:
					mi.set_surface_override_material(i, _toon_material(src))
	(harbor.get_node("Sea") as MeshInstance3D).extra_cull_margin = 1.0
	# Leuchtende Teile: je Objekt eine eigene Kopie (Laterne flackert, Lampe blitzt)
	lantern_mat = _unique(harbor.find_child("LanternGlass", true, false))
	lamp_mat = _unique(harbor.find_child("LighthouseLamp", true, false))
	for glass in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
		(harbor.find_child(glass, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


func _toon_material(src: StandardMaterial3D) -> ShaderMaterial:
	var key := src.resource_name
	if not toon_mats.has(key):
		var m := ShaderMaterial.new()
		m.shader = preload("res://shaders/p3d_toon.gdshader")
		m.set_shader_parameter("albedo", src.albedo_color)
		m.set_shader_parameter("smooth_light", 0.0 if opt.toon else 1.0)
		m.set_shader_parameter("flat_normals", key in FLAT)
		if key in FLAT:
			m.set_shader_parameter("band_hi", 0.55)
		if key == "Rock":
			m.set_shader_parameter("pattern", 0.26)
		if src.emission_enabled:
			m.set_shader_parameter("albedo", Color.BLACK)
			m.set_shader_parameter("emission", Color("ffc86e"))
			m.set_shader_parameter("emission_energy", 1.0)
		toon_mats[key] = m
	return toon_mats[key]


func _unique(node: Node) -> ShaderMaterial:
	var mi := node as MeshInstance3D
	var m := (mi.get_surface_override_material(0) as ShaderMaterial).duplicate() as ShaderMaterial
	mi.set_surface_override_material(0, m)
	return m


func _attach_to_empties() -> void:
	for holder in $World/Attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt in harbor.glb" % holder.name)
			continue
		for c in holder.get_children():
			c.reparent(target, false)


func _halo(parent: Node3D, size: float, color: Color, offset: Vector3) -> ShaderMaterial:
	var q := QuadMesh.new()
	q.size = Vector2(size, size)
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/p3d_halo.gdshader")
	m.render_priority = 11
	m.set_shader_parameter("color", color)
	var mi := MeshInstance3D.new()
	mi.mesh = q
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.position = offset
	parent.add_child(mi)
	return m


func _build_halos() -> void:
	halo_lantern = _halo(harbor.find_child("LanternLight", true, false), 0.8, Color(1.0, 0.75, 0.4), Vector3.ZERO)
	halo_lamp = _halo(harbor.find_child("LighthouseLight", true, false), 2.6, Color(1.0, 0.85, 0.55), Vector3.ZERO)


# --- Prüfen ------------------------------------------------------------------------------------------
func _apply_mask() -> void:
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color.WHITE
	var black := StandardMaterial3D.new()
	black.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	black.albedo_color = Color.BLACK
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		mi.material_override = white
	for mi: GeometryInstance3D in harbor.find_children("*", "GeometryInstance3D", true, false):
		mi.material_override = black
	($World/WorldEnvironment as WorldEnvironment).environment.background_mode = Environment.BG_COLOR
	($World/WorldEnvironment as WorldEnvironment).environment.background_color = Color.BLACK
	post_mat.set_shader_parameter("outlines", 0.0)
	post_mat.set_shader_parameter("highlights", 0.0)
	post_mat.set_shader_parameter("fog", 0.0)
	(screen.material as ShaderMaterial).set_shader_parameter("enabled", 0.0)
	ui.visible = false
	(harbor.find_child("Beam", true, false) as Node3D).visible = false
	for h in find_children("*", "MeshInstance3D", true, false):
		if (h as MeshInstance3D).material_override is ShaderMaterial and \
				((h as MeshInstance3D).material_override as ShaderMaterial).shader == preload("res://shaders/p3d_halo.gdshader"):
			h.visible = false


## Bildlage (sichtbares 426⅔×240-Bild) von Kopf und Füßen des Dachses
func _measure() -> void:
	var skel := badger.find_child("Skeleton3D", true, false) as Skeleton3D
	var out := {"frame": Engine.get_process_frames(), "t": snappedf(t, 0.0001), "pan": snappedf(pan, 0.0001),
		"sx": screen.position.x}
	for bone in ["foot.L", "foot.R", "head"]:
		var idx := skel.find_bone(bone)
		var gp := skel.global_transform * skel.get_bone_global_pose(idx)
		var pts := {"heel": gp.origin}
		if bone.begins_with("foot"):
			pts["toe"] = gp * Vector3(0.0, 0.12, 0.0)
		for k in pts:
			var sp := camera.unproject_position(pts[k])
			var vis := _visible_xy(sp)
			out["%s.%s" % [bone, k]] = [snappedf(vis.x, 0.01), snappedf(vis.y, 0.01), snappedf(pts[k].x, 0.0001), snappedf(pts[k].y, 0.0001)]
	print("MEASURE ", JSON.stringify(out))


## Renderpixel -> Pixel im sichtbaren Bild (mit Restversatz)
func _visible_xy(sp: Vector2) -> Vector2:
	return Vector2(sp.x + screen.position.x / SCALE, sp.y + screen.position.y / SCALE)


func _dump_frame() -> void:
	var img := world.get_texture().get_image()
	var k := Engine.get_process_frames()
	img.save_png("%s/r%04d.png" % [opt.dump, k])
	var full := get_viewport().get_texture().get_image()
	full.save_png("%s/f%04d.png" % [opt.dump, k])
