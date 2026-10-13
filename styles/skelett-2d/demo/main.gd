extends Node2D
## Hafen von Lornholm mit dem Dachs-Kurier als Mesh-Rig (Skeleton2D + Polygon2D, Gewichte weich).
## Der Dachs läuft fünf Doppelschritte (walk), bremst (stop) und steht (idle); alle drei Animationen spielt der
## AnimationPlayer der Figur. Die Wurzel bewegt sich mit der Geschwindigkeit, für die walk/stop berechnet sind
## (Metadaten in badger.tscn), damit die Standfüße nicht rutschen. Schalenden und Tasche schwingen als
## Federn nach (eigener Code nach der Animation, fester Zeitschritt).
## Alles hängt nur von der aufsummierten Zeit ab; Zufall nur über RandomNumberGenerator mit festem Seed.
##
## Benutzerargumente (nach "--"):
##   --rigid         jedes Dreieck ganz am stärksten Knochen: getrennte starre Teile (Vergleich starr/weich)
##   --badger-only   nur die Figur vor Magenta (Messung von Füßen und Kopf)
##   --t0=<s>        Startzeit (Langzeitprüfung)
##   --no-springs    Schal und Tasche ohne Feder (Vergleich)
##   --only=a,b      nur diese Polygon2D der Figur zeigen (z. B. leg_n), für die Fußmessung
##   --overlay-check=gpu|cpu  nur die Rig-Ansicht: Rasterlinien als Textur (GPU) bzw. auf der CPU verformt

const BADGER_SCALE := 0.70
const GROUND_Y := 684.0
const STOP_X := 446.0
const WALK_CYCLES := 5
const LINE := "Die Laterne flackert im Wind.\nAm Kai wartet ein Paket auf dich."
const TYPE_START := 0.25
const CPS := 40.0
const PARSER := "> nimm paket"
const PARSER_START := 1.95
const PACKED := preload("res://badger.tscn")

var t := 0.0
var rng := RandomNumberGenerator.new()
var rigid := false
var badger_only := false
var springs := true
var only := PackedStringArray()
var cur_anim := ""
var walk_speed := 0.0      # Rig-Pixel/s
var walk_cycle := 0.0
var stop_time := 0.0
var stop_dist := 0.0
var t_stop := 0.0
var x0 := 0.0
var flick_noise := FastNoiseLite.new()

# Federn
var chains := {}           # name -> {bones:[Bone2D], a:[Winkel], w:[Winkelgeschwindigkeit], prev, vprev}
var satchel_a := 0.0
var satchel_w := 0.0
var satchel_prev := Vector2.ZERO
var satchel_vprev := Vector2.ZERO

@onready var badger: Node2D = $Badger
@onready var ap: AnimationPlayer = $Badger/AnimationPlayer
@onready var skel: Skeleton2D = $Badger/Skeleton2D
@onready var shadow: Node2D = $Shadow
@onready var bg_mat: ShaderMaterial = $Bg.material
@onready var fx_nodes := [$Smoke, $Glow, $Gulls]
@onready var rig_view = $UI/RigView
@onready var line_label: Label = $UI/Dialog/Line
@onready var parser_label: Label = $UI/Dialog/Parser
@onready var cursor: ColorRect = $UI/Dialog/Cursor
@onready var choices: Array = [$UI/Dialog/C1, $UI/Dialog/C2, $UI/Dialog/C3]


