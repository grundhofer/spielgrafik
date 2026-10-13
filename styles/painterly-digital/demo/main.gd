extends Node2D
## Hafen von Lornholm, digital gemalt und atmosphärisch (Parallax-Ebenen, Nebel, Glow, Lichtschein).
## Alles hängt nur von der aufsummierten Zeit t ab; Zufall nur mit festem Seed.
## So ist die Aufnahme mit --fixed-fps Bild für Bild reproduzierbar.

const HALO := preload("res://art/halo.png")
const PUFF := preload("res://art/puff.png")
const MOTE := preload("res://art/mote.png")
const STREAK := preload("res://art/streak.png")

# Lage im Bild (Weltkoordinaten der Spielebene; Bildschirm = Welt - Kamera). Zahlen aus assets/sep/layout.json
# (scripts/build_sep_layers.py): Kai hinten 608, Kaikante vorn 668, Fuß der Taurolle 640.
const GROUND := 652.0                       # Fußsohlen des Dachses auf dem Kai (vor dem Fuß der Taurolle)
const LANTERN := Vector2(552.9, 466.3)
const WINDOW := Vector2(368.0, 477.4)
const CHIMNEY := Vector2(323.8, 208.7)
const LAMP := Vector2(1130.4, 129.5)        # in der Ebene der Landzunge
const HORIZON := 349.85
const REFLECT_TOP := 440.0                  # Fuß der Landzunge unter dem Leuchtturm (Wasserlinie)
const SKY_OFFSET := Vector2(-40.0, -88.0)   # Lage der Himmel-und-Meer-Textur (sky_sea.png)
# Boote: Schaukeln um die Wasserlinie (Grad, Periode s, Phase), leichtes Heben und Senken in px
const BOAT_ROCK := [[1.3, 3.7, 0.0, 0.9], [1.0, 4.3, 1.9, 0.7]]

# Kamera: leichte Fahrt nach rechts (Ebenen verschieben sich mit ihrem scroll_scale)
const CAM_PAN := 80.0

# Dachs: Schnittfigur (140 px hoch). Schrittlänge S, Endpunkt so gewählt, dass er mit dem nahen Bein in der
# Standmitte und dem fernen Bein im Durchschwung ankommt; danach setzt er das ferne Bein ab.
const STEP := 31.5                          # Bein ±25° (größere Winkel lassen das starre Bein wie einen Stiefel wirken)
const X_END := 548.0                        # Hüfte unter der Laterne (LANTERN.x 553)
const X_START_WISH := 20.0
const T_WALK := 4.3                         # konstantes Tempo bis hier (110 px/s, ~3,5 Schritte/s)
const T_DEC := 0.8                          # Abbremsen
const FAR_OFFSET := Vector2(-7.5, 0.0)
const LIFT_SCALE := 0.12                    # Schwungbein wird im Schwung so viel kürzer
const LIFT_PX := 2.5
const LEAN_DEG := 1.2                       # Vorlage des Rumpfs beim Gehen
const SWAY_DEG := 0.8                       # Neigen im Schrittakt
# Hinteres Schalende: gedämpfte Feder (fester Zeitschritt), angetrieben von Tempo (Fahrtwind) und
# Beschleunigung der Hüfte (Abbremsen, Auf und Ab beim Gehen). Positiver Winkel = Ende weht nach hinten.
const TAIL_DT := 1.0 / 240.0
const TAIL_OMEGA := 10.0                    # Eigenfrequenz (rad/s), ~1,6 Hz
const TAIL_ZETA := 0.22                     # Dämpfung
const TAIL_WIND := 0.0015                   # rad je px/s Gehtempo (~9,5° bei 110 px/s)
const TAIL_LEN := 24.0                      # px, Länge des Schalendes in Endgröße
const TAIL_BOB := 1.0                       # Anteil der senkrechten Beschleunigung, der das Ende auslenkt

# Leuchtfeuer: zwei Strahlen, eine Umdrehung in 10 s
const BEAM_PERIOD := 10.0
const BEAM_PHASE := 0.02

