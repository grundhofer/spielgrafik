extends Node2D
## Der Dachs als Papier-Gliederpuppe: starre Papierteile an Musterklammern (Rumpf mit Schalwicklung und Tasche,
## Kopf, je Arm Oberarm und Unterarm, Paket, Schalende, je Bein Schienbein und Fuß). Die Teile stammen aus
## KI-Teilbildern (prep_puppet.py), Lage und Drehpunkte aus art/puppet/rig.json in Pixeln der KI-Gesamtfigur (C1).
## Ferner Arm und fernes Bein sind abgedunkelte Kopien der nahen; die ferne Pfote hält das Paket.
##
## Gang aus Formeln: starres Bein, der Standfuß steht fest, die Hüfte läuft auf dem Kreis um den Knöchel;
## das Schwungbein gleitet im verdeckten Hüftgelenk nach oben, damit der Fuß nicht schleift. Abbremsen mit
## stetiger Geschwindigkeit, danach Blick zur Laterne, Winken mit dem nahen Arm (Oberarm hoch, Unterarm schwingt
## am Ellbogen auf Mützenhöhe) und zwei Lidschläge.
## Die Pose wird auf das 15er-Raster gelegt (Legetrick-Takt), die Umgebung läuft mit 30 Bildern/s.

const SHADOW_OFF := Vector2(2.5, 3.5)
const SHADOW_A := 0.42
const PHI0 := 0.4887          # 28° Beinwinkel an Fersenaufsatz und Abstoß
const POSE_FPS := 15.0
const HOLD_U := -44.0          # ferner Oberarm (Grad, 0 = hängend): Pfote auf dem Paket (C1 650/660)
const HOLD_F := -18.0          # ferner Unterarm relativ zum Oberarm
const WAVE_U := -185.0         # naher Oberarm beim Winken: senkrecht, leicht nach hinten (Pfote hinter der Mütze)
const WAVE_F := 15.0           # naher Unterarm relativ, schwingt ±20° über Augenhöhe (Auge bei C1 y 306)

var S := 0.1784               # Bildschirm-px je C1-px
var rig: Dictionary
var c1: Dictionary
var hip_n_c1: Vector2
var parts := {}               # Name -> {"node", "shadow"}
var elbow_off: Vector2        # Schulter -> Ellbogen (Bildschirm-px, Oberarm in Ruhe)
var far_sh: Vector2           # ferne Schulter gegenüber der Hüfte (Rumpfraum)
var parcel_local: Transform2D # Paket im Raum des fernen Unterarms
var mat: ShaderMaterial
var lid: Polygon2D
var smooth := false
var only: Array = []
var no_shadows := false

# Gang (Bildschirm-px, Sekunden)
var G := 600.0                # Sohlenzeile
var L := 0.0                  # Hüfte–Knöchel
var ankle_h := 0.0            # Knöchel über der Sohle
var step := 0.0
var x_start := 440.0
var v := 72.0
var p0 := 0.25
var k_end := 9
var t_dec := 0.0
var T_d := 0.5
var t_end := 0.0
var x_stop := 0.0
var legs := []                # [{"off": Vector2, "shin": name, "foot": name}]

# Schalfeder
var scarf_a := 0.0
var scarf_w := 0.0
var last_vx := 0.0
var shown_scarf := 0.0
var last_tick := -1


