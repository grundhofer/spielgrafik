extends Node2D
## Hafen von Lornholm auf einer Fantasy-Konsole: 128x128 Pixel, feste 16 Farben, 8x8-Sprites, 3x5-Schrift.
## Dieses Skript ist das Spielprogramm. Es zeichnet jedes Bild neu, nur mit den Befehlen der Konsole
## (P8: cls, rectfill, fillp, line, circfill, spr, map, pal, palt, print …) in einen Bildspeicher mit
## Farbnummern; shaders/screen.gdshader setzt die Palette ein. Grafikdaten: cart/lornholm.p8.
## Wie auf der Konsole läuft _update/_draw mit 30 Bildern/s. Zeit über delta aufsummiert, Zufall mit festem
## Seed: Aufnahmen sind reproduzierbar.
## Benutzerargumente (nach "--"): --t0=<s> startet später (Dauerlauf-Prüfung), --only=badger zeichnet nur den
## Dachs auf Rosa (Fußmessung), --probe schreibt je Bild Pose und Position ins Log.

const FPS := 30
const LOCATION := "Hafen von Lornholm"
const LINE := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf", "dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"

# Ablauf (Bildnummern bei 30 Bildern/s)
const WALK_HOLD := 3            # Laufbild alle 3 Bilder (10 Bilder/s), 2 px Vorschub je Laufbild
const WALK_X0 := -8             # Dachs startet halb im Bild
const WALK_STEPS := 32          # 32 Laufbilder = 8 Zyklen, endet auf pass2 -> Stand ohne Fußrutschen
const TEXT_START := 15          # Schreibmaschine ab 0,5 s, 1 Zeichen je Bild, Pause nach Satzzeichen
const MENU_START := 129         # Auswahl ab 4,3 s
const CURSOR_MOVE := 150        # Cursor springt bei 5,0 s auf den zweiten Eintrag
const PARSER_START := 138       # Parserzeile tippt ab 4,6 s (1 Zeichen je 2 Bilder)
const BLINK_AT := [34, 71]      # Dachs blinzelt ab Standbeginn (Bild 96) bei 4,3 s und 5,6 s, dann alle 4 s
const BLINK_PERIOD := 120       # (je 4 Bilder, Lid über 2 px)
const SCARF_HOLD := 10          # Stand: Schalende flattert, Wechsel alle 10 Bilder
const BREATH_PERIOD := 30       # Stand: Oberkörper 1 px gehoben in der zweiten Hälfte jeder Sekunde
const BEAM_PHASE := 0.2167      # Leuchtfeuer: bei Bild 108 (Poster) zeigt der Strahl schräg nach links

# Licht der Laterne: Farbtabelle (warm aufhellen), wie auf der Konsole über pal()/Speicher üblich
const LIGHT := [0, 1, 4, 3, 9, 4, 15, 7, 14, 10, 7, 10, 6, 6, 15, 7]

var p8: P8
var spr_info := {}
var frame := 0
var t := 0.0
var t0 := 0.0
var only_badger := false
var probe := false
var img: Image
var tex: ImageTexture
var rng := RandomNumberGenerator.new()
var stars := []
var glints := []
var smoke := []
var lantern_seq := PackedByteArray()

@onready var screen: TextureRect = $Screen


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a == "--only=badger":
			only_badger = true
		elif a == "--probe":
			probe = true
	p8 = P8.new()
	p8.load_cart("res://cart/lornholm.p8")
	p8.load_font("res://cart/font35.json")
	spr_info = JSON.parse_string(FileAccess.get_file_as_string("res://cart/sprites.json"))
	rng.seed = 8128
	for i in 14:
		stars.append([rng.randi_range(2, 125), rng.randi_range(1, 14), rng.randi_range(0, 59)])
	# Glitzerstriche im Meer: Zeile, Länge, Startspalte, Tempo (Bilder je px), Phase
	for row in [[47, 9], [49, 9], [52, 2], [55, 13], [58, 13], [62, 12], [66, 13], [70, 12], [74, 12]]:
		for k in 3:
			glints.append([row[0], row[1], rng.randi_range(2, 5), rng.randi_range(0, 127),
				[10, 15, 20][rng.randi_range(0, 2)], rng.randi_range(0, 89)])
	for i in 400:
		lantern_seq.append(rng.randi_range(0, 9))
	img = Image.create_empty(128, 128, false, Image.FORMAT_R8)
	tex = ImageTexture.create_from_image(img)
	screen.texture = tex
	frame = int(round(t0 * FPS))
	# Rauch vorlaufen lassen, damit er bei Bild 0 schon steht
	for f in range(frame - 90, frame):
		_update_smoke(f)
	_draw_frame()