# Text
const TITLE_IN := Vector2(0.3, 0.9)
const TITLE_OUT := Vector2(1.75, 2.25)
const PANEL_IN := Vector2(2.2, 2.6)
const TYPE_START := 2.55
const TYPE_CPS := 42.0
const CHOICE_T := [3.75, 3.9, 4.05]
const HOVER_T := 4.35
const PARSER := "> nimm paket"
const PARSER_T := 4.55
const PARSER_CPS := 16.0
const CHOICE_COLOR := Color(0.78, 0.81, 0.82)
const HOVER_COLOR := Color(1.0, 0.86, 0.6)

const SMOKE_LIFE := 5.0
const SMOKE_EVERY := 0.42

var t := 0.0
var rig := {}
var x0 := 0.0
var v := 0.0
var smoke: Array = []
var sparks: Array = []
var motes: Array = []
var stars: Array = []
var reflect: Array = []
var rays: Array = []
var boats: Array = []
var test_mode := false          # Prüfmodus: Kamera steht, damit Fußmessungen in Weltkoordinaten sind
var tail_t := 0.0               # Zeit, bis zu der die Feder des Schalendes gerechnet ist
var tail_a := 0.0               # Winkel (rad)
var tail_w := 0.0               # Winkelgeschwindigkeit (rad/s)

@onready var cam: Camera2D = $Camera
@onready var plate_mat: ShaderMaterial = $SkyPar/Plate.material
@onready var badger: Node2D = $Badger
@onready var body: Sprite2D = $Badger/Body
@onready var near_leg: Sprite2D = $Badger/NearLeg
@onready var far_leg: Sprite2D = $Badger/FarLeg
@onready var shadow: Sprite2D = $Badger/Shadow
@onready var tail: Sprite2D = $Badger/Tail
@onready var badger_mat: ShaderMaterial = $Badger/Body.material
@onready var leg_mat: ShaderMaterial = $Badger/NearLeg.material
@onready var tail_mat: ShaderMaterial = $Badger/Tail.material
@onready var beam_a: Sprite2D = $HeadPar/Beam/BeamA
@onready var beam_b: Sprite2D = $HeadPar/Beam/BeamB
@onready var lamp_halo: Sprite2D = $HeadPar/LampHalo
@onready var lantern_halo: Sprite2D = $Harbour/LanternHalo
@onready var lantern_core: Sprite2D = $Harbour/LanternCore
@onready var light_pool: Sprite2D = $Harbour/LightPool
@onready var window_halo: Sprite2D = $Harbour/WindowHalo
@onready var fogs: Array = [$FogFarPar/FogFar, $FogNearPar/FogNear, $FogLowPar/FogLow]
@onready var title: Control = $UI/Title
@onready var panel: ColorRect = $UI/Panel
@onready var line: Label = $UI/Panel/Line
@onready var choices: Array = [$UI/Panel/Choice1, $UI/Panel/Choice2, $UI/Panel/Choice3]
@onready var marker: Polygon2D = $UI/Panel/Marker
@onready var parser: Label = $UI/Panel/Parser


