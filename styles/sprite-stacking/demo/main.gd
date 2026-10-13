extends Node2D
## Sprite-Stacking: der Hafen von Lornholm aus übereinandergelegten Pixel-Schichten.
##
## Jedes Modell ist ein Stapel von Querschnitten (stacks/<name>.png, aus Voxeln gebaut von
## scripts/build_stacks.py). Jede Schicht ist ein Sprite2D, um ihre Höhe nach oben versetzt und mit Modell plus
## Kamera gedreht. Gezeichnet wird global nach Höhe (z_index = Schicht): bei diesem Blickwinkel ist das die
## richtige Reihenfolge für alle Modelle zugleich, ohne Sortierung nach Objekten.
## Alles hängt an der aufsummierten Zeit t und festen Seeds (deterministisch).
##
## Schalter nach "--": --static-cam (Kamera fest auf 0°), --mask (nur der Dachs, Schichtnummer als Farbe, für
## scripts/measure_badger.py), --no-shadows (ohne Schlagschatten), --flat (ohne Normalenlicht, Vergleich),
## --ysort (klassische Sortierung je Objekt nach Bildzeile statt global nach Schichthöhe, Vergleich),
## --stats (Zahl der Schicht-Sprites, Draw Calls und Rechenzeit der Platzierung bei Bild 60).

const Z0 := 100                      # z_index der Schicht 0; Wasser liegt darunter
const STACKS := "res://stacks/"

var cfg: Dictionary
var layer_h := 0.75
var sun := Vector3(-0.74, 0.3, 0.6)
var shadow_step := Vector2(0.6, 0.0)       # Weltversatz des Schlagschattens je Schicht Höhe
var t := 0.0
var theta := 0.0
var cs := Vector2(1, 0)
var pivot := Vector2(213, 96)
var center := Vector2(213, 96)
var res := {}                        # Stackname -> {tex, mat, smat, info}
var items: Array = []
var groups := {}                     # Schattenebene -> CanvasGroup
var args := PackedStringArray()
var frame_no := 0
var place_usec := 0                  # --stats: Rechenzeit der Schichtplatzierung
var mask_max := 999                  # --mask-layers=N: im Messbild nur Schichten 0..N des Dachses

var badger_walk: StackItem
var badger_idle: StackItem
var badger_wave: StackItem
var boat_a: StackItem
var boat_b: StackItem
var gulls: Array = []
var smoke: Array = []
var cottage: StackItem
var lantern: StackItem
var lighthouse: StackItem
var beam: Polygon2D
var halos := {}
var noise := FastNoiseLite.new()
var silhouette: Shader
var world_map: Texture2D
var terrain_rect: Vector4
var shadow_mats := {}                # Schattenebene -> ShaderMaterial

@onready var world: Node2D = $World
@onready var shadow_root: Node2D = $Shadows
@onready var fx: Node2D = $Effects


class StackItem:
	var name := ""
	var info: Dictionary
	var pos := Vector2.ZERO          # Welt (Rasterweiten = Bildpixel)
	var base := 0.0                  # Höhe des Bodenpunkts in Schichten
	var angle := 0.0                 # Drehung in der Welt (rad)
	var frame := 0
	var roll := Vector2.ZERO         # Versatz je Schicht in Modellkoordinaten (Schaukeln)
	var bob := 0.0                   # Heben in Schichten
	var shown := true
	var plane := -2                  # Schattenebene (oberste Geländeschicht), -1 = Wasser, -2 = kein Schatten
	var sprites: Array = []
	var shadow: Array = []
	var mask := false


