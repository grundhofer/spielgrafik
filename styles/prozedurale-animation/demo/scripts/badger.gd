extends Node2D
## Der Dachs-Kurier, nur aus Code bewegt.
## Ein KI-Körperbild (starr: Kopf, Rumpf, Arm mit Paket), ein KI-Bein (zweimal verwendet, als Gitter mit
## Zwei-Gelenk-IK verbogen), ein Schalende als Verlet-Streifen und die Tasche an einer Verlet-Riemenkette.
## Einheit: Texturpixel (KI-Blatt x 0,30). Ursprung: Boden unter der Hüfte des nahen Beins.
## Der Knoten ist mit DS skaliert, Bildschirm = position + DS * lokal.

const Chain := preload("res://scripts/chain.gd")
const Util := preload("res://scripts/util.gd")

const DS := 0.6667
const V0 := 112.5            # Lauftempo in Texturpixeln/s (75 px/s im Bild)
const T_STOP := 3.4          # ab hier bremsen: hält bei x ≈ 520 rechts neben dem Laternenpfahl, unter der Laterne
const T_DEC := 0.40          # Bremsdauer
const T_SW := 0.23           # Schwungdauer eines Fußes
const T_ST := 0.39           # Standdauer bei vollem Tempo -> Vorgriff = v * T_ST / 2
const LIFT := 7.0            # Fußhub
const FOOT_ROT := 0.22       # Abrollen/Fersenaufsatz (rad)
const BOUNCE := 3.0          # Hüfte hebt sich, während das andere Bein durchschwingt
const ANKLE_H := 18.9        # Knöchel über der Sohle
const GRAV := Vector2(0, 1800)
const K_AIR := 0.085         # quadratischer Luftwiderstand Riemen (mit drag 0,3 je Glied)
const K_AIR_SCARF := 0.05    # Schal: weniger Widerstand, damit er beim Anhalten über die Senkrechte nach vorn schwingt
const WIND0 := -24.0         # Grundwind (Texturpixel/s, nach links); bewegt auch den Rauch
const LAND_IMP := 0.8       # Stauchimpuls beim Aufsetzen
const KQ := 0.010           # Stauchung aus vertikaler Beschleunigung
const KT := 0.00028          # Vorneigen aus Bremsbeschleunigung (rad je px/s²)
const LEAN := 0.075          # Vorlage bei vollem Tempo (rad)
const BAG_TILT := 0.0        # Tasche hängt im Stand aufrecht am vorderen Ring

var R: Dictionary
var x0 := 168.0
var pivot: Vector2
var hip0: Vector2
var knee0: Vector2
var ankle0: Vector2
var leg_origin: Vector2
var far_off: Vector2
var L1: float
var L2: float
var RMAX: float
var H_STAND: float
var toe_off: Vector2
var sole_pts := PackedVector2Array()

var leg_rest := PackedVector2Array()      # Gitterpunkte, lokale Texturkoordinaten des Beins
var leg_wt := PackedFloat32Array()
var leg_ws := PackedFloat32Array()
var leg_wf := PackedFloat32Array()


class Foot:
	var name := ""
	var hip_off := Vector2()     # Hüfte dieses Beins relativ zum Körperdrehpunkt (Ruhe)
	var off := 0.0               # Knöchel-x relativ zur Körperhüfte (Ruhe)
	var ground := 0.0
	var pos := Vector2()         # Knöchel-x auf dem Boden (geplant/stehend)
	var swing := false
	var s := 0.0
	var start := Vector2()
	var target := Vector2()
	var step_len := 0.0
	var phi := 0.0
	# Ergebnis für Zeichnen und Prüfen
	var H := Vector2()
	var K := Vector2()
	var A := Vector2()


var feet: Array[Foot] = []
var hip := Vector2()
var hip_vy := 0.0
var prev_hip_vy := 0.0
var prev_v := V0
var q := 0.0
var qv := 0.0
var tilt := 0.0
var tiltv := 0.0
var sx := 1.0
var sy := 1.0
var t := 0.0
var idle := 0.0
var last_land := -10.0
var n_steps := 0
var air := Vector2()
var blink := 0.0
var blink_at: Array[float] = []