func _ready() -> void:
	rig = JSON.parse_string(FileAccess.get_file_as_string("res://art/badger_rig.json"))
	if RenderingServer.get_current_rendering_method() == "gl_compatibility":
		# Compatibility kennt kein HDR-2D: mit eingeschaltetem hdr_2d wird das ganze Bild ausgewaschen (gemessen:
		# mittlere Abweichung 53 statt 10 Tonwerte zum Forward+-Bild). Ohne HDR bleibt nur der Glow schwächer.
		get_viewport().use_hdr_2d = false
	body.offset = -Vector2(rig["body_pivot"][0], rig["body_pivot"][1])
	near_leg.offset = -Vector2(rig["leg_pivot"][0], rig["leg_pivot"][1])
	far_leg.offset = near_leg.offset
	tail.offset = -Vector2(rig["tail_pivot"][0], rig["tail_pivot"][1])
	badger_mat.set_shader_parameter("rim_cut", float(rig["cut_top_px"]) / float(rig["body_size"][1]))
	far_leg.modulate = Color(0.5, 0.53, 0.58)
	shadow.modulate = Color(0.0, 0.02, 0.03, 0.5)
	# Laufweg: ganze Zahl von Doppelschritten + 1/4, damit das nahe Bein am Ende senkrecht steht
	var n := roundi((X_END - X_START_WISH) / (2.0 * STEP) - 0.25)
	x0 = X_END - 2.0 * STEP * (n + 0.25)
	v = (X_END - x0) / (T_WALK + T_DEC * 0.5)
	tail_a = TAIL_WIND * v              # eingeschwungen starten
	# Text: geschütztes Leerzeichen hält "auf dich." zusammen
	line.text = "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261010
	_build_smoke(rng)
	_build_sparks(rng)
	_build_motes(rng)
	_build_stars(rng)
	_build_reflection(rng)
	_build_rays(rng)
	for b in [$Boats/Row, $Boats/Mast]:
		boats.append({"node": b, "base": (b as Node2D).position, "hull": b.get_node("Hull"), "refl": b.get_node("Refl")})
	if "--badger-only" in OS.get_cmdline_user_args():
		_badger_only()
	_apply(0.0)


func _badger_only() -> void:
	## Prüfmodus für scripts/measure_badger.py: nur der Dachs vor flacher Fläche, ohne Glow und Oberfläche
	test_mode = true
	for c in get_children():
		if c is CanvasItem and c != badger:
			(c as CanvasItem).visible = false
		elif c is CanvasLayer:
			(c as CanvasLayer).visible = false
	$WorldEnvironment.environment = null
	shadow.visible = false
	if "--only-near" in OS.get_cmdline_user_args():
		far_leg.visible = false
		body.visible = false
		tail.visible = false
	if "--only-far" in OS.get_cmdline_user_args():
		near_leg.visible = false
		body.visible = false
		tail.visible = false
	RenderingServer.set_default_clear_color(Color(1, 0, 1))


func _process(delta: float) -> void:
	t += delta
	_apply(t)


# --- Aufbau -----------------------------------------------------------------------------------

func _sprite(tex: Texture2D, parent: Node, additive: bool) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = tex
	if additive:
		s.material = beam_a.material
	parent.add_child(s)
	return s


func _build_smoke(rng: RandomNumberGenerator) -> void:
	var n := int(ceil((6.0 + SMOKE_LIFE) / SMOKE_EVERY)) + 1
	for i in n:
		var s := _sprite(PUFF, $Harbour/Smoke, false)
		s.flip_h = rng.randf() < 0.5
		smoke.append({"node": s, "spawn": -SMOKE_LIFE + i * SMOKE_EVERY, "period": n * SMOKE_EVERY,
				"wob": rng.randf_range(0.0, TAU), "rot": rng.randf_range(-0.5, 0.5),
				"end": rng.randf_range(0.75, 1.05), "drift": rng.randf_range(-10.0, -6.0)})


func _build_sparks(rng: RandomNumberGenerator) -> void:
	for i in 9:
		var s := _sprite(MOTE, $Harbour/Sparks, true)
		sparks.append({"node": s, "period": rng.randf_range(1.8, 2.8), "phase": rng.randf(),
				"dx": rng.randf_range(-14.0, 14.0), "drift": rng.randf_range(4.0, 14.0),
				"size": rng.randf_range(0.10, 0.17), "wob": rng.randf_range(0.0, TAU)})


func _build_motes(rng: RandomNumberGenerator) -> void:
	# Schwebeteilchen in der Luft (Staub, Gischt): langsam treibend, leise pulsierend
	for i in 46:
		var s := _sprite(MOTE, $MotePar/Motes, true)
		var p := Vector2(rng.randf_range(-100.0, 1600.0), rng.randf_range(250.0, 700.0))
		motes.append({"node": s, "p": p, "vx": rng.randf_range(4.0, 14.0), "vy": rng.randf_range(-7.0, -2.0),
				"amp": rng.randf_range(4.0, 12.0), "f": rng.randf_range(0.3, 0.8), "ph": rng.randf_range(0.0, TAU),
				"size": rng.randf_range(0.07, 0.2), "a": rng.randf_range(0.18, 0.5)})


