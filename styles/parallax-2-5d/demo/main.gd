extends Node3D
## 2,5D-Parallax aus einem Gemälde: Das KI-Gemälde liegt als Relief (Gitter, im Shader nach der KI-Tiefenkarte
## verschoben) vor einer Kamera, die exakt der Gemälde-Kamera entspricht. Die Kamera fährt langsam vor, zur Seite
## und abwärts; davor läuft der Dachs als Schnittfigur im Raum, dazu Licht, Rauch, Möwen, Wasser und das Textfeld.
## Alles hängt nur von der aufsummierten Zeit ab (feste Seeds), die Aufnahme ist Bild für Bild reproduzierbar.
##
## Prüfmodi (Benutzerargumente nach „--“):
##   --t0=<s>          Startzeit
##   --fill=stretch    Vergleich: nur die vordere Schicht, über Tiefensprünge gestreckt (keine hintere Schicht)
##   --cam=x,y,z       feste Kameraposition (m, Gemälde-Kamera = 0,0,0)
##   --only=front|mid|back eine Schicht; --tint Schichten einfärben (vorn rot, Mitte grün, hinten blau)
##   --nowave ohne Wasserbewegung; --flat=<m> flaches Relief
##   --badger-only     nur der Dachs vor Magenta, Kamera fest (für tools/measure_badger.py); --legs-log Fußpunkte
##   --parts=a,b       nur diese Teile der Figur (near_foot, far_foot, near_leg, far_leg, scarf, body)
##   --nofx            nur das Relief ohne Effekte und Figur (Bildtreue); --noui ohne Textfeld

const RIG_DIR := "res://badger/"
const BADGER_SHADER := preload("res://shaders/badger.gdshader")
const GLOW_SHADER := preload("res://shaders/glow.gdshader")
const SOFT_SHADER := preload("res://shaders/soft.gdshader")
const SOFT_ND_SHADER := preload("res://shaders/soft_nodepth.gdshader")
const HALO := preload("res://fx/halo.png")
const BEAM := preload("res://fx/beam.png")
const PUFF := preload("res://fx/puff.png")
const SHADOW := preload("res://fx/shadow.png")
const GULLS := [preload("res://fx/gull0.png"), preload("res://fx/gull1.png"), preload("res://fx/gull2.png")]

# Kamera: Bildausschnitt (Quellpixel des Gemäldes) und Fahrt in 6 s
const FRAME_CENTER := Vector2(768.0, 506.0)
const FRAME_H := 792.0
const CAM_END := Vector3(0.3, -0.25, -0.9)  # seitlich, abwärts (verhindert Lücken am Kai-Rand), vor
const CAM_T := 6.0

# Dachs: Schnittfigur, 1 m hoch, läuft auf dem Kai in 8,6 m Entfernung von links bis vor den Laternenpfahl (weiter
# hinten als zuerst mit 7,6 m: dort standen die Füße am Ende nur 10 px über dem Textfeld)
const Z_B := 8.6
const X_START_WISH := -5.6                  # m (Hüfte), links außerhalb des Bildes
const X_END := -1.6                         # m, Hüfte vor dem Laternenpfahl
const A_MAX := 26.0                         # Grad, größter Beinwinkel
const T_WALK := 3.95                        # konstantes Tempo bis hier
const T_DEC := 0.6                          # Abbremsen
const LIFT := 13.0                          # px, Fußhub im Schwung
const LEAN_DEG := 2.0
const SWAY_DEG := 1.2
const SCARF_DT := 1.0 / 240.0
const SCARF_OMEGA := 9.0
const SCARF_ZETA := 0.25
const SCARF_WIND := 0.0009                  # rad je px/s
const SCARF_LEN := 70.0

# Leuchtfeuer: zwei Strahlen, eine Umdrehung in 8 s
const BEAM_PERIOD := 8.0
const BEAM_LEN := 26.0

