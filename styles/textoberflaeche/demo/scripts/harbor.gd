extends Node2D
## Der gemalte Hafen von Lornholm als wiederverwendbare Szene: Gemälde, Licht- und Wasser-Animationen,
## Rauch, Möwen und der Dachs-Kurier. Jede Oberfläche instanziert sie und zeigt einen Ausschnitt davon.
## Alle Lagen kommen aus art/scene.json (von scripts/prep.py aus dem Gemälde ausgemessen), in Pixeln
## des auf 640 px Breite verkleinerten Gemäldes. Alles hängt nur von der aufsummierten Zeit t ab.

@export var show_badger := true
@export var show_parcel := false

const SEED := 20261010

var t := 0.0
var cfg: Dictionary
var parcel: Sprite2D
var parcel_shadow: Sprite2D
var lamp_glow: Sprite2D
var lamp_core: Sprite2D
var beam: Sprite2D
var lantern_glow: Sprite2D
var lantern_core: Sprite2D
var window_glow: Sprite2D
var smoke: Array[Sprite2D] = []
var glints: Array[Dictionary] = []
var gulls: Array[Dictionary] = []

# Dachs als Schnittfigur (aus scene.json → badger, walk): Wurzel auf der Fußlinie unter der Hüfte,
# darin fernes Bein, nahes Bein, Rumpf. Die Beine drehen um die Hüfte; das Standbein rollt über Ferse und Zehe,
# und die Hüfthöhe folgt daraus, so bleibt der Standfuß rechnerisch fest auf dem Pflaster.
var badger: Node2D
var body: Sprite2D
var legs: Array[Sprite2D] = []   # [nah, fern]
var shadow: Sprite2D
var heel: Vector2
var toe: Vector2
var walk: Dictionary
var leg_off: Array[float] = [0.0, 0.0]

var add_mat := CanvasItemMaterial.new()
var flicker_rng := RandomNumberGenerator.new()
var flicker: PackedFloat32Array = []   # vorab gewürfeltes Flackern, 30 Werte pro Sekunde


func _ready() -> void:
	cfg = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene.json"))
	add_mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	var bg := Sprite2D.new()
	bg.texture = load("res://art/" + cfg.bg.file)
	bg.centered = false
	add_child(bg)
	flicker_rng.seed = SEED
	for i in 30 * 8:
		flicker.append(flicker_rng.randf())
	_build_lights()
	_build_glints()
	_build_smoke()
	_build_gulls()
	if show_parcel:
		_build_parcel()
	if show_badger:
		_build_badger()
	if "--mask" in OS.get_cmdline_user_args():
		_mask_mode()
	_update()


func _process(delta: float) -> void:
	t += delta
	_update()


func v2(a: Array) -> Vector2:
	return Vector2(a[0], a[1])


func glow_texture(size: int, falloff: float) -> GradientTexture2D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, falloff, 1.0])
	g.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 0.35), Color(1, 1, 1, 0)])
	var tex := GradientTexture2D.new()
	tex.gradient = g
	tex.width = size
	tex.height = size
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	return tex


func _sprite(tex: Texture2D, pos: Vector2, col: Color, additive: bool, sc := 1.0) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = tex
	s.position = pos
	s.modulate = col
	s.scale = Vector2(sc, sc)
	if additive:
		s.material = add_mat
	add_child(s)
	return s


func _build_lights() -> void:
	var a: Dictionary = cfg.anchors
	var soft := glow_texture(128, 0.18)
	# Fenster: warmer, ruhiger Schein (Lasur in normaler Mischung).
	window_glow = _sprite(soft, v2(a.window), Color(1.0, 0.72, 0.36, 0.28), false, 0.42)
	# Laterne: Lasur plus kleiner additiver Kern.
	lantern_glow = _sprite(soft, v2(a.lantern), Color(1.0, 0.74, 0.38, 0.32), false, 0.62)
	lantern_core = _sprite(soft, v2(a.lantern), Color(1.0, 0.80, 0.45, 0.55), true, 0.16)
	# Leuchtturm: Strahl (aus prep.py) dreht sich um die Lampe, Lampe blitzt auf, wenn er zur Kamera zeigt.
	beam = Sprite2D.new()
	beam.texture = load("res://art/beam.png")
	beam.centered = false
	beam.offset = Vector2(0, -beam.texture.get_height() / 2.0)
	beam.position = v2(a.lamp)
	beam.material = add_mat
	add_child(beam)
	lamp_glow = _sprite(soft, v2(a.lamp), Color(1.0, 0.86, 0.55, 0.30), false, 0.55)
	lamp_core = _sprite(soft, v2(a.lamp), Color(1.0, 0.92, 0.65, 0.8), true, 0.14)


