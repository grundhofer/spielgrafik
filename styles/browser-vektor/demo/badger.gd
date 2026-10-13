extends Node2D
## Dachs-Kurier als Symbol-Puppe: wenige Teile (Kopf, Rumpf, Arme, Beine, Füße, Schal),
## jedes ein eigener Knoten mit Drehpunkt am Gelenk. Gezeichnet in Puppen-Koordinaten
## (Boden y = 0, Hüftmitte x = 0, Blick nach rechts); bewegt wird nur über Transformationen.

const V = preload("res://vec.gd")

const S := 18.0          # Schrittlänge (Bühnenpixel)
const LK := 16.0         # Bein Hüfte–Knöchel
const HIP_Y := -20.0     # Hüfthöhe im Stand
const ANKLE := 4.0       # Knöchel über dem Boden
const LIFT := 3.6        # Fußhub beim Schwingen
const BOB := 0.6         # Anteil des Pendelwegs, um den die Hüfte absinkt
const N_STEPS := 11

const FUR := Color("3d3943")
const FUR_LIGHT := Color("57525e")
const WHITE := Color("f3eee2")
const STRIPE := Color("221f28")
const CAP := Color("3f7238")
const CAP_DARK := Color("2e5628")
const CAP_LIGHT := Color("6b9a5c")
const BAND := Color("6b4024")
const BRASS := Color("e3b440")
const VEST := Color("4b7d3b")
const VEST_DARK := Color("36602c")
const VEST_LIGHT := Color("6f9f5a")
const SHIRT := Color("f2e5c6")
const SCARF := Color("d43a33")
const SCARF_DARK := Color("a2262a")
const SATCHEL := Color("8c5428")
const SATCHEL_DARK := Color("6b3d1c")
const PARCEL := Color("c99a5c")
const PARCEL_DARK := Color("a5773f")
const STRING := Color("f3e5c2")
const FAR_TINT := Color(0.68, 0.68, 0.76)

var x0 := 0.0            # Hüfte zu Beginn des Gangs
var shadow: Node2D
var far_leg: Node2D
var near_leg: Node2D
var far_foot: Node2D
var near_foot: Node2D
var body: Node2D
var head: Node2D
var eye: Node2D
var pupil: Node2D
var far_arm: Node2D
var near_arm: Node2D
var scarf_end: Node2D
var hip := Vector2(0, HIP_Y)
var hop := 0.0           # Sprunghöhe (für den Freudenhüpfer)
var feet_x := Vector2.ZERO   # x der Füße (nah, fern) im Stand


func _init() -> void:
	name = "Badger"
	shadow = V.group(self, "Shadow")
	V.fill(shadow, V.ellipse(Vector2.ZERO, 21, 3.2, 28), Color(0.08, 0.04, 0.12, 0.35))
	far_leg = _leg("FarLeg")
	far_foot = _foot("FarFoot")
	near_leg = _leg("NearLeg")
	near_foot = _foot("NearFoot")
	far_leg.modulate = FAR_TINT
	far_foot.modulate = FAR_TINT
	body = _pivot(self, "Body", Vector2(0, HIP_Y))
	var art: Node2D = body.get_child(0)
	_far_arm(art)
	_torso(art)
	_scarf_end(art)
	_parcel(art)
	_near_arm(art)
	_head(art)
	_scarf_wrap(art)


## Drehpunkt-Knoten: Gruppe an p, darin eine Gegen-Verschiebung, damit die Teile in
## Puppen-Koordinaten gezeichnet werden können.
func _pivot(parent: Node, nm: String, p: Vector2) -> Node2D:
	var piv := V.group(parent, nm, p)
	V.group(piv, "Art", -p)
	return piv


func _leg(nm: String) -> Node2D:
	var g := V.group(self, nm)
	var cap := V.capsule(Vector2(0, -1), Vector2(0, LK - 1.5), 5.0, 4.6)
	V.shape(g, cap, FUR, 1.6, 0.4)
	V.fill(g, V.capsule(Vector2(-2.2, 1), Vector2(-2.4, LK - 2), 1.2, 0.8), FUR_LIGHT)
	return g