func _build_stars(rng: RandomNumberGenerator) -> void:
	# gemalte Sterne in sky_sea.png (Lage gemessen, Texturkoordinaten) plus einige schwache zusätzliche
	var pts := [Vector2(1137, 68), Vector2(956, 118), Vector2(1030, 30), Vector2(1169, 109), Vector2(1301, 44),
			Vector2(676, 68), Vector2(988, 130), Vector2(1254, 81), Vector2(1097, 108), Vector2(823, 63)]
	var painted := pts.size()
	for i in 9:
		pts.append(Vector2(rng.randf_range(600.0, 1380.0), rng.randf_range(20.0, 170.0)))
	for i in pts.size():
		var s := _sprite(MOTE, $StarPar/Stars, true)
		s.position = pts[i] + SKY_OFFSET
		stars.append({"node": s, "f": rng.randf_range(1.2, 3.5), "ph": rng.randf_range(0.0, TAU),
				"size": 0.16 if i < painted else rng.randf_range(0.07, 0.11), "a": 0.9 if i < painted else 0.45})


func _build_reflection(rng: RandomNumberGenerator) -> void:
	# Spiegelung des Leuchtfeuers: Säule aus waagerechten Glanzstrichen im freien Wasser vor der Landzunge
	# (unterhalb ihres Fußes bei y ~455), im Nebel weich. Liegt in HeadPar NACH dem Headland-Sprite.
	var y := REFLECT_TOP + 6.0
	while y < REFLECT_TOP + 108.0:
		var s := _sprite(STREAK, $HeadPar/Reflect, true)
		reflect.append({"node": s, "y": y, "ph": rng.randf_range(0.0, TAU), "w": rng.randf_range(0.35, 1.2),
				"dx": rng.randf_range(-4.0, 4.0), "a": rng.randf_range(0.5, 1.0)})
		y += rng.randf_range(4.0, 9.0) * (1.0 + 0.6 * (y - REFLECT_TOP) / 108.0)


func _build_rays(rng: RandomNumberGenerator) -> void:
	# Dämmerungsstrahlen: fächern von der untergegangenen Sonne am Horizont nach oben (Lichtkegel-Textur,
	# additiv, sehr schwach); sie atmen langsam
	for i in 5:
		var s := _sprite(preload("res://art/beam.png"), $RayPar/Rays, true)
		s.centered = false
		s.offset = Vector2(0, -80)
		s.rotation = deg_to_rad(-90.0 + (i - 2) * 24.0 + rng.randf_range(-5.0, 5.0))
		s.scale = Vector2(rng.randf_range(0.75, 1.0), rng.randf_range(1.2, 1.8))
		rays.append({"node": s, "ph": rng.randf_range(0.0, TAU), "a": rng.randf_range(0.08, 0.13)})


# --- Dachs: Schnittfigur ------------------------------------------------------------------------

func _walk_x(time: float) -> float:
	if time < T_WALK:
		return x0 + v * time
	var u := minf(time - T_WALK, T_DEC)
	return x0 + v * T_WALK + v * (u - u * u / (2.0 * T_DEC))


func _walk_speed(time: float) -> float:
	if time < T_WALK:
		return v
	return v * maxf(0.0, 1.0 - (time - T_WALK) / T_DEC)


func _hip_y(x: float) -> float:
	## Hüfthöhe aus dem Standbein (ungerundet; für die Feder des Schalendes)
	var near := _leg_state(x, 0.0)
	var far := _leg_state(x, STEP)
	var a: float = _solve_angle(x, near["foot"]) if near["stance"] else _solve_angle(x, far["foot"])
	return GROUND - _contact_height(a)