# Textfeld
const PANEL_IN := Vector2(0.8, 1.4)
const TYPE_START := 1.3
const TYPE_CPS := 38.0
const CHOICE_T := [3.0, 3.2, 3.4]
const HOVER_T := 3.9
const PARSER_T := 4.4
const PARSER_CPS := 14.0
const PARSER := "> nimm paket"

var calib: Dictionary
var rig: Dictionary
var args := {}
var t := 0.0
var t0 := 0.0
var badger_only := false
var ps := 1.0 / 320.0                       # m je Rig-Pixel
var L0 := 1.0
var step := 1.0
var x0 := 0.0                               # Rig-Pixel (Hüfte) zu Beginn
var v := 1.0                                # px/s
var scarf_a := 0.0
var scarf_w := 0.0
var scarf_t := 0.0
var parts := {}
var mats := {}
var rig_root: Node3D
var shadow: MeshInstance3D
var glows := {}
var beams: Array = []
var puffs: Array = []
var gulls: Array = []
var gull_data: Array = []
var points := {}

@onready var cam: Camera3D = $Camera
@onready var front: MeshInstance3D = $Front
@onready var back: MeshInstance3D = $Back
@onready var mid: MeshInstance3D = $Mid
@onready var env: WorldEnvironment = $Env
@onready var ui: CanvasLayer = $UI
@onready var panel: Panel = $UI/Panel
@onready var place: Label = $UI/Panel/Place
@onready var line: Label = $UI/Panel/Line
@onready var choices: Array = [$UI/Panel/Choice1, $UI/Panel/Choice2, $UI/Panel/Choice3]
@onready var parser: Label = $UI/Panel/Parser


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--"):
			var kv := a.substr(2).split("=", true, 1)
			args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	calib = JSON.parse_string(FileAccess.get_file_as_string("res://scene/calib.json"))
	rig = JSON.parse_string(FileAccess.get_file_as_string(RIG_DIR + "rig.json"))
	t0 = float(args.get("t0", "0"))
	badger_only = args.has("badger-only")
	for k in calib["points"]:
		var p: Array = calib["points"][k]
		points[k] = Vector3(p[0], p[1], p[2])
	_setup_relief()
	_setup_badger()
	_setup_fx()
	_setup_debug()
	_apply(t0)


func _process(delta: float) -> void:
	t += delta
	_apply(t0 + t)


# --- Relief -------------------------------------------------------------------------------------

func _setup_relief() -> void:
	var gs: Array = calib["grid_size"]
	var pm := PlaneMesh.new()
	pm.size = Vector2(1, 1)
	pm.subdivide_width = int(gs[0]) - 2
	pm.subdivide_depth = int(gs[1]) - 2
	front.mesh = pm
	mid.mesh = pm
	back.mesh = pm
	for m in [front.material_override, mid.material_override, back.material_override]:
		m.set_shader_parameter("f", calib["f"])
		m.set_shader_parameter("cx", calib["cx"])
		m.set_shader_parameter("yh", calib["yh"])
		m.set_shader_parameter("img", Vector2(calib["image"][0], calib["image"][1]))
		m.set_shader_parameter("grid", Vector2(gs[0], gs[1]))
		m.set_shader_parameter("grid_step", float(calib["grid"]))
		m.set_shader_parameter("z_min", calib["z_min"])


## Bildausschnitt als verschobenes Frustum (Objektivverschiebung): Mitte und Höhe in Quellpixeln. Die Kamera dreht
## sich nie; so bleiben Senkrechte senkrecht wie im Gemälde.
func _frame(center: Vector2, height_px: float) -> void:
	var f: float = calib["f"]
	var n := cam.near
	cam.size = height_px / f * n
	cam.frustum_offset = Vector2((center.x - float(calib["cx"])) / f * n, -(center.y - float(calib["yh"])) / f * n)


func _ease(u: float) -> float:
	u = clampf(u, 0.0, 1.0)
	return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)