var scarf: Chain
var strap: Chain
var scarf_w := 28.0
var bag_center := Vector2()
var cap_a := Vector2()
var cap_b := Vector2()
var cap_r := 0.0

var mat: ShaderMaterial
var legs: Array[Polygon2D] = []
var body_spr: Sprite2D
var wrap_spr: Sprite2D
var scarf_poly: Polygon2D
var strap_out: Line2D
var strap_line: Line2D
var bag: Sprite2D
var lid: Node2D
var shadow: Node2D
var shadow_tex: Texture2D
var overlay: Node2D
var only := ""


func v2(a) -> Vector2:
	return Vector2(float(a[0]), float(a[1]))


func setup(rig: Dictionary, ground_y: float, start_x_screen: float, only_parts := "") -> void:
	R = rig
	only = only_parts
	position = Vector2(0, ground_y)
	scale = Vector2(DS, DS)
	x0 = start_x_screen / DS
	pivot = v2(R["body_pivot"])
	leg_origin = v2(R["leg_tex_origin"])
	var ll: Dictionary = R["leg_local"]
	hip0 = leg_origin + v2(ll["hip"])
	knee0 = leg_origin + v2(ll["knee"])
	ankle0 = leg_origin + v2(ll["ankle"])
	far_off = v2(R["far_leg_offset"])
	L1 = hip0.distance_to(knee0)
	L2 = knee0.distance_to(ankle0)
	RMAX = 0.985 * (L1 + L2)
	H_STAND = 0.955 * (L1 + L2)
	var toe: Vector2 = leg_origin + v2(ll["toe"])
	var heel: Vector2 = leg_origin + v2(ll["heel"])
	toe_off = toe - ankle0
	sole_pts = PackedVector2Array([heel - ankle0, Vector2(-10, ANKLE_H), Vector2(12, ANKLE_H),
		Vector2(32, ANKLE_H - 0.6), toe_off])

	var sz: Vector2 = v2(R["satchel_size"])
	bag_center = sz * 0.5 - v2(R["satchel_rings"][1])
	mat = ShaderMaterial.new()
	mat.shader = load("res://shaders/badger.gdshader")
	_build_nodes()
	_build_leg_mesh()

	for k in 2:
		var f := Foot.new()
		f.name = "far" if k == 0 else "near"
		f.hip_off = far_off if k == 0 else Vector2.ZERO
		f.off = (ankle0.x - hip0.x) + f.hip_off.x
		f.ground = far_off.y if k == 0 else 0.0
		feet.append(f)

	# Blinzeln: fest gesetzt und danach alle 3–5 s (fester Seed)
	var rng := RandomNumberGenerator.new()
	rng.seed = 5
	var tb := 1.35
	blink_at.append(tb)
	tb = 4.45
	while tb < 400.0:
		blink_at.append(tb)
		tb += rng.randf_range(3.0, 5.0)


