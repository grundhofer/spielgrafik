extends Node2D
## Hafen von Lornholm mit dem Dachs-Kurier als AnimatedSprite2D aus KI-Sprite-Sheets.
## Zustandsfolge wie im Spiel: walk -> idle -> jump -> idle -> wave -> idle. Die Bilder und ihre Dauern stehen
## in badger_frames.tres (SpriteFrames); Anker, Vorschub und Fußpunkte in art/anim.json (build_sprites.py).
## Welches Bild gezeigt wird, rechnet main.gd in ganzen Videobildern aus der aufsummierten Zeit (bei 30 fps
## hält jedes Bild genau 5 bzw. 3 Videobilder), damit nichts von Rundungen der Wiedergabe abhängt.
## Der Laufvorschub kommt nur beim Bildwechsel dazu (gemessen am Standfuß), nie zwischen zwei Wechseln.
## Stehen: die SpriteFrames-Schleife "idle" ist nur das Atmen (3 s); das Blinzeln ("blink", je Atemstufe ein Bild)
## setzt main.gd in unregelmäßigen Abständen von 3–5 s ein (RandomNumberGenerator mit fester seed), erstmals bei 3,0 s.
##
## Benutzerargumente (nach "--"):
##   --t0=<s>          Startzeit (Langzeitprüfung)
##   --badger-only     nur die große Figur vor Magenta, ohne Schatten und Oberfläche (Fuß- und Kopfmessung)
##   --key=<rrggbb>    Grundfarbe für --badger-only (Standard ff00ff); zwei Läufe mit verschiedener Farbe ergeben Alpha
##   --raw             die große Figur aus der rohen Fassung (sprites.py slice, kein Vorschub-Abgleich)

const FPS := 30
const GROUND_Y := 656.0
const X_STOP := 420.0          # Zehen des Standfußes, an denen der Dachs nach dem Laufen steht
const PLAN := [["walk", 0], ["idle", 80], ["jump", 100], ["idle", 124], ["wave", 130], ["idle", 180]]
const LINE := "Die Laterne flackert im Wind.\nAm Kai wartet ein Paket auf dich."
const TYPE_START := 0.3
const CPS := 38.0
const PARSER := "> nimm paket"
const PARSER_START := 2.1
const TINT := Color(0.90, 0.88, 0.97)
const BLINK_FIRST := 90        # erstes Blinzeln (Videobild, 3,0 s)
const BLINK_LEN := 5           # ein Bild bei 6 Bildern/s
const BLINK_SEED := 23

var t := 0.0
var meta: Dictionary
var frames_res: SpriteFrames
var raw_res: SpriteFrames
var badger_only := false
var raw_mode := false
var seg_x: Array = []          # Knotenlage (x) je Abschnitt; beim Laufen die Lage beim ersten Bild
var walk_adv: Array = []       # Vorschub je Zelle (Wechsel Zelle c -> nächste)
var flick_noise := FastNoiseLite.new()
var shadow_x := 0.0
var shadow_gap := 0.0
var blinks: Array = []         # Startbilder der Blinzler (Vielfache von 5 Videobildern)
var key_color := Color(1, 0, 1)

@onready var badger: AnimatedSprite2D = $Badger
@onready var shadow: Node2D = $Shadow
@onready var bg_mat: ShaderMaterial = $Bg.material
@onready var fx_nodes := [$Smoke, $Glow, $Gulls]
@onready var panel = $UI/SheetPanel
@onready var line_label: Label = $UI/Dialog/Line
@onready var parser_label: Label = $UI/Dialog/Parser
@onready var cursor: ColorRect = $UI/Dialog/Cursor
@onready var choices: Array = [$UI/Dialog/C1, $UI/Dialog/C2, $UI/Dialog/C3]


func _ready() -> void:
	flick_noise.seed = 11
	flick_noise.frequency = 2.0
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t = float(a.substr(5))
		elif a == "--badger-only":
			badger_only = true
		elif a == "--raw":
			raw_mode = true
		elif a.begins_with("--key="):
			key_color = Color.html(a.substr(6))
	meta = JSON.parse_string(FileAccess.get_file_as_string("res://art/anim.json"))
	frames_res = badger.sprite_frames
	raw_res = load("res://raw_frames.tres")
	walk_adv = meta.anims.walk.advance
	plan_positions()
	plan_blinks()
	panel.setup(meta, frames_res, raw_res)
	if raw_mode:
		badger.sprite_frames = raw_res
	if badger_only:
		for n in [$Bg, $Smoke, $Glow, $Gulls, $UI, $Shadow]:
			n.visible = false
		RenderingServer.set_default_clear_color(key_color)
		badger.modulate = Color(1, 1, 1)
	else:
		badger.modulate = TINT
	line_label.visible_characters = 0
	shadow.draw.connect(_draw_shadow)
	update_all()