func _ready() -> void:
	args = OS.get_cmdline_user_args()
	for a in args:
		if a.begins_with("--mask-layers="):
			mask_max = int(a.split("=")[1])
	cfg = JSON.parse_string(FileAccess.get_file_as_string(STACKS + "stacks.json"))
	layer_h = cfg.layer_h
	sun = Vector3(cfg.sun[0], cfg.sun[1], cfg.sun[2])
	shadow_step = Vector2(cfg.shadow_step[0], cfg.shadow_step[1])
	pivot = Vector2(cfg.layout.pivot[0], cfg.layout.pivot[1])
	center = Vector2(cfg.layout.center[0], cfg.layout.center[1])
	RenderingServer.global_shader_parameter_set("sun_dir", sun)
	RenderingServer.global_shader_parameter_set("cam_pivot", pivot)
	RenderingServer.global_shader_parameter_set("cam_center", center)
	RenderingServer.global_shader_parameter_set("flat_light", 1.0 if "--flat" in args else 0.0)
	RenderingServer.global_shader_parameter_set("mask_mode", 1.0 if "--mask" in args else 0.0)
	noise.seed = 7
	noise.frequency = 2.2
	var ramps: Texture2D = load(STACKS + "ramps.png")
	var wmap: Texture2D = load(STACKS + "water.png")
	var vshader: Shader = load("res://shaders/voxel.gdshader")
	var sshader: Shader = load("res://shaders/silhouette.gdshader")
	var trect := Vector4(cfg.terrain.x0, cfg.terrain.y0, cfg.terrain.w, cfg.terrain.h)
	for n in cfg.stacks:
		var m := ShaderMaterial.new()
		m.shader = vshader
		m.set_shader_parameter("normal_tex", load(STACKS + n + "_n.png"))
		m.set_shader_parameter("ramp_tex", ramps)
		m.set_shader_parameter("glow_start", int(cfg.glow_start))
		m.set_shader_parameter("dither", float(cfg.stacks[n].dither))
		res[n] = {"tex": load(STACKS + n + ".png"), "mat": m, "info": cfg.stacks[n]}
	silhouette = sshader
	world_map = wmap
	terrain_rect = trect
	var wm: ShaderMaterial = $Water.material
	wm.set_shader_parameter("world_map", wmap)
	wm.set_shader_parameter("world_rect", trect)
	build_scene()
	_process(0.0)


# ---------------------------------------------------------------- Aufbau
func add_stack(n: String, pos: Vector2, base: float, angle_deg: float, plane: int) -> StackItem:
	var it := StackItem.new()
	it.name = n
	it.info = res[n].info
	it.pos = pos
	it.base = base
	it.angle = deg_to_rad(angle_deg)
	it.plane = plane if not "--no-shadows" in args else -2
	for z in int(it.info.layers):
		var sp := Sprite2D.new()
		sp.texture = res[n].tex
		sp.region_enabled = true
		sp.centered = false
		sp.material = res[n].mat
		sp.z_as_relative = false
		world.add_child(sp)
		it.sprites.append(sp)
		if it.plane > -2:
			var sh := Sprite2D.new()
			sh.texture = res[n].tex
			sh.region_enabled = true
			sh.centered = false
			sh.material = shadow_mat(it.plane)
			shadow_group(it.plane).add_child(sh)
			it.shadow.append(sh)
	items.append(it)
	return it


func shadow_mat(plane: int) -> ShaderMaterial:
	if not shadow_mats.has(plane):
		var sm := ShaderMaterial.new()
		sm.shader = silhouette
		sm.set_shader_parameter("world_map", world_map)
		sm.set_shader_parameter("world_rect", terrain_rect)
		sm.set_shader_parameter("plane_h", float(plane))
		shadow_mats[plane] = sm
	return shadow_mats[plane]


func shadow_group(plane: int) -> CanvasGroup:
	if not groups.has(plane):
		var g := CanvasGroup.new()
		g.z_as_relative = false
		g.z_index = Z0 + plane         # nach der obersten Geländeschicht dieser Höhe, vor allem, was darauf steht
		var m := ShaderMaterial.new()
		m.shader = load("res://shaders/shadow_group.gdshader")
		g.material = m
		shadow_root.add_child(g)
		groups[plane] = g
	return groups[plane]


