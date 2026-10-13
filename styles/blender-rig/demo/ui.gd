extends Control
## Oberfläche der Technik-Demo, alles in _draw():
##   - oben links ein kleines Debug-Fenster mit dem AnimationTree des Dachses (Knoten wie im Godot-Editor:
##     Idle, Walk -> TimeScale, Blend2, Wave -> OneShot); die Verbindungen leuchten nach ihrem Gewicht,
##     Blend2 zeigt blend_amount, TimeScale das Tempo, OneShot den Fortschritt des Winkens.
##   - unten rechts der Dialogkasten mit ui_text aus data/motif.json (Ort, Zeile, Auswahl, Parser).
## Zustand kommt je Bild aus main.gd (set_state), Zeit aus aufsummiertem delta.

const BG := Color(0.065, 0.075, 0.105, 0.86)
const EDGE := Color(0.62, 0.78, 0.96, 0.30)
const TEXT := Color(0.93, 0.95, 0.98)
const DIM := Color(0.60, 0.66, 0.76)
const ACCENT := Color(0.36, 0.82, 1.0)
const WARM := Color(1.0, 0.80, 0.28)
const NODE_BG := Color(0.15, 0.17, 0.22, 0.96)
const HEAD_ANIM := Color(0.33, 0.50, 0.85)
const HEAD_BLEND := Color(0.55, 0.42, 0.85)
const HEAD_SHOT := Color(0.85, 0.48, 0.30)

const LOCATION := "Hafen von Lornholm"
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"

const PANEL := Rect2(24, 22, 486, 200)
const BOX := Rect2(612, 552, 644, 146)
const BOX_T := 0.2
const TYPE_T := 0.45
const TYPE_RATE := 42.0
const CHOICE_T := 2.0
const PARSER_T := 3.1

var t := 0.0
var st := {"blend": 1.0, "speed": 2.0, "walk_time": 0.0, "wave_active": false, "wave_t": -1.0, "rig": 0.0}
var body: FontVariation
var bold: FontVariation
var mono: Font
var mono_b: Font


func _ready() -> void:
	var ts := TextServerManager.get_primary_interface()
	var nunito := load("res://fonts/Nunito.ttf") as FontFile
	body = FontVariation.new()
	body.base_font = nunito
	body.variation_opentype = {ts.name_to_tag("wght"): 600}
	bold = FontVariation.new()
	bold.base_font = nunito
	bold.variation_opentype = {ts.name_to_tag("wght"): 800}
	mono = load("res://fonts/IBMPlexMono-Regular.ttf") as Font
	mono_b = load("res://fonts/IBMPlexMono-SemiBold.ttf") as Font


func set_state(time_s: float, s: Dictionary) -> void:
	t = time_s
	st = s
	queue_redraw()


func _draw() -> void:
	_draw_tree_panel()
	_draw_dialog()


# --- AnimationTree --------------------------------------------------------------------------------
func _box(r: Rect2, fill: Color, radius: int, border := Color(0, 0, 0, 0), bw := 0) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = fill
	sb.set_corner_radius_all(radius)
	sb.anti_aliasing = true
	if bw > 0:
		sb.border_color = border
		sb.set_border_width_all(bw)
	draw_style_box(sb, r)


func _node(r: Rect2, title: String, head: Color, glow: float) -> void:
	if glow > 0.01:
		_box(r.grow(3), Color(ACCENT, 0.35 * glow), 8)
	_box(r, NODE_BG, 6, Color(head, 0.9), 1)
	var hr := Rect2(r.position, Vector2(r.size.x, 18))
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(head, 0.85)
	sb.corner_radius_top_left = 6
	sb.corner_radius_top_right = 6
	sb.anti_aliasing = true
	draw_style_box(sb, hr)
	draw_string(mono_b, r.position + Vector2(7, 13.5), title, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, TEXT)


func _wire(a: Vector2, b: Vector2, w: float) -> void:
	var pts := PackedVector2Array()
	var dx := maxf(24.0, (b.x - a.x) * 0.5)
	for i in 21:
		var u := i / 20.0
		var p := a.bezier_interpolate(a + Vector2(dx, 0), b - Vector2(dx, 0), b, u)
		pts.append(p)
	draw_polyline(pts, Color(DIM, 0.45), 1.6, true)
	if w > 0.01:
		draw_polyline(pts, Color(ACCENT, w), 1.0 + 2.2 * w, true)
	draw_circle(a, 3.5, Color(ACCENT.lerp(DIM, 1.0 - w), 1.0), true, -1.0, true)
	draw_circle(b, 3.5, Color(ACCENT.lerp(DIM, 1.0 - w), 1.0), true, -1.0, true)