# ------------------------------------------------------------------ Zeitleiste
func vframes(res: SpriteFrames, anim: String) -> Array:
	## Haltedauer je Bild in Videobildern (Dauer und Tempo aus den SpriteFrames)
	var out := []
	var sp := res.get_animation_speed(anim)
	for i in res.get_frame_count(anim):
		out.append(int(round(FPS / sp * res.get_frame_duration(anim, i))))
	return out


func sample(res: SpriteFrames, anim: String, local: int) -> Array:
	## [Bildindex, Zahl der Bildwechsel seit Abschnittsbeginn]; Schleife nach SpriteFrames, sonst letztes Bild
	var d := vframes(res, anim)
	var total := 0
	for v in d:
		total += v
	var loops := res.get_animation_loop(anim)
	var n := d.size()
	var changes := 0
	var l := local
	if loops:
		changes = int(l / total) * n
		l = l % total
	elif l >= total:
		return [n - 1, n - 1]
	var acc := 0
	for i in n:
		if l < acc + d[i]:
			return [i, changes + i]
		acc += d[i]
	return [n - 1, changes + n - 1]


func segment(vf: int) -> int:
	var s := 0
	for i in PLAN.size():
		if vf >= PLAN[i][1]:
			s = i
	return s


func cell_of(anim: String, frame: int) -> int:
	## Zelle (Spalte im Streifen) des SpriteFrames-Bilds: aus der Atlas-Region
	var tex := frames_res.get_frame_texture(anim, frame) as AtlasTexture
	return int(round(tex.region.position.x / tex.region.size.x))


func anchor(anim: String) -> Vector2:
	var a: Array = meta.anims[anim].anchor
	return Vector2(a[0], a[1])


func foot(anim: String, cell: int, key := "body_x") -> float:
	## Fußpunkt einer Zelle: "toe_x" (Zehenende am Boden, Seitenansicht) oder "body_x" (Mitte beider Füße)
	var v = meta.anims[anim][key][cell]
	return float(v) if v != null else anchor(anim).x


func plan_positions() -> void:
	## Knotenlage je Abschnitt so, dass die Füße beim Zustandswechsel an derselben Stelle bleiben:
	## zwischen Seitenansichten (walk, idle, jump) die Zehen am Boden, mit der Dreiviertelansicht (wave)
	## die Mitte beider Füße. Laufen endet mit den Zehen des Standfußes bei X_STOP; davor wird der
	## gemessene Vorschub zurückgerechnet.
	seg_x.resize(PLAN.size())
	var walk_len: int = PLAN[1][1] - PLAN[0][1]
	var last := sample(frames_res, "walk", walk_len - 1)
	var adv_sum := 0.0
	for m in last[1]:
		adv_sum += walk_adv[cell_of("walk", m % frames_res.get_frame_count("walk"))]
	var c_last := cell_of("walk", last[0])
	var x_end := X_STOP - (foot("walk", c_last, "toe_x") - anchor("walk").x)
	seg_x[0] = x_end - adv_sum
	var prev_anim := "walk"
	var prev_cell := c_last
	var prev_x := x_end
	for s in range(1, PLAN.size()):
		var anim: String = PLAN[s][0]
		var c0 := cell_of(anim, 0)
		var key := "body_x" if "wave" in [anim, prev_anim] else "toe_x"
		var world := prev_x - anchor(prev_anim).x + foot(prev_anim, prev_cell, key)
		seg_x[s] = world - (foot(anim, c0, key) - anchor(anim).x)
		var length: int = (PLAN[s + 1][1] - PLAN[s][1]) if s + 1 < PLAN.size() else 1
		var e := sample(frames_res, anim, length - 1)
		prev_anim = anim
		prev_cell = cell_of(anim, e[0])
		prev_x = seg_x[s]


func plan_blinks() -> void:
	## Blinzelzeiten für zwei Stunden: Abstand 3–5 s, auf das 6-Bilder/s-Raster gerundet (Vielfache von 5)
	var rng := RandomNumberGenerator.new()
	rng.seed = BLINK_SEED
	var vf := BLINK_FIRST
	while vf < FPS * 7200:
		blinks.append(vf)
		vf += BLINK_LEN * int(round(rng.randf_range(3.0, 5.0) * FPS / BLINK_LEN))


func blinking(vf: int, s: int) -> bool:
	## Blinzeln nur, wenn es ganz im Stehen-Abschnitt liegt und auf dessen Bildraster beginnt
	var i := blinks.bsearch(vf, false) - 1
	if i < 0 or vf >= blinks[i] + BLINK_LEN:
		return false
	var b: int = blinks[i]
	var start: int = PLAN[s][1]
	var stop: int = PLAN[s + 1][1] if s + 1 < PLAN.size() else 1 << 30
	return b >= start and b + BLINK_LEN <= stop and (b - start) % BLINK_LEN == 0