func _build_nodes() -> void:
	# Kontaktschatten zuerst (unter Beinen und Körper), ohne Dämmerungs-Shader
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.45, 1.0])
	g.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 0.6), Color(1, 1, 1, 0)])
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill = GradientTexture2D.FILL_RADIAL
	gt.fill_from = Vector2(0.5, 0.5)
	gt.fill_to = Vector2(1.0, 0.5)
	gt.width = 64
	gt.height = 64
	shadow_tex = gt
	shadow = Node2D.new()
	shadow.draw.connect(_draw_shadow)
	add_child(shadow)
	var tex_leg: Texture2D = load("res://art/badger_leg.png")
	for k in 2:
		var p := Polygon2D.new()
		p.texture = tex_leg
		p.material = mat
		p.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		if k == 0:
			p.self_modulate = Color(0.62, 0.62, 0.68)
		add_child(p)
		legs.append(p)
	body_spr = _sprite("res://art/badger_body.png")
	body_spr.offset = v2(R["body_tex_origin"]) - v2(R["body_pivot"])
	scarf_poly = Polygon2D.new()
	scarf_poly.texture = load("res://art/badger_scarf.png")
	scarf_poly.material = mat
	scarf_poly.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	add_child(scarf_poly)
	strap_out = Line2D.new()
	strap_out.width = 5.6
	strap_out.default_color = Color(0.16, 0.08, 0.05)
	strap_line = Line2D.new()
	strap_line.width = 3.4
	strap_line.default_color = Color(0.50, 0.29, 0.16)
	for l in [strap_out, strap_line]:
		l.joint_mode = Line2D.LINE_JOINT_ROUND
		l.begin_cap_mode = Line2D.LINE_CAP_ROUND
		l.end_cap_mode = Line2D.LINE_CAP_ROUND
		l.material = mat
		l.antialiased = true
		add_child(l)
	bag = _sprite("res://art/badger_satchel.png")
	var rings: Array = R["satchel_rings"]
	bag.offset = -v2(rings[1])          # Tasche hängt am vorderen Ring
	wrap_spr = _sprite("res://art/badger_wrap.png")
	wrap_spr.offset = body_spr.offset
	lid = Node2D.new()
	lid.draw.connect(_draw_lid)
	add_child(lid)


func _sprite(path: String) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = load(path)
	s.centered = false
	s.material = mat
	s.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	add_child(s)
	return s


## Gitter über dem Bein (4-px-Zellen, nur gedeckte Zellen) und Gewichte für Oberschenkel, Unterschenkel, Fuß.
func _build_leg_mesh() -> void:
	var img: Image = (load("res://art/badger_leg.png") as Texture2D).get_image()
	var w := img.get_width()
	var h := img.get_height()
	var cell := 4
	var nx := int(ceil(float(w) / cell))
	var ny := int(ceil(float(h) / cell))
	var idx := {}
	var polys: Array = []
	var uv := PackedVector2Array()
	for cy in ny:
		for cx in nx:
			var covered := false
			for yy in range(cy * cell, mini((cy + 1) * cell, h)):
				for xx in range(cx * cell, mini((cx + 1) * cell, w)):
					if img.get_pixel(xx, yy).a > 0.01:
						covered = true
						break
				if covered:
					break
			if not covered:
				continue
			var ids := []
			for c in [Vector2i(cx, cy), Vector2i(cx + 1, cy), Vector2i(cx + 1, cy + 1), Vector2i(cx, cy + 1)]:
				if not idx.has(c):
					idx[c] = leg_rest.size()
					var pt := Vector2(minf(c.x * cell, w), minf(c.y * cell, h))
					leg_rest.append(pt)
					uv.append(pt)
				ids.append(idx[c])
			if (cx + cy) % 2 == 0:
				polys.append(PackedInt32Array([ids[0], ids[1], ids[2]]))
				polys.append(PackedInt32Array([ids[0], ids[2], ids[3]]))
			else:
				polys.append(PackedInt32Array([ids[0], ids[1], ids[3]]))
				polys.append(PackedInt32Array([ids[1], ids[2], ids[3]]))
	var ll: Dictionary = R["leg_local"]
	var yk: float = v2(ll["knee"]).y
	var ya: float = v2(ll["ankle"]).y
	for pt in leg_rest:
		var wf := maxf(smoothstep(ya - 3.0, ya + 5.0, pt.y), smoothstep(40.0, 46.0, pt.x) * smoothstep(60.0, 68.0, pt.y))
		var ws := smoothstep(yk - 8.0, yk + 8.0, pt.y) * (1.0 - wf)
		leg_wf.append(wf)
		leg_ws.append(ws)
		leg_wt.append(1.0 - wf - ws)
	for p in legs:
		p.uv = uv
		p.polygons = polys
		p.polygon = leg_rest


# ------------------------------------------------------------------ Bewegungsprofil