func _foot(nm: String) -> Node2D:
	var g := V.group(self, nm)
	var paw := V.smooth([Vector2(-6, 0), Vector2(-7, -3.8), Vector2(-4, -7.2), Vector2(3, -7.4), Vector2(8, -5), Vector2(10.5, -1.4), Vector2(9.5, 0)], true, 6)
	V.fill(g, paw, FUR)
	V.fill(g, V.smooth([Vector2(-4, -5.6), Vector2(0, -6.6), Vector2(3, -6.4), Vector2(-1, -5.2)], true, 4), FUR_LIGHT)
	V.ink(g, paw, 1.6, 0.4)
	for c in [Vector2(7.2, -2.4), Vector2(9.6, -1.4)]:
		V.stroke(g, PackedVector2Array([c, c + Vector2(1.6, 0.9)]), 1.0, 0.1, 0.6, 0.3, WHITE)
	return g


func _torso(art: Node2D) -> void:
	var torso := V.smooth([Vector2(-4, -11), Vector2(-15, -14), Vector2(-20, -25), Vector2(-20, -37), Vector2(-15, -47),
		Vector2(-6, -54), Vector2(6, -56), Vector2(15, -51), Vector2(20, -41), Vector2(22, -29), Vector2(19, -17), Vector2(10, -11)], true, 8)
	V.fill(art, torso, FUR)
	V.fill(art, V.smooth([Vector2(2, -11.5), Vector2(12, -12.5), Vector2(19, -18), Vector2(21, -27), Vector2(17, -30), Vector2(9, -25), Vector2(3, -17)], true, 6), WHITE)
	V.fill(art, V.smooth([Vector2(9, -50), Vector2(15, -50), Vector2(20, -40), Vector2(21.5, -30), Vector2(16, -29), Vector2(12, -40)], true, 6), SHIRT)
	var vest := V.smooth([Vector2(-19.5, -24), Vector2(-20, -37), Vector2(-15, -47), Vector2(-6, -53.5), Vector2(4, -54.5), Vector2(10, -50),
		Vector2(12.5, -40), Vector2(16, -30), Vector2(15, -24), Vector2(6, -21), Vector2(-8, -20)], true, 7)
	V.fill(art, vest, VEST)
	V.fill(art, V.smooth([Vector2(-19.5, -24), Vector2(-20, -33), Vector2(-12, -29), Vector2(2, -25), Vector2(15, -25), Vector2(6, -21), Vector2(-8, -20)], true, 6), VEST_DARK)
	V.fill(art, V.smooth([Vector2(-16, -42), Vector2(-11, -49), Vector2(-4, -52), Vector2(-9, -47), Vector2(-14, -38)], true, 5), VEST_LIGHT)
	V.ink(art, vest, 1.1, 0.5, [0.15])
	V.stroke(art, PackedVector2Array([Vector2(-3, -31.5), Vector2(4, -31), Vector2(9, -31.6)]), 0.9, 0.3, 0.3, 0.2)
	for b in [Vector2(12.6, -43), Vector2(14.6, -34)]:
		V.shape(art, V.ellipse(b, 1.3, 1.3, 10), BRASS, 0.6)
	# Umhängetasche hinten an der Hüfte, Riemen über die Brust
	var sat := V.rpoly([Vector2(-26, -37), Vector2(-11, -37), Vector2(-10, -20), Vector2(-25, -20)], 3.0)
	V.fill(art, sat, SATCHEL)
	V.fill(art, V.rpoly([Vector2(-26, -37), Vector2(-11, -37), Vector2(-11, -29), Vector2(-25.5, -29)], [3, 3, 1, 1]), SATCHEL_DARK)
	V.shape(art, V.rpoly([Vector2(-20, -31), Vector2(-16, -31), Vector2(-16, -27), Vector2(-20, -27)], 0.8), BRASS, 0.7)
	V.ink(art, sat, 1.3, 0.45)
	var strap := V.smooth([Vector2(-14, -36), Vector2(-4, -44), Vector2(6, -51), Vector2(12, -55)], false, 6)
	V.stroke(art, strap, 3.0, 0.0, 0.0, 1.0, SATCHEL_DARK)
	V.ink(art, torso, 1.8, 0.4)