func setup(rig_data: Dictionary, material: ShaderMaterial, ground: float, start_x: float) -> void:
	rig = rig_data
	mat = material
	G = ground
	x_start = start_x
	S = float(rig["screen_scale"])
	c1 = rig["c1"]
	hip_n_c1 = _v(c1["hip_n"])
	L = (_v(c1["ankle_n"]).y - hip_n_c1.y) * S
	ankle_h = (float(c1["sole"]) - _v(c1["ankle_n"]).y) * S
	step = 2.0 * L * sin(PHI0)
	x_stop = x_start + (k_end + 0.5 - p0) * step
	t_dec = (x_stop - x_start - v * T_d * 0.5) / v
	t_end = t_dec + T_d
	var far := (_v(c1["hip_f"]) - hip_n_c1) * S
	legs = [{"off": Vector2.ZERO, "shin": "shin_n", "foot": "foot_n"},
			{"off": far, "shin": "shin_f", "foot": "foot_f"}]
	# Zeichenreihenfolge hinten -> vorn
	var order := [["scarf", "scarf", 1.0], ["foot_f", "foot", 0.72], ["shin_f", "shin", 0.72],
			["foot_n", "foot", 1.0], ["shin_n", "shin", 1.0], ["uarm_f", "upper_arm", 0.72],
			["parcel", "parcel", 1.0], ["farm_f", "forearm", 0.72], ["head", "head", 1.0], ["body", "body", 1.0],
			["farm", "forearm", 1.0], ["uarm", "upper_arm", 1.0]]
	for o in order:
		_add_part(o[0], o[1], o[2])
	# Arme: Ellbogen, ferne Schulter und Paket in der fernen Pfote (so gesetzt, dass es in der Haltepose an
	# seiner Stelle aus der Gesamtfigur liegt)
	elbow_off = (_v(c1["elbow"]) - _v(c1["shoulder"])) * S
	far_sh = (_v(c1["shoulder"]) + _v(c1["far_arm_shift"]) - hip_n_c1) * S
	var u0 := deg_to_rad(HOLD_U)
	var farm0 := Transform2D(u0 + deg_to_rad(HOLD_F), far_sh + elbow_off.rotated(u0))
	parcel_local = farm0.affine_inverse() * Transform2D(0.0, (_v(c1["parcel"]) - hip_n_c1) * S)
	# Musterklammern: Schulter, Ellbogen, nahe Hüfte, naher Knöchel
	_add_pin("uarm", Vector2.ZERO)
	_add_pin("uarm", elbow_off)
	_add_pin("body", Vector2.ZERO)
	_add_pin("shin_n", (_v(c1["ankle_n"]) - hip_n_c1) * S)
	# Lid (Lidschlag): dunkles Papieroval über dem Auge, im Kopfraum
	lid = Polygon2D.new()
	var eye := (Vector2(537, 306) - _v(c1["neck"])) * S
	var pts := PackedVector2Array()
	for i in 14:
		var a := TAU * i / 14.0
		pts.append(eye + Vector2(cos(a) * 3.6, sin(a) * 3.3))
	lid.polygon = pts
	lid.color = Color(0.13, 0.13, 0.15)
	lid.visible = false
	parts["head"]["node"].add_child(lid)
	for a in OS.get_cmdline_user_args():
		if a == "--smooth":
			smooth = true
		elif a.begins_with("--only="):
			only = Array(a.substr(7).split(","))
		elif a == "--no-shadows":
			no_shadows = true
	for k in parts:
		var vis: bool = only.is_empty() or only.has(k)
		parts[k]["node"].visible = vis
		parts[k]["shadow"].visible = vis and not no_shadows


func _v(a) -> Vector2:
	return Vector2(float(a[0]), float(a[1]))


func _add_part(name: String, tex_name: String, shade: float) -> void:
	var meta: Dictionary = rig["parts"][tex_name]
	var piv := _v(meta["pivots"]["root"])
	var pad := float(meta["shadow_pad"])
	var sh := Node2D.new()
	var shs := Sprite2D.new()
	shs.texture = load("res://art/puppet/" + meta["shadow"])
	shs.centered = false
	shs.offset = -piv - Vector2(pad, pad)
	shs.scale = Vector2(0.5, 0.5)
	shs.modulate = Color(1, 1, 1, SHADOW_A)
	sh.add_child(shs)
	add_child(sh)
	var n := Node2D.new()
	var sp := Sprite2D.new()
	sp.texture = load("res://art/puppet/" + meta["file"])
	sp.centered = false
	sp.offset = -piv
	sp.scale = Vector2(0.5, 0.5)
	sp.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	sp.material = mat
	sp.modulate = Color(shade, shade, shade * 1.02)
	n.add_child(sp)
	add_child(n)
	parts[name] = {"node": n, "shadow": sh}