func body_x(tt: float) -> float:
	if tt < T_STOP:
		return x0 + V0 * tt
	var u := minf((tt - T_STOP) / T_DEC, 1.0)
	return x0 + V0 * T_STOP + V0 * T_DEC * (u - u * u * u + 0.5 * u * u * u * u)


func body_v(tt: float) -> float:
	if tt < T_STOP:
		return V0
	var u := minf((tt - T_STOP) / T_DEC, 1.0)
	return V0 * (1.0 - u * u * (3.0 - 2.0 * u))


func body_xf() -> Transform2D:
	return Transform2D(tilt, Vector2(sx, sy), 0.0, hip)


func bpt(p_rest: Vector2) -> Vector2:
	return body_xf() * (p_rest - pivot)


## Wind aus Grundwind und Böen; dieselbe Böenfunktion (fbm, Seed 11) lässt die Laterne flackern und treibt den Rauch.
static func wind_at(tt: float) -> Vector2:
	return Vector2(WIND0 + 28.0 * Util.fbm(tt * 0.55, 11), 5.0 * Util.fbm(tt * 0.8, 23))


# ------------------------------------------------------------------ Simulation (fester Schritt)

func init_state(tt: float) -> void:
	t = tt
	hip = Vector2(body_x(tt), -(ANKLE_H + H_STAND))
	feet[0].pos = Vector2(hip.x + feet[0].off - 10.0, feet[0].ground)
	feet[1].pos = Vector2(hip.x + feet[1].off + 12.0, feet[1].ground)
	var xf := body_xf()
	scarf = Chain.new()
	var sa: Vector2 = bpt(v2(R["scarf_anchor"]))
	scarf.init_line(sa, Vector2(-0.8, 0.6), 7, 88.0 / 6.0)
	strap = Chain.new()
	var st: Vector2 = bpt(v2(R["strap_anchor"]))
	strap.init_line(st, Vector2(-0.3, 0.95), 6, 64.0 / 5.0)
	strap.inv_m[5] = 0.25
	for i in strap.size():
		strap.drag[i] = 0.3
	strap.drag[5] = 0.3
	strap.min_fold = 0.35