func _step_tail(time: float) -> void:
	## Feder des Schalendes mit festem Zeitschritt bis time weiterrechnen (halbimplizites Euler-Verfahren).
	## Antrieb: Fahrtwind (Zielwinkel ~ Tempo) und Beschleunigung der Hüfte, beides als Funktion der Zeit.
	while tail_t + TAIL_DT <= time + 1e-6:
		var t1 := tail_t + TAIL_DT
		var h := TAIL_DT
		var ax := (_walk_x(t1 + h) - 2.0 * _walk_x(t1) + _walk_x(t1 - h)) / (h * h)
		var ay := (_hip_y(_walk_x(t1 + h)) - 2.0 * _hip_y(_walk_x(t1)) + _hip_y(_walk_x(t1 - h))) / (h * h)
		var force := -TAIL_OMEGA * TAIL_OMEGA * (tail_a - TAIL_WIND * _walk_speed(t1)) \
				- 2.0 * TAIL_ZETA * TAIL_OMEGA * tail_w + (ax + TAIL_BOB * ay) / TAIL_LEN
		tail_w += force * TAIL_DT
		tail_a += tail_w * TAIL_DT
		tail_t = t1


func _solve_angle(hip_x: float, foot_x: float) -> float:
	## Winkel des Beins (positiv = Fuß nach hinten), bei dem Ferse (Fuß vorn) bzw. Zehe (Fuß hinten)
	## genau an ihrer Bodenstelle steht. foot_x = Mitte der Sohle bei flachem Fuß.
	var hf: float = rig["half_foot"]
	var sy: float = rig["sole_y"]
	var px := -hf if foot_x >= hip_x else hf
	var target := foot_x + px
	var lo := -1.0
	var hi := 1.0
	for i in 30:
		var m := (lo + hi) * 0.5
		var g := hip_x + px * cos(m) - sy * sin(m) - target
		if g > 0.0:
			lo = m
		else:
			hi = m
	return (lo + hi) * 0.5


func _contact_height(a: float) -> float:
	## Höhe der Hüfte über dem Boden, wenn der tiefste Punkt der Sohle (Ferse oder Zehe) den Boden berührt
	var hf: float = rig["half_foot"]
	var sy: float = rig["sole_y"]
	return maxf(-hf * sin(a), hf * sin(a)) + sy * cos(a)


func _leg_state(hip_x: float, offset: float) -> Dictionary:
	## Phase eines Beins aus der Hüftposition. Standphase: Fuß fest auf F; Schwungphase: Fuß von F zu F + 2S.
	var u := (hip_x - x0 - offset) / (2.0 * STEP)
	var n := floorf(u)
	var fr := u - n
	var f_plant := x0 + offset + STEP * 0.5 + n * 2.0 * STEP
	if fr < 0.5:
		return {"stance": true, "foot": f_plant, "s": 0.0}
	var s := (fr - 0.5) / 0.5
	# waagerecht nur in der Mitte des Schwungs: erst abheben, dann vorschwingen, dann senkrecht aufsetzen,
	# sonst berührt die Ferse den Boden, bevor sie an ihrer Stelle ist, und rutscht
	var e := smoothstep(0.18, 0.82, s)
	return {"stance": false, "foot": lerpf(f_plant, f_plant + 2.0 * STEP, e), "s": s}