func _build_glints() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED + 1
	var tex := load("res://art/glint.png")
	for z in cfg.glints:
		var r := Rect2(z[0], z[1], z[2] - z[0], z[3] - z[1])
		for i in int(z[4]):
			var s := _sprite(tex, Vector2(round(rng.randf_range(r.position.x, r.end.x)),
					round(rng.randf_range(r.position.y, r.end.y))), Color(1.0, 0.86, 0.6, 0.0), true,
					rng.randf_range(0.5, 1.0))
			glints.append({"s": s, "period": rng.randf_range(1.3, 2.6), "phase": rng.randf(),
					"warm": z[5]})


func _build_smoke() -> void:
	var tex := load("res://art/smoke.png")
	for i in 9:
		var s := _sprite(tex, v2(cfg.anchors.chimney), Color(0.70, 0.76, 0.80, 0.0), false, 0.2)
		smoke.append(s)


func _build_gulls() -> void:
	for g in cfg.gulls:
		var l := Line2D.new()
		l.width = g[4]
		l.default_color = Color(0.93, 0.92, 0.88, 0.95)
		l.joint_mode = Line2D.LINE_JOINT_ROUND
		l.begin_cap_mode = Line2D.LINE_CAP_ROUND
		l.end_cap_mode = Line2D.LINE_CAP_ROUND
		l.antialiased = true
		l.points = PackedVector2Array([Vector2.ZERO, Vector2.ZERO, Vector2.ZERO, Vector2.ZERO, Vector2.ZERO])
		add_child(l)
		gulls.append({"l": l, "p0": Vector2(g[0], g[1]), "vx": g[2], "span": g[3], "phase": g[5]})


func _build_parcel() -> void:
	var p: Array = cfg.parcel.pos
	parcel_shadow = _sprite(glow_texture(64, 0.5), v2(p) + Vector2(0, 1), Color(0.05, 0.05, 0.09, 0.45), false)
	parcel_shadow.scale = Vector2(cfg.parcel.size / 64.0 * 1.4, cfg.parcel.size / 64.0 * 0.35)
	parcel = Sprite2D.new()
	parcel.texture = load("res://art/icons/parcel.png")
	parcel.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	parcel.centered = true
	var k: float = cfg.parcel.size / float(parcel.texture.get_width())
	parcel.scale = Vector2(k, k)
	parcel.offset = Vector2(0, -parcel.texture.get_height() / 2.0)
	parcel.position = v2(p)
	add_child(parcel)


func _build_badger() -> void:
	var rig: Dictionary = cfg.badger
	walk = cfg.walk
	heel = v2(rig.heel)
	toe = v2(rig.toe)
	leg_off = [0.0, float(walk.far_dx)]
	shadow = _sprite(glow_texture(64, 0.55), Vector2.ZERO, Color(0.04, 0.04, 0.08, 0.42), false)
	shadow.scale = Vector2(walk.shadow_w / 64.0, walk.shadow_w / 64.0 * 0.22)
	badger = Node2D.new()
	add_child(badger)
	var leg_tex: Texture2D = load("res://art/" + rig.leg)
	for i in 2:
		var l := Sprite2D.new()
		l.texture = leg_tex
		l.centered = false
		l.offset = -v2(rig.leg_pivot)
		if i == 1:
			var sh: float = walk.far_shade
			l.modulate = Color(sh, sh, sh)
		legs.append(l)
	badger.add_child(legs[1])
	badger.add_child(legs[0])
	body = Sprite2D.new()
	body.texture = load("res://art/" + rig.body)
	body.centered = false
	body.offset = -v2(rig.body_pivot)
	badger.add_child(body)