func _cam_pos(time: float) -> Vector3:
	if args.has("cam"):
		var p: PackedStringArray = args["cam"].split(",")
		return Vector3(float(p[0]), float(p[1]), float(p[2]))
	if badger_only:
		return Vector3.ZERO
	# sanft anfahren, gleichmäßig gleiten, sanft auslaufen (Mischung aus linear und Smootherstep)
	var u := clampf(time / CAM_T, 0.0, 1.0)
	return CAM_END * (0.35 * u + 0.65 * _ease(u))


# --- Dachs: Schnittfigur ------------------------------------------------------------------------

func _setup_badger() -> void:
	rig_root = Node3D.new()
	rig_root.name = "Badger"
	add_child(rig_root)
	ps = 1.0 / float(rig["height_px"])
	var ank: Array = rig["ankle"]
	L0 = float(ank[1])
	step = 2.0 * L0 * sin(deg_to_rad(A_MAX))
	# Laufweg: ganze Zahl von Doppelschritten + 1/4, damit das nahe Bein am Ende senkrecht steht
	var dist_wish := (X_END - X_START_WISH) / ps
	var n := roundi(dist_wish / (2.0 * step) - 0.25)
	var dist := 2.0 * step * (float(n) + 0.25)
	x0 = 0.0
	v = dist / (T_WALK + T_DEC * 0.5)
	rig_root.position = Vector3(X_END - dist * ps, -float(calib["hq"]), -Z_B)
	# Teile in Zeichenreihenfolge (render_priority): Schatten, ferner Fuß, fernes Bein, Schalende, naher Fuß,
	# nahes Bein, Rumpf
	shadow = _quad(SHADOW, Vector2(128, 48), SOFT_ND_SHADER, 0)
	shadow.mesh.size = Vector2(0.95, 0.36)
	shadow.rotation_degrees.x = -90.0
	shadow.material_override.set_shader_parameter("tint", Color(0.02, 0.03, 0.06, 0.55))
	parts["far_foot"] = _part("far_foot", "foot", "foot_pivot", 1, 0.55)
	parts["far_leg"] = _part("far_leg", "leg", "leg_pivot", 2, 0.55)
	parts["scarf"] = _part("scarf", "scarf", "scarf_pivot", 3, 1.0)
	parts["near_foot"] = _part("near_foot", "foot", "foot_pivot", 4, 1.0)
	parts["near_leg"] = _part("near_leg", "leg", "leg_pivot", 5, 1.0)
	parts["body"] = _part("body", "body", "body_pivot", 6, 1.0)
	# Lichtkanten nur auf Rumpf und Schalende, am Rumpf nicht an der unteren Schnittkante
	var bs: Array = rig["sizes"]["body"]
	mats["body"].set_shader_parameter("rim_cut", (float(rig["body_pivot"][1]) - 4.0) / float(bs[1]))
	for k in ["far_foot", "far_leg", "near_foot", "near_leg"]:
		mats[k].set_shader_parameter("rim_cut", -1.0)
	scarf_a = SCARF_WIND * v


func _quad(tex: Texture2D, pivot: Vector2, shader: Shader, prio: int) -> MeshInstance3D:
	var q := QuadMesh.new()
	var sz := Vector2(tex.get_width(), tex.get_height()) * ps
	q.size = sz
	q.center_offset = Vector3((tex.get_width() * 0.5 - pivot.x) * ps, -(tex.get_height() * 0.5 - pivot.y) * ps, 0.0)
	var m := ShaderMaterial.new()
	m.shader = shader
	m.render_priority = prio
	m.set_shader_parameter("tex", tex)
	var mi := MeshInstance3D.new()
	mi.mesh = q
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.custom_aabb = AABB(Vector3(-50, -50, -50), Vector3(100, 100, 100))
	rig_root.add_child(mi)
	return mi


func _part(key: String, file: String, pivot_key: String, prio: int, shade: float) -> MeshInstance3D:
	var tex: Texture2D = load(RIG_DIR + file + ".png")
	var pv: Array = rig[pivot_key]
	var mi := _quad(tex, Vector2(pv[0], pv[1]), BADGER_SHADER, prio)
	var m: ShaderMaterial = mi.material_override
	m.set_shader_parameter("texel", Vector2(1.0 / tex.get_width(), 1.0 / tex.get_height()))
	m.set_shader_parameter("shade", shade)
	mats[key] = m
	return mi