func step(tt: float, dt: float) -> void:
	t = tt
	var x := body_x(tt)
	var v := body_v(tt)
	# Füße: Schwung fortschreiben, Aufsetzen
	var any_swing := false
	for f in feet:
		if f.swing:
			f.s += dt / T_SW
			if f.s >= 1.0:
				f.swing = false
				f.s = 1.0
				f.pos = f.target
				f.phi = 0.0
				last_land = tt
				n_steps += 1
				qv -= LAND_IMP * clampf(absf(f.step_len) / 40.0, 0.15, 1.0)
		any_swing = any_swing or f.swing
	# Schritt auslösen: der Fuß, der am weitesten hinter seiner Ruhelage steht
	if not any_swing and tt - last_land >= 0.04:
		var best: Foot = null
		var best_lag := -1e9
		for f in feet:
			var lag: float = x + f.off - f.pos.x
			if lag > best_lag:
				best_lag = lag
				best = f
		var trig := maxf(2.5, v * T_ST * 0.5)
		if best_lag > trig:
			var tl := tt + T_SW
			best.swing = true
			best.s = 0.0
			best.start = best.pos
			best.target = Vector2(body_x(tl) + best.off + body_v(tl) * T_ST * 0.5, best.ground)
			best.step_len = best.target.x - best.start.x
			any_swing = true
	# Hüfthöhe: Standhöhe, Heben im Durchschwung, Reichweite der stehenden Beine
	var target_y := -(ANKLE_H + H_STAND)
	for f in feet:
		if f.swing:
			target_y -= BOUNCE * sin(PI * f.s) * clampf(absf(f.step_len) / 30.0, 0.0, 1.0)
	for f in feet:
		if f.swing:
			continue
		var a := Vector2(f.pos.x, f.ground - ANKLE_H)
		var dx := x + f.hip_off.x - a.x
		var hmax := sqrt(maxf(RMAX * RMAX - dx * dx, 1.0))
		target_y = maxf(target_y, a.y - hmax - f.hip_off.y)
	var wy := 34.0
	hip_vy += (wy * wy * (target_y - hip.y) - 2.0 * wy * hip_vy) * dt
	hip.y += hip_vy * dt
	hip.x = x
	# Federn des Körpers: Stauchung aus vertikaler Beschleunigung, Neigung aus Tempo und Bremsen
	var ay := (hip_vy - prev_hip_vy) / dt
	prev_hip_vy = hip_vy
	var ax := (v - prev_v) / dt
	prev_v = v
	var wq := 22.0
	qv += (-wq * wq * q - 2.0 * 0.32 * wq * qv + KQ * ay) * dt
	q += qv * dt
	var wt := 9.0
	tiltv += (-wt * wt * (tilt - LEAN * v / V0) - 2.0 * 0.36 * wt * tiltv - KT * ax * wt * wt) * dt
	tilt += tiltv * dt
	idle = move_toward(idle, 1.0 if (v < 1.0 and not any_swing) else 0.0, dt / 0.8)
	var breath := sin(TAU * (tt - T_STOP) / 2.7) * idle
	sy = 1.0 + q + 0.014 * breath
	sx = 1.0 - 0.55 * q - 0.005 * breath
	# Schwungfüße: Bahn, Abrollen
	for f in feet:
		if f.swing:
			var e := Util.minjerk(f.s)
			var lift := minf(LIFT, 0.3 * absf(f.step_len) + 1.0)
			f.phi = FOOT_ROT * sin(TAU * f.s) * clampf(absf(f.step_len) / 25.0, 0.0, 1.0)
			f.A = Vector2(lerpf(f.start.x, f.target.x, e), f.ground - ANKLE_H - lift * sin(PI * f.s))
			# Sohle nicht unter den Boden drehen (Abrollen über Ballen bzw. Ferse)
			var low := -1e9
			for sp in sole_pts:
				low = maxf(low, f.A.y + sp.rotated(f.phi).y)
			if low > f.ground:
				f.A.y -= low - f.ground
		else:
			f.A = Vector2(f.pos.x, f.ground - ANKLE_H)
	_step_chains(tt, dt)
	blink = 0.0
	for b in blink_at:
		var u := tt - b
		if u >= 0.0 and u < 0.17:
			blink = clampf(u / 0.06, 0.0, 1.0) if u < 0.06 else (1.0 if u < 0.09 else 1.0 - (u - 0.09) / 0.08)
			break
		if b > tt:
			break


func _step_chains(tt: float, dt: float) -> void:
	var xf := body_xf()
	air = wind_at(tt)
	var bs := 0.5 * (sx + sy)
	var cap: Dictionary = R["back_capsule"]
	cap_a = xf * (v2(cap["a"]) - pivot)
	cap_b = xf * (v2(cap["b"]) - pivot)
	cap_r = float(cap["r"]) * bs
	# Schalende
	var sa := xf * (v2(R["scarf_anchor"]) - pivot)
	var root_dir := xf.basis_xform(Vector2(-0.45, 0.89)).normalized()
	scarf.pp[0] = scarf.p[0]
	scarf.p[0] = sa
	scarf.integrate(dt, GRAV, air, K_AIR_SCARF, 0.12)
	for it in 8:
		scarf.p[0] = sa
		scarf.p[1] = scarf.p[1].lerp(sa + root_dir * scarf.seg, 0.3)
		scarf.solve()
	# Riemen mit Tasche
	var st := xf * (v2(R["strap_anchor"]) - pivot)
	strap.pp[0] = strap.p[0]
	strap.p[0] = st
	strap.integrate(dt, GRAV, air, K_AIR, 0.3)
	var n := strap.size()
	for it in 8:
		strap.p[0] = st
		strap.solve()
		strap.push_out_capsule(cap_a, cap_b, cap_r + 1.5, 1, n - 1)
		# Taschenkörper liegt außen an Rücken und Hüfte an (Mitte aus der Lage am Ring)
		var c: Vector2 = bag_xf() * bag_center
		var ab := cap_b - cap_a
		var u := clampf((c - cap_a).dot(ab) / ab.length_squared(), 0.0, 1.0)
		var cc := cap_a + ab * u
		var dd := c - cc
		var rr := cap_r + 10.0
		if dd.length() < rr and dd.length() > 1e-6:
			strap.p[n - 1] += dd.normalized() * (rr - dd.length())