func _far_arm(art: Node2D) -> void:
	far_arm = _pivot(art, "FarArm", Vector2(-8, -48))
	var a: Node2D = far_arm.get_child(0)
	far_arm.modulate = FAR_TINT
	V.shape(a, V.capsule(Vector2(-8, -49), Vector2(-9, -39), 4.6, 4.2), SHIRT, 1.3)
	V.shape(a, V.capsule(Vector2(-9, -38), Vector2(-10, -30), 3.6, 3.4), FUR, 1.3)
	V.shape(a, V.ellipse(Vector2(-10, -28), 3.6, 3.2, 14), FUR, 1.3)


func _near_arm(art: Node2D) -> void:
	near_arm = _pivot(art, "NearArm", Vector2(5, -49))
	var a: Node2D = near_arm.get_child(0)
	var fore := V.capsule(Vector2(6, -41), Vector2(17, -33), 3.8, 3.4)
	V.shape(a, fore, FUR, 1.5)
	V.fill(a, V.capsule(Vector2(7, -42.5), Vector2(14, -37), 1.0, 0.7), FUR_LIGHT)
	var paw := V.ellipse(Vector2(19, -32.5), 4.0, 3.6, 16)
	V.shape(a, paw, FUR, 1.4)
	for c in [Vector2(21.5, -34.5), Vector2(22.5, -32), Vector2(21.8, -29.6)]:
		V.stroke(a, PackedVector2Array([c, c + Vector2(1.4, 0.3)]), 0.8, 0.1, 0.6, 0.3, WHITE)
	var sleeve := V.rpoly([Vector2(-1, -53), Vector2(9.5, -53), Vector2(11, -41), Vector2(0, -39.5)], [4, 4, 3, 3])
	V.fill(a, sleeve, SHIRT)
	V.fill(a, V.rpoly([Vector2(0, -43), Vector2(11, -44.5), Vector2(11, -41), Vector2(0, -39.5)], 1.5), Color("dccfae"))
	V.ink(a, sleeve, 1.5, 0.4)
	V.stroke(a, PackedVector2Array([Vector2(1, -44), Vector2(10.4, -45)]), 0.8, 0.2, 0.2, 0.3)


func _parcel(art: Node2D) -> void:
	var box := V.rpoly([Vector2(2, -39), Vector2(21, -39), Vector2(21, -25), Vector2(2, -25)], 1.6)
	V.fill(art, box, PARCEL)
	V.fill(art, PackedVector2Array([Vector2(15, -38), Vector2(20, -38), Vector2(20, -26), Vector2(15, -26)]), PARCEL_DARK)
	V.stroke(art, PackedVector2Array([Vector2(11, -38.5), Vector2(11, -25.5)]), 1.1, 0.0, 0.0, 1.0, STRING)
	V.stroke(art, PackedVector2Array([Vector2(2.5, -32), Vector2(20.5, -32)]), 1.1, 0.0, 0.0, 1.0, STRING)
	V.ink(art, box, 1.4, 0.45)


