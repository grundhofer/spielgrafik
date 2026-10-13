extends Node2D
## Der Dachs-Kurier als Scherenschnitt-Gliederpuppe: zehn starre Papierteile (Rumpf, Kopf, zwei Arme,
## zwei Beine, zwei Füße, zwei Schalenden) an Gelenken, so wie Schattentheaterfiguren mit Drahtgelenken.
## Keine Verformung: jedes Teil dreht sich nur um seinen Stift. Weil alles schwarz ist, sind Überlappungen
## an den Gelenken unsichtbar; wo der nahe Arm oder das nahe Bein über anderen Teilen liegt, trennt eine
## feine Schnittfuge (gap.gdshader) die Teile wie bei aufeinanderliegenden Scherenschnitten.
##
## Gang: starres Bein, Fuß mit Knöchelgelenk. Im Stand liegt der Fuß flach und fest; die Hüfte läuft auf
## einem Kreis um den Knöchel (umgekehrtes Pendel). Das Schwungbein hebt sich, indem es im Hüftgelenk nach
## oben gleitet (hinter dem Rumpf verborgen), wie man es bei Legefiguren mit der Hand macht.
## Alle Werte hängen nur von der Zeit ab (pose(t)).

const COL := Color(0.07, 0.045, 0.09)
const ALPHA := 18.0              # halber Schrittwinkel (Grad)
const T_STEP := 0.40             # Dauer eines Schritts (s)
const N_WALK := 6                # volle Schritte, dann Abbremsen
const STAND_D := 10.0            # Fußabstand im Stand (px)
const LIFT := 7.0                # Hub des Schwungbeins (px)

var rig: Dictionary
var ground := 576.5             # Sohle 1 px im schwarzen Kai (sonst helle Naht an der Kante)
var start_x := 522.0
var L := 0.0                     # Hüftstift -> Knöchel
var a0 := 0.0                    # Ruhewinkel dieses Vektors (rad, von der Senkrechten, + = nach rechts)
var ankle_h := 0.0               # Knöchel über der Sohle
var beta := 0.0
var t_stop_len := 0.0
var t_stop := 0.0                # Zeitpunkt, an dem die Puppe steht
var stop_x := 0.0
var use_gap := true

var body_back: Node2D
var body_front: Node2D
var neck: Node2D
var shoulder_n: Node2D
var shoulder_f: Node2D
var scarf_root: Node2D
var legs := {}                   # "n"/"f" -> {leg: Node2D, ankle: Node2D}
var sprites := {}
var eyelid: Polygon2D
var scarf_mats := []


