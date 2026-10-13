extends Control
## Textoberfläche im Toon-Stil: Ortsschild als schräges Band oben links (von Anfang an), Dialogkasten
## unten rechts, der beim Heranfahren der Kamera aufspringt (Überschwingen wie eine Comic-Blase),
## Text Zeichen für Zeichen, danach die Auswahl als Pillen; die gewählte orange mit hüpfendem Pfeil.
## Dicke Tintenkontur, harter Versatzschatten ohne Unschärfe, runde Schrift (Fredoka, Lilita One).
## Alles in _draw(); Zeit aus aufsummiertem delta (deterministische Aufnahme).

const INK := Color("24182c")
const PAPER := Color("fff6e3")
const ACCENT := Color("ff8f3a")
const PILL := Color("f6e6c8")
const TAG := Color("ffd25a")

const LOCATION := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]

const BOX_T := 3.95          # Kasten springt auf
const TYPE_T := 4.1          # Text beginnt
const TYPE_RATE := 95.0      # Zeichen je Sekunde
const CHOICE_T := 4.55       # Auswahl erscheint
const BOX := Rect2(486, 528, 758, 168)

var t := 0.0
var body_font: FontVariation
var title_font: Font
var text_lines: PackedStringArray


func _ready() -> void:
	var base := load("res://fonts/Fredoka-wdth-wght.ttf") as FontFile
	body_font = FontVariation.new()
	body_font.base_font = base
	var ts := TextServerManager.get_primary_interface()
	body_font.variation_opentype = {ts.name_to_tag("wght"): 560}
	title_font = load("res://fonts/LilitaOne-Regular.ttf") as Font
	# Satzweise umbrechen (jeder Satz auf eigener Zeile, falls er passt)
	text_lines = PackedStringArray()
	for sentence in LINE.replace(". ", ".|").split("|"):
		text_lines.append_array(_wrap(sentence, 384.0, 24))


func _process(delta: float) -> void:
	t += delta
	queue_redraw()


## Überschwingen beim Aufspringen: 0 -> 1 mit kurzem Hinausschießen
static func _back_out(x: float) -> float:
	x = clampf(x, 0.0, 1.0) - 1.0
	var c := 2.2
	return 1.0 + (c + 1.0) * x * x * x + c * x * x


func _panel(rect: Rect2, fill: Color, radius: int, border: int, shadow: Vector2, alpha := 1.0) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(INK, 0.5 * alpha)
	sb.set_corner_radius_all(radius)
	sb.anti_aliasing = true
	if shadow != Vector2.ZERO:
		draw_style_box(sb, Rect2(rect.position + shadow, rect.size))
	sb = StyleBoxFlat.new()
	sb.bg_color = Color(fill, fill.a * alpha)
	sb.border_color = Color(INK, alpha)
	sb.set_border_width_all(border)
	sb.set_corner_radius_all(radius)
	sb.anti_aliasing = true
	draw_style_box(sb, rect)


func _draw() -> void:
	# Ortsschild oben links, leicht gedreht
	var tag_size := 30
	var tw := title_font.get_string_size(LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, tag_size).x
	draw_set_transform(Vector2(34, 30), deg_to_rad(-2.5), Vector2.ONE)
	_panel(Rect2(0, 0, tw + 44, 50), TAG, 12, 4, Vector2(5, 5))
	draw_string(title_font, Vector2(22, 37), LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, tag_size, INK)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

	if t < BOX_T:
		return
	# Dialogkasten: springt von der linken unteren Ecke (zum Dachs hin) auf
	var k := _back_out((t - BOX_T) / 0.32)
	var pivot := BOX.position + Vector2(0, BOX.size.y)
	var sc := lerpf(0.6, 1.0, k)
	var a := clampf((t - BOX_T) / 0.12, 0.0, 1.0)
	draw_set_transform(pivot * (1.0 - sc), 0.0, Vector2(sc, sc))
	_panel(BOX, PAPER, 24, 5, Vector2(7, 7), a)

	# Text Zeichen für Zeichen
	var shown := int(maxf(t - TYPE_T, 0.0) * TYPE_RATE)
	var fs := 24
	var y := BOX.position.y + 52
	for line in text_lines:
		if shown <= 0:
			break
		var part := line.substr(0, shown)
		draw_string(body_font, Vector2(BOX.position.x + 30, y), part, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, INK)
		shown -= line.length() + 1
		y += 36

	# Auswahl als Pillen rechts im Kasten
	var ca := clampf((t - CHOICE_T) / 0.2, 0.0, 1.0)
	if ca > 0.0:
		var cx := BOX.position.x + 424
		var cw := BOX.size.x - 424 - 22
		var cy := BOX.position.y + 18
		for i in CHOICES.size():
			var slide := (1.0 - _back_out(clampf((t - CHOICE_T - 0.06 * i) / 0.25, 0.0, 1.0))) * 30.0
			var r := Rect2(cx + slide, cy + i * 46, cw, 38)
			var sel := i == 0
			_panel(r, ACCENT if sel else PILL, 20, 3, Vector2(3, 3) if sel else Vector2.ZERO, ca)
			draw_string(body_font, Vector2(r.position.x + 40, r.position.y + 27), CHOICES[i],
				HORIZONTAL_ALIGNMENT_LEFT, -1, 22, Color(Color.WHITE if sel else INK, ca))
			if sel:
				var bx := r.position.x + 14 + 4.0 * absf(sin((t - CHOICE_T) * 6.0))
				var by := r.position.y + 19
				var tri := PackedVector2Array([Vector2(bx, by - 8), Vector2(bx + 14, by), Vector2(bx, by + 8)])
				draw_colored_polygon(tri, Color(Color.WHITE, ca))
				draw_polyline(PackedVector2Array([tri[0], tri[1], tri[2], tri[0]]), Color(INK, ca), 2.5, true)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


func _wrap(text: String, width: float, fs: int) -> PackedStringArray:
	var out := PackedStringArray()
	var cur := ""
	for word in text.split(" "):
		var test := word if cur == "" else cur + " " + word
		if body_font.get_string_size(test, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x > width and cur != "":
			out.append(cur)
			cur = word
		else:
			cur = test
	if cur != "":
		out.append(cur)
	return out