func _head(art: Node2D) -> void:
	head = _pivot(art, "Head", Vector2(6, -55))
	var h: Node2D = head.get_child(0)
	# Ohr hinten
	var ear := V.ellipse(Vector2(-6, -70), 4.4, 4.0, 18)
	V.shape(h, ear, FUR, 1.3)
	V.fill(h, V.ellipse(Vector2(-6, -70), 2.4, 2.1, 14), WHITE)
	var face := V.smooth([Vector2(-12, -60), Vector2(-12, -69), Vector2(-6, -77), Vector2(6, -79.5), Vector2(16, -75), Vector2(25, -68.5),
		Vector2(32.5, -62.5), Vector2(32, -57.5), Vector2(25, -54), Vector2(12, -52), Vector2(-2, -53), Vector2(-9, -55)], true, 8)
	V.fill(h, face, WHITE)
	V.fill(h, V.smooth([Vector2(-12, -60), Vector2(-12, -69), Vector2(-8, -74), Vector2(-2, -71), Vector2(0, -63), Vector2(-3, -54), Vector2(-9, -55)], true, 6), FUR)
	V.fill(h, V.smooth([Vector2(28, -63.5), Vector2(19, -70), Vector2(7, -72.5), Vector2(-4, -71.5), Vector2(-5, -65), Vector2(4, -64), Vector2(17, -61.5), Vector2(27, -59.5)], true, 6), STRIPE)
	V.fill(h, V.smooth([Vector2(14, -55), Vector2(24, -55.5), Vector2(28, -54.5), Vector2(22, -53.2), Vector2(14, -53.4)], true, 4), Color("d9d2c4"))
	V.ink(h, face, 1.7, 0.4)
	# Auge (Blinzeln über scale.y der Gruppe)
	eye = V.group(h, "Eye", Vector2(12.5, -66.8))
	V.shape(eye, V.ellipse(Vector2.ZERO, 3.5, 4.2, 20), Color.WHITE, 0.8)
	pupil = V.group(eye, "Pupil", Vector2(1.0, 0.4))
	V.fill(pupil, V.ellipse(Vector2.ZERO, 2.2, 2.6, 16), Color("15121a"))
	V.fill(pupil, V.ellipse(Vector2(0.8, -1.1), 0.9, 0.9, 10), Color.WHITE)
	# Nase, Mund
	var nose := V.ellipse(Vector2(31.5, -60.2), 3.4, 2.6, 18)
	V.fill(h, nose, Color("1d1a22"))
	V.fill(h, V.ellipse(Vector2(32.2, -61.3), 1.2, 0.7, 10), Color("8a8494"))
	V.stroke(h, V.smooth([Vector2(28.5, -56.4), Vector2(25, -55.2), Vector2(21, -55.8)], false, 5), 1.0, 0.2, 0.5, 0.0)
	# Mütze
	var crown := V.smooth([Vector2(-13.5, -71), Vector2(-11.5, -79), Vector2(-3, -85.5), Vector2(9, -86.5), Vector2(19, -81.5),
		Vector2(21.5, -75.5), Vector2(16, -74.2), Vector2(2, -73)], true, 7)
	V.fill(h, crown, CAP)
	V.fill(h, V.smooth([Vector2(-13.5, -71), Vector2(-12.5, -76), Vector2(-4, -77), Vector2(8, -77.5), Vector2(19, -77), Vector2(21.5, -75.5), Vector2(16, -74.2), Vector2(2, -73)], true, 5), CAP_DARK)
	V.fill(h, V.smooth([Vector2(-6, -81), Vector2(0, -84.6), Vector2(8, -85.4), Vector2(2, -82.4)], true, 5), CAP_LIGHT)
	V.ink(h, crown, 1.7, 0.4)
	var band := V.smooth([Vector2(-13.5, -71.5), Vector2(2, -74), Vector2(18, -76.2), Vector2(18.6, -73.2), Vector2(2, -70.6), Vector2(-13.2, -68.4)], true, 4)
	V.shape(h, band, BAND, 1.1)
	var peak := V.smooth([Vector2(14, -75.8), Vector2(24, -77), Vector2(31, -74.6), Vector2(27, -72.4), Vector2(15, -72.4)], true, 5)
	V.shape(h, peak, CAP_DARK, 1.5)
	V.shape(h, V.ellipse(Vector2(16.5, -74.8), 1.8, 1.8, 12), BRASS, 0.8)
	V.fill(h, V.ellipse(Vector2(16.0, -75.4), 0.6, 0.6, 8), Color("fff2b0"))