func build(rig_path: String) -> void:
	rig = JSON.parse_string(FileAccess.get_file_as_string(rig_path))
	var P: Dictionary = rig["pieces"]
	var J: Dictionary = rig["joints"]
	var r0 := _v(P["leg_n"]["ankle_rel"])
	L = r0.length()
	a0 = atan2(r0.x, r0.y)
	ankle_h = float(P["foot_n"]["sole_rel"])
	beta = asin(STAND_D / (2.0 * L))
	t_stop_len = T_STEP * (deg_to_rad(ALPHA) - beta) / deg_to_rad(ALPHA)
	t_stop = N_WALK * T_STEP + t_stop_len
	stop_x = start_x + N_WALK * 2.0 * L * sin(deg_to_rad(ALPHA)) + L * sin(deg_to_rad(ALPHA)) - L * sin(beta)

	var bbc := BackBufferCopy.new()
	bbc.copy_mode = BackBufferCopy.COPY_MODE_VIEWPORT
	add_child(bbc)

	body_back = Node2D.new()
	add_child(body_back)
	scarf_root = _joint(body_back, _v(J["scarf_root"]))
	for nm in ["scarf_b", "scarf_a"]:
		var s := _piece(scarf_root, nm)
		var m := ShaderMaterial.new()
		m.shader = load("res://shaders/scarf.gdshader")
		m.set_shader_parameter("tex_size", _v(P[nm]["size"]))
		m.set_shader_parameter("root_x", float(P[nm]["pivot"][0]))
		m.set_shader_parameter("phase", 0.0 if nm == "scarf_a" else 2.1)
		s.material = m
		scarf_mats.append(m)
	shoulder_f = _joint(body_back, _v(J["shoulder_f"]))
	_piece(shoulder_f, "arm_f")

	for side in ["f", "n"]:
		var leg := Node2D.new()
		add_child(leg)
		if side == "n":
			_piece(leg, "leg_n_gap", true)
		var ankle := _joint(leg, _v(P["leg_" + side]["ankle_rel"]))
		if side == "n":
			_piece(ankle, "foot_n_gap", true)
		_piece(ankle, "foot_" + side)
		_piece(leg, "leg_" + side)
		legs[side] = {"leg": leg, "ankle": ankle}

	body_front = Node2D.new()
	add_child(body_front)
	neck = _joint(body_front, _v(J["neck"]))
	_piece(neck, "head")
	eyelid = Polygon2D.new()
	var pts := PackedVector2Array()
	var er := float(J["eye_r"]) + 1.2
	for i in 16:
		var a := TAU * i / 16.0
		pts.append(Vector2(cos(a) * er * 1.25, sin(a) * er))
	eyelid.polygon = pts
	eyelid.color = COL
	eyelid.position = _v(rig["eye_rel_head"])
	eyelid.visible = false
	neck.add_child(eyelid)
	_piece(body_front, "torso")
	shoulder_n = _joint(body_front, _v(J["shoulder_n"]))
	_piece(shoulder_n, "arm_n_gap", true)
	_piece(shoulder_n, "arm_n")


func show_only(names: PackedStringArray) -> void:
	# nur diese Teile (samt Futter und Fuge) zeigen, für die Fußmessung
	for k in sprites:
		var base: String = k.trim_suffix("_fill").trim_suffix("_gap")
		sprites[k].visible = base in names
	eyelid.visible = false


func set_lining(on: bool) -> void:
	for k in sprites:
		if k.ends_with("_fill"):
			sprites[k].visible = on


func set_gap(on: bool) -> void:
	use_gap = on
	for k in sprites:
		if k.ends_with("_gap"):
			sprites[k].visible = on


func _v(a) -> Vector2:
	return Vector2(float(a[0]), float(a[1]))


func _joint(parent: Node, pos: Vector2) -> Node2D:
	var n := Node2D.new()
	n.position = pos
	parent.add_child(n)
	return n


func _piece(parent: Node, nm: String, gap := false) -> Sprite2D:
	var base := nm.trim_suffix("_gap")
	var pc: Dictionary = rig["pieces"][base]
	if not gap and ResourceLoader.exists("res://art/puppet/" + nm + "_fill.png"):
		var f := Sprite2D.new()
		f.texture = load("res://art/puppet/" + nm + "_fill.png")
		f.centered = false
		f.offset = -_v(pc["pivot"])
		var fm := ShaderMaterial.new()
		fm.shader = load("res://shaders/lining.gdshader")
		f.material = fm
		parent.add_child(f)
		sprites[nm + "_fill"] = f
	var s := Sprite2D.new()
	s.texture = load("res://art/puppet/" + nm + ".png")
	s.centered = false
	s.offset = -_v(pc["pivot"])
	s.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	if gap:
		var m := ShaderMaterial.new()
		m.shader = load("res://shaders/gap.gdshader")
		s.material = m
	else:
		s.modulate = COL
	parent.add_child(s)
	sprites[nm] = s
	return s


func _leg_rot(angle: float) -> float:
	# gewünschter Winkel des Vektors Hüfte->Knöchel (von der Senkrechten, + = nach vorn/rechts)
	return a0 - angle