func _walk_x(time: float) -> float:
	if time < T_WALK:
		return x0 + v * time
	var u := minf(time - T_WALK, T_DEC)
	return x0 + v * T_WALK + v * (u - u * u / (2.0 * T_DEC))


func _walk_speed(time: float) -> float:
	if time < T_WALK:
		return v
	return v * maxf(0.0, 1.0 - (time - T_WALK) / T_DEC)


## Phase eines Beins aus der Hüftposition (px). Standphase: Knöchel fest auf A (Fuß flach am Boden), Hüfte schwingt
## als umgekehrtes Pendel darüber; Schwungphase: Knöchel von A nach A + 2·step mit Hub.
func _leg_state(hip_x: float, offset: float) -> Dictionary:
	var u := (hip_x - x0 - offset) / (2.0 * step)
	var n := floorf(u)
	var fr := u - n
	var a := x0 + offset + step * 0.5 + n * 2.0 * step
	if fr < 0.5:
		return {"stance": true, "ankle": a, "s": 0.0}
	var s := (fr - 0.5) / 0.5
	var e := smoothstep(0.12, 0.88, s)
	return {"stance": false, "ankle": lerpf(a, a + 2.0 * step, e), "s": s}


func _hip_y(hip_x: float) -> float:
	## Hüfthöhe (px, nach unten positiv, Boden = 0) aus dem Standbein
	var near := _leg_state(hip_x, 0.0)
	var far := _leg_state(hip_x, step)
	var st: Dictionary = near if near["stance"] else far
	var dx: float = hip_x - float(st["ankle"])
	var sole_to_ankle: float = float(rig["sole_y"]) - L0
	return -(sole_to_ankle + sqrt(maxf(L0 * L0 - dx * dx, 0.0)))


func _step_scarf(time: float) -> void:
	while scarf_t + SCARF_DT <= time + 1e-6:
		var t1 := scarf_t + SCARF_DT
		var h := SCARF_DT
		var ax := (_walk_x(t1 + h) - 2.0 * _walk_x(t1) + _walk_x(t1 - h)) / (h * h)
		var ay := (_hip_y(_walk_x(t1 + h)) - 2.0 * _hip_y(_walk_x(t1)) + _hip_y(_walk_x(t1 - h))) / (h * h)
		var force := -SCARF_OMEGA * SCARF_OMEGA * (scarf_a - SCARF_WIND * _walk_speed(t1)) \
				- 2.0 * SCARF_ZETA * SCARF_OMEGA * scarf_w + (ax + 0.8 * ay) / SCARF_LEN
		scarf_w += force * SCARF_DT
		scarf_a += scarf_w * SCARF_DT
		scarf_t = t1


func _place(mi: MeshInstance3D, p: Vector2, ang: float, layer: float, sy := 1.0) -> void:
	## Rig-Pixel (y nach unten, Boden = 0) -> lokale Lage im Raum; ang im Uhrzeigersinn (Bild)
	mi.position = Vector3(p.x * ps, -p.y * ps, layer)
	mi.rotation = Vector3(0.0, 0.0, -ang)
	mi.scale = Vector3(1.0, sy, 1.0)