func build_scene() -> void:
	var q: int = cfg.layout.quay_h          # Oberfläche des Kais = Schicht q-1, Gegenstände ab Schicht q
	add_stack("terrain", Vector2.ZERO, 0, 0, -2)
	add_stack("jetty", Vector2(cfg.layout.jetty.x0, cfg.layout.jetty.y0), 0, 0, -1)
	cottage = add_stack("cottage", Vector2(36, 146), q, 0, q - 1)
	add_stack("barrel", Vector2(86, 150), q, 0, q - 1)
	add_stack("barrel", Vector2(98, 140), q, 35, q - 1)
	add_stack("crates", Vector2(306, 142), q, 0, q - 1)
	add_stack("rope", Vector2(178, 135), q, 20, q - 1)
	lantern = add_stack("lantern", Vector2(240, 133), q, 0, q - 1)
	for x in [140.0, 206.0, 316.0]:
		add_stack("bollard", Vector2(x, 123), q, 0, q - 1)
	add_stack("parcel", Vector2(214, 166), q, 15, q - 1)
	lighthouse = add_stack("lighthouse", Vector2(388, 114), 19, 0, 18)
	for d in cfg.decor:
		add_stack(d[0], Vector2(d[1], d[2]), d[3], d[4], d[3] - 1)
	boat_a = add_stack("boat_a", Vector2(226, 74), 0, -90, -1)
	boat_b = add_stack("boat_b", Vector2(304, 66), 0, -90, -1)
	badger_walk = add_stack("badger_walk", Vector2(150, 158), q, 0, q - 1)
	badger_idle = add_stack("badger_idle", Vector2(150, 158), q, 0, q - 1)
	badger_wave = add_stack("badger_wave", Vector2(150, 158), q, 0, q - 1)
	for b in [badger_walk, badger_idle, badger_wave]:
		b.mask = true
	for i in 2:
		gulls.append(add_stack("gull", Vector2.ZERO, 60, 0, -1))
	for i in 7:
		smoke.append(add_stack("smoke", Vector2.ZERO, 0, 0, -2))
	# Lichtkegel und Lichthöfe
	beam = Polygon2D.new()
	var bm := ShaderMaterial.new()
	bm.shader = load("res://shaders/beam.gdshader")
	beam.material = bm
	beam.z_as_relative = false
	beam.z_index = Z0 + 300
	beam.uv = PackedVector2Array([Vector2(0, 0), Vector2(1, -1), Vector2(1, 1)])
	fx.add_child(beam)
	var hs: Shader = load("res://shaders/halo.gdshader")
	for k in ["lantern", "window", "lamp"]:
		var r := ColorRect.new()
		var hm := ShaderMaterial.new()
		hm.shader = hs
		r.material = hm
		r.z_as_relative = false
		r.z_index = Z0 + 299
		r.mouse_filter = Control.MOUSE_FILTER_IGNORE
		fx.add_child(r)
		halos[k] = r
	if "--mask" in args:
		$Water.visible = false
		fx.visible = false
		shadow_root.visible = false
		$UI.visible = false


# ---------------------------------------------------------------- Abbildung Welt -> Bild
func rot(v: Vector2, c: Vector2) -> Vector2:
	return Vector2(c.x * v.x - c.y * v.y, c.y * v.x + c.x * v.y)


func w2s(w: Vector2) -> Vector2:
	return center + rot(w - pivot, cs)


func anchor(it: StackItem, key: String) -> Vector3:
	## Ankerpunkt eines Modells in Welt: xy in Rasterweiten, z in Schichten
	var a: Array = it.info.anchors[key]
	var p := it.pos + rot(Vector2(a[0], a[1]), Vector2(cos(it.angle), sin(it.angle)))
	return Vector3(p.x, p.y, it.base + it.bob + a[2])


func place(it: StackItem) -> void:
	var info: Dictionary = it.info
	var L: int = info.layers
	var pz: float = info.pivot_z
	var s := w2s(it.pos)
	var r := theta + it.angle
	var rcs := Vector2(cos(r), sin(r))
	var cells: Array = info.cells
	var step := shadow_step
	var mask_mode := "--mask" in args
	var ysort := "--ysort" in args
	for z in L:
		var sp: Sprite2D = it.sprites[z]
		var sh: Sprite2D = it.shadow[z] if it.shadow.size() > 0 else null
		var cell = cells[it.frame * L + z]
		var hz := float(z) - pz                   # Höhe über dem Bodenpunkt
		var h := roundf(it.base + it.bob + hz)    # absolute Schicht
		if cell == null or not it.shown or h < 0.0 or (mask_mode and (not it.mask or z > mask_max)):
			sp.visible = false
			if sh:
				sh.visible = false
			continue
		sp.visible = true
		sp.region_rect = Rect2(cell[0], cell[1], cell[2], cell[3])
		sp.offset = Vector2(cell[4], cell[5])
		sp.position = (s + rot(it.roll * hz, rcs) + Vector2(0, -h)).round()
		sp.rotation = r
		if ysort and it.name != "terrain":
			# Vergleich: klassisch je Objekt nach Bildzeile des Bodenpunkts sortiert (über allem Gelände,
			# unter Lichtkegel und Lichthöfen); Schichten eines Objekts in Baumreihenfolge
			sp.z_index = Z0 + 40 + clampi(int(floorf((s.y + 60.0) * 0.5)), 0, 240)
		else:
			sp.z_index = Z0 + int(h)
		sp.self_modulate = Color(h / 255.0, float(z) / 255.0, 0, 1)   # Höhe und Schicht für den Shader
		if sh:
			sh.visible = true
			sh.region_rect = sp.region_rect
			sh.offset = sp.offset
			var above := it.base + it.bob + hz + 0.5 - float(it.plane + 1)
			var po := float(maxi(it.plane, 0))
			sh.position = (s + rot(step * above + it.roll * hz, cs) + Vector2(0, -po)).round()
			sh.rotation = r