func _process(delta: float) -> void:
	t += delta
	var target := int(round((t0 + t) * FPS))
	while frame < target:
		frame += 1
		_update_smoke(frame)
	var t_us := Time.get_ticks_usec()
	_draw_frame()
	if probe and not only_badger:
		print("PROBE frame=%d draw_us=%d" % [frame, Time.get_ticks_usec() - t_us])


# --- Aktualisieren ----------------------------------------------------------------------------------------

func _update_smoke(f: int) -> void:
	if f % 10 == 0:
		smoke.append({"x": 19.0, "y": 32.0, "age": 0, "w": rng.randf_range(0.0, 6.28)})
	for s in smoke:
		s["age"] += 1
		s["y"] -= 0.25
		s["x"] -= 0.03 + 0.002 * s["age"]
	smoke = smoke.filter(func(s): return s["age"] < 80)


# --- Zeichnen ---------------------------------------------------------------------------------------------

func _draw_frame() -> void:
	if only_badger:
		p8.cls(14)
		_draw_badger()
		_flip()
		return
	_draw_sky()
	_draw_sea()
	_draw_beam()
	_draw_gulls()
	_draw_boats()
	_draw_smoke()
	# Felder nutzen Rosa als Durchsichtsfarbe, damit schwarze Konturen vor dem Meer stehen bleiben
	p8.palt(0, false)
	p8.palt(14, true)
	p8.map(0, 0, 0, int(spr_info["map_sy"]), 16, int(spr_info["map_rows"]))
	p8.palt()
	_draw_lamp()
	_draw_lantern()
	_draw_actor("parcel", 79, 82)
	_draw_badger()
	_draw_box()
	_flip()


func _flip() -> void:
	img.set_data(128, 128, false, Image.FORMAT_R8, p8.fb)
	tex.update(img)


func _draw_sky() -> void:
	p8.cls(1)
	# Abendhimmel in Bändern, Übergänge mit Füllmuster (Schachbrett und Streifen)
	p8.fillp(0b0101101001011010)
	p8.rectfill(0, 15, 127, 16, 0x21)
	p8.fillp()
	p8.rectfill(0, 17, 127, 26, 2)
	p8.fillp(0b1010010110100101)
	p8.rectfill(0, 27, 127, 28, 0xe2)
	p8.fillp()
	p8.rectfill(0, 29, 127, 35, 14)
	p8.fillp(0b0101101001011010)
	p8.rectfill(0, 36, 127, 37, 0x9e)
	p8.fillp()
	p8.rectfill(0, 38, 127, 44, 9)
	p8.line(0, 44, 127, 44, 10)
	# Sterne funkeln (Farbe wechselt alle 15 Bilder je nach Phase)
	for s in stars:
		var ph := int((frame + s[2]) / 15) % 4
		var c: int = [7, 6, 7, 13][ph]
		p8.pset(s[0], s[1], c)
	# Wolken ziehen langsam nach rechts (1 px je 15 Bilder)
	var dx := int(frame / 15)
	_cloud(8 + dx, 31, 18)
	_cloud(58 + dx, 21, 24)
	_cloud(86 + dx, 34, 12)


func _cloud(x: int, y: int, w: int) -> void:
	x = ((x + 20) % 168) - 20
	p8.rectfill(x + 2, y - 2, x + w - 4, y - 1, 15)
	p8.rectfill(x, y, x + w, y + 1, 15)
	p8.line(x + 1, y + 2, x + w - 1, y + 2, 9)


func _draw_sea() -> void:
	p8.rectfill(0, 45, 127, 90, 1)
	# Horizont: Abendlicht auf dem Wasser
	p8.fillp(0b0101101001011010)
	p8.rectfill(0, 45, 127, 45, 0x29)
	p8.fillp()
	for g in glints:
		var y: int = g[0]
		var c: int = g[1]
		var ln: int = g[2]
		var x: int = (g[3] + int((frame + g[5]) / g[4])) % 140 - 6
		# Striche blinken: 2/3 der Zeit sichtbar, dann kurz kürzer
		var vis := int((frame + g[5]) / 10) % 6
		if vis == 5:
			continue
		if vis == 4:
			ln = max(1, ln - 2)
		p8.line(x, y, x + ln - 1, y, c)
	# Spiegelung des Leuchtfeuers unter der Felsnase
	var lit := _lamp_level()
	if lit > 0:
		for k in 4:
			var yy := 60 + k * 4
			var off := int((frame + k * 7) / 6) % 3 - 1
			p8.line(116 + off - (2 if lit > 1 else 1), yy, 116 + off + (2 if lit > 1 else 1), yy, 10 if lit > 1 else 9)


