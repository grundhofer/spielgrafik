extends Node2D
## Sprite-Skalierung & Rasterstraße: Der Kai von Lornholm als Arcade-Straße.
## Je Bild: (1) Zeilenpass – Weltschritte von nah nach fern, Krümmung aufsummiert (dx += k·dz, x += dx·dz),
## projiziert; eine Bildzeile wird nur belegt, wenn sie oberhalb der bisher belegten liegt (Zeilenauswahl an der
## Kuppe). Ergebnis: Tabelle mit Mitte, Breite, s, Materialien je Bildzeile (lines, 5×224 RGBAF) für road.gdshader.
## (2) Sprites: Fässer, Kisten, Poller, Laternenpfähle, Boote, Häuschen werden aus ihrer Weltlage projiziert und
## stufenlos mit Nearest skaliert (Maßstab = Pixel je Meter am Ort / 40), Reihenfolge fern → nah.
## (3) Horizontebene (backdrop.gd) verschiebt sich mit dem aufsummierten Kurs.
## Benutzerargumente nach "--": --t0=<s>, --measure (nur Dachs auf Schwarz), --nostripes, --smooth (Sprites
## linear gefiltert), --nohill (Kuppe flach), --dump=<datei> (Zustand je Bild als JSON-Zeilen).

const W := 320
const H := 224
const HY := 106              # Horizontzeile (unendlich ferne Punkte)
const D := 220.0             # Brennweite in Pixeln (73° waagrecht)
const CAM_H := 1.72          # Augenhöhe über dem Boden unter dem Dachs (m)
const Z_B := 3.44            # Abstand Kamera → Dachs (m): Füße in Zeile 216
const FEET_Y := 216
const SPEED := 6.0           # m/s
const ROAD_HW := 2.2         # halbe Kaibreite (m)
const KERB := 0.35           # Kantenstein (m)
const S_JETTY := 60.0        # ab hier Holzsteg mit Wasser auf beiden Seiten
const S_END := 230.0         # Ende des Stegs, dahinter nur Meer
const PPM := 40.0            # Speicherdichte der Requisiten (Pixel je Meter in der größten Stufe)
const WALK_FPS := 10.0
const WALK_SEQ := [0, 1, 2, 1]
const LEAN_GAIN := 300.0     # Versatz der Kopfzeile in Texeln je 1/m Krümmung
const POSTER_T := 3.9

# Krümmung je Abschnitt [von, bis, k in 1/m]; an den Enden 6 m Rampe
const CURVES := [
	[-30.0, 14.0, 0.012],
	[22.0, 60.0, -0.011],
	[66.0, 108.0, 0.010],
	[116.0, 170.0, -0.007],
]
const RAMP := 6.0
# Buckel im Kai (Brücke über die Hafenschleuse): Höhe 1,1 m zwischen 24 und 46 m
const HUMP_A := 24.0
const HUMP_B := 46.0
const HUMP_H := 1.1

var t := 0.0
var t0 := 0.0
var s_cam := 0.0
var heading := 0.0
var cam_e := 0.0
var lean := 0.0
var walk_frame := 0
var tick := 0
var measure := false
var no_stripes := false
var smooth := false
var no_hill := false
var dump_path := ""
var dump_file: FileAccess

var spr: Dictionary = {}          # Name → Daten aus sprites.json
var tex: Dictionary = {}          # Name → Texture2D
var props: Array = []             # {kind, s, x, flip, node, halo?, phase}
var puffs: Array = []
var line_img: Image
var line_tex: ImageTexture
var samp_s := PackedFloat64Array()
var samp_y := PackedFloat64Array()
var samp_cx := PackedFloat64Array()
var samp_clip := PackedFloat64Array()
var flicker: PackedFloat32Array = PackedFloat32Array()
var hidden_from := -1.0          # Kuppe: erster und letzter verdeckter Weltschritt (s in m) dieses Bildes
var hidden_to := -1.0
var crest_row := -1.0
var lantern_level := 1.0
var window_level := 1.0
var lh_level := 0.0
var key_lantern := Color()
var key_window := Color()
var key_lh := Color()