func _apply_badger(time: float, flick: float, cam_p: Vector3) -> void:
	_step_scarf(time)
	var x := _walk_x(time)
	var near := _leg_state(x, 0.0)
	var far := _leg_state(x, step)
	var y := _hip_y(x)
	var sole_to_ankle: float = float(rig["sole_y"]) - L0
	var stop_t := T_WALK + T_DEC
	var legs := {"near": near, "far": far}
	var hip := Vector2(x, y)
	var fs: float = float(rig["far_shift"])
	for side in ["near", "far"]:
		var st: Dictionary = legs[side]
		var lift := 0.0 if st["stance"] else sin(PI * float(st["s"]))
		var ax: float = st["ankle"]
		var k_arr := 0.0
		if side == "far" and time > stop_t:
			# Ankunft: fernes Bein in 0,3 s neben dem nahen absetzen (Hub und Fußneigung gehen auf 0)
			k_arr = smoothstep(0.0, 0.3, time - stop_t)
			lift *= 1.0 - k_arr
			ax = lerpf(ax, x, k_arr)
		var ankle := Vector2(ax, -sole_to_ankle - LIFT * lift)
		var d := ankle - hip
		var ang := atan2(-d.x, d.y)
		var len_k := d.length() / L0
		var off := Vector2(fs, 0.0) if side == "far" else Vector2.ZERO
		var lz := -0.004 if side == "far" else 0.0
		_place(parts[side + "_leg"], hip + off, ang, lz, len_k)
		# Fuß: flach; im Schwung leicht mit der Bewegung geneigt (Zehe beim Abheben unten, beim Aufsetzen oben)
		var tilt := 0.0 if st["stance"] else deg_to_rad(9.0) * sin(TAU * float(st["s"])) * -1.0
		tilt *= 1.0 - k_arr
		_place(parts[side + "_foot"], ankle + off, tilt, lz)
		if args.has("legs-log") and side == "near":
			print("LEG %d x=%.2f ankle=%.2f stance=%s" % [roundi(time * 30.0), x, ax, str(st["stance"])])
	var walk_k := _walk_speed(time) / v
	var phase := (x - x0) / step
	var tilt_b := deg_to_rad(walk_k * (LEAN_DEG + SWAY_DEG * sin(TAU * phase * 0.5 + 0.6)))
	var breathe := 0.0
	if time > stop_t:
		breathe = 0.5 - 0.5 * cos((time - stop_t) * TAU / 2.0)
	_place(parts["body"], hip, tilt_b, 0.002, 1.0 + 0.012 * breathe)
	var sp := Vector2(rig["scarf_from_hip"][0], rig["scarf_from_hip"][1] * (1.0 + 0.012 * breathe)).rotated(tilt_b)
	_place(parts["scarf"], hip + sp, tilt_b + scarf_a, 0.001)
	shadow.position = Vector3((x + 6.0) * ps, 0.004, 0.0)
	# Licht: Laterne (Raumlage aus dem Gemälde) relativ zum Dachs, im Bild projiziert
	var chest_w := rig_root.position + Vector3(x * ps, (-y + 120.0) * ps, 0.0)
	var to_l: Vector3 = points["lantern"] - chest_w
	var dir := Vector2(to_l.x, -to_l.y).normalized()
	var dist := to_l.length()
	var k_l := clampf(1.0 - (dist - 4.0) / 6.0, 0.0, 1.0)
	# Umgebungston: kühl im Dämmerlicht, unter der Laterne wärmer (der Kai ist dort orange beschienen)
	var warm := clampf(1.0 - (dist - 3.0) / 5.0, 0.0, 1.0)
	var amb := Vector3(0.62, 0.62, 0.76).lerp(Vector3(0.8, 0.66, 0.56), warm)
	for m in mats.values():
		m.set_shader_parameter("ambient", amb)
		m.set_shader_parameter("lamp_dir", dir)
		m.set_shader_parameter("lamp_strength", (0.35 + 0.65 * k_l) * (0.9 + 0.2 * flick))
		m.set_shader_parameter("sky_rim", 0.35)


# --- Umgebung -----------------------------------------------------------------------------------

func _fx_quad(tex: Texture2D, shader: Shader, size_m: Vector2, prio: int) -> MeshInstance3D:
	var q := QuadMesh.new()
	q.size = size_m
	var m := ShaderMaterial.new()
	m.shader = shader
	m.render_priority = prio
	m.set_shader_parameter("tex", tex)
	var mi := MeshInstance3D.new()
	mi.mesh = q
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	return mi