func _add_pin(part: String, at: Vector2) -> void:
	var p := Sprite2D.new()
	p.texture = load("res://art/ui/pin.png")
	p.scale = Vector2(0.3, 0.3)
	p.position = at
	p.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	p.material = mat
	parts[part]["node"].add_child(p)


func hip_x(t: float) -> float:
	if t < t_dec:
		return x_start + v * t
	if t < t_end:
		var tau := t - t_dec
		return x_start + v * t_dec + v * tau - v * tau * tau / (2.0 * T_d)
	return x_stop


func speed(t: float) -> float:
	if t < t_dec:
		return v
	if t < t_end:
		return v * (1.0 - (t - t_dec) / T_d)
	return 0.0


func _ankle_x(k: int, leg: Dictionary) -> float:
	return x_start + (k + 0.5 - p0) * step + leg["off"].x


func _place(name: String, pos: Vector2, rot: float) -> void:
	var n: Node2D = parts[name]["node"]
	n.position = pos
	n.rotation = rot
	var sh: Node2D = parts[name]["shadow"]
	sh.position = pos + SHADOW_OFF
	sh.rotation = rot


func _ease(x: float) -> float:
	x = clampf(x, 0.0, 1.0)
	return x * x * (3.0 - 2.0 * x)


## Federn mit der echten Bildzeit, Anzeige im Posentakt.
func advance(t: float, dt: float) -> void:
	var vx := speed(t)
	var ax := (vx - last_vx) / maxf(dt, 1e-4)
	last_vx = vx
	var wind := 0.10 * sin(t * 2.1) + 0.06 * sin(t * 5.3 + 1.0)
	var target := 0.10 + 0.22 * vx / v + wind
	var sub := 4
	var h := dt / sub
	for i in sub:
		var acc := -60.0 * (scarf_a - target) - 5.0 * scarf_w + 0.004 * ax
		scarf_w += acc * h
		scarf_a += scarf_w * h
	scarf_a = clampf(scarf_a, -0.35, 0.7)
	var tp: float = t if smooth else floor(t * POSE_FPS + 1e-4) / POSE_FPS
	var tick := int(round(tp * 1000.0))
	if tick != last_tick:
		shown_scarf = scarf_a
		last_tick = tick
	pose(tp)