## Leuchtfeuer: dreht sich in 3 s einmal; Stufe 0 aus (Rückseite), 1 seitlich, 2 zur Kamera
func _beam_angle() -> float:
	return fmod(frame / 90.0 + BEAM_PHASE, 1.0) * TAU


func _lamp_level() -> int:

	var s := sin(_beam_angle())
	if s > 0.85:
		return 2
	if s > -0.2:
		return 1
	return 0


func _draw_beam() -> void:
	var a := _beam_angle()
	var s := sin(a)
	if s < -0.2:
		return
	var lx := 118
	var ly := 15
	var blen := int(70.0 * abs(cos(a)))
	var dir := -1 if cos(a) < 0 else 1
	if blen < 3:
		return
	# Strahl als Keil im Schachbrett-Füllmuster (50 % durchsichtig), Kern als Linie
	p8.fillp(0b0101101001011010, true)
	for i in range(1, blen):
		var hw := i / 18
		p8.line(lx + dir * i, ly - hw, lx + dir * i, ly + hw, 10)
	p8.fillp()
	p8.line(lx, ly, lx + dir * (blen * 2 / 5), ly, 10)


func _draw_lamp() -> void:
	var lvl := _lamp_level()
	var c: int = [9, 10, 7][lvl]
	p8.rectfill(117, 15, 119, 16, c)
	if lvl == 2:
		# Aufblitzen zur Kamera: kurze Strahlen nach links und rechts
		p8.line(114, 15, 116, 15, 10)
		p8.line(120, 15, 122, 15, 10)
		p8.pset(118, 13, 10)


func _draw_gulls() -> void:
	var gx := (int(frame / 2) + 10) % 160 - 20
	var wing := int(frame / 5) % 2
	_draw_actor("gull_%d" % wing, gx, 24 + (1 if int(frame / 10) % 2 == 0 else 0))
	var gx2 := 70 + int(frame / 3)
	_draw_actor("gull_%d" % (1 - wing), (gx2 + 20) % 160 - 20, 9)


func _draw_boats() -> void:
	# Boot A links vom Steg, Boot B am rechten Stegende; Bordwand etwa auf Planken-Höhe, Wasserlinie y 68-69
	var ya := 62 + (1 if int(frame / 20) % 2 == 1 else 0)
	var yb := 59 + (1 if int((frame + 10) / 22) % 2 == 1 else 0)
	# Masten als Linien (Schattenseite schwarz, vor dem Meer), Wimpel rot
	p8.line(33, ya - 15, 33, ya + 1, 0)
	p8.line(34, ya - 14, 34, ya + 1, 4)
	p8.line(35, ya - 14, 37, ya - 13, 8)
	p8.line(86, yb - 13, 86, yb + 4, 0)
	p8.line(87, yb - 12, 87, yb + 4, 4)
	_draw_actor("boat_a", 22, ya)
	_draw_actor("boat_b", 71, yb)
	# Festmacherleine von Boot A zum Poller auf dem Kai (Poller ist Teil der Karte, x 45..49)
	p8.line(43, ya + 2, 45, ya + 6, 6)
	p8.line(45, ya + 6, 46, 74, 6)


func _draw_smoke() -> void:
	for s in smoke:
		var age: int = s["age"]
		var c := 6 if age < 25 else (13 if age < 55 else 5)
		var x := int(round(s["x"] + sin(s["w"] + age * 0.08) * 1.2))
		var y := int(round(s["y"]))
		if age >= 62:
			p8.fillp(0b0101101001011010, true)
		# Wölkchen wachsen: 1 px, 2x2, dann Kreis r=2 (5x5 ohne Ecken)
		if age < 8:
			p8.pset(x, y, c)
		elif age < 30:
			p8.rectfill(x, y, x + 1, y + 1, c)
		else:
			p8.circfill(x, y, 2, c)
		p8.fillp()


func _draw_lantern() -> void:
	# Flackern: Stufe aus fester Folge, wechselt alle 3 Bilder
	var k := lantern_seq[int(frame / 3) % lantern_seq.size()]
	var lvl := 2 if k < 6 else (1 if k < 9 else 0)
	var r: int = [6, 9, 11][lvl]
	# Lichtfleck auf dem Kai unter der Laterne: Farben über die Tabelle LIGHT aufhellen, Rand im Schachbrett
	_light_ellipse(93, 79, r + 3, 3, 77)
	# Schein um das Glas (nur auf Pfahl und Arm, das Meer bleibt dunkel)
	_light_ellipse(93, 56, (r + 1) / 2, (r + 1) / 2, 0)
	if lvl == 0:
		p8.pal(10, 9)
		p8.pal(9, 4)
	elif lvl == 1:
		p8.pal(9, 10)
	_draw_actor("lantern", 91, 52)
	p8.pal()