@onready var road: ColorRect = $Road
@onready var sky: ColorRect = $Sky
@onready var objs: Node2D = $Objs
@onready var badger: Sprite2D = $Badger
@onready var shadow: Sprite2D = $Shadow
@onready var backdrop: Node2D = $Backdrop
@onready var beam: Node2D = $Beam
@onready var ui: Node2D = $UI

var badger_tex: Array = []
var badger_pad := 6


static func q5(c: Color) -> Color:
	## auf 15-Bit-RGB (5 Bit je Kanal) runden, als 8-Bit-Wert k·255/31
	return Color8(roundi(roundi(c.r * 31.0) * 255.0 / 31.0), roundi(roundi(c.g * 31.0) * 255.0 / 31.0),
		roundi(roundi(c.b * 31.0) * 255.0 / 31.0))


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a == "--measure":
			measure = true
		elif a == "--nostripes":
			no_stripes = true
		elif a == "--smooth":
			smooth = true
		elif a == "--nohill":
			no_hill = true
		elif a.begins_with("--dump="):
			dump_path = a.substr(7)
	if dump_path != "":
		dump_file = FileAccess.open(dump_path, FileAccess.WRITE)
	spr = JSON.parse_string(FileAccess.get_file_as_string("res://data/sprites.json"))
	var k: Array = spr["keys"]["lantern"]
	key_lantern = Color8(int(k[0]), int(k[1]), int(k[2]))
	k = spr["keys"]["window"]
	key_window = Color8(int(k[0]), int(k[1]), int(k[2]))
	k = spr["keys"]["lighthouse"]
	key_lh = Color8(int(k[0]), int(k[1]), int(k[2]))
	for n in ["barrel", "crates", "bollard", "post", "rope", "parcel", "boat_a", "boat_b", "cottage"]:
		tex[n] = load("res://art/%s.png" % n)
	_make_flicker()
	_make_sky()
	_make_road()
	_make_badger()
	_place_props()
	backdrop.setup(self)
	beam.setup(self)
	ui.setup(self)
	if measure:
		sky.visible = false
		road.visible = false
		backdrop.visible = false
		beam.visible = false
		objs.visible = false
		shadow.visible = false
		ui.visible = false
	_update(0.0)


func _make_flicker() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 1986
	var v := 0.85
	for i in 15 * 400:
		v = clampf(v + rng.randf_range(-0.22, 0.22), 0.55, 1.0)
		if rng.randf() < 0.06:
			v = 0.5
		flicker.append(v)


# ---------------------------------------------------------------- Strecke

func curv(s: float) -> float:
	for c in CURVES:
		if s > c[0] and s < c[1]:
			return c[2] * clampf((s - c[0]) / RAMP, 0.0, 1.0) * clampf((c[1] - s) / RAMP, 0.0, 1.0)
	return 0.0


func elev(s: float) -> float:
	if no_hill or s <= HUMP_A or s >= HUMP_B:
		return 0.0
	return HUMP_H * 0.5 * (1.0 - cos(TAU * (s - HUMP_A) / (HUMP_B - HUMP_A)))


func left_mat(s: float) -> float:
	return 0.0 if s > S_JETTY else 1.0      # 0 Wasser, 1 Gras


func surface(s: float) -> float:
	return 1.0 if s > S_JETTY else 0.0      # 0 Pflaster, 1 Planken


# ---------------------------------------------------------------- Himmel, Straße, Farben

