extends Control
## Textoberfläche im Stil einer Comic-Bildunterschrift: Kästen aus cremefarbenem Papier mit
## Tuscherand und schraffiertem Versatzschatten, Handlettering (Patrick Hand / Patrick Hand SC).
## Ortsschild oben links von Anfang an; der Textkasten erscheint mit dem Schnitt auf die Nahaufnahme,
## der Text läuft Zeichen für Zeichen ein, danach die Auswahl und die Parserzeile mit Schreibmarke.
## main.gd setzt t (Sekunden) und shot (1 Totale, 2 Nahaufnahme) in jedem Bild.

const INK := Color("1f1a1c")
const PAPER := Color("fbf3df")
const MARK := Color("f3cf6e")        # Markierung der gewählten Auswahl (Textmarker)
const RED := Color("c4452f")

const LOCATION := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"
const SELECTED := 1

const BOX_T := 2.95                  # Textkasten erscheint (kurz nach dem Schnitt bei 2,7 s)
const CPS := 42.0                    # Zeichen je Sekunde
const PARSER_T := 4.6                # Parsereingabe beginnt

var t := 0.0
var shot := 1

var font_hand: FontFile = preload("res://fonts/PatrickHand-Regular.ttf")
var font_caps: FontFile = preload("res://fonts/PatrickHandSC-Regular.ttf")


func _process(_delta: float) -> void:
	queue_redraw()


func _draw() -> void:
	# Ortsschild oben links
	var cap_size := 30
	var cap_w := font_caps.get_string_size(LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, cap_size).x
	var cap := Rect2(26, 22, cap_w + 34, 46)
	_box(cap)
	draw_string(font_caps, Vector2(cap.position.x + 17, cap.position.y + 33), LOCATION,
		HORIZONTAL_ALIGNMENT_LEFT, -1, cap_size, INK)

	if t < BOX_T or shot < 2:
		return
	# Textkasten unten rechts, neben dem Dachs, unter dem Horizont (Boote bleiben frei)
	var box := Rect2(636, 534, 612, 168)
	_box(box)
	var x0 := box.position.x + 22
	var y := box.position.y + 34
	var shown := int(clampf((t - BOX_T) * CPS, 0.0, LINE.length()))
	for ln in _wrap(LINE.substr(0, shown), LINE, 25, box.size.x - 44):
		draw_string(font_hand, Vector2(x0, y), ln, HORIZONTAL_ALIGNMENT_LEFT, -1, 25, INK)
		y += 28
	var done_t := BOX_T + LINE.length() / CPS
	if t < done_t + 0.1:
		return
	y = box.position.y + 72
	for i in CHOICES.size():
		var cx := x0 + 2
		# Nummer im gezeichneten Kreis
		draw_arc(Vector2(cx + 9, y - 8), 10.5, 0.0, TAU, 28, INK, 1.6, true)
		draw_string(font_hand, Vector2(cx + 4, y - 1), "%d" % (i + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 19, INK)
		var tx := cx + 28
		var w := font_hand.get_string_size(CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 23).x
		if i == SELECTED:
			draw_rect(Rect2(tx - 4, y - 17, w + 9, 20), MARK)
		draw_string(font_hand, Vector2(tx, y), CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 23,
			RED if i == SELECTED else INK)
		y += 27
	# Parserzeile rechts unten
	if t >= PARSER_T:
		var typed := int(clampf((t - PARSER_T) * 10.0, 0.0, PARSER.length()))
		var s := PARSER.substr(0, typed)
		var px := box.position.x + box.size.x - 196
		var py := box.position.y + box.size.y - 18
		draw_string(font_hand, Vector2(px, py), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 25, INK)
		var sw := font_hand.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, 25).x
		if fmod(t, 0.8) < 0.5:
			draw_rect(Rect2(px + sw + 3, py - 18, 8, 21), INK)


## Kasten: schraffierter Versatzschatten, Papierfläche, Tuscherand.
func _box(r: Rect2) -> void:
	var off := Vector2(7, 7)
	var sh := Rect2(r.position + off, r.size)
	var spacing := 5.0
	var n := int((sh.size.x + sh.size.y) / spacing) + 1
	for i in n:
		# Striche von unten links nach oben rechts, auf das Schattenrechteck beschnitten
		var c := sh.position.x + i * spacing - sh.size.y
		var a := Vector2(c, sh.end.y)
		var b := Vector2(c + sh.size.y, sh.position.y)
		var seg := _clip(a, b, sh)
		if seg.size() == 2:
			draw_line(seg[0], seg[1], INK, 1.2, true)
	draw_rect(r, PAPER)
	draw_rect(r, INK, false, 2.6, true)


## Strecke a-b auf das Rechteck r beschneiden (Liang-Barsky); leer, wenn außerhalb.
func _clip(a: Vector2, b: Vector2, r: Rect2) -> Array:
	var t0 := 0.0
	var t1 := 1.0
	var d := b - a
	var p := [-d.x, d.x, -d.y, d.y]
	var q := [a.x - r.position.x, r.end.x - a.x, a.y - r.position.y, r.end.y - a.y]
	for i in 4:
		if absf(p[i]) < 1e-6:
			if q[i] < 0.0:
				return []
		else:
			var u: float = q[i] / p[i]
			if p[i] < 0.0:
				t0 = maxf(t0, u)
			else:
				t1 = minf(t1, u)
	if t0 > t1:
		return []
	return [a + d * t0, a + d * t1]


## Umbruch nach dem vollständigen Text (damit Wörter beim Einlaufen nicht springen).
func _wrap(part: String, full: String, size: int, width: float) -> Array:
	var out := []
	var words := full.split(" ")
	var line := ""
	var start := 0
	var breaks := []
	for w in words:
		var test := w if line == "" else line + " " + w
		if font_hand.get_string_size(test, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x > width and line != "":
			breaks.append(start + line.length())
			start += line.length() + 1
			line = w
		else:
			line = test
	var pos := 0
	for b in breaks:
		if part.length() > pos:
			out.append(part.substr(pos, mini(b, part.length()) - pos))
		pos = b + 1
	if part.length() > pos:
		out.append(part.substr(pos))
	return out