# ------------------------------------------------------------------ Zeichnen (einmal je Bild)

func _ik(H: Vector2, A: Vector2) -> Vector2:
	var d := H.distance_to(A)
	var dir := (A - H) / maxf(d, 1e-4)
	var dc := clampf(d, absf(L1 - L2) + 0.01, L1 + L2 - 0.01)
	var cos_a := clampf((L1 * L1 + dc * dc - L2 * L2) / (2.0 * L1 * dc), -1.0, 1.0)
	var k := H + dir.rotated(-acos(cos_a)) * L1
	if d > L1 + L2:   # überstreckt: Knie mitziehen, Bein dehnt sich minimal
		k = H + dir * L1 * d / (L1 + L2)
	return k


func render() -> void:
	var xf := body_xf()
	for k in 2:
		var f: Foot = feet[k]
		var off := far_off if k == 0 else Vector2.ZERO
		f.H = xf * (hip0 + off - pivot)
		f.K = _ik(f.H, f.A)
		var h0 := hip0 + off
		var k0 := knee0 + off
		var a0 := ankle0 + off
		var rt := (f.K - f.H).angle() - (k0 - h0).angle()
		var rs := (f.A - f.K).angle() - (a0 - k0).angle()
		var out := PackedVector2Array()
		out.resize(leg_rest.size())
		for i in leg_rest.size():
			var pr: Vector2 = leg_rest[i] + leg_origin + off
			var pt: Vector2 = (pr - h0).rotated(rt) + f.H
			var ps: Vector2 = (pr - k0).rotated(rs) + f.K
			var pf: Vector2 = (pr - a0).rotated(f.phi) + f.A
			out[i] = pt * leg_wt[i] + ps * leg_ws[i] + pf * leg_wf[i]
		legs[k].polygon = out
	body_spr.transform = xf
	wrap_spr.transform = xf
	lid.transform = xf
	lid.queue_redraw()
	shadow.queue_redraw()
	_render_scarf()
	_render_strap()
	_apply_only()
	if overlay:
		overlay.queue_redraw()


func _render_scarf() -> void:
	var pts := scarf.p
	var n := pts.size()
	var sub := 4
	var tex_w: float = float(R["scarf_size"][0])
	var tex_h: float = float(R["scarf_size"][1])
	var poly := PackedVector2Array()
	var uv := PackedVector2Array()
	var rows := 0
	for i in n - 1:
		var p0: Vector2 = pts[maxi(i - 1, 0)]
		var p1: Vector2 = pts[i]
		var p2: Vector2 = pts[i + 1]
		var p3: Vector2 = pts[mini(i + 2, n - 1)]
		var last := 1 if i < n - 2 else 0
		for kk in sub + 1 - last:
			var u := float(kk) / sub
			var c := _catmull(p0, p1, p2, p3, u)
			var tg := _catmull_d(p0, p1, p2, p3, u).normalized()
			var pr := Vector2(tg.y, -tg.x)
			var vv := (float(i) + u) / float(n - 1) * tex_h
			poly.append(c - pr * scarf_w * 0.5)
			poly.append(c + pr * scarf_w * 0.5)
			uv.append(Vector2(0, vv))
			uv.append(Vector2(tex_w, vv))
			rows += 1
	var tris: Array = []
	for j in rows - 1:
		var a := 2 * j
		tris.append(PackedInt32Array([a, a + 1, a + 3]))
		tris.append(PackedInt32Array([a, a + 3, a + 2]))
	scarf_poly.polygons = tris
	scarf_poly.uv = uv
	scarf_poly.polygon = poly