func _walk_dist(tt: float) -> float:
	## Zurückgelegter Weg der Hüfte: gleichmäßig, am Ende gleichmäßig abgebremst bis zum Stillstand.
	var v: float = walk.speed
	var td: float = walk.decel
	var t1 := (float(walk.distance) - v * td / 2.0) / v
	if tt <= t1:
		return v * maxf(tt, 0.0)
	var u := minf(tt - t1, td)
	return v * t1 + v * u - v * u * u / (2.0 * td)


func _walk_end() -> float:
	var v: float = walk.speed
	return (float(walk.distance) - v * float(walk.decel) / 2.0) / v + float(walk.decel)


func _stance_angle(p: Vector2, d: float) -> float:
	## Drehung des Beins, bei der der Fußpunkt p (relativ zur Hüfte) waagerecht um d neben der Hüfte liegt.
	return acos(clampf(d / p.length(), -1.0, 1.0)) - atan2(p.y, p.x)


func _pose(tt: float) -> Dictionary:
	## Hüfte (x auf ganze Pixel, y relativ zur Fußlinie), Drehung und Hub beider Beine.
	var s: float = walk.step
	var x0: float = walk.start_x
	var n: int = int(walk.steps)
	var dist := _walk_dist(tt)
	var hx := roundf(x0 + dist)
	var p := (hx - x0) / s
	var p_raw := dist / s                          # ungerundet: Schwungbein gleitet stetig
	var k := mini(int(floor(p)), n)
	var u := clampf(p - k, 0.0, 1.0)
	var st := k % 2
	var sw := 1 - st
	# Standbein: Mitte der Sohle steht bei xk; vor der Hüfte rollt es über die Ferse, dahinter über die Zehe.
	var xk := x0 + s * 0.5 + k * s + leg_off[st]
	var px := hx + leg_off[st]
	var r_st: float
	var hip_y: float
	if px <= xk:
		r_st = _stance_angle(heel, xk + heel.x - px)
		hip_y = -heel.rotated(r_st).y
	else:
		r_st = _stance_angle(toe, xk + toe.x - px)
		hip_y = -toe.rotated(r_st).y
	# Schwungbein: von der Zehenablösung zum Fersenaufsatz; im letzten Schritt landet es neben dem Standfuß.
	var r_end := _stance_angle(toe, toe.x - s * 0.5)
	var r_start := _stance_angle(heel, heel.x + s * 0.5)
	var us := clampf(p_raw - k, 0.0, 1.0)
	var r_target := r_start
	if k == n:
		# letzter halber Schritt: kurz vor dem Stillstand neben dem Standfuß aufsetzen
		us = clampf((p_raw - k) / 0.45, 0.0, 1.0)
		r_target = 0.0
	var r_sw := lerpf(r_end, r_target, smoothstep(0.0, 1.0, us))
	var low := maxf(heel.rotated(r_sw).y, toe.rotated(r_sw).y)
	var lift := maxf(float(walk.lift) * sin(PI * us), hip_y + low)
	var r := [0.0, 0.0]
	var h := [0.0, 0.0]
	r[st] = r_st
	r[sw] = r_sw
	h[sw] = lift
	return {"x": hx, "y": hip_y, "r": r, "lift": h}