func _make_sky() -> void:
	var keys := [[0, Color8(20, 12, 52)], [34, Color8(42, 24, 90)], [58, Color8(86, 40, 120)],
		[76, Color8(160, 58, 120)], [90, Color8(226, 96, 92)], [99, Color8(250, 146, 72)],
		[104, Color8(255, 200, 100)], [106, Color8(255, 224, 140)]]
	var img := Image.create(1, H, false, Image.FORMAT_RGBA8)
	for y in H:
		var c: Color = keys[-1][1]
		for i in keys.size() - 1:
			if y >= keys[i][0] and y < keys[i + 1][0]:
				var f := float(y - keys[i][0]) / float(keys[i + 1][0] - keys[i][0])
				c = (keys[i][1] as Color).lerp(keys[i + 1][1], f)
				break
		img.set_pixel(0, y, q5(c))
	(sky.material as ShaderMaterial).set_shader_parameter("sky", ImageTexture.create_from_image(img))


func pal_color(i: int) -> Color:
	var p := [Color8(184, 148, 156), Color8(140, 108, 132), Color8(234, 216, 208), Color8(92, 74, 112),
		Color8(78, 136, 60), Color8(52, 100, 50), Color8(0, 0, 0), Color8(0, 0, 0),
		Color8(192, 122, 72), Color8(154, 90, 54), Color8(74, 42, 36), Color8(214, 186, 182),
		Color8(255, 236, 170), Color8(106, 60, 44), Color8(24, 32, 82), Color8(120, 92, 116)]
	return q5(p[i])


func water_cols(z: float) -> Array:
	## Wasserfarbe hell/dunkel nach Entfernung: nah tiefblau, mittel violett, am Horizont Spiegelung des Abendrots
	var near_a := Color8(46, 76, 164)
	var near_b := Color8(32, 54, 128)
	var mid_a := Color8(88, 70, 158)
	var mid_b := Color8(64, 50, 128)
	var far_a := Color8(236, 128, 98)
	var far_b := Color8(178, 86, 112)
	var f := clampf(log(maxf(z, 1.0) / 12.0) / log(10.0), 0.0, 1.0)     # 12 m → 0, 120 m → 1
	var g := clampf((z - 140.0) / 300.0, 0.0, 1.0)
	var a := near_a.lerp(mid_a, f).lerp(far_a, g)
	var b := near_b.lerp(mid_b, f).lerp(far_b, g)
	return [q5(a), q5(b)]


func _make_road() -> void:
	line_img = Image.create(5, H, false, Image.FORMAT_RGBAF)
	line_tex = ImageTexture.create_from_image(line_img)
	var pimg := Image.create(16, 1, false, Image.FORMAT_RGBA8)
	for i in 16:
		pimg.set_pixel(i, 0, pal_color(i))
	var m := road.material as ShaderMaterial
	m.set_shader_parameter("lines", line_tex)
	m.set_shader_parameter("pal", ImageTexture.create_from_image(pimg))
	m.set_shader_parameter("stripes", not no_stripes)