func pose(t: float) -> void:
	var hx := hip_x(t)
	var p := p0 + (hx - x_start) / step
	var vnow := speed(t)
	var settle := 0.0
	if t >= t_end:
		p = k_end + 0.5
		settle = clampf((t - t_end) / 0.2, 0.0, 1.0)
	var k := int(floor(p))
	var s := p - k
	var st: Dictionary = legs[k % 2]
	var sw: Dictionary = legs[(k + 1) % 2]
	# Standbein: Knöchel fest, Hüfte auf dem Kreis
	var a_st := _ankle_x(k, st)
	var phi := asin(clampf((a_st - (hx + st["off"].x)) / L, -1.0, 1.0))
	# jedes Bein steht auf seiner eigenen Bodenzeile (fernes Bein 1 px höher, wie in der Vorlage)
	var hy := G - ankle_h - L * cos(phi)
	var H := Vector2(hx, hy)
	# Rumpf: Vorlage beim Gehen, Wippen je Schritt, im Stand Atmen als leichtes Kippen um die Hüfte
	var walkf := vnow / v
	var idle := clampf((t - t_end) / 0.4, 0.0, 1.0)
	var body_rot := deg_to_rad(2.2) * walkf + deg_to_rad(1.3) * sin(TAU * s) * walkf
	body_rot += idle * deg_to_rad(0.8) * sin(TAU * (t - t_end) / 2.4)
	var bx := Transform2D(body_rot, H)
	_place("body", H, body_rot)
	# Beine
	for leg in [st, sw]:
		var hip: Vector2 = bx * leg["off"]
		var ang := 0.0
		var foot_rot := 0.0
		var ankle: Vector2
		if leg == st:
			ang = -asin(clampf((a_st - hip.x) / L, -1.0, 1.0))
			ankle = Vector2(a_st, G + leg["off"].y - ankle_h)
		else:
			var lift := 4.5 * sin(PI * s) * (1.0 - settle)
			var a0 := _ankle_x(k - 1, leg)
			var a1 := _ankle_x(k + 1, leg)
			var ax := lerpf(a0, a1, _ease(s))
			hip.y -= lift
			ang = -asin(clampf((ax - hip.x) / L, -1.0, 1.0))
			ankle = hip + Vector2(0, L).rotated(ang)
			foot_rot = -deg_to_rad(9.0) * sin(PI * s) * (1.0 - settle)
		_place(leg["shin"], hip, ang)
		_place(leg["foot"], ankle, foot_rot)
	# Kopf: gleicht das Wippen halb aus, schaut nach dem Anhalten zur Laterne hinauf
	var look := _ease((t - t_end - 0.15) / 0.5) - 0.6 * _ease((t - 5.5) / 0.4)
	var head_rot := -0.5 * deg_to_rad(1.3) * sin(TAU * s) * walkf + deg_to_rad(1.2) * sin(TAU * p * 0.5) * walkf
	head_rot += -deg_to_rad(8.0) * look
	_place("head", bx * ((_v(c1["neck"]) - hip_n_c1) * S), body_rot + head_rot)
	# Naher Arm: pendelt gegen das nahe Bein, der Ellbogen beugt sich beim Vorschwingen; danach Winken mit
	# erhobenem Oberarm, der Unterarm schwingt am Ellbogen über Augenhöhe hin und her
	var swing := sin(PI * p) * walkf
	var ua := deg_to_rad(15.0) * swing
	var fa := deg_to_rad(-8.0) + deg_to_rad(8.0) * swing
	var up := _ease((t - 3.85) / 0.35) * (1.0 - _ease((t - 5.35) / 0.4))
	var wave := sin(TAU * (t - 4.2) / 0.5) * _ease((t - 4.15) / 0.15) * (1.0 - _ease((t - 5.15) / 0.2))
	ua = lerpf(ua, deg_to_rad(WAVE_U), up)
	fa = lerpf(fa, deg_to_rad(WAVE_F) + deg_to_rad(20.0) * wave, up)
	var sh := bx * ((_v(c1["shoulder"]) - hip_n_c1) * S)
	_place("uarm", sh, body_rot + ua)
	_place("farm", sh + elbow_off.rotated(body_rot + ua), body_rot + ua + fa)
	# Ferner Arm hält das Paket und schwingt leicht gegenläufig; das Paket hängt an der fernen Pfote
	var ua_f := deg_to_rad(HOLD_U) - deg_to_rad(4.0) * swing
	var shf := bx * far_sh
	var farm_f := Transform2D(body_rot + ua_f + deg_to_rad(HOLD_F), shf + elbow_off.rotated(body_rot + ua_f))
	_place("uarm_f", shf, body_rot + ua_f)
	_place("farm_f", farm_f.origin, farm_f.get_rotation())
	var pt := farm_f * parcel_local
	_place("parcel", pt.origin, pt.get_rotation())
	_place("scarf", bx * ((_v(c1["scarf"]) - hip_n_c1) * S), body_rot + shown_scarf - 0.1)
	# Lidschläge (je zwei Posen)
	lid.visible = (t >= 4.6 and t < 4.73) or (t >= 5.87 and t < 6.0)