func _update() -> void:
	var a: Dictionary = cfg.anchors
	# Flackern: vorab gewürfelte Werte, 30 pro Sekunde, weich überblendet
	var fi := t * 30.0
	var i0 := int(fi) % flicker.size()
	var f := lerpf(flicker[i0], flicker[(i0 + 1) % flicker.size()], fi - floor(fi))
	var lf := 0.78 + 0.16 * sin(t * 13.0) * 0.5 + 0.22 * f
	lantern_glow.modulate.a = 0.26 * lf
	lantern_glow.scale = Vector2.ONE * (0.58 + 0.06 * f)
	lantern_core.modulate.a = 0.45 * lf
	window_glow.modulate.a = 0.22 + 0.04 * sin(t * 2.1) + 0.03 * f

	# Leuchtturm: Drehung in 5 s; cos > 0 heißt Strahl nach rechts, die Breite folgt |cos|.
	var ang := TAU * (t / 5.0) + float(cfg.beam_phase)
	var c := cos(ang)
	var toward := maxf(sin(ang), 0.0)      # zeigt zur Kamera
	beam.scale = Vector2(c * float(cfg.beam_len), 1.0 + 0.3 * toward)
	beam.modulate = Color(1.0, 0.9, 0.65, 0.16 + 0.10 * (1.0 - absf(c)) * 0.0 + 0.10 * absf(c))
	lamp_core.modulate.a = 0.55 + 0.45 * pow(toward, 3.0)
	lamp_core.scale = Vector2.ONE * (0.12 + 0.10 * pow(toward, 3.0))
	lamp_glow.modulate.a = 0.22 + 0.25 * pow(toward, 2.0)

	# Wasserglitzern: kurzes Aufblitzen je Punkt, dazwischen dunkel.
	for g in glints:
		var ph: float = fposmod(t / g.period + g.phase, 1.0)
		var on := clampf(1.0 - absf(ph - 0.5) * 6.0, 0.0, 1.0)
		var s: Sprite2D = g.s
		s.modulate = Color(1.0, 0.82, 0.55, on * 0.9) if g.warm > 0 else Color(0.75, 0.82, 1.0, on * 0.7)

	# Rauch: Wolken steigen auf, treiben nach rechts, wachsen und verblassen (fposmod, vorgewärmt).
	var ch := v2(a.chimney)
	for k in smoke.size():
		var life := 4.5
		var age := fposmod(t + 10.0 + k * life / smoke.size(), life)
		var u := age / life
		var s: Sprite2D = smoke[k]
		s.position = ch + Vector2(round(10.0 * u + 7.0 * u * u * 3.0), round(-34.0 * u - 6.0 * sin(u * 3.0 + k)))
		s.scale = Vector2.ONE * (0.10 + 0.22 * u)
		s.modulate.a = 0.42 * smoothstep(0.0, 0.12, u) * (1.0 - smoothstep(0.55, 1.0, u))
		s.rotation = k * 1.7 + u * 0.6

	# Möwen: gleiten und schlagen ab und zu mit den Flügeln.
	for g in gulls:
		var p: Vector2 = g.p0 + Vector2(g.vx * t, 3.0 * sin(t * 0.9 + g.phase))
		var flap := sin(t * 9.0 + g.phase) if fposmod(t * 0.35 + g.phase, 1.0) < 0.45 else 0.35
		var sp: float = g.span
		var l: Line2D = g.l
		l.points = PackedVector2Array([
			p + Vector2(-sp, -flap * sp * 0.55), p + Vector2(-sp * 0.45, -sp * 0.18 - flap * sp * 0.2),
			p, p + Vector2(sp * 0.45, -sp * 0.18 - flap * sp * 0.2), p + Vector2(sp, -flap * sp * 0.55)])

	if badger:
		var po := _pose(t)
		var g := float(walk.ground_y)
		badger.position = Vector2(po.x, g)
		body.position = Vector2(0.0, po.y)
		body.scale = Vector2.ONE
		var te := _walk_end()
		if t > te:
			# Stehen: Atmen um die Hüfte, sehr leicht.
			body.scale = Vector2(1.0, 1.0 + 0.018 * (0.5 - 0.5 * cos((t - te) * 2.6)))
		for i in 2:
			var l: Sprite2D = legs[i]
			l.position = Vector2(leg_off[i], po.y - float(po.lift[i]))
			l.rotation = float(po.r[i])
		shadow.position = Vector2(po.x, g + 1.0)


func _mask_mode() -> void:
	## Messlauf "-- --mask": nur der Dachs mit hartem Alpha, Rumpf blau, nahes Bein rot, fernes Bein grün
	## (für scripts/measure_walk.py: Sohle und Standfuß je Bein).
	for c in get_children():
		if c != badger:
			c.visible = false
	if badger:
		var cols := {body: Color(0, 0, 1), legs[0]: Color(1, 0, 0), legs[1]: Color(0, 1, 0)}
		for c in cols:
			var sh := Shader.new()
			sh.code = "shader_type canvas_item;\nuniform vec3 mask_col;\nvoid fragment() { COLOR = vec4(mask_col, step(0.5, texture(TEXTURE, UV).a)); }"
			var m := ShaderMaterial.new()
			m.shader = sh
			m.set_shader_parameter("mask_col", cols[c])
			var ci: CanvasItem = c
			ci.material = m
			ci.modulate = Color(1, 1, 1)
