extends Node2D
## Der Dachs-Kurier als Rubber-Hose-Puppe: Kopf und Rumpf sind KI-Cels (Seiten- und Vorderansicht ohne Arme
## und Beine), Handschuhe und Paket ebenfalls. Arme und Beine sind Gummischläuche aus Code: gleich dicke Röhre
## ohne Gelenk, als quadratische Bézierkurve, deren Bogen so gewählt wird, dass die Röhre ihre feste Länge
## behält (je näher Hand oder Fuß am Ansatz, desto stärker biegt sie sich). Füße sind gezeichnete Ovale.
## Alles läuft auf Zweien (15 Posen/s, Takt = 6 Ticks = 0,4 s). Die Pose hängt nur vom Tick ab.
## Alle Längen sind für Teile im Maßstab 0,19 entworfen und werden mit K auf den Bogenmaßstab 0,14 gebracht
## (kleinerer Dachs, damit er zu Häuschen und Tür passt).

const BEAT := 6
const K := 0.14 / 0.19     # Maßstab der Puppe gegenüber dem Entwurf (Teile ×0,19)
const GROUND := 590.0      # Unterkante der Füße (Bildschirm-y)
const X0 := -24.0          # Wurzel (Mitte zwischen den Füßen) beim ersten Tick
const STEP := 44.0         # Schrittlänge je Takt (60 · K, ganzzahlig, damit der Standfuß auf ganzen Pixeln steht)
const WALK_BEATS := 9
const STOP_TICK := 54      # ab hier der letzte halbe Schritt
const TURN_TICK := 60      # Drehung zur Kamera
const BLINK_TICKS := [76, 77]

const L_LEG := 62.0 * K
const L_ARM := 88.0 * K
const W_LEG := 12.0 * K
const W_ARM := 10.0 * K
const INK_W := 2.6 * K     # Tuschekante je Seite
const ANKLE_H := 9.0 * K   # Knöchel über dem Boden

var meta: Dictionary
var fur := Color(0.25, 0.2, 0.18)
var fur_far := Color(0.17, 0.14, 0.12)
var ink := Color(0.03, 0.02, 0.015)
var shine := Color(0.98, 0.93, 0.82)

var shadow_layer: Node2D
var back_layer: Node2D      # ferner Arm (Seitenansicht)
var leg_layer: Node2D
var body: Sprite2D
var face_layer: Node2D      # Lider
var parcel: Sprite2D
var front_layer: Node2D     # naher Arm bzw. beide Arme (Vorderansicht)
var glove_back: Sprite2D
var glove_a: Sprite2D
var glove_b: Sprite2D
var tex := {}

# aktuelle Pose (Weltkoordinaten)
var pose := {}


func setup(scene_meta: Dictionary, drawer_script: Script, shadow_parent: Node2D) -> void:
	meta = scene_meta
	if absf(float(meta["scale"]) - 0.19 * K) > 0.0001:
		push_error("puppet.gd: K passt nicht zum Maßstab der Teile in scene.json")
	var f: Array = meta["fur"]
	fur = Color(f[0], f[1], f[2])
	fur_far = fur.darkened(0.3)
	var k: Array = meta["ink"]
	ink = Color(k[0], k[1], k[2])
	for n in ["body_side", "body_front", "glove_open", "glove_fist", "glove_wave", "glove_grip", "parcel"]:
		tex[n] = load("res://art/" + meta[n]["file"])
	shadow_layer = _drawer(drawer_script, _draw_shadow)
	shadow_parent.add_child(shadow_layer)
	back_layer = _drawer(drawer_script, _draw_back)
	add_child(back_layer)
	glove_back = _sprite()
	leg_layer = _drawer(drawer_script, _draw_legs)
	add_child(leg_layer)
	body = _sprite()
	face_layer = _drawer(drawer_script, _draw_face)
	add_child(face_layer)
	parcel = _sprite()
	front_layer = _drawer(drawer_script, _draw_front)
	add_child(front_layer)
	glove_a = _sprite()
	glove_b = _sprite()


func _drawer(script: Script, fn: Callable) -> Node2D:
	var d: Node2D = script.new()
	d.fn = fn
	return d


func _sprite() -> Sprite2D:
	var s := Sprite2D.new()
	s.centered = false
	add_child(s)
	return s