func badger_state(vf: int) -> Dictionary:
	var s := segment(vf)
	var anim: String = PLAN[s][0]
	var local: int = vf - PLAN[s][1]
	var smp := sample(frames_res, anim, local)
	var x: float = seg_x[s]
	if anim == "walk":
		for m in smp[1]:
			x += walk_adv[cell_of("walk", m % frames_res.get_frame_count("walk"))]
	var cell := cell_of(anim, smp[0])
	var st := {"anim": anim, "frame": smp[0], "local": local, "x": x, "cell": cell,
		"sprite_anim": anim, "sprite_frame": smp[0]}
	if anim == "idle" and blinking(vf, s):
		# "blink" hat je Atemstufe ein Bild in derselben Reihenfolge wie die Atemzellen
		st.sprite_anim = "blink"
		st.sprite_frame = cell
		st.cell = cell_of("blink", cell)
	return st


# ------------------------------------------------------------------ Bild
func _process(delta: float) -> void:
	t += delta
	update_all()


func update_all() -> void:
	var vf := int(floor(t * FPS + 0.5))
	var st := badger_state(vf)
	var anim: String = st.anim
	if raw_mode:
		var rj: Dictionary = meta.raw[anim]
		var ri := int(floor(st.local * float(rj.fps) / FPS))
		ri = ri % int(rj.count) if anim != "jump" else mini(ri, int(rj.count) - 1)
		badger.animation = anim
		badger.frame = ri
		badger.offset = Vector2(-float(rj.frame_w) / 2.0, -float(rj.frame_h))
		badger.scale = Vector2(1.6, 1.6)
		badger.position = Vector2(round(st.x), GROUND_Y)
	else:
		if badger.animation != StringName(st.sprite_anim):
			badger.animation = st.sprite_anim
		badger.frame = st.sprite_frame
		badger.offset = -anchor(anim)
		badger.position = Vector2(round(st.x), GROUND_Y)
	shadow_x = badger.position.x - anchor(anim).x + foot(anim, st.cell) if not raw_mode else badger.position.x
	if anim == "walk" and not raw_mode:
		shadow_x = badger.position.x - anchor(anim).x + float(meta.anims.walk.body_x[st.cell])
	shadow_gap = float(meta.anims[anim].gap[st.cell])
	shadow.queue_redraw()
	panel.show_state(st, vf)

	# Licht
	var fl := 0.86 + 0.10 * flick_noise.get_noise_1d(t * 3.0) + 0.05 * flick_noise.get_noise_1d(t * 11.0 + 40.0)
	var fw := 0.94 + 0.05 * flick_noise.get_noise_1d(t * 1.3 + 90.0)
	for n in fx_nodes:
		n.t = t
		n.flicker = fl
		n.flicker_w = fw
	bg_mat.set_shader_parameter("t", t)
	bg_mat.set_shader_parameter("lantern_amount", fl)

	# Oberfläche: Zeile tippt sich, dann Auswahl, dann Parserzeile
	line_label.visible_characters = clampi(int((t - TYPE_START) * CPS), 0, LINE.length())
	var type_end := TYPE_START + LINE.length() / CPS
	for i in choices.size():
		var c: Control = choices[i]
		c.modulate.a = clampf((t - type_end - 0.1 - 0.12 * i) / 0.25, 0.0, 1.0)
	var n_par := clampi(int((t - PARSER_START) * 12.0), 0, PARSER.length())
	parser_label.text = PARSER.substr(0, n_par)
	var fnt := parser_label.get_theme_font("font")
	var fsz := parser_label.get_theme_font_size("font_size")
	cursor.position.x = parser_label.position.x + fnt.get_string_size(parser_label.text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fsz).x + 3.0
	cursor.visible = t > PARSER_START - 0.6 and (n_par < PARSER.length() or fmod(t, 0.9) < 0.5)


func _draw_shadow() -> void:
	# weicher Schatten unter den Füßen; beim Springen kleiner und heller
	var tex: Texture2D = $Glow.soft
	var k := clampf(1.0 - shadow_gap / 70.0, 0.4, 1.0)
	var c := Vector2(shadow_x, GROUND_Y + 1.0)
	shadow.draw_texture_rect(tex, Rect2(c - Vector2(52, 9) * k, Vector2(104, 18) * k), false,
		Color(0.08, 0.06, 0.14, 0.55 * k))
	shadow.draw_texture_rect(tex, Rect2(c - Vector2(34, 5) * k, Vector2(68, 10) * k), false,
		Color(0.08, 0.06, 0.14, 0.35 * k))