func _bar(r: Rect2, v: float, col: Color) -> void:
	_box(r, Color(0, 0, 0, 0.45), 3)
	if v > 0.002:
		_box(Rect2(r.position, Vector2(maxf(r.size.x * clampf(v, 0.0, 1.0), 6.0), r.size.y)), col, 3)


func _draw_tree_panel() -> void:
	var P := PANEL
	_box(P, BG, 12, EDGE, 1)
	var o := P.position
	draw_string(mono_b, o + Vector2(16, 26), "AnimationTree", HORIZONTAL_ALIGNMENT_LEFT, -1, 15, TEXT)
	draw_string(mono, o + Vector2(16, 26), "badger.glb · 21 Knochen", HORIZONTAL_ALIGNMENT_RIGHT,
		P.size.x - 32, 12, DIM)

	var b: float = st["blend"]
	var wave_w := 0.0
	var wt: float = st["wave_t"]
	if wt >= 0.0 and wt <= 1.5:
		wave_w = clampf(wt / 0.25, 0.0, 1.0) * clampf((1.5 - wt) / 0.3, 0.0, 1.0)

	var g := o + Vector2(16, 42)
	var r_idle := Rect2(g + Vector2(0, 0), Vector2(86, 40))
	var r_walk := Rect2(g + Vector2(0, 54), Vector2(86, 40))
	var r_speed := Rect2(g + Vector2(104, 54), Vector2(96, 40))
	var r_blend := Rect2(g + Vector2(222, 14), Vector2(104, 54))
	var r_wave := Rect2(g + Vector2(222, 82), Vector2(104, 40))
	var r_shot := Rect2(g + Vector2(350, 34), Vector2(104, 54))

	_wire(r_idle.position + Vector2(r_idle.size.x, 29), r_blend.position + Vector2(0, 33), (1.0 - b) * (1.0 - wave_w))
	_wire(r_walk.position + Vector2(r_walk.size.x, 29), r_speed.position + Vector2(0, 29), b * (1.0 - wave_w))
	_wire(r_speed.position + Vector2(r_speed.size.x, 29), r_blend.position + Vector2(0, 47), b * (1.0 - wave_w))
	_wire(r_blend.position + Vector2(r_blend.size.x, 33), r_shot.position + Vector2(0, 33), 1.0 - wave_w)
	_wire(r_wave.position + Vector2(r_wave.size.x, 29), r_shot.position + Vector2(0, 47), wave_w)
	var out_a := r_shot.position + Vector2(r_shot.size.x, 33)
	draw_line(out_a, out_a + Vector2(10, 0), Color(ACCENT, 0.9), 2.0, true)
	draw_colored_polygon(PackedVector2Array([out_a + Vector2(10, -5), out_a + Vector2(17, 0), out_a + Vector2(10, 5)]),
		Color(ACCENT, 0.9))

	var walk_phase := fposmod(float(st["walk_time"]), 1.0)
	_node(r_idle, "Idle", HEAD_ANIM, (1.0 - b) * (1.0 - wave_w))
	draw_string(mono, r_idle.position + Vector2(7, 33), "2,0 s  Loop", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, DIM)
	_node(r_walk, "Walk", HEAD_ANIM, b * (1.0 - wave_w))
	_bar(Rect2(r_walk.position + Vector2(7, 26), Vector2(r_walk.size.x - 14, 6)), walk_phase if b > 0.01 else 0.0,
		Color(ACCENT, 0.9))
	_node(r_speed, "TimeScale", HEAD_BLEND, 0.0)
	draw_string(mono, r_speed.position + Vector2(7, 33), "× %.2f" % float(st["speed"]), HORIZONTAL_ALIGNMENT_LEFT,
		-1, 12, TEXT)
	_node(r_blend, "Blend2", HEAD_BLEND, 0.0)
	draw_string(mono, r_blend.position + Vector2(7, 33), "Idle", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, DIM)
	draw_string(mono, r_blend.position + Vector2(7, 33), "Walk", HORIZONTAL_ALIGNMENT_RIGHT, r_blend.size.x - 14, 11, DIM)
	_bar(Rect2(r_blend.position + Vector2(7, 40), Vector2(r_blend.size.x - 14, 7)), b, Color(WARM, 0.95))
	_node(r_wave, "Wave", HEAD_ANIM, wave_w)
	draw_string(mono, r_wave.position + Vector2(7, 33), "1,5 s  einmal", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, DIM)
	_node(r_shot, "OneShot", HEAD_SHOT, wave_w)
	var active: bool = st["wave_active"]
	draw_string(mono, r_shot.position + Vector2(7, 33), "aktiv" if active else "bereit", HORIZONTAL_ALIGNMENT_LEFT,
		-1, 11, ACCENT if active else DIM)
	_bar(Rect2(r_shot.position + Vector2(7, 40), Vector2(r_shot.size.x - 14, 7)),
		clampf(wt / 1.5, 0.0, 1.0) if wt >= 0.0 and wt <= 1.5 else 0.0, Color(HEAD_SHOT.lightened(0.2), 0.95))

	# Legende der Knochenfarben (rig_overlay.gd), hell, solange Knochen und Gitter eingeblendet sind
	var rig: float = st["rig"]
	var lx := o.x + 16.0
	var ly := P.end.y - 13.0
	var lcol := Color(DIM.lerp(TEXT, rig), 0.75 + 0.25 * rig)
	for item in [["Mitte", Color(1.0, 0.80, 0.28)], [".L", Color(0.30, 0.82, 1.0)], [".R", Color(1.0, 0.42, 0.72)],
			["Schal/Schwanz", Color(0.50, 0.95, 0.52)]]:
		draw_circle(Vector2(lx + 5, ly - 4), 4.5, item[1], true, -1.0, true)
		draw_string(mono, Vector2(lx + 14, ly), item[0], HORIZONTAL_ALIGNMENT_LEFT, -1, 11, lcol)
		lx += 22.0 + mono.get_string_size(item[0], HORIZONTAL_ALIGNMENT_LEFT, -1, 11).x
	draw_string(mono, Vector2(o.x + 16, ly), "Gitter: Vierecke", HORIZONTAL_ALIGNMENT_RIGHT, P.size.x - 32, 11, lcol)