# ---------------------------------------------------------------- Ablauf

static func smooth(u: float) -> float:
	return u * u * (3.0 - 2.0 * u)


static func pulse(j: int) -> float:
	# Federn auf dem Schlag: gestaucht, gestreckt, nachschwingen
	return [1.0, -0.55, 0.2, 0.0, 0.0, 0.0][j]


func final_x() -> float:
	return X0 + WALK_BEATS * STEP + STEP * 0.5 + 7.0 * K


func update_pose(tick: int) -> void:
	var p := {}
	if tick < STOP_TICK:
		var b := floori(float(tick) / BEAT)
		var u := float(tick % BEAT) / BEAT
		var xb := X0 + STEP * b
		var near_stance := b % 2 == 0
		var stance := Vector2(xb + STEP * 0.5, GROUND - ANKLE_H)
		var sw := Vector2(lerp(xb - STEP * 0.5, xb + STEP * 1.5, smooth(u)), GROUND - ANKLE_H - 16.0 * K * sin(PI * u))
		p["view"] = "side"
		p["root"] = Vector2(xb + STEP * u, GROUND)
		p["hp"] = (61.0 + 6.0 * sin(PI * u)) * K
		p["near_ankle"] = stance if near_stance else sw
		p["far_ankle"] = sw if near_stance else stance
		p["near_tilt"] = 0.0 if near_stance else -0.35 * sin(PI * u)
		p["far_tilt"] = -0.35 * sin(PI * u) if near_stance else 0.0
		p["sy"] = 1.0 - 0.035 * cos(TAU * u)
		p["rot"] = 0.05
		p["arm"] = 0.95 * cos(PI * (b + u))
	elif tick < TURN_TICK:
		var u := float(tick - STOP_TICK) / BEAT
		var xb := X0 + STEP * WALK_BEATS
		var stance := Vector2(xb + STEP * 0.5, GROUND - ANKLE_H)
		var sw := Vector2(lerp(xb - STEP * 0.5, stance.x + 14.0 * K, smooth(min(1.0, u * 1.5))),
				GROUND - ANKLE_H - 12.0 * K * sin(PI * min(1.0, u * 1.5)))
		p["view"] = "side"
		p["root"] = Vector2(lerp(xb, final_x(), smooth(min(1.0, u * 1.5))), GROUND)
		p["hp"] = (lerp(61.0, 62.0, u) + 4.0 * sin(PI * min(1.0, u * 1.5))) * K
		p["near_ankle"] = sw   # Takt 9 ist ungerade: der ferne Fuß steht
		p["far_ankle"] = stance
		p["near_tilt"] = -0.3 * sin(PI * min(1.0, u * 1.5))
		p["far_tilt"] = 0.0
		var settle: float = [0.0, 0.0, 0.0, 0.045, -0.03, 0.01][tick - STOP_TICK]
		p["sy"] = 1.0 - settle
		p["rot"] = 0.05 * (1.0 - u)
		p["arm"] = 0.95 * cos(PI * (WALK_BEATS + u)) * (1.0 - smooth(u))
	else:
		var j := tick % BEAT
		var x := final_x()
		p["view"] = "front"
		p["root"] = Vector2(x, GROUND)
		var pl := pulse(j)
		p["hp"] = (62.0 - 3.0 * pl) * K
		p["sy"] = 1.0 - 0.025 * pl
		var pop := tick - TURN_TICK
		if pop < 3:
			p["sy"] = [0.86, 1.09, 0.98][pop]
		p["rot"] = 0.0
		p["l_ankle"] = Vector2(x - 17.0 * K, GROUND - ANKLE_H)
		p["r_ankle"] = Vector2(x + 17.0 * K, GROUND - ANKLE_H)
		# Winken: Arm hebt sich in 4 Ticks, dann je Takt ein Ausschlag (2 Takte = hin und zurück)
		var raise_u := clampf(float(tick - TURN_TICK - 1) / 4.0, 0.0, 1.0)
		var ph := TAU * float(tick - TURN_TICK - 5) / (2.0 * BEAT)
		p["wave_raise"] = smooth(raise_u)
		p["wave_phase"] = ph if tick >= TURN_TICK + 5 else 0.0
		p["blink"] = tick in BLINK_TICKS
	p["sx"] = 1.0 + (1.0 - float(p["sy"])) * 0.7
	pose = p
	_layout()