func _scarf_end(art: Node2D) -> void:
	scarf_end = _pivot(art, "ScarfEnd", Vector2(-9, -54))
	var a: Node2D = scarf_end.get_child(0)
	var tail := V.smooth([Vector2(-12, -56), Vector2(-6, -55), Vector2(-7, -42), Vector2(-9, -31), Vector2(-12, -26), Vector2(-17, -27), Vector2(-15, -40)], true, 7)
	V.fill(a, tail, SCARF)
	V.fill(a, V.smooth([Vector2(-7.5, -50), Vector2(-7, -42), Vector2(-9, -31), Vector2(-12, -26), Vector2(-11, -34), Vector2(-10, -44)], true, 5), SCARF_DARK)
	V.ink(a, tail, 1.4, 0.4)
	for k in 4:
		var p := Vector2(-16.0 + k * 1.6, -26.6 + k * 0.4)
		V.stroke(a, PackedVector2Array([p, p + Vector2(-0.6, 4.0)]), 1.2, 0.0, 0.6, 0.6, SCARF_DARK)
	for y in [-48.0, -41.0, -34.0]:
		V.stroke(a, PackedVector2Array([Vector2(-14.2 + (y + 48) * 0.05, y), Vector2(-7.6 - (y + 48) * 0.1, y + 0.6)]), 0.8, 0.3, 0.3, 0.0, SCARF_DARK)


func _scarf_wrap(art: Node2D) -> void:
	var wrap := V.smooth([Vector2(-12, -56.5), Vector2(-4, -60.5), Vector2(8, -60), Vector2(18, -57), Vector2(20.5, -52.5),
		Vector2(14, -48.5), Vector2(2, -49), Vector2(-9, -50), Vector2(-13.5, -53)], true, 7)
	V.fill(art, wrap, SCARF)
	V.fill(art, V.smooth([Vector2(-13, -53), Vector2(-4, -52), Vector2(8, -52), Vector2(18, -52), Vector2(14, -48.5), Vector2(2, -49), Vector2(-9, -50)], true, 5), SCARF_DARK)
	for x in [-7.0, -1.0, 5.0, 11.0]:
		V.stroke(art, PackedVector2Array([Vector2(x, -59), Vector2(x + 0.8, -51)]), 0.8, 0.3, 0.3, 0.0, SCARF_DARK)
	V.ink(art, wrap, 1.6, 0.4)
	var knot := V.ellipse(Vector2(18.5, -51.5), 3.6, 3.4, 16)
	V.shape(art, knot, SCARF, 1.3)
	var flap := V.smooth([Vector2(17, -49), Vector2(21, -48), Vector2(22, -41), Vector2(19.5, -38.5), Vector2(17.5, -42)], true, 5)
	V.shape(art, flap, SCARF, 1.3)
	V.stroke(art, PackedVector2Array([Vector2(18.2, -38.8), Vector2(18.0, -36.4)]), 1.0, 0.0, 0.6, 0.6, SCARF_DARK)
	V.stroke(art, PackedVector2Array([Vector2(20.4, -38.8), Vector2(20.6, -36.6)]), 1.0, 0.0, 0.6, 0.6, SCARF_DARK)


# ------------------------------------------------------------------ Posen

func _place_leg(leg: Node2D, hip_pt: Vector2, ankle: Vector2) -> void:
	var d := ankle - hip_pt
	leg.position = hip_pt
	leg.rotation = atan2(-d.x, d.y)
	leg.scale = Vector2(1, d.length() / LK)


func _apply(hip_pt: Vector2, near_ft: Vector2, far_ft: Vector2, near_rot: float, far_rot: float, sq: float) -> void:
	hip = hip_pt
	near_foot.position = near_ft
	near_foot.rotation = near_rot
	far_foot.position = far_ft
	far_foot.rotation = far_rot
	_place_leg(near_leg, hip_pt + Vector2(3, 0), near_ft + Vector2(0, -ANKLE))
	_place_leg(far_leg, hip_pt + Vector2(-4, 0), far_ft + Vector2(0, -ANKLE))
	body.position = hip_pt
	body.scale = Vector2(1.0 + sq, 1.0 - sq)
	shadow.position = Vector2(hip_pt.x + 2, -0.5)
	var lift := clampf((HIP_Y - hip_pt.y) / -12.0, 0.0, 1.0)
	shadow.scale = Vector2(1.0 - 0.3 * lift, 1.0 - 0.3 * lift)