func _catmull(p0: Vector2, p1: Vector2, p2: Vector2, p3: Vector2, u: float) -> Vector2:
	var u2 := u * u
	var u3 := u2 * u
	return 0.5 * ((2.0 * p1) + (-p0 + p2) * u + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * u2 + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * u3)


func _catmull_d(p0: Vector2, p1: Vector2, p2: Vector2, p3: Vector2, u: float) -> Vector2:
	var u2 := u * u
	return 0.5 * ((-p0 + p2) + 2.0 * (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * u + 3.0 * (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * u2)


func bag_xf() -> Transform2D:
	var n := strap.size()
	var e: Vector2 = strap.p[n - 1]
	var d: Vector2 = (e - strap.p[n - 2]).normalized()
	return Transform2D(d.angle() - PI * 0.5 - BAG_TILT, e)


func _render_strap() -> void:
	bag.transform = bag_xf()
	var pts := PackedVector2Array(strap.p)
	strap_line.points = pts
	strap_out.points = pts


## Weicher Kontaktschatten: schwacher Gesamtschatten unter dem Körper, dazu je Fuß eine Ellipse unter der Sohle,
## die mit der Fußhöhe schmaler und blasser wird (Bodenbezug für den Fußhub).
func _draw_shadow() -> void:
	var col := Color(0.07, 0.05, 0.12)
	_ellipse(Vector2(hip.x + 10.0, 1.0), Vector2(160.0, 26.0), Color(col, 0.36))
	for f in feet:
		var h := maxf(0.0, (f.ground - ANKLE_H) - f.A.y)
		var k := clampf(1.0 - h / 12.0, 0.25, 1.0)
		var c := Vector2(f.A.x + 14.0, f.ground + 2.5)
		var a := (0.62 if f.name == "near" else 0.48) * k
		_ellipse(c, Vector2(80.0 * (0.65 + 0.35 * k), 18.0 * (0.7 + 0.3 * k)), Color(col, a))


func _ellipse(c: Vector2, size: Vector2, col: Color) -> void:
	shadow.draw_texture_rect(shadow_tex, Rect2(c - size * 0.5, size), false, col)


func _draw_lid() -> void:
	if blink <= 0.01:
		return
	var eye: Vector2 = v2(R["eye"]) - pivot
	var rx := 4.6
	var ry := 4.9
	var yl := -ry + 2.0 * ry * blink
	var col := Color(float(R["lid_color"][0]), float(R["lid_color"][1]), float(R["lid_color"][2]))
	var s0 := clampf(yl / ry, -0.999, 1.0)
	var a0 := PI - asin(s0)
	var a1 := TAU + asin(s0)
	var poly := PackedVector2Array()
	for i in 25:
		var ang := lerpf(a0, a1, float(i) / 24.0)
		poly.append(eye + Vector2(cos(ang) * rx, sin(ang) * ry))
	lid.draw_colored_polygon(poly, col)
	var lash := PackedVector2Array()
	var half := rx * sqrt(maxf(0.0, 1.0 - (yl / ry) * (yl / ry)))
	for i in 9:
		var xx := -half + 2.0 * half * float(i) / 8.0
		lash.append(eye + Vector2(xx, yl + 0.6 * (1.0 - pow(xx / maxf(half, 0.01), 2.0))))
	if half > 0.5:
		lid.draw_polyline(lash, Color(0.12, 0.08, 0.07), 1.3, true)


## Prüfschalter: nur bestimmte Teile zeigen (--only=near_leg,far_leg,body,...)
func _apply_only() -> void:
	if only == "":
		return
	var parts := only.split(",")
	legs[0].visible = parts.has("far_leg")
	legs[1].visible = parts.has("near_leg")
	body_spr.visible = parts.has("body")
	wrap_spr.visible = parts.has("body")
	lid.visible = parts.has("body")
	shadow.visible = parts.has("shadow")
	scarf_poly.visible = parts.has("scarf")
	strap_line.visible = parts.has("strap")
	strap_out.visible = parts.has("strap")
	bag.visible = parts.has("strap")
