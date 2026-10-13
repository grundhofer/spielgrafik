extends Control
## Textoberfläche im Modellbau-Stil: eine cremefarbene Karteikarte, die mit weichem Schatten über dem
## Diorama liegt, darauf ein Messingschild mit dem Ort (wie das Schild vorn am Sockel), die Zeile, die
## Auswahl als Pillen mit Messingnummern und die Eingabezeile. Erscheint, wenn die Kamera beim Dachs
## ankommt; Text Zeichen für Zeichen. Zeit kommt von main.gd (set_time), damit --t0 auch hier gilt.

const PAPER := Color("f7efdd")
const PAPER_EDGE := Color("d9c7a3")
const INK := Color("3a2a1f")
const MUTED := Color("8a7660")
const PILL := Color("ece0c6")
const ACCENT := Color("c4473a")
const BRASS_HI := Color("f1d08a")
const BRASS := Color("cf9f4a")
const BRASS_LO := Color("9c7232")

const LOCATION := "Hafen von Lornholm"
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "nimm paket"
const SELECTED := 1

const CARD := Rect2(778, 420, 478, 276)
const IN_T := 3.45           # Karte gleitet herein
const IN_LEN := 0.45
const TYPE_T := 3.6
const TYPE_RATE := 100.0
const CHOICE_T := 4.2
const PARSE_T := 4.45        # "> nimm paket" ist bei 4,9 s fertig (Poster bei 4,97 s)
const PARSE_RATE := 22.0

var t := 0.0
var body: FontVariation
var bold: FontVariation
var title: Font


func _ready() -> void:
	var base := load("res://fonts/Nunito-wght.ttf") as FontFile
	var ts := TextServerManager.get_primary_interface()
	body = FontVariation.new()
	body.base_font = base
	body.variation_opentype = {ts.name_to_tag("wght"): 600}
	bold = FontVariation.new()
	bold.base_font = base
	bold.variation_opentype = {ts.name_to_tag("wght"): 760}
	title = load("res://fonts/MarcellusSC-Regular.ttf") as Font


func set_time(time: float) -> void:
	t = time
	queue_redraw()


static func _ease_out(x: float) -> float:
	x = clampf(x, 0.0, 1.0)
	return 1.0 - pow(1.0 - x, 3.0)


func _box(rect: Rect2, fill: Color, radius: int, border := 0, border_col := Color.TRANSPARENT,
		shadow := 0, shadow_col := Color(0, 0, 0, 0)) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = fill
	sb.set_corner_radius_all(radius)
	sb.anti_aliasing = true
	sb.corner_detail = 12
	if border > 0:
		sb.set_border_width_all(border)
		sb.border_color = border_col
	if shadow > 0:
		sb.shadow_size = shadow
		sb.shadow_color = shadow_col
		sb.shadow_offset = Vector2(0, shadow * 0.45)
	draw_style_box(sb, rect)


func _brass(rect: Rect2, radius: int, a: float) -> void:
	# Messing: dunkler Rand, mittlerer Ton, helle obere Hälfte (gebürstet)
	_box(rect, Color(BRASS_LO, a), radius, 0, Color.TRANSPARENT, 6, Color(0, 0, 0, 0.3 * a))
	var inner := rect.grow(-2)
	_box(inner, Color(BRASS, a), radius - 1)
	_box(Rect2(inner.position, Vector2(inner.size.x, inner.size.y * 0.48)), Color(BRASS_HI, 0.55 * a), radius - 1)


func _draw() -> void:
	if t < IN_T:
		return
	var k := _ease_out((t - IN_T) / IN_LEN)
	var a := k
	var card := CARD
	card.position.y += (1.0 - k) * 40.0

	# Karte mit weichem Schatten (liegt über dem Modell), feiner Innenrand wie bei einer Karteikarte
	_box(card, Color(PAPER, 0.97 * a), 16, 0, Color.TRANSPARENT, 22, Color(0.08, 0.04, 0.1, 0.42 * a))
	_box(card.grow(-7), Color(0, 0, 0, 0), 11, 2, Color(PAPER_EDGE, a))

	# Messingschild mit dem Ort, halb über der Oberkante
	var tsize := 21
	var tw := title.get_string_size(LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, tsize).x
	var tag := Rect2(card.position + Vector2(30, -19), Vector2(tw + 46, 36))
	_brass(tag, 7, a)
	for sx in [tag.position.x + 10, tag.end.x - 10]:
		draw_circle(Vector2(sx, tag.position.y + 18), 3.2, Color(BRASS_LO, a))
		draw_circle(Vector2(sx - 0.8, tag.position.y + 17.2), 1.4, Color(BRASS_HI, a))
	draw_string(title, tag.position + Vector2(23, 26), LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, tsize, Color(0.24, 0.15, 0.06, a))

	# Zeilen Zeichen für Zeichen (satzweise umbrochen)
	var n := int(clampf((t - TYPE_T) * TYPE_RATE, 0.0, 999.0))
	var ly := card.position.y + 52.0
	for line: String in LINES:
		if n > 0:
			draw_string(bold, Vector2(card.position.x + 32, ly), line.substr(0, n), HORIZONTAL_ALIGNMENT_LEFT, -1, 24, Color(INK, a))
		n -= line.length() + 1
		ly += 32.0

	# Auswahl als Pillen mit Messingnummern, untereinander
	var ca := clampf((t - CHOICE_T) / 0.3, 0.0, 1.0) * a
	if ca > 0.0:
		var x := card.position.x + 26.0
		var y := card.position.y + 102.0
		for i in CHOICES.size():
			var label: String = CHOICES[i]
			var w := body.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, 19).x + 64.0
			var sel := i == SELECTED
			var r := Rect2(x, y, w, 36)
			if sel:
				_box(r, Color(ACCENT, ca), 18, 0, Color.TRANSPARENT, 5, Color(0.3, 0.05, 0.02, 0.35 * ca))
			else:
				_box(r, Color(PILL, ca), 18, 1, Color(PAPER_EDGE, ca))
			_brass(Rect2(x + 5, y + 5, 26, 26), 13, ca)
			var num := str(i + 1)
			var nw := bold.get_string_size(num, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x
			draw_string(bold, Vector2(x + 18 - nw / 2.0, y + 24), num, HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color(0.24, 0.15, 0.06, ca))
			draw_string(body, Vector2(x + 41, y + 25), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 19,
				Color(Color.WHITE if sel else INK, ca))
			y += 44.0

	# Eingabezeile
	var pa := clampf((t - PARSE_T + 0.25) / 0.25, 0.0, 1.0) * a
	if pa > 0.0:
		var m := int(clampf((t - PARSE_T) * PARSE_RATE, 0.0, PARSER.length()))
		var txt := "> " + PARSER.substr(0, m)
		var py := card.position.y + 254.0
		draw_string(bold, Vector2(card.position.x + 34, py), txt, HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color(MUTED, pa))
		var cw := bold.get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, 18).x
		if fmod(t, 0.8) < 0.5:
			draw_rect(Rect2(card.position.x + 36 + cw, py - 15, 9, 18), Color(ACCENT, pa))