func _apply_badger(time: float, flick: float) -> void:
	_step_tail(time)
	var x := _walk_x(time)
	var xr := roundf(x)
	var near := _leg_state(xr, 0.0)
	# fernes Bein: gleiche Kinematik wie das nahe (halbe Periode versetzt), nur 7,5 px weiter hinten gezeichnet;
	# so wechseln Stand- und Schwungphase lückenlos und die Hüfthöhe springt nicht
	var far := _leg_state(xr, STEP)
	var a_n := _solve_angle(xr, near["foot"])
	var a_f := _solve_angle(xr, far["foot"])
	var stance_a: float = a_n if near["stance"] else a_f
	var y := GROUND - _contact_height(stance_a)
	var stop_t := T_WALK + T_DEC
	var lift_n := 0.0 if near["stance"] else sin(PI * float(near["s"]))
	var lift_f := 0.0 if far["stance"] else sin(PI * float(far["s"]))
	if time > stop_t:
		# Ankunft: fernes Bein in 0,25 s absetzen, dann ruhig atmen
		var k := clampf((time - stop_t) / 0.25, 0.0, 1.0)
		lift_f *= 1.0 - k * k * (3.0 - 2.0 * k)
		a_f *= 1.0 - k
	var yr := roundf(y)
	if test_mode and "--debug-legs" in OS.get_cmdline_user_args():
		print("LEG %d xr=%.0f y=%.2f near=%s a_n=%.3f far=%s a_f=%.3f tail=%.2f" % [roundi(time * 30.0), xr, y, near, a_n, far, a_f, rad_to_deg(tail_a)])
	# Rumpf: beim Gehen leicht vorgeneigt und im Schrittakt pendelnd, im Stand aufrecht
	var walk_k := _walk_speed(time) / v
	var phase := (xr - x0) / STEP
	var tilt := deg_to_rad(walk_k * (LEAN_DEG + SWAY_DEG * sin(TAU * phase + 0.6)))
	body.position = Vector2(xr, yr)
	body.rotation = tilt
	near_leg.position = Vector2(xr, yr - LIFT_PX * lift_n)
	near_leg.rotation = a_n
	near_leg.scale = Vector2(1.0, 1.0 - LIFT_SCALE * lift_n)
	far_leg.position = Vector2(xr, yr) + FAR_OFFSET + Vector2(0.0, -LIFT_PX * lift_f)
	far_leg.rotation = a_f
	far_leg.scale = Vector2(1.0, 1.0 - LIFT_SCALE * lift_f)
	var breathe := 0.0
	if time > stop_t:
		breathe = 0.5 - 0.5 * cos((time - stop_t) * TAU / 2.2)
	body.scale = Vector2(1.0, 1.0 + 0.014 * breathe)
	var tp := Vector2(rig["tail_from_hip"][0], rig["tail_from_hip"][1] * body.scale.y)
	tail.position = body.position + tp.rotated(tilt)
	tail.rotation = tilt + tail_a
	shadow.position = Vector2(xr + 3.0, GROUND + 1.0)
	shadow.scale = Vector2(0.37, 0.065)
	# Licht auf der Figur: warmes Laternenlicht von rechts oben, je näher, desto stärker
	var chest := Vector2(xr, yr - 60.0)
	var to_l := LANTERN - chest
	var near_k := clampf(1.0 - absf(to_l.x) / 330.0, 0.0, 1.0)
	for m in [badger_mat, leg_mat, tail_mat]:
		m.set_shader_parameter("lamp_dir", to_l.normalized())
		m.set_shader_parameter("lamp_strength", near_k * near_k * (0.85 + 0.25 * flick))
		m.set_shader_parameter("ambient", Vector3(0.84, 0.88, 0.96).lerp(Vector3(1.0, 0.94, 0.86), near_k * 0.7))


# --- Animation ----------------------------------------------------------------------------------

func _flicker(time: float) -> float:
	# Laternenflackern: unharmonische Sinusschwingungen plus kurze Einbrüche, etwa -1..1
	var f := 0.5 * sin(time * 11.0) + 0.3 * sin(time * 23.7 + 1.1) + 0.2 * sin(time * 41.3 + 2.3)
	var dip := pow(maxf(0.0, sin(time * 2.9 + 0.7)), 24.0)
	return clampf(f - 1.2 * dip, -1.0, 1.0)