# ---------------------------------------------------------------- Aufbau der Pose

func _body_xform() -> Transform2D:
	# Rumpf: Anker (Unterkante Mitte) liegt hp - Hüftversatz über dem Boden, gedreht und gestaucht um den Anker
	var m: Dictionary = meta["body_side"] if pose["view"] == "side" else meta["body_front"]
	var hip_key := "hip_near" if pose["view"] == "side" else "hip_l"
	var hip_off: float = m["anchor"][1] - m["points"][hip_key][1]
	var root: Vector2 = pose["root"]
	var origin := Vector2(round(root.x), round(root.y - (float(pose["hp"]) - hip_off)))
	return Transform2D(float(pose["rot"]), Vector2(pose["sx"], pose["sy"]), 0.0, origin)


func _bp(name: String) -> Vector2:
	# Merkpunkt des aktuellen Rumpfteils in Weltkoordinaten
	var m: Dictionary = meta["body_side"] if pose["view"] == "side" else meta["body_front"]
	var a := Vector2(m["anchor"][0], m["anchor"][1])
	var q := Vector2(m["points"][name][0], m["points"][name][1]) - a
	return _body_xform() * q


func _place_glove(s: Sprite2D, gname: String, at: Vector2, angle: float, flip := false) -> void:
	var m: Dictionary = meta[gname]
	s.texture = tex[gname]
	s.offset = -Vector2(m["anchor"][0], m["anchor"][1])
	s.position = at.round()
	var axis := Vector2(m["axis"][0], m["axis"][1])
	s.rotation = angle - axis.angle()
	s.flip_v = flip
	if flip:
		s.offset.y = -(float(m["size"][1]) - float(m["anchor"][1]))
	s.visible = true


func _layout() -> void:
	var view: String = pose["view"]
	var xf := _body_xform()
	var bm: Dictionary = meta["body_side"] if view == "side" else meta["body_front"]
	body.texture = tex["body_side"] if view == "side" else tex["body_front"]
	body.offset = -Vector2(bm["anchor"][0], bm["anchor"][1])
	body.position = xf.origin
	body.rotation = float(pose["rot"])
	body.scale = Vector2(pose["sx"], pose["sy"])
	var pm: Dictionary = meta["parcel"]
	parcel.texture = tex["parcel"]
	parcel.offset = -Vector2(pm["anchor"][0], pm["anchor"][1])
	glove_back.visible = false
	glove_a.visible = false
	glove_b.visible = false
	if view == "side":
		# naher Arm: aus dem Ärmel nach vorn unten, Hand hält das Paket vor dem Bauch
		var hand := xf * (Vector2(36.0, -40.0) * K)
		pose["near_arm"] = [_bp("sleeve"), hand, Vector2(-0.4, 1.0)]
		parcel.position = (xf * (Vector2(60.0, -37.0) * K)).round()
		parcel.rotation = float(pose["rot"])
		_place_glove(glove_a, "glove_grip", hand, float(pose["rot"]))
		# ferner Arm: pendelt hinter dem Rumpf, gegengleich zum fernen Bein
		var sh := _bp("shoulder_far")
		var th: float = pose["arm"]
		var fhand := sh + Vector2(sin(th), cos(th)) * (L_ARM * 0.86)
		pose["far_arm"] = [sh, fhand, Vector2(-1.0, 0.2)]
		var tube := _tube(sh, fhand, L_ARM, Vector2(-1.0, 0.2))
		var tan: Vector2 = tube[tube.size() - 1] - tube[tube.size() - 3]
		_place_glove(glove_back, "glove_open", fhand, tan.angle())
		pose["near_hip"] = _bp("hip_near")
		pose["far_hip"] = _bp("hip_far")
	else:
		# Vorderansicht: links (vom Betrachter) hält das Paket vor dem Bauch, rechts winkt
		var hand_l := xf * (Vector2(-22.0, -34.0) * K)
		pose["arm_l"] = [_bp("sleeve_l"), hand_l, Vector2(-0.6, 1.0)]
		parcel.position = (xf * (Vector2(4.0, -31.0) * K)).round()
		parcel.rotation = 0.0
		_place_glove(glove_a, "glove_grip", hand_l, 0.0)
		var sh_r := _bp("sleeve_r")
		var rest := sh_r + Vector2(10.0, 74.0) * K
		var ph: float = pose["wave_phase"]
		var up := sh_r + Vector2(36.0 + 15.0 * sin(ph), -62.0 + 4.0 * abs(cos(ph))) * K
		var hand_r: Vector2 = rest.lerp(up, float(pose["wave_raise"]))
		var hint := Vector2(-cos(ph), 0.0) if pose["wave_raise"] >= 1.0 else Vector2(1.0, 0.0)
		pose["arm_r"] = [sh_r, hand_r, hint]
		var tube := _tube(sh_r, hand_r, L_ARM, hint)
		var tan: Vector2 = tube[tube.size() - 1] - tube[tube.size() - 3]
		var g_name := "glove_wave" if pose["wave_raise"] > 0.5 else "glove_open"
		_place_glove(glove_b, g_name, hand_r, tan.angle() + 0.25 * sin(ph) * float(pose["wave_raise"]))
		pose["hip_l"] = _bp("hip_l")
		pose["hip_r"] = _bp("hip_r")
	for n in [shadow_layer, back_layer, leg_layer, face_layer, front_layer]:
		n.queue_redraw()