static func ease_io(u: float) -> float:
	return 0.5 - 0.5 * cos(PI * u)


## p = Schritte seit Beginn, 0 … N_STEPS + 1 (der letzte Schritt schließt die Füße).
func walk_pose(p: float) -> void:
	var near_ft: Vector2
	var far_ft: Vector2
	var hip_x: float
	var near_rot := 0.0
	var far_rot := 0.0
	var stance_x: float
	var u: float
	if p < N_STEPS:
		var k := int(floor(p))
		u = p - k
		hip_x = x0 + p * S
		stance_x = x0 + k * S + S * 0.5
		var sw_from := x0 + k * S - S * 0.5
		var sw_to := x0 + (k + 1) * S + S * 0.5
		var sw := Vector2(lerpf(sw_from, sw_to, ease_io(u)), -LIFT * sin(PI * u))
		var sw_rot := -0.28 * sin(PI * u)
		if k % 2 == 0:
			near_ft = Vector2(stance_x, 0)
			far_ft = sw
			far_rot = sw_rot
		else:
			far_ft = Vector2(stance_x, 0)
			near_ft = sw
			near_rot = sw_rot
	else:
		# Schlussschritt: hinterer Fuß schließt auf, Hüfte rückt S/4 vor
		u = clampf(p - N_STEPS, 0.0, 1.0)
		var e := ease_io(u)
		var h0 := x0 + N_STEPS * S
		hip_x = h0 + S * 0.25 * (1.0 - pow(1.0 - u, 2.0))
		stance_x = h0 + S * 0.5
		var back_from := h0 - S * 0.5
		var back_to := h0 + S * 0.25 - 3.0
		var sw := Vector2(lerpf(back_from, back_to, e), -LIFT * 0.7 * sin(PI * u))
		var front := Vector2(stance_x, 0)
		if (N_STEPS - 1) % 2 == 0:
			far_ft = front
			near_ft = sw
			near_rot = -0.2 * sin(PI * u)
		else:
			near_ft = front
			far_ft = sw
			far_rot = -0.2 * sin(PI * u)
	var dx := hip_x - stance_x
	var drop := LK - sqrt(LK * LK - dx * dx)
	var hip_y := HIP_Y + BOB * drop
	var c := cos(TAU * u) if p < N_STEPS else 0.0
	_apply(Vector2(hip_x, hip_y), near_ft, far_ft, near_rot, far_rot, 0.022 * c)
	feet_x = Vector2(near_ft.x, far_ft.x)
	# Arme, Kopf, Schal folgen dem Gang
	var walking := 1.0 if p < N_STEPS else 1.0 - clampf(p - N_STEPS, 0.0, 1.0)
	far_arm.rotation = -0.55 * cos(PI * p) * walking
	near_arm.rotation = 0.05 * sin(TAU * u) * walking
	head.rotation = 0.045 * sin(TAU * u - 0.9) * walking
	scarf_end.rotation = (0.55 + 0.12 * sin(TAU * p * 0.5)) * walking + 0.12 * (1.0 - walking)


## Stand nach dem Gang: Füße bleiben, Rumpf atmet / staucht (sq), Sprung über hop.
func stand_pose(sq: float, hop_y: float) -> void:
	var hx := hip.x
	var near_ft := Vector2(feet_x.x, -hop_y)
	var far_ft := Vector2(feet_x.y, -hop_y)
	var hy := HIP_Y + sq * 9.0 - hop_y
	_apply(Vector2(hx, hy), near_ft, far_ft, 0.0, 0.0, sq)