func _apply(time: float) -> void:
	var fl := _flicker(time)
	var cx := 0.0 if test_mode else CAM_PAN * smoothstep(0.1, 5.8, time)
	cam.position = Vector2(cx, 0.0)
	plate_mat.set_shader_parameter("cam_x", cx)
	plate_mat.set_shader_parameter("time_s", time)
	for f in fogs:
		(f as ColorRect).material.set_shader_parameter("time_s", time)

	_apply_badger(time, fl)

	# Leuchtfeuer: Strahlen drehen sich um die senkrechte Achse; zur Kamera hin blitzt die Lampe auf
	var th := TAU * (time / BEAM_PERIOD + BEAM_PHASE)
	for k in 2:
		var b: Sprite2D = beam_a if k == 0 else beam_b
		var a := th + PI * k
		var side := cos(a)
		var front := sin(a)
		b.scale = Vector2(side * 1.25, lerpf(0.5, 0.85, absf(side)))
		b.rotation = 0.035 * signf(side)
		var strength := (0.10 + 0.30 * absf(side)) * (0.55 if front < 0.0 else 1.0)
		b.modulate = Color(1.25, 1.08, 0.8, strength)
	var flare := pow(maxf(0.0, sin(th)), 8.0) + pow(maxf(0.0, sin(th + PI)), 8.0)
	# Lichthof kleiner als bei der geschnittenen Fassung: der getrennt erzeugte Leuchtturm ist kleiner (Lampenhaus 35 statt 46 px)
	lamp_halo.scale = Vector2.ONE * (0.15 + 0.12 * flare)
	lamp_halo.modulate = Color(2.0, 1.65, 1.1, 0.75 + 0.2 * flare)
	for r in reflect:
		var s: Sprite2D = r["node"]
		var y: float = r["y"]
		var depth := (y - REFLECT_TOP) / 105.0
		s.position = Vector2(LAMP.x + float(r["dx"]) * (0.5 + depth) + 3.0 * sin(time * 1.9 + r["ph"]) * (0.4 + depth), y)
		s.scale = Vector2(r["w"] * (0.5 + 0.8 * depth), 0.4 + 0.4 * depth)
		var tw := 0.5 + 0.5 * sin(time * 3.1 + float(r["ph"]) * 2.0)
		s.modulate = Color(1.7, 1.3, 0.8, float(r["a"]) * (0.6 - 0.3 * depth) * tw * (1.0 + flare))

	# Laterne, Lichtpfütze auf dem Kai, Fenster
	lantern_core.scale = Vector2.ONE * (0.13 + 0.006 * fl)
	lantern_core.modulate = Color(2.4, 1.6, 0.8, 0.85 + 0.12 * fl)
	lantern_halo.scale = Vector2.ONE * (0.62 + 0.04 * fl)
	lantern_halo.modulate = Color(1.0, 0.62, 0.3, 0.36 + 0.08 * fl)
	light_pool.position = Vector2(LANTERN.x + 3.0, 648.0)
	light_pool.scale = Vector2(1.6, 0.3)
	light_pool.modulate = Color(1.0, 0.6, 0.28, 0.2 + 0.05 * fl)
	var wf := 0.5 * sin(time * 5.3) + 0.5 * sin(time * 8.9 + 0.4)
	window_halo.scale = Vector2(0.42, 0.5)
	window_halo.modulate = Color(1.0, 0.66, 0.32, 0.3 + 0.04 * wf)

	# Boote schaukeln um die Wasserlinie; das Spiegelbild dreht gegensinnig, der Shader hält die Wasserlinie waagerecht
	for i in boats.size():
		var b: Dictionary = boats[i]
		var r: Array = BOAT_ROCK[i]
		var w := TAU * time / float(r[1]) + float(r[2])
		var rot := deg_to_rad(float(r[0])) * (sin(w) + 0.25 * sin(2.3 * w + 0.7))
		(b["node"] as Node2D).position = b["base"] + Vector2(0.0, float(r[3]) * sin(w * 0.9 + 1.2))
		var hull: Sprite2D = b["hull"]
		var refl: Sprite2D = b["refl"]
		hull.rotation = rot
		refl.rotation = -rot
		for m in [hull.material, refl.material]:
			(m as ShaderMaterial).set_shader_parameter("tilt", rot)
			(m as ShaderMaterial).set_shader_parameter("time_s", time)

	# Rauch: steigt, wird größer, treibt nach links, vergeht
	for p in smoke:
		var s: Sprite2D = p["node"]
		var age: float = fposmod(time - p["spawn"], p["period"])
		if age > SMOKE_LIFE:
			s.visible = false
			continue
		s.visible = true
		var k := age / SMOKE_LIFE
		s.position = CHIMNEY + Vector2(p["drift"] * age - 0.6 * age * age + 5.0 * sin(age * 1.1 + p["wob"]),
				-(22.0 * age - 1.1 * age * age))
		s.scale = Vector2.ONE * lerpf(0.16, p["end"], sqrt(k))
		s.rotation = p["rot"] + 0.1 * age
		s.modulate = Color(0.6, 0.66, 0.72, smoothstep(0.0, 0.25, age) * (1.0 - smoothstep(0.35, 1.0, k)) * 0.34)

	# Funken an der Laterne
	for p in sparks:
		var s: Sprite2D = p["node"]
		var ph: float = fposmod(time / p["period"] + p["phase"], 1.0)
		s.position = LANTERN + Vector2(p["dx"] + 5.0 * sin(ph * 6.0 + p["wob"]), 18.0 - p["drift"] - 70.0 * ph)
		s.scale = Vector2.ONE * float(p["size"]) * (1.0 - 0.5 * ph)
		s.modulate = Color(2.4, 1.5, 0.6, sin(ph * PI) * 0.8)

	# Schwebeteilchen
	for m in motes:
		var s: Sprite2D = m["node"]
		var p: Vector2 = m["p"]
		var x := fposmod(p.x + m["vx"] * time + 100.0, 1800.0) - 100.0
		var y: float = p.y + m["vy"] * time + m["amp"] * sin(time * m["f"] + m["ph"])
		s.position = Vector2(x, y)
		s.scale = Vector2.ONE * float(m["size"])
		var warm := clampf(1.0 - (Vector2(x, y) - LANTERN).length() / 260.0, 0.0, 1.0)
		var pulse := 0.6 + 0.4 * sin(time * 1.7 + m["ph"] * 3.0)
		s.modulate = Color(1.0, 1.0, 1.0).lerp(Color(1.8, 1.2, 0.6), warm) * Color(1, 1, 1, float(m["a"]) * pulse)

	# Dämmerungsstrahlen
	for r in rays:
		var s: Sprite2D = r["node"]
		s.modulate = Color(1.0, 0.72, 0.45, float(r["a"]) * (0.7 + 0.3 * sin(time * 0.7 + r["ph"])))

	# Sterne funkeln
	for st in stars:
		var s: Sprite2D = st["node"]
		var tw := 0.6 + 0.4 * sin(time * st["f"] + st["ph"])
		s.scale = Vector2.ONE * float(st["size"]) * (0.85 + 0.25 * tw)
		s.modulate = Color(1.3, 1.3, 1.4, float(st["a"]) * tw)

	_apply_ui(time)