# ---------------------------------------------------------------- Ablauf
const WALK_FPS := 15.0
const WALK_FRAMES := 47                       # letztes Laufbild 46 % 8 = 6 (Durchgang, Beine fast beisammen)
const WALK_X0 := 150.0
const TURN_T0 := WALK_FRAMES / WALK_FPS
const WAVE_T0 := 3.7
const THETA0 := 22.0
const THETA1 := 7.0


func _process(delta: float) -> void:
	t += delta
	frame_no += 1
	# Kamera: dreht beim Betreten des Orts von THETA0 auf THETA1, zuletzt immer langsamer
	var k := clampf(t / 6.0, 0.0, 1.0)
	theta = deg_to_rad(lerpf(THETA0, THETA1, 1.0 - pow(1.0 - k, 2.2)))
	if "--static-cam" in args:
		theta = 0.0
	cs = Vector2(cos(theta), sin(theta))
	RenderingServer.global_shader_parameter_set("cam_cs", cs)
	RenderingServer.global_shader_parameter_set("sim_time", t)
	animate_badger()
	animate_boats()
	animate_gulls()
	animate_smoke()
	animate_lights()
	var t0 := Time.get_ticks_usec()
	for it in items:
		place(it)
	if "--stats" in args:
		place_usec += Time.get_ticks_usec() - t0
		if frame_no == 61:
			var n := 0
			for it in items:
				n += it.sprites.size() + it.shadow.size()
			print("STATS sprites=%d draw_calls=%d objects=%d place_ms_avg=%.3f" % [n,
				RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
				RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME),
				place_usec / 60000.0])
	if "--mask" in args:
		var b: StackItem = badger_walk if badger_walk.shown else (badger_wave if badger_wave.shown else badger_idle)
		print("MASK %d %.6f %.8f %s %d %.4f %.4f %.6f" % [frame_no, t, theta, b.name, b.frame, b.pos.x, b.pos.y, b.angle])


func animate_badger() -> void:
	var fi := int(floor(t * WALK_FPS + 1e-6))
	var walking := fi < WALK_FRAMES
	# Vorschub je Laufbild aus dem gemessenen Standfuß (stacks.json: walk_advance), Summe = 0,367 m je Zyklus
	var x := WALK_X0
	var adv: Array = cfg.walk_advance
	for k in mini(fi, WALK_FRAMES):
		x += float(adv[k % adv.size()])
	for b in [badger_walk, badger_idle, badger_wave]:
		b.pos = Vector2(x, 158)
		b.shown = false
	if walking:
		badger_walk.shown = true
		badger_walk.frame = fi % 8
		badger_walk.angle = 0.0
		return
	# Drehung zur Kamera in sechs Schritten (ein Schritt je Laufbild-Takt); Ziel = Blick zur Kamera bei etwa 10°
	var turn := clampf(floor((t - TURN_T0) * WALK_FPS) / 6.0, 0.0, 1.0)
	var ang := deg_to_rad(80.0) * turn
	var wave_i := int(floor((t - WAVE_T0) * 10.0 + 1e-6))
	if t >= WAVE_T0 and wave_i < 15:
		badger_wave.shown = true
		badger_wave.frame = wave_i
		badger_wave.angle = ang
	else:
		badger_idle.shown = true
		badger_idle.frame = int(floor((t - TURN_T0) * 6.0)) % 12
		badger_idle.angle = ang


func animate_boats() -> void:
	# Schaukeln: Gieren um die Festmachleine, Rollen als Schichtversatz quer zum Rumpf, Heben um ganze Schichten
	var ya := deg_to_rad(-90.0 + 4.0 * sin(t * 0.9))
	boat_a.angle = ya
	boat_a.roll = Vector2(0, 0.10 * sin(t * 1.7))
	boat_a.bob = roundf(0.7 * sin(t * 1.7 + 0.6))
	var yb := deg_to_rad(-90.0 - 5.0 * sin(t * 0.8 + 1.3))
	boat_b.angle = yb
	boat_b.roll = Vector2(0, 0.14 * sin(t * 1.5 + 2.0))
	boat_b.bob = roundf(0.7 * sin(t * 1.5 + 2.6))
	RenderingServer.global_shader_parameter_set("boat_a", Vector4(boat_a.pos.x, boat_a.pos.y, ya, 52.0))
	RenderingServer.global_shader_parameter_set("boat_b", Vector4(boat_b.pos.x, boat_b.pos.y, yb, 46.0))