func compute_lines() -> int:
	## Zeilenpass. Gibt die Zahl der Straßenzeilen zurück.
	cam_e = elev(s_cam + Z_B) + CAM_H
	for r in H:
		line_img.set_pixel(0, r, Color(0, 0, 0, 0))
	samp_s.clear()
	samp_y.clear()
	samp_cx.clear()
	samp_clip.clear()
	var maxy := float(H)
	var z := 0.8
	var x := 0.0
	var dx := 0.0
	var py := HY + (cam_e - elev(s_cam + z)) * D / z
	var pcx := W * 0.5
	var road_rows := 0
	hidden_from = -1.0
	hidden_to = -1.0
	crest_row = -1.0
	samp_s.append(s_cam + z)
	samp_y.append(py)
	samp_cx.append(pcx)
	samp_clip.append(maxy)
	while true:
		var dz := 0.2 + z * 0.012
		var z2 := z + dz
		var s2 := s_cam + z2
		if s2 > S_END:
			break
		dx += curv(s_cam + z + dz * 0.5) * dz
		x += dx * dz
		var y2 := HY + (cam_e - elev(s2)) * D / z2
		var cx2 := W * 0.5 + x * D / z2
		samp_s.append(s2)
		samp_y.append(y2)
		samp_cx.append(cx2)
		samp_clip.append(maxy)
		if y2 < maxy:
			var top := maxi(ceili(y2 - 0.5), 0)
			var bot := mini(ceili(minf(py, maxy) - 0.5) - 1, H - 1)
			for r in range(top, bot + 1):
				var f := (r + 0.5 - py) / (y2 - py)
				var iz := lerpf(1.0 / z, 1.0 / z2, f)     # 1/z ist linear in der Bildzeile
				var zz := 1.0 / iz
				var ss := s_cam + zz
				var cx := lerpf(pcx, cx2, f)
				var ppm := D * iz
				line_img.set_pixel(0, r, Color(cx, ROAD_HW * ppm, KERB * ppm, 1.0))
				line_img.set_pixel(1, r, Color(ss, zz, left_mat(ss), 0.0))
				line_img.set_pixel(2, r, Color(surface(ss), ppm, 0.0, 0.0))
				var wc := water_cols(zz)
				line_img.set_pixel(3, r, wc[0])
				line_img.set_pixel(4, r, wc[1])
				road_rows += 1
			maxy = y2
		elif maxy < H:
			if hidden_from < 0.0:
				hidden_from = s2
				crest_row = maxy
			hidden_to = s2
		z = z2
		py = y2
		pcx = cx2
	# Zeilen über der fernsten Straße bis zum Horizont: offenes Meer auf Höhe 0
	for r in range(HY, mini(ceili(maxy - 0.5), H)):
		var zs := cam_e * D / (r + 0.5 - HY)
		line_img.set_pixel(0, r, Color(0, 0, 0, 2.0))
		line_img.set_pixel(1, r, Color(s_cam + zs, zs, 0.0, 0.0))
		line_img.set_pixel(2, r, Color(0, D / zs, 0, 0))
		var wc := water_cols(zs)
		line_img.set_pixel(3, r, wc[0])
		line_img.set_pixel(4, r, wc[1])
	line_tex.update(line_img)
	return road_rows


func project(s: float) -> Array:
	## [Straßenmitte x, Grundzeile y, Pixel je Meter, Abschneidezeile] für einen Punkt bei s, oder []
	var z := s - s_cam
	if z < 0.9 or s > S_END:
		return []
	var i := samp_s.bsearch(s)
	if i <= 0 or i >= samp_s.size():
		return []
	var f := (s - samp_s[i - 1]) / (samp_s[i] - samp_s[i - 1])
	var cx := lerpf(samp_cx[i - 1], samp_cx[i], f)
	var y := HY + (cam_e - elev(s)) * D / z
	return [cx, y, D / z, samp_clip[i]]


# ---------------------------------------------------------------- Sprites

func _new_prop_material(key: Color = Color(-1, -1, -1)) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = preload("res://shaders/prop.gdshader")
	m.set_shader_parameter("key1", Vector3(key.r, key.g, key.b) if key.r >= 0.0 else Vector3(-1, -1, -1))
	m.set_shader_parameter("use_linear", smooth)
	return m


func _add(kind: String, s: float, x: float, flip := false, phase := 0.0) -> Dictionary:
	var n := Sprite2D.new()
	n.texture = tex[kind]
	n.centered = false
	var sz: Vector2 = tex[kind].get_size()
	n.offset = Vector2(-sz.x * 0.5, -sz.y)
	n.flip_h = flip
	var key := Color(-1, -1, -1)
	if kind == "post":
		key = key_lantern
	elif kind == "cottage":
		key = key_window
	n.material = _new_prop_material(key)
	if smooth:
		(n.material as ShaderMaterial).set_shader_parameter("lin_tex", tex[kind])
	objs.add_child(n)
	var p := {"kind": kind, "s": s, "x": x, "flip": flip, "node": n, "phase": phase, "w": sz.x, "h": sz.y}
	if kind == "post":
		var hn := Sprite2D.new()
		hn.texture = _halo_tex()
		var m := ShaderMaterial.new()
		m.shader = preload("res://shaders/halo.gdshader")
		hn.material = m
		objs.add_child(hn)
		p["halo"] = hn
	props.append(p)
	return p