func _ready() -> void:
	rng.seed = 20261012
	flick_noise.seed = 7
	flick_noise.frequency = 2.2
	for a in OS.get_cmdline_user_args():
		if a == "--rigid":
			rigid = true
		elif a == "--badger-only":
			badger_only = true
		elif a == "--no-springs":
			springs = false
		elif a.begins_with("--t0="):
			t = float(a.substr(5))
		elif a.begins_with("--only="):
			only = a.substr(7).split(",")
	walk_speed = badger.get_meta("walk_speed")
	walk_cycle = badger.get_meta("walk_cycle")
	stop_time = badger.get_meta("stop_time")
	stop_dist = badger.get_meta("stop_dist")
	t_stop = WALK_CYCLES * walk_cycle
	x0 = STOP_X - BADGER_SCALE * (walk_speed * t_stop + stop_dist)
	badger.scale = Vector2(BADGER_SCALE, BADGER_SCALE)
	ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	if rigid:
		rig_view.make_rigid(badger)
	var tl0 := timeline(t)
	ap.play(tl0[0])
	ap.seek(tl0[1], true)
	cur_anim = tl0[0]
	init_chains()
	rig_view.setup(badger, PACKED, preload("res://fonts/JetBrainsMono-var.ttf"), rigid)
	if badger_only:
		for n in [$Bg, $Smoke, $Glow, $Gulls, $UI, $Shadow]:
			n.visible = false
		RenderingServer.set_default_clear_color(Color(1, 0, 1))
		(badger.get_node("body") as Polygon2D).material.set_shader_parameter("light_amount", 0.0)
	if rig_view.check != "":
		for n in [$Bg, $Smoke, $Glow, $Gulls, $Shadow, badger, $UI/Dialog]:
			n.visible = false
		RenderingServer.set_default_clear_color(Color(0, 0, 0))
	if only.size() > 0:
		for p: Polygon2D in badger.find_children("*", "Polygon2D", false, false):
			p.visible = String(p.name) in only
	line_label.visible_characters = 0
	shadow.draw.connect(_draw_shadow)
	update_all(0.0)


func _draw_shadow() -> void:
	var tex: Texture2D = $Glow.soft
	shadow.draw_texture_rect(tex, Rect2(Vector2(-46, -9), Vector2(92, 18)), false, Color(0.06, 0.05, 0.10, 0.55))
	shadow.draw_texture_rect(tex, Rect2(Vector2(-30, -5), Vector2(60, 10)), false, Color(0.06, 0.05, 0.10, 0.35))


func _process(delta: float) -> void:
	t += delta
	update_all(delta)


func timeline(tt: float) -> Array:
	if tt < t_stop:
		return ["walk", fmod(tt, walk_cycle)]
	if tt < t_stop + stop_time:
		return ["stop", tt - t_stop]
	return ["idle", tt - t_stop - stop_time]


func root_x(tt: float) -> float:
	if tt < t_stop:
		return x0 + BADGER_SCALE * walk_speed * tt
	var tau: float = min(tt - t_stop, stop_time)
	return x0 + BADGER_SCALE * (walk_speed * t_stop + walk_speed * (tau - tau * tau / (2.0 * stop_time)))


func root_v(tt: float) -> float:
	# Geschwindigkeit der Wurzel in Rig-Pixeln/s (für die Trägheit der Federn)
	if tt < t_stop:
		return walk_speed
	var tau: float = tt - t_stop
	return walk_speed * (1.0 - tau / stop_time) if tau < stop_time else 0.0


func update_all(delta: float) -> void:
	# --- Figur: Animation, Wurzel, Federn
	var tl := timeline(t)
	if tl[0] != cur_anim:
		ap.play(tl[0])
		ap.seek(tl[1], true)
		cur_anim = tl[0]
	else:
		ap.advance(delta)
	badger.position = Vector2(root_x(t), GROUND_Y)
	if springs:
		step_springs(delta)
	shadow.position = Vector2(badger.position.x - 4.0, GROUND_Y + 1.0)
	shadow.queue_redraw()
	rig_view.sync()

	# --- Licht
	var fl := 0.86 + 0.10 * flick_noise.get_noise_1d(t * 3.0) + 0.05 * flick_noise.get_noise_1d(t * 11.0 + 40.0)
	var fw := 0.94 + 0.05 * flick_noise.get_noise_1d(t * 1.3 + 90.0)
	for n in fx_nodes:
		n.t = t
		n.flicker = fl
		n.flicker_w = fw
	bg_mat.set_shader_parameter("t", t)
	bg_mat.set_shader_parameter("lantern_amount", fl)
	var bm: ShaderMaterial = (badger.get_node("body") as Polygon2D).material
	if not badger_only:
		bm.set_shader_parameter("light_amount", 0.42 * fl)

	# --- Oberfläche
	line_label.visible_characters = clampi(int((t - TYPE_START) * CPS), 0, LINE.length())
	var type_end := TYPE_START + LINE.length() / CPS
	for i in choices.size():
		var c: Control = choices[i]
		var a := clampf((t - type_end - 0.1 - 0.12 * i) / 0.25, 0.0, 1.0)
		c.modulate.a = a
	var n_par := clampi(int((t - PARSER_START) * 12.0), 0, PARSER.length())
	parser_label.text = PARSER.substr(0, n_par)
	cursor.position.x = parser_label.position.x + parser_label.get_theme_font("font").get_string_size(
		parser_label.text, HORIZONTAL_ALIGNMENT_LEFT, -1, parser_label.get_theme_font_size("font_size")).x + 3.0
	cursor.visible = t > PARSER_START - 0.6 and (n_par < PARSER.length() or fmod(t, 0.9) < 0.5)