func _light_ellipse(cx: int, cy: int, rx: int, ry: int, ymin: int) -> void:
	for y in range(max(cy - ry, ymin), cy + ry + 1):
		for x in range(cx - rx, cx + rx + 1):
			var u := float(x - cx) / (rx + 0.5)
			var v := float(y - cy) / (ry + 0.5)
			var d := u * u + v * v
			if d > 1.0:
				continue
			if d > 0.55 and (x + y) % 2 == 0:
				continue
			var c := p8.pget(x, y)
			if c == 1 and y < 77:
				continue
			p8.pset(x, y, LIGHT[c])


func _draw_actor(name: String, x: int, y: int, flip := false) -> void:
	var a: Dictionary = spr_info["actors"][name]
	var key := int(a["key"])
	if key != 0:
		p8.palt(0, false)
		p8.palt(key, true)
	p8.sspr(int(a["sx"]), int(a["sy"]), int(a["w"]), int(a["h"]), x, y, -1, -1, flip)
	p8.palt()


## Dachs: Laufbild aus der Bildnummer, Vorschub 2 px je Laufbild, danach Stand mit Blinzeln.
func badger_state() -> Array:
	var walk := ["contact", "pass", "contact2", "pass2"]
	var k := int(frame / WALK_HOLD)
	if k < WALK_STEPS:
		return [walk[k % 4], WALK_X0 + 2 * k]
	# Stand: Schalende flattert (alle 10 Bilder), Atemhub 1 px (15 Bilder unten, 15 oben), Füße fest.
	# Blinzeln liegt in Fenstern mit Schalstellung b und gesenktem Oberkörper (eigenes Sprite).
	var f := frame - WALK_STEPS * WALK_HOLD
	var pose := ("breath_" if f % BREATH_PERIOD >= BREATH_PERIOD / 2 else "stand_") \
		+ ("b" if int(f / SCARF_HOLD) % 2 == 1 else "a")
	for b in BLINK_AT:
		if f % BLINK_PERIOD >= b and f % BLINK_PERIOD < b + 4:
			pose = "blink"
	return [pose, WALK_X0 + 2 * WALK_STEPS]


func _draw_badger() -> void:
	var st := badger_state()
	_draw_actor("badger_" + st[0], st[1], 73)
	if probe:
		print("PROBE frame=%d pose=%s x=%d" % [frame, st[0], st[1]])


# --- Textbox ----------------------------------------------------------------------------------------------

func _draw_box() -> void:
	p8.rectfill(0, 91, 127, 127, 0)
	p8.rect(1, 92, 126, 126, 6)
	for c in [[1, 92], [126, 92], [1, 126], [126, 126]]:
		p8.pset(c[0], c[1], 0)
	p8.prnt(LOCATION, 5, 95, 9)
	if frame < MENU_START:
		_draw_story()
	else:
		_draw_menu()


func _draw_story() -> void:
	var n := _typed_chars(frame - TEXT_START)
	var y := 102
	var left := n
	for l in LINE:
		if left <= 0:
			break
		p8.prnt(l.substr(0, min(left, l.length())), 5, y, 7)
		left -= l.length()
		y += 6
	var total := 0
	for l in LINE:
		total += l.length()
	if n >= total and int(frame / 10) % 2 == 0:
		p8.prnt("▼", 117, 121, 9)


## Wie viele Zeichen nach f Bildern stehen: 1 Zeichen je Bild, nach . und , 6 Bilder Pause
func _typed_chars(f: int) -> int:
	if f < 0:
		return 0
	var s := "".join(LINE)
	var n := 0
	var budget := f
	while n < s.length() and budget > 0:
		budget -= 1
		n += 1
		if s[n - 1] in [".", ","]:
			budget -= 6
	return n


func _draw_menu() -> void:
	var sel := 0 if frame < CURSOR_MOVE else 1
	for i in CHOICES.size():
		var y := 102 + i * 6
		var c := 10 if i == sel else 6
		if i == sel:
			p8.prnt("▶", 5, y, 8)
		p8.prnt(CHOICES[i], 10, y, c)
	var n: int = clamp(int((frame - PARSER_START) / 2), 0, PARSER.length())
	var x := p8.prnt(PARSER.substr(0, n), 5, 120, 11)
	if int(frame / 8) % 2 == 0:
		p8.prnt("█", x, 120, 11)