func _setup_fx() -> void:
	# Lichthöfe etwas vor der Lampe (sie hellen Pfahl und Rahmen mit auf); Größe in m
	var specs := {
		"lantern": [Vector2(2.4, 2.4), Color(1.0, 0.66, 0.32), 0.6],
		"lantern_core": [Vector2(0.55, 0.55), Color(1.0, 0.85, 0.6), 0.6],
		"window": [Vector2(3.4, 3.0), Color(1.0, 0.6, 0.28), 0.4],
		"walllamp": [Vector2(1.8, 1.8), Color(1.0, 0.66, 0.34), 0.4],
		"lighthouse": [Vector2(5.0, 5.0), Color(1.0, 0.86, 0.6), 2.0],
	}
	for k in specs:
		var sp: Array = specs[k]
		var g := _fx_quad(HALO, GLOW_SHADER, sp[0], 10)
		var src: Vector3 = points["lantern" if k == "lantern_core" else k]
		g.position = src + Vector3(0.0, 0.0, float(sp[2]))
		g.material_override.set_shader_parameter("color", Vector3(sp[1].r, sp[1].g, sp[1].b))
		glows[k] = g
	# Leuchtfeuer: zwei gegenüberliegende Strahlen
	for i in 2:
		var b := _fx_quad(BEAM, GLOW_SHADER, Vector2(BEAM_LEN, 2.2), 11)
		b.mesh.center_offset = Vector3(BEAM_LEN * 0.5, 0.0, 0.0)
		b.material_override.set_shader_parameter("color", Vector3(1.0, 0.9, 0.7))
		beams.append(b)
	# Rauch: Ballen steigen aus dem Schornstein, treiben mit dem Wind nach rechts
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261012
	for i in 9:
		var p := _fx_quad(PUFF, SOFT_SHADER, Vector2(1.0, 1.0), 5)
		p.material_override.set_shader_parameter("tint", Color(0.5, 0.5, 0.6, 1.0))
		p.set_meta("phase", float(i) / 9.0)
		p.set_meta("jit", Vector2(rng.randf_range(-0.15, 0.15), rng.randf_range(0.0, 1.0)))
		puffs.append(p)
	# Möwen: drei, ziehen in 21–30 m Entfernung über den Himmel (vor dem Himmel, also mit eigener Parallaxe)
	gull_data = [
		{"p0": Vector3(-7.5, 3.6, -24.0), "vel": Vector3(1.5, 0.08, 0.0), "span": 1.3, "ph": 0.0},
		{"p0": Vector3(-3.0, 5.4, -30.0), "vel": Vector3(1.25, -0.05, 0.0), "span": 1.3, "ph": 0.37},
		{"p0": Vector3(10.0, 3.0, -21.0), "vel": Vector3(-1.1, 0.1, 0.0), "span": 1.2, "ph": 0.71},
	]
	for gd in gull_data:
		var gq := _fx_quad(GULLS[0], SOFT_SHADER, Vector2(gd["span"], gd["span"]), 4)
		gq.material_override.set_shader_parameter("tint", Color(0.8, 0.78, 0.86, 1.0))
		gulls.append(gq)


func _flicker(time: float, seed_: float) -> float:
	## Flackern einer Flamme: unharmonische Schwingungen plus kurze Einbrüche, etwa -1..1
	var f := 0.5 * sin(time * 11.0 + seed_) + 0.3 * sin(time * 23.7 + 1.1 + seed_ * 2.0) + 0.2 * sin(time * 41.3 + 2.3)
	var dip := pow(maxf(0.0, sin(time * 2.9 + 0.7 + seed_)), 24.0)
	return clampf(f - 1.2 * dip, -1.0, 1.0)