# ------------------------------------------------------------------ Federn (Schalenden, Tasche)
func init_chains() -> void:
	for c in ["b", "f"]:
		var base := "Skeleton2D/hip/spine/neck/scarf_%s1" % c
		var bones: Array[Bone2D] = [badger.get_node(base), badger.get_node(base + "/scarf_%s2" % c),
			badger.get_node(base + "/scarf_%s2/scarf_%s3" % [c, c])]
		chains[c] = {"bones": bones, "a": [0.0, 0.0, 0.0], "w": [0.0, 0.0, 0.0],
			"prev": anchor_world(bones[0]), "vprev": Vector2(root_v(t), 0.0)}
	# Startzustand der Federn passend zur Bewegung zur Startzeit, sonst gibt es im ersten Bild einen Stoß
	# (Beschleunigung aus 0 -> walk_speed in einem Bild)
	satchel_prev = anchor_world(skel.get_node("hip/satchel"))
	satchel_vprev = Vector2(root_v(t), 0.0)


func anchor_world(b: Bone2D) -> Vector2:
	# Lage eines Knochens im mitbewegten Weltraum in Rig-Pixeln (Skelettraum + Wurzelweg)
	return bone_pos(b) + Vector2(root_x(t) / BADGER_SCALE, 0.0)


func bone_pos(b: Bone2D) -> Vector2:
	return (skel.global_transform.affine_inverse() * b.global_transform).origin


func step_springs(delta: float) -> void:
	# Schalenden: je Glied eine gedämpfte Drehfeder (lokaler Winkel zum Elternglied). Ziel = Auslenkung durch
	# Wind und Fahrtwind, verteilt auf die drei Glieder; das erste Glied gleicht die Halsdrehung zum Teil aus
	# (das Ende hängt weiter nach unten). Angetrieben wird zusätzlich von der waagerechten Beschleunigung des
	# Aufhängepunkts (Bremsen, Wippen). Fester Unterschritt, Winkel begrenzt.
	if delta <= 0.0:
		return
	var v := root_v(t)
	var sub := 4
	var h := delta / sub
	var wind_x := -40.0 + 25.0 * sin(t * 1.3) + 15.0 * sin(t * 3.7 + 1.0) - 1.2 * v
	var inv := skel.global_transform.affine_inverse()
	for c in chains:
		var ch: Dictionary = chains[c]
		var bones: Array = ch.bones
		var pos := anchor_world(bones[0])
		var vel: Vector2 = (pos - ch.prev) / delta
		var acc: Vector2 = (vel - ch.vprev) / delta
		ch.prev = pos
		ch.vprev = vel
		var neck: Bone2D = bones[0].get_parent()
		var neck_rot := (inv * neck.global_transform).get_rotation()
		var defl := -wind_x * 0.0018
		for i in 3:
			var share: float = [0.45, 0.33, 0.22][i]
			var om: float = [9.0, 8.0, 7.0][i]
			var target := defl * share - (neck_rot * 0.8 if i == 0 else 0.0)
			for _s in sub:
				var a: float = -om * om * (ch.a[i] - target) - 2.0 * 0.35 * om * ch.w[i] + acc.x * 0.04 * share
				ch.w[i] += a * h
				ch.a[i] += ch.w[i] * h
			ch.a[i] = clampf(ch.a[i], -0.6, 0.6)
			(bones[i] as Bone2D).rotation = ch.a[i]
	# Tasche: Pendel an der Hüfte, angetrieben von der Beschleunigung des Aufhängepunkts
	var sb: Bone2D = skel.get_node("hip/satchel")
	var spos := anchor_world(sb)
	var svel := (spos - satchel_prev) / delta
	var sacc := (svel - satchel_vprev) / delta
	satchel_prev = spos
	satchel_vprev = svel
	for _s in sub:
		var torque := -60.0 * satchel_a - 7.0 * satchel_w + sacc.x * 0.03
		satchel_w += torque * h
		satchel_a += satchel_w * h
	sb.rotation = clampf(satchel_a, -0.35, 0.35)