# ---------------------------------------------------------------- Gummischläuche

func _qbez(a: Vector2, c: Vector2, b: Vector2, n: int) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in range(n + 1):
		var t := float(i) / n
		pts.append(a * (1.0 - t) * (1.0 - t) + c * 2.0 * t * (1.0 - t) + b * t * t)
	return pts


func _length(pts: PackedVector2Array) -> float:
	var s := 0.0
	for i in range(pts.size() - 1):
		s += pts[i].distance_to(pts[i + 1])
	return s


func _tube(a: Vector2, b: Vector2, length: float, hint: Vector2) -> PackedVector2Array:
	# Bogen k so wählen, dass die Kurve die Länge length hat (Bisektion); Seite nach hint
	var d := b - a
	var chord := d.length()
	var mid := (a + b) * 0.5
	var n := Vector2(-d.y, d.x).normalized()
	if n.dot(hint) < 0.0:
		n = -n
	if chord >= length - 0.01:
		return _qbez(a, mid, b, 16)
	var lo := 0.0
	var hi := length
	for i in range(24):
		var k := (lo + hi) * 0.5
		if _length(_qbez(a, mid + n * k, b, 16)) < length:
			lo = k
		else:
			hi = k
	return _qbez(a, mid + n * lo, b, 16)


func _draw_tube(ci: CanvasItem, pts: PackedVector2Array, w: float, col: Color) -> void:
	var a := pts[0]
	var b := pts[pts.size() - 1]
	ci.draw_polyline(pts, ink, w + 2.0 * INK_W, true)
	ci.draw_circle(a, w * 0.5 + INK_W, ink, true, -1.0, true)
	ci.draw_circle(b, w * 0.5 + INK_W, ink, true, -1.0, true)
	ci.draw_polyline(pts, col, w, true)
	ci.draw_circle(a, w * 0.5, col, true, -1.0, true)
	ci.draw_circle(b, w * 0.5, col, true, -1.0, true)
	# Glanzlinie auf der Lichtseite (oben links), wie die weißen Glanzstriche der Cels
	var hl := PackedVector2Array()
	var n := pts.size()
	for i in range(int(n * 0.25), int(n * 0.6)):
		var tdir := (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
		var nrm := Vector2(-tdir.y, tdir.x)
		if nrm.dot(Vector2(-0.6, -0.8)) < 0.0:
			nrm = -nrm
		hl.append(pts[i] + nrm * (w * 0.22))
	if hl.size() > 1:
		ci.draw_polyline(hl, Color(shine, 0.28), max(1.5, w * 0.16), true)


func _ellipse(c: Vector2, r: Vector2, rot: float, n := 28) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in range(n):
		var t := TAU * i / n
		pts.append(c + Vector2(cos(t) * r.x, sin(t) * r.y).rotated(rot))
	return pts


func _draw_foot(ci: CanvasItem, ankle: Vector2, tilt: float, col: Color, front_dir := 1.0, front := false) -> void:
	# Fuß: Oval, Knöchel im hinteren Drittel; Sohle berührt bei tilt = 0 den Boden (GROUND)
	var r := (Vector2(17.0, 8.0) if not front else Vector2(12.0, 8.0)) * K
	var off := (Vector2(8.0 * front_dir, 1.0) if not front else Vector2(5.0 * front_dir, 1.0)) * K
	var rot := tilt * front_dir if not front else 0.35 * front_dir
	var c := ankle + off.rotated(rot)
	if front:
		# Vorderansicht: gedrehtes Oval so setzen, dass die Sohle auf derselben Zeile liegt wie seitlich
		var R := r + Vector2(INK_W, INK_W)
		c.y = ankle.y + off.y + r.y + INK_W - sqrt(pow(R.x * sin(rot), 2.0) + pow(R.y * cos(rot), 2.0))
	ci.draw_colored_polygon(_ellipse(c, r + Vector2(INK_W, INK_W), rot), ink)
	ci.draw_colored_polygon(_ellipse(c, r, rot), col)
	ci.draw_colored_polygon(_ellipse(c + Vector2(r.x * 0.35 * front_dir, -r.y * 0.45).rotated(rot),
			Vector2(r.x * 0.28, r.y * 0.2), rot - 0.2 * front_dir, 12), Color(shine, 0.55))


func _draw_shadow(ci: CanvasItem) -> void:
	if pose.is_empty():
		return
	var root: Vector2 = pose["root"]
	var f := 1.0 - (float(pose["hp"]) / K - 61.0) * 0.03
	ci.draw_colored_polygon(_ellipse(Vector2(root.x + 4.0 * K, GROUND + 1.0), Vector2(46.0, 7.0) * K * f, 0.0, 32),
			Color(0.08, 0.04, 0.03, 0.30))


func _draw_back(ci: CanvasItem) -> void:
	if pose.is_empty() or pose["view"] != "side":
		return
	var a: Array = pose["far_arm"]
	_draw_tube(ci, _tube(a[0], a[1], L_ARM, a[2]), W_ARM, fur_far)


func _draw_legs(ci: CanvasItem) -> void:
	if pose.is_empty():
		return
	if pose["view"] == "side":
		_draw_tube(ci, _tube(pose["far_hip"], pose["far_ankle"], L_LEG, Vector2(1, 0)), W_LEG, fur_far)
		_draw_foot(ci, pose["far_ankle"], pose["far_tilt"], fur_far)
		_draw_tube(ci, _tube(pose["near_hip"], pose["near_ankle"], L_LEG, Vector2(1, 0)), W_LEG, fur)
		_draw_foot(ci, pose["near_ankle"], pose["near_tilt"], fur)
	else:
		_draw_tube(ci, _tube(pose["hip_l"], pose["l_ankle"], L_LEG, Vector2(-1, 0)), W_LEG, fur)
		_draw_tube(ci, _tube(pose["hip_r"], pose["r_ankle"], L_LEG, Vector2(1, 0)), W_LEG, fur)
		_draw_foot(ci, pose["l_ankle"], 0.0, fur, -1.0, true)
		_draw_foot(ci, pose["r_ankle"], 0.0, fur, 1.0, true)


func _draw_face(ci: CanvasItem) -> void:
	if pose.is_empty() or pose["view"] != "front" or not pose["blink"]:
		return
	# Lidschlag: Pupille mit Augenweiß abdecken, geschlossenes Auge als Tuschebogen (fröhlich zugekniffen)
	for e in ["eye_l", "eye_r"]:
		var c := _bp(e)
		ci.draw_colored_polygon(_ellipse(c, Vector2(4.6, 8.8) * K, 0.0, 24), Color(0.97, 0.9, 0.78))
		ci.draw_arc(c + Vector2(0, -3.0) * K, 4.6 * K, 0.25, PI - 0.25, 12, ink, 2.4 * K, true)


func _draw_front(ci: CanvasItem) -> void:
	if pose.is_empty():
		return
	if pose["view"] == "side":
		var a: Array = pose["near_arm"]
		_draw_tube(ci, _tube(a[0], a[1], L_ARM, a[2]), W_ARM, fur)
	else:
		for key in ["arm_l", "arm_r"]:
			var a: Array = pose[key]
			_draw_tube(ci, _tube(a[0], a[1], L_ARM, a[2]), W_ARM, fur)