var _halo: ImageTexture
func _halo_tex() -> ImageTexture:
	## gestufter Lichthof: drei Ringe, additiv; Radius 16 px bei 40 px/m
	if _halo:
		return _halo
	var r := 16
	var img := Image.create(2 * r + 1, 2 * r + 1, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	var rings := [[15.5, Color8(48, 26, 6)], [11.0, Color8(84, 50, 12)], [6.5, Color8(132, 92, 30)]]
	for y in 2 * r + 1:
		for x in 2 * r + 1:
			var d := Vector2(x - r, y - r).length()
			for ring in rings:
				if d <= ring[0]:
					img.set_pixel(x, y, ring[1])
	_halo = ImageTexture.create_from_image(img)
	return _halo


func _place_props() -> void:
	# Kai (Gras links, Wasser rechts): Laternenpfähle links, Poller rechts an der Kante
	for s in [6.0, 22.0, 38.0, 54.0]:
		_add("post", s, -(ROAD_HW + KERB + 0.25))
	var s2 := 3.0
	while s2 < S_JETTY:
		_add("bollard", s2, ROAD_HW + 0.25)
		s2 += 7.0
	_add("rope", 9.5, ROAD_HW - 0.45)
	_add("barrel", 12.0, -3.4)
	_add("barrel", 12.7, -4.1)
	_add("crates", 16.5, -3.9)
	_add("cottage", 36.5, -7.4)
	_add("barrel", 27.0, -3.3)
	_add("crates", 41.0, -3.6)
	_add("parcel", 45.0, -0.75)
	_add("boat_a", 27.0, 6.2, false, 0.0)
	_add("boat_b", 49.0, 6.6, false, 1.7)
	# Steg: Pfähle mit Laternen auf beiden Seiten, Boote links und rechts
	var s3 := S_JETTY + 8.0
	var side := 1.0
	while s3 < S_END - 4.0:
		_add("post", s3, side * (ROAD_HW + KERB + 0.15), side > 0.0)
		s3 += 15.0
		side = -side
	_add("boat_b", 82.0, -6.0, true, 0.6)
	_add("boat_a", 108.0, 6.2, false, 2.2)
	_add("boat_b", 145.0, -6.4, true, 4.0)
	# Rauch: 9 Wolken über dem Schornstein
	for i in 9:
		var n := Sprite2D.new()
		n.centered = true
		n.material = _new_prop_material()
		objs.add_child(n)
		puffs.append(n)
	_make_puff_textures()


var puff_tex: Array = []
func _make_puff_textures() -> void:
	## Rauchballen in drei Größen (12, 16, 20 px bei 40 px/m), zwei Töne und Kontur
	for r in [6, 8, 10]:
		var img := Image.create(2 * r + 2, 2 * r + 2, false, Image.FORMAT_RGBA8)
		img.fill(Color(0, 0, 0, 0))
		for y in 2 * r + 2:
			for x in 2 * r + 2:
				var d := Vector2(x - r - 0.5, y - r - 0.5).length()
				if d <= r:
					var c := q5(Color8(150, 134, 176))
					if d > r - 1.2:
						c = q5(Color8(78, 62, 104))
					elif x + y < 2 * r - 1 and d < r - 2.5:
						c = q5(Color8(196, 176, 200))
					img.set_pixel(x, y, c)
		puff_tex.append(ImageTexture.create_from_image(img))
	for i in puffs.size():
		(puffs[i] as Sprite2D).texture = puff_tex[0]


func _make_badger() -> void:
	var b: Dictionary = spr["badger"]
	for i in 3:
		var src: Image = (load("res://art/badger_%d.png" % i) as Texture2D).get_image()
		src.convert(Image.FORMAT_RGBA8)
		var img := Image.create(src.get_width() + 2 * badger_pad, src.get_height(), false, Image.FORMAT_RGBA8)
		img.fill(Color(0, 0, 0, 0))
		img.blit_rect(src, Rect2i(Vector2i.ZERO, src.get_size()), Vector2i(badger_pad, 0))
		badger_tex.append(ImageTexture.create_from_image(img))
	badger.texture = badger_tex[0]
	badger.centered = false
	var sh := Image.create(41, 7, false, Image.FORMAT_RGBA8)
	sh.fill(Color(1, 1, 1, 0))
	for y in 7:
		for x in 41:
			if Vector2((x - 20) / 20.5, (y - 3) / 3.5).length() <= 1.0:
				sh.set_pixel(x, y, Color8(120, 110, 140))
	shadow.texture = ImageTexture.create_from_image(sh)
	shadow.centered = true


# ---------------------------------------------------------------- Ablauf

func _process(delta: float) -> void:
	t += delta
	_update(delta)


func _update(delta: float) -> void:
	var tt := t + t0 + 1e-6
	var s_prev := s_cam
	s_cam = SPEED * tt
	# Kurs: Kamera bleibt tangential zur Straße; der Horizont wandert um den Kurswechsel
	if delta > 0.0:
		heading += curv(0.5 * (s_prev + s_cam) + Z_B) * (s_cam - s_prev)
	else:
		heading = _heading_at(s_cam)
	tick = int(floor(tt * 15.0))
	lantern_level = flicker[tick % flicker.size()]
	window_level = 0.9 + 0.1 * flicker[(tick * 7 + 31) % flicker.size()]
	var rows := compute_lines()
	var rm := road.material as ShaderMaterial
	rm.set_shader_parameter("wave", tt * 1.6)
	rm.set_shader_parameter("tick", tick)
	_update_badger(tt)
	var vis := _update_props(tt)
	beam.refresh(tt)
	backdrop.refresh(tt)
	ui.refresh(tt)
	if dump_file:
		dump_file.store_line(JSON.stringify({"t": snappedf(tt, 0.0001), "s": snappedf(s_cam, 0.001),
			"heading": snappedf(heading, 0.00001), "lean": lean, "frame": walk_frame, "rows": rows,
			"hidden": [snappedf(hidden_from, 0.01), snappedf(hidden_to, 0.01), snappedf(crest_row, 0.01)],
			"sprites": vis}))


func _heading_at(s_end: float) -> float:
	var h := 0.0
	var s := 0.0
	var step := 0.05
	while s < s_end:
		h += curv(s + step * 0.5 + Z_B) * step
		s += step
	return h


func _update_badger(tt: float) -> void:
	walk_frame = WALK_SEQ[int(floor(tt * WALK_FPS)) % 4]
	badger.texture = badger_tex[walk_frame]
	var hc: float = spr["badger"]["head_cx"][walk_frame]
	var sz: Vector2 = badger.texture.get_size()
	badger.offset = Vector2(-(badger_pad + roundf(hc)), -sz.y)
	lean = clampf(roundf(curv(s_cam + Z_B) * LEAN_GAIN), -4.0, 4.0)
	var m := badger.material as ShaderMaterial
	m.set_shader_parameter("lean", lean)
	m.set_shader_parameter("tex_size", sz)
	# Dachs läuft auf der Straßenmitte; in Kurven liegt sie bei Z_B leicht seitlich
	var p := project(s_cam + Z_B)
	var bx := W * 0.5
	if not p.is_empty():
		bx = p[0]
	badger.position = Vector2(roundf(bx), FEET_Y)
	badger.z_index = 3000 - int(Z_B * 8.0)
	shadow.position = Vector2(roundf(bx), FEET_Y - 1)
	shadow.z_index = badger.z_index - 1
	if measure:
		badger.position = Vector2(W * 0.5, FEET_Y)


func _update_props(tt: float) -> Array:
	var vis: Array = []
	var lc := q5(Color8(210, 120, 30).lerp(Color8(255, 246, 150), lantern_level))
	var wc := q5(Color8(200, 120, 40).lerp(Color8(255, 214, 96), window_level))
	for p in props:
		var n: Sprite2D = p["node"]
		var pr := project(p["s"])
		var halo: Sprite2D = p.get("halo")
		if pr.is_empty():
			n.visible = false
			if halo:
				halo.visible = false
			continue
		var ppm: float = pr[2]
		var sc := ppm / PPM
		var x: float = pr[0] + float(p["x"]) * ppm
		var y: float = pr[1]
		var hpx: float = p["h"] * sc
		var wpx: float = p["w"] * sc
		var on: bool = hpx >= 1.5 and x + wpx * 0.5 > -2.0 and x - wpx * 0.5 < W + 2.0 and y - hpx < pr[3]
		n.visible = on
		if halo:
			halo.visible = on
		if not on:
			continue
		if p["kind"].begins_with("boat"):
			y += roundf(sin(tt * 1.7 + p["phase"]) * 0.07 * ppm)      # Boote wippen
		n.position = Vector2(roundf(x), roundf(y))
		n.scale = Vector2(sc, sc)
		var zi := clampi(3000 - int((p["s"] - s_cam) * 8.0), 1, 3990)
		n.z_index = zi
		var m := n.material as ShaderMaterial
		m.set_shader_parameter("clip_y", pr[3])
		if p["kind"] == "post":
			m.set_shader_parameter("key1_col", Vector3(lc.r, lc.g, lc.b))
			var lamp: Array = spr["points"]["post_lamp"]
			var lx: float = (lamp[0] - p["w"] * 0.5) * (-1.0 if p["flip"] else 1.0)
			var ly: float = p["h"] - lamp[1]
			halo.position = Vector2(roundf(x + lx * sc), roundf(y - ly * sc))
			halo.scale = Vector2(sc, sc)
			halo.z_index = zi - 1
			var hm := halo.material as ShaderMaterial
			hm.set_shader_parameter("clip_y", pr[3])
			hm.set_shader_parameter("gain", 0.55 + 0.6 * lantern_level)
		elif p["kind"] == "cottage":
			m.set_shader_parameter("key1_col", Vector3(wc.r, wc.g, wc.b))
			_update_smoke(tt, x, y, sc, zi, pr[3])
		vis.append([p["kind"], snappedf(p["s"] - s_cam, 0.01), snappedf(sc, 0.0001), roundi(x), roundi(y),
			snappedf(pr[3], 0.1)])
	return vis


func _update_smoke(tt: float, x: float, y: float, sc: float, zi: int, clip: float) -> void:
	var ch: Array = spr["points"]["cottage_chimney"]
	var cw: float = spr["cottage"]["size"][0]
	var chh: float = spr["cottage"]["size"][1]
	var ox: float = (ch[0] - cw * 0.5) * sc
	var oy: float = (chh - ch[1]) * sc
	var life := 3.0
	for i in puffs.size():
		var n: Sprite2D = puffs[i]
		var age := fmod(tt + i * life / puffs.size(), life)
		var size_i := 0 if age < 0.8 else (1 if age < 1.9 else 2)
		if age > 2.7:
			size_i = 1
		n.texture = puff_tex[size_i]
		var wob := sin(age * 2.3 + i) * 0.12
		var px: float = x + ox + (-0.45 * age + wob) * PPM * sc
		var py: float = y - oy - (0.25 + 0.55 * age) * PPM * sc
		n.position = Vector2(roundf(px), roundf(py))
		n.scale = Vector2(sc, sc)
		n.z_index = zi + 1
		n.visible = sc * 12.0 >= 1.5
		(n.material as ShaderMaterial).set_shader_parameter("clip_y", clip)