func _apply_ui(time: float) -> void:
	var ta := smoothstep(TITLE_IN.x, TITLE_IN.y, time) * (1.0 - smoothstep(TITLE_OUT.x, TITLE_OUT.y, time))
	title.modulate.a = ta
	title.position.y = 6.0 * (1.0 - smoothstep(TITLE_IN.x, TITLE_IN.y + 0.4, time))
	var pa := smoothstep(PANEL_IN.x, PANEL_IN.y, time)
	panel.modulate.a = pa
	panel.visible = pa > 0.0
	line.visible_characters = clampi(int((time - TYPE_START) * TYPE_CPS), 0, line.text.length())
	for i in choices.size():
		var c: Label = choices[i]
		c.modulate.a = smoothstep(CHOICE_T[i], CHOICE_T[i] + 0.3, time)
		var hover := i == 1 and time >= HOVER_T
		c.self_modulate = HOVER_COLOR / CHOICE_COLOR if hover else Color.WHITE
	var sel := 1 if time >= HOVER_T else 0
	marker.position = Vector2(64.0, 141.0 + 30.0 * sel)
	marker.modulate.a = smoothstep(CHOICE_T[0], CHOICE_T[0] + 0.3, time) * (0.75 + 0.25 * sin(time * 4.0))
	var n := clampi(int((time - PARSER_T) * PARSER_CPS) + 1, 1, PARSER.length())
	var caret := "_" if fposmod(time, 0.8) < 0.45 else " "
	parser.text = PARSER.substr(0, n) + caret if time >= PARSER_T - 0.5 else ""