func _apply_fx(time: float, cam_p: Vector3) -> float:
	var fl := _flicker(time, 0.0)
	var fw := _flicker(time * 0.6, 3.1)
	var fwl := _flicker(time * 0.8, 5.3)
	# Leuchtfeuer: Strahlrichtung in der Waagerechten; zeigt ein Strahl zur Kamera, blitzt das Feuer auf
	var th := TAU * (time / BEAM_PERIOD) + 0.9
	var lamp: Vector3 = points["lighthouse"]
	var flash := 0.0
	for i in 2:
		var a := th + PI * float(i)
		var d := Vector3(cos(a), 0.0, sin(a))
		var to_cam := (cam_p - lamp).normalized()
		var facing := d.dot(to_cam)                        # 1 = zur Kamera
		flash = maxf(flash, pow(maxf(facing, 0.0), 6.0))
		var b: MeshInstance3D = beams[i]
		# Viereck entlang des Strahls, zur Kamera gedreht
		var xb := d
		var yb := to_cam.cross(xb).normalized()
		var zb := xb.cross(yb).normalized()
		b.global_transform = Transform3D(Basis(xb, yb, zb), lamp)
		var side := sqrt(maxf(1.0 - facing * facing, 0.0))   # sichtbare Länge ~ seitliche Ausrichtung
		b.material_override.set_shader_parameter("intensity", 0.55 * side * (0.6 if facing < 0.0 else 1.0))
	var gains := Vector4(1.0 + 0.22 * fl, 1.0 + 0.08 * fw, 1.0 + 0.15 * fwl, 1.0 + 0.6 * flash)
	if args.has("nofx"):
		gains = Vector4.ONE
	for m in [front.material_override]:
		m.set_shader_parameter("lamp_gain", gains)
	glows["lantern"].material_override.set_shader_parameter("intensity", 0.5 + 0.12 * fl)
	glows["lantern"].scale = Vector3.ONE * (1.0 + 0.05 * fl)
	glows["lantern_core"].material_override.set_shader_parameter("intensity", 1.1 + 0.3 * fl)
	glows["window"].material_override.set_shader_parameter("intensity", 0.22 + 0.05 * fw)
	glows["walllamp"].material_override.set_shader_parameter("intensity", 0.45 + 0.1 * fwl)
	glows["lighthouse"].material_override.set_shader_parameter("intensity", 0.4 + 0.7 * flash)
	glows["lighthouse"].scale = Vector3.ONE * (1.0 + 0.35 * flash)
	# Rauch
	var ch: Vector3 = points["chimney"]
	var life := 5.4
	for p in puffs:
		var ph: float = p.get_meta("phase")
		var jit: Vector2 = p.get_meta("jit")
		var age := fposmod(time / life + ph, 1.0)
		var rise := age * life
		var pos := ch + Vector3(0.0, 0.2, 0.0) + Vector3(0.75 * rise + 0.05 * rise * rise + jit.x, 0.32 * rise - 0.012 * rise * rise, -0.2)
		pos.x += 0.12 * sin(rise * 1.7 + jit.y * 6.0)
		p.position = pos
		var sc := 0.45 + 0.32 * rise
		p.scale = Vector3(sc, sc, 1.0)
		var op := smoothstep(0.0, 0.06, age) * (1.0 - smoothstep(0.4, 1.0, age)) * 0.5
		p.material_override.set_shader_parameter("opacity", op)
		p.rotation.z = jit.y * 6.0 + rise * 0.25
	# Möwen: Flügelschlag 6 Bilder/s (0-1-2-1), Gleitphasen
	for i in gulls.size():
		var gd: Dictionary = gull_data[i]
		var gq: MeshInstance3D = gulls[i]
		var pos: Vector3 = gd["p0"] + gd["vel"] * time
		pos.y += 0.35 * sin(time * 1.3 + float(gd["ph"]) * 9.0)
		gq.position = pos
		var cyc := [0, 1, 2, 1]
		var glide := fposmod(time * 0.35 + float(gd["ph"]), 1.0) > 0.55
		var fr: int = 1 if glide else int(cyc[int(floor(time * 6.0 + float(gd["ph"]) * 4.0)) % 4])
		gq.material_override.set_shader_parameter("tex", GULLS[fr])
		gq.scale.x = -1.0 if gd["vel"].x < 0.0 else 1.0
	return fl