# --- Dialogkasten ---------------------------------------------------------------------------------
func _draw_dialog() -> void:
	var k := smoothstep(BOX_T, BOX_T + 0.3, t)
	if k <= 0.0:
		return
	var r := BOX
	r.position.y += (1.0 - k) * 18.0
	_box(r, Color(BG, BG.a * k), 14, Color(EDGE, EDGE.a * k), 1)
	var o := r.position
	# Ort
	draw_string(bold, o + Vector2(22, 30), LOCATION.to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(ACCENT, k))
	# Zeile, Zeichen für Zeichen
	var n := int(floor(maxf(t - TYPE_T, 0.0) * TYPE_RATE))
	var y := 62.0
	for line in LINES:
		var shown: String = line.substr(0, clampi(n, 0, line.length()))
		n -= line.length() + 1
		draw_string(body, o + Vector2(22, y), shown, HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color(TEXT, k))
		y += 28.0
	# Parser
	if t >= PARSER_T:
		var m := clampi(int(floor((t - PARSER_T) * 14.0)), 0, PARSER.length())
		var ptxt := PARSER.substr(0, m)
		var pp := o + Vector2(22, 130)
		draw_string(mono, pp, ptxt, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color(WARM, k))
		var cx := mono.get_string_size(ptxt, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x
		if fposmod(t, 0.8) < 0.5:
			draw_rect(Rect2(pp + Vector2(cx + 2, -13), Vector2(8, 16)), Color(WARM, 0.85 * k))
	# Auswahl
	var c := smoothstep(CHOICE_T, CHOICE_T + 0.35, t) * k
	if c > 0.0:
		var cx0 := o.x + 384.0
		draw_line(Vector2(cx0 - 18, o.y + 22), Vector2(cx0 - 18, r.end.y - 22), Color(EDGE, 0.8 * c), 1.0)
		for i in CHOICES.size():
			var cy := o.y + 30.0 + i * 38.0
			var sel := i == 0
			if sel:
				_box(Rect2(cx0 - 6, cy - 4, 248, 32), Color(ACCENT, 0.18 * c), 8, Color(ACCENT, 0.7 * c), 1)
			draw_string(bold, Vector2(cx0 + 4, cy + 18), str(i + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 15,
				Color(ACCENT if sel else DIM, c))
			draw_string(body, Vector2(cx0 + 24, cy + 18), CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 17,
				Color(TEXT if sel else TEXT.darkened(0.15), c))