func pose(t: float) -> void:
	var al := deg_to_rad(ALPHA)
	var step := 2.0 * L * sin(al)
	var t_walk := N_WALK * T_STEP
	var theta := beta
	var s := 0.0          # Phase des Schwungbeins 0..1
	var k := N_WALK
	var walking := 0.0
	if t < t_walk:
		k = int(floor(t / T_STEP))
		s = (t - k * T_STEP) / T_STEP
		theta = al * (1.0 - 2.0 * s)
		walking = 1.0
	elif t < t_stop:
		s = (t - t_walk) / t_stop_len
		var e := 1.0 - (1.0 - s) * (1.0 - s)
		theta = al + (beta - al) * e
		s = e
		walking = 1.0 - e
	else:
		s = 1.0
	var plant := start_x + L * sin(al) + k * step
	var stance := "n" if k % 2 == 0 else "f"
	var swing := "f" if stance == "n" else "n"
	var hip := Vector2(plant - L * sin(theta), ground - ankle_h - L * cos(theta))
	position = hip

	var lift := LIFT * sin(PI * s) if t < t_stop else 0.0
	var st: Dictionary = legs[stance]
	var sw: Dictionary = legs[swing]
	st["leg"].position = Vector2.ZERO
	st["leg"].rotation = _leg_rot(theta)
	st["ankle"].rotation = -st["leg"].rotation
	sw["leg"].position = Vector2(0.0, -lift)
	sw["leg"].rotation = _leg_rot(-theta)
	var foot_w := deg_to_rad(10.0) * sin(PI * s) * (1.0 - 2.0 * s) if t < t_stop else 0.0
	sw["ankle"].rotation = foot_w - sw["leg"].rotation

	# Oberkörper
	var cyc := t / (2.0 * T_STEP) * TAU
	var stand_t := maxf(t - t_stop, 0.0)
	var lean := deg_to_rad(3.0) * walking + deg_to_rad(0.6) * sin(stand_t * 2.2) * (1.0 - walking)
	lean += deg_to_rad(1.0) * sin(cyc * 2.0) * walking
	body_back.rotation = lean
	body_front.rotation = lean
	var look := smoothstep(t_stop + 0.25, t_stop + 0.85, t)
	var nod := deg_to_rad(1.5) * cos(cyc * 2.0) * walking
	neck.rotation = nod - deg_to_rad(11.0) * look + deg_to_rad(1.2) * sin(stand_t * 1.7) * look
	var present := smoothstep(4.25, 4.75, t)
	shoulder_n.rotation = deg_to_rad(-30.0 + 3.0 * sin(cyc) * walking - 26.0 * present)
	shoulder_f.rotation = deg_to_rad(8.0 - 16.0 * sin(cyc) * walking)
	# Schal im Wind: beim Laufen fast waagerecht nach hinten, im Stand hängend und flatternd
	var wind := smoothstep(0.0, 1.0, walking)
	var sa := deg_to_rad(lerpf(-56.0, -30.0, wind) + 6.0 * sin(TAU * 1.6 * t) + 3.0 * sin(TAU * 2.7 * t + 1.0))
	var sb := deg_to_rad(lerpf(-70.0, -40.0, wind) + 5.0 * sin(TAU * 1.25 * t + 2.0) + 3.0 * sin(TAU * 3.1 * t))
	sprites["scarf_a"].rotation = sa
	sprites["scarf_b"].rotation = sb
	for m in scarf_mats:
		m.set_shader_parameter("t", t)
		m.set_shader_parameter("amp", lerpf(1.6, 2.8, wind))
	# Lidschlag
	var blink := false
	# zwei Posen lang (Zeiten auf dem 15er-Raster der Puppe), danach alle 3,6 s
	for tb in [1.7333, 3.8667]:
		if t >= tb - 0.001 and t < tb + 0.13:
			blink = true
	if t >= 5.4667 - 0.001 and fmod(t - 5.4657, 3.6) < 0.13:
		blink = true
	eyelid.visible = blink and sprites["head"].visible