# --- Textfeld -----------------------------------------------------------------------------------

func _apply_ui(time: float) -> void:
	var a := smoothstep(PANEL_IN.x, PANEL_IN.y, time)
	panel.modulate.a = a
	panel.position.y = 588.0 + 14.0 * (1.0 - a)
	var full: String = line.get_meta("full")
	var n := clampi(int(floor((time - TYPE_START) * TYPE_CPS)), 0, full.length())
	line.visible_characters = n
	for i in 3:
		var c: Label = choices[i]
		c.modulate.a = smoothstep(CHOICE_T[i], CHOICE_T[i] + 0.25, time)
	var hov := smoothstep(HOVER_T, HOVER_T + 0.2, time)
	choices[1].add_theme_color_override("font_color", Color(0.86, 0.84, 0.8).lerp(Color(1.0, 0.82, 0.5), hov))
	var pn := clampi(int(floor((time - PARSER_T) * PARSER_CPS)), 0, PARSER.length())
	var cursor := "▏" if fposmod(time, 0.8) < 0.45 and time > PARSER_T - 0.4 else " "
	parser.text = PARSER.substr(0, pn) + cursor
	parser.modulate.a = smoothstep(PARSER_T - 0.4, PARSER_T - 0.1, time)


# --- Ablauf -------------------------------------------------------------------------------------

func _apply(time: float) -> void:
	var cp := _cam_pos(time)
	cam.position = cp
	_frame(FRAME_CENTER, FRAME_H)
	for m in [front.material_override, mid.material_override, back.material_override]:
		m.set_shader_parameter("time", time)
	var fl := 0.0
	if not badger_only:
		fl = _apply_fx(time, cp)
		_apply_ui(time)
	_apply_badger(time, fl, cp)


func _setup_debug() -> void:
	line.set_meta("full", line.text)
	if args.has("tint"):
		front.material_override.set_shader_parameter("debug_tint", Vector3(1.0, 0.45, 0.45))
		mid.material_override.set_shader_parameter("debug_tint", Vector3(0.45, 1.0, 0.45))
		back.material_override.set_shader_parameter("debug_tint", Vector3(0.45, 0.6, 1.0))
	if args.has("flat"):
		front.material_override.set_shader_parameter("debug_flat", float(args["flat"]))
		front.material_override.set_shader_parameter("stretch_max", 100.0)
		front.material_override.set_shader_parameter("tol_rel", 100.0)
	if args.has("nowave"):
		for m in [front.material_override, back.material_override]:
			m.set_shader_parameter("wave_amp", 0.0)
			m.set_shader_parameter("glitter", 0.0)
	if args.get("only", "") == "front":
		back.visible = false
		mid.visible = false
	if args.get("only", "") == "mid":
		front.visible = false
		back.visible = false
	if args.get("only", "") == "back":
		front.visible = false
		mid.visible = false
	if args.get("fill", "") == "stretch":
		front.material_override.set_shader_parameter("fill_mode", 0)
		back.visible = false
		mid.visible = false
	if args.has("noui"):
		ui.visible = false
	if args.has("nofx"):
		# Prüfmodus Bildtreue: nur das Relief, Lampen unverändert, keine Zusatzeffekte und keine Figur
		for g in glows.values():
			g.visible = false
		for b in beams + puffs + gulls:
			b.visible = false
		rig_root.visible = false
		front.material_override.set_shader_parameter("star_twinkle", 0.0)
		env.environment.glow_enabled = false
	if args.has("parts"):
		var keep: PackedStringArray = args["parts"].split(",")
		for k in parts:
			parts[k].visible = k in keep
	if badger_only:
		front.visible = false
		mid.visible = false
		back.visible = false
		ui.visible = false
		shadow.visible = false
		env.environment.background_color = Color(1, 0, 1)
		env.environment.glow_enabled = false
		for g in glows.values():
			g.visible = false
		for b in beams + puffs + gulls:
			b.visible = false