func animate_gulls() -> void:
	var spec := [[Vector2(160, 104), 46.0, 0.62, 0.0, 58.0], [Vector2(330, 56), 34.0, -0.8, 2.1, 72.0]]
	for i in gulls.size():
		var g: StackItem = gulls[i]
		var c: Vector2 = spec[i][0]
		var a: float = spec[i][3] + spec[i][2] * t
		g.pos = c + Vector2(cos(a), sin(a)) * spec[i][1]
		g.angle = a + (PI / 2.0 if spec[i][2] > 0.0 else -PI / 2.0)
		g.base = spec[i][4] + 3.0 * sin(t * 1.1 + i)
		# Flügelschlag mit Gleitphasen: 10 Bilder/s, Muster oben-Mitte-unten-Mitte
		var f := int(floor(t * 10.0 + i * 3))
		var glide := fmod(t + i * 1.3, 2.6) > 1.5
		g.frame = 1 if glide else [0, 1, 2, 1][f % 4]


func animate_smoke() -> void:
	var top := anchor(cottage, "top")
	var life := 2.6
	for i in smoke.size():
		var p: StackItem = smoke[i]
		var age := fmod(t + i * (life / smoke.size()), life)
		var u := age / life
		p.pos = Vector2(top.x, top.y) + Vector2(12.0 * age + 3.0 * age * age, -2.0 * age)
		p.base = top.z + 1.0 + 10.0 * age
		p.frame = clampi(int(floor(1.0 + u * 7.0)), 0, 5) if u < 0.75 else clampi(int(floor((1.0 - u) * 20.0)), 0, 5)
		p.angle = u * 2.0


func animate_lights() -> void:
	# Laterne: Rauschen mit festem Seed; Fenster ruhig; Leuchtfeuer blitzt, wenn der Strahl zur Kamera zeigt
	var fl := 0.72 + 0.28 * noise.get_noise_1d(t * 1.0)
	fl = clampf(fl + 0.12 * noise.get_noise_1d(t * 7.0 + 30.0), 0.35, 1.0)
	var beam_a := 0.9 + t * TAU / 5.0
	var toward := cos(beam_a - (PI / 2.0 - theta))
	var flash := clampf((toward - 0.82) / 0.18, 0.0, 1.0)
	var lamp_lvl := 0.72 + 0.28 * flash
	RenderingServer.global_shader_parameter_set("glow_levels", Vector3(0.86, fl, lamp_lvl))
	var lp := anchor(lantern, "glow")
	var wp := anchor(cottage, "glow_south")
	var mp := anchor(lighthouse, "glow")
	RenderingServer.global_shader_parameter_set("light_lantern", Vector4(lp.x, lp.y, lp.z * layer_h, 1.45 * fl))
	RenderingServer.global_shader_parameter_set("light_window", Vector4(wp.x, wp.y + 6.0, wp.z * layer_h, 0.55))
	RenderingServer.global_shader_parameter_set("light_lamp", Vector4(mp.x, mp.y, mp.z * layer_h, 0.5 + 0.4 * flash))
	# Lichtkegel: waagrecht in Lampenhöhe, dreht in der Welt
	var lamp_s := w2s(Vector2(mp.x, mp.y)) - Vector2(0, mp.z)
	var dir := Vector2(cos(beam_a), sin(beam_a))
	var side := Vector2(-dir.y, dir.x)
	var length := 190.0
	var p1 := rot(dir * length + side * length * 0.2, cs)
	var p2 := rot(dir * length - side * length * 0.2, cs)
	beam.polygon = PackedVector2Array([lamp_s, lamp_s + p1, lamp_s + p2])
	beam.uv = PackedVector2Array([Vector2(0, 0), Vector2(1, -1), Vector2(1, 1)])
	set_halo("lantern", w2s(Vector2(lp.x, lp.y)) - Vector2(0, lp.z), 16.0, 0.6 + 0.6 * fl)
	set_halo("window", w2s(Vector2(wp.x, wp.y)) - Vector2(0, wp.z), 9.0, 0.7)
	set_halo("lamp", lamp_s, 9.0 + 7.0 * flash, 0.65 + 0.6 * flash)


func set_halo(k: String, p: Vector2, r: float, i: float) -> void:
	var h: ColorRect = halos[k]
	h.position = (p - Vector2(r, r)).round()
	h.size = Vector2(2.0 * r, 2.0 * r).round()
	h.set_instance_shader_parameter("intensity", i)
