extends Node2D
## Flaches Vektordesign: Hafen von Lornholm.
## Szene und Figur kommen als Polygon2D-Knoten aus SVG (art/harbor.tscn, art/badger.tscn, erzeugt von
## scripts/svg2godot.py). Dieses Skript bewegt nur benannte Knoten (Drehpunkte aus dem SVG) und baut die
## Oberfläche aus StyleBoxFlat und der Schrift Montserrat.
## Benutzerargumente nach "--": --t0=<s> (Startzeit), --probe-no-badger, --probe-no-ui, --probe-no-caret, --probe-static, --probe-stats (Zeichenaufrufe in Bild 20).

const W := 1280.0
const H := 720.0
const GROUND := 574.0          # Fußlinie (Unterkante der Pfoten)
const PAW_Y := GROUND - 5.0    # Pfotenmitte; im SVG liegt die Pfotenunterkante bei +5
const LEG := 30.0              # Entwurfslänge Hüfte -> Pfotenmitte (wie LEG in scripts/build_svg.py)
const STEP := 30.0
const STEP_T := 7.0 / 30.0     # genau 7 Bilder je Schritt bei 30 fps (30 px je 0,2333 s = 128,6 px/s); 0,24 s ergab 7,2 Bilder und ungleiche Standphasen
const N_STEPS := 14
const F0 := 100.0              # erster Fußpunkt (Bild 0: Hüfte bei 85, vor der Haustür)
const GAP := 6.0               # Abstand der Pfoten im Stand
const LIFT := 6.0
const HIP_FAR := Vector2(-6, 0)
const HIP_NEAR := Vector2(8, 0)

const BEAM_P := 4.4            # Umlaufzeit des Drehfeuers
const SEL_AT := 3.95           # Auswahl springt auf "Das Paket ansehen"
const TYPE_AT := 2.0           # Beginn der getippten Eingabe
const LOOK_AT := 3.75          # Kopf dreht zum Paket

const CREAM := Color("#f6ecdc")
const CORAL := Color("#e8574b")
const INK := Color("#17183f")
const AMBER := Color("#ffd88f")

var t := 0.0
var t0 := 0.0
var probe_static := false
var no_caret := false   # --probe-no-caret: nur für scripts/check_ui_timing.py

var hb: Node2D       # harbor
var bd: Node2D       # badger
var n := {}          # Kurzzugriff auf Knoten
var puffs: Array[Polygon2D] = []
var choice_panels: Array[Panel] = []
var choice_labels: Array[Label] = []
var parser_label: Label
var caret: ColorRect
var cloud_x := {}
var star_phase := []

const PARSER := "> nimm paket"
const PUFF_N := 7
const PUFF_LIFE := 3.6


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a == "--probe-no-badger":
			$badger.visible = false
		elif a == "--probe-static":
			probe_static = true
		elif a == "--probe-no-caret":
			no_caret = true
	hb = $harbor
	bd = $badger
	for path in ["lighthouse/beam", "lighthouse/lamp_glow", "lantern", "lantern_glow", "boat_a", "boat_b",
			"cottage/window_glow", "cottage/smoke_origin", "hotspot", "sunpath", "shimmer", "stars", "gulls/gull0", "gulls/gull1"]:
		n[path] = hb.get_node(path)
	for path in ["body", "body/head", "body/head/eye", "body/arm_far", "body/arm_near", "body/scarf_tail",
			"leg_far", "leg_near", "paw_far", "paw_near", "shadow"]:
		n[path] = bd.get_node(path)
	for c in hb.get_node("clouds").get_children():
		cloud_x[c.name] = c.position.x
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261013
	for s in n["stars"].get_children():
		star_phase.append(rng.randf() * TAU)
	_make_puffs()
	_make_ui()
	if "--probe-no-ui" in OS.get_cmdline_user_args():
		$ui.visible = false
	_apply(t0)


func _process(delta: float) -> void:
	t += delta
	_apply(t0 + t)
	if "--probe-stats" in OS.get_cmdline_user_args() and Engine.get_frames_drawn() == 20:
		print("draw_calls=%d objects=%d primitives=%d" % [
			Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
			Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME),
			Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)])


# ------------------------------------------------------------------ Hilfen
func smooth(x: float) -> float:
	x = clampf(x, 0.0, 1.0)
	return x * x * (3.0 - 2.0 * x)


func gust(time: float) -> float:
	# Windstoß 4,3–5,7 s (sin²-Hüllkurve), danach periodisch alle 9 s
	var u := fposmod(time - 4.3, 9.0) / 1.4
	return sin(PI * u) ** 2 if u < 1.0 else 0.0


func flicker(time: float) -> float:
	return 0.5 * sin(time * 13.0) + 0.3 * sin(time * 23.7 + 1.3) + 0.2 * sin(time * 41.0 + 0.4)


# ------------------------------------------------------------------ Gang (umgekehrtes Pendel, feste Fußpunkte)
func foothold(j: int) -> float:
	return F0 + j * STEP


func gait(time: float) -> Dictionary:
	var walk_end := N_STEPS * STEP_T
	var v := STEP / STEP_T
	var d_close := STEP * 0.5 - GAP * 0.5
	var t_close := 2.0 * d_close / v
	var hip_x: float
	var feet := [0.0, 0.0]        # Pfotenmitte x für Bein 0 (nah) und 1 (fern)
	var lift := [0.0, 0.0]
	var stance: float
	var moving := 0.0
	var phase := 0.0
	if time < walk_end:
		var i := int(floor(maxf(time, 0.0) / STEP_T))
		var s := (maxf(time, 0.0) - i * STEP_T) / STEP_T
		stance = foothold(i)
		hip_x = stance - STEP * 0.5 + STEP * s
		feet[i % 2] = stance
		var sw := (i + 1) % 2
		feet[sw] = lerpf(foothold(i - 1), foothold(i + 1), smooth(s))
		lift[sw] = LIFT * sin(PI * s)
		moving = 1.0
		phase = PI * (i + s)
	else:
		var tc := time - walk_end
		var front := foothold(N_STEPS)
		stance = front
		var x_s := front - STEP * 0.5
		if tc < t_close:
			hip_x = x_s + v * tc - v * v / (4.0 * d_close) * tc * tc
			var s := tc / t_close
			feet[N_STEPS % 2] = front
			feet[(N_STEPS + 1) % 2] = lerpf(foothold(N_STEPS - 1), front - GAP, smooth(s))
			lift[(N_STEPS + 1) % 2] = LIFT * 0.6 * sin(PI * s)
			moving = 1.0 - s
			phase = PI * (N_STEPS + s * 0.5)
		else:
			hip_x = front - GAP * 0.5
			feet[N_STEPS % 2] = front
			feet[(N_STEPS + 1) % 2] = front - GAP
			phase = PI * (N_STEPS + 0.5)
	var dx := hip_x - stance
	var hip_h := sqrt(LEG * LEG - dx * dx)
	return {"hip": Vector2(hip_x, PAW_Y - hip_h), "feet": feet, "lift": lift, "moving": moving, "phase": phase,
			"stop_t": walk_end + t_close}


func _place_leg(leg: Node2D, hip: Vector2, paw: Vector2) -> void:
	var dv := paw - hip
	leg.position = hip
	leg.rotation = atan2(-dv.x, dv.y)
	leg.scale = Vector2(1.0, dv.length() / LEG)


func _badger(time: float) -> void:
	var g := gait(time)
	var hip: Vector2 = g.hip
	var mv: float = g.moving
	var ph: float = g.phase
	var since_stop := time - float(g.stop_t)
	var lean := 0.07 * mv
	if since_stop > 0.0:
		lean = -0.035 * exp(-since_stop * 4.0) * sin(since_stop * 11.0)
	var body: Node2D = n["body"]
	body.position = hip
	body.rotation = lean
	var breathe := 0.0 if mv > 0.0 else 0.012 * sin(TAU * maxf(since_stop, 0.0) / 2.4)
	body.scale = Vector2(1.0, 1.0 + breathe)
	var paws := [n["paw_near"], n["paw_far"]]
	var legs := [n["leg_near"], n["leg_far"]]
	var offs := [HIP_NEAR, HIP_FAR]
	for k in 2:
		var paw_pos := Vector2(g.feet[k], PAW_Y - g.lift[k])
		paws[k].position = paw_pos
		paws[k].rotation = -0.25 * (g.lift[k] / LIFT)      # Zehen heben sich im Schwung
		_place_leg(legs[k], hip + offs[k].rotated(lean), paw_pos)
	n["shadow"].position = Vector2(hip.x + 4.0, GROUND)
	# Arme gegen die Beine, Kopf nickt mit dem Schritt, Schal weht nach hinten
	n["body/arm_far"].rotation = -0.5 * sin(ph) * mv
	n["body/arm_near"].rotation = 0.07 * sin(ph) * mv
	var look := smooth((time - LOOK_AT) / 0.45)
	n["body/head"].rotation = 0.035 * sin(2.0 * ph) * mv + 0.16 * look - lean * 0.6
	var gs := gust(time)
	n["body/scarf_tail"].rotation = 0.55 * mv + 0.12 * sin(ph * 2.0) * mv + 0.08 + gs * (0.75 + 0.18 * sin(time * 17.0))
	# Blinzeln (3 Bilder) bei 1,4 s und 5,0 s
	var blink := (fposmod(time, 6.0) > 1.40 and fposmod(time, 6.0) < 1.50) or (fposmod(time, 6.0) > 5.00 and fposmod(time, 6.0) < 5.10)
	n["body/head/eye"].scale = Vector2(1.0, 0.15 if blink else 1.0)


# ------------------------------------------------------------------ Umgebung
func _ambient(time: float) -> void:
	# Drehfeuer: Seitenansicht = Projektion, Länge cos(θ); Blitz, wenn der Strahl zum Betrachter zeigt
	var th := TAU * (time / BEAM_P) + 2.2
	var beam: Node2D = n["lighthouse/beam"]
	beam.scale = Vector2(cos(th), 1.0 + 0.25 * maxf(0.0, sin(th)))
	var flash := pow(maxf(0.0, sin(th)), 10.0)
	n["lighthouse/lamp_glow"].scale = Vector2.ONE * (1.0 + 1.6 * flash)
	n["lighthouse/lamp_glow"].modulate.a = 0.75 + 0.25 * flash

	# Laterne: pendelt im Wind, Schein flackert
	var gs := gust(time)
	var lan: Node2D = n["lantern"]
	lan.rotation = 0.05 * sin(time * 2.1) + gs * (0.16 * sin(time * 7.3))
	n["lantern_glow"].position = lan.position + Vector2(0, 16).rotated(lan.rotation)
	var fl := flicker(time) * (0.35 + 0.65 * gs)
	n["lantern_glow"].modulate.a = clampf(0.82 + 0.18 * fl - 0.25 * gs * maxf(0.0, -fl), 0.3, 1.0)
	n["lantern_glow"].scale = Vector2.ONE * (1.0 + 0.07 * fl)
	n["cottage/window_glow"].modulate.a = 0.85 + 0.15 * flicker(time * 0.6 + 3.0)

	# Boote schaukeln
	var ba: Node2D = n["boat_a"]
	ba.rotation = 0.035 * sin(TAU * time / 3.1)
	ba.position.y = 534.0 + 1.5 * sin(TAU * time / 3.1 + 1.2)
	var bb: Node2D = n["boat_b"]
	bb.rotation = 0.022 * sin(TAU * time / 3.7 + 1.0)
	bb.position.y = 546.0 + 1.2 * sin(TAU * time / 3.7 + 2.0)

	# Wasser: Sonnenpfad atmet, Glanzstriche blinken
	var k := 0
	for sp in n["sunpath"].get_children():
		sp.scale = Vector2(1.0 + 0.28 * sin(TAU * time / 1.7 + k * 1.1), 1.0)
		sp.position.x = 3.0 * sin(TAU * time / 2.3 + k * 0.7)
		k += 1
	k = 0
	for sh in n["shimmer"].get_children():
		var u := sin(TAU * time / 2.6 + k * 2.39)
		sh.modulate.a = clampf(0.15 + 0.85 * u, 0.0, 1.0)
		sh.scale = Vector2(0.7 + 0.3 * maxf(u, 0.0), 1.0)
		k += 1
	k = 0
	for s in n["stars"].get_children():
		s.modulate.a = 0.55 + 0.45 * sin(TAU * time / 1.9 + star_phase[k])
		k += 1

	# Wolken ziehen langsam nach links; Umbruch außerhalb des Bildes
	for c in hb.get_node("clouds").get_children():
		var span := W + 700.0
		var x0: float = cloud_x[c.name]
		var speed := 5.0 if c.position.y < 280.0 else 8.0
		c.position.x = fposmod(x0 - speed * time + 350.0, span) - 350.0

	# Möwen: gleiten nach links, Flügelschlag über scale.y
	var gi := 0
	for gpath in ["gulls/gull0", "gulls/gull1"]:
		var gull: Node2D = n[gpath]
		var span2 := W + 400.0
		var base_x := 420.0 + gi * 50.0
		gull.position.x = fposmod(base_x - 26.0 * time - 0.0 + 200.0, span2) - 200.0
		gull.position.y = (196.0 - gi * 20.0) + 4.0 * sin(TAU * time / 2.8 + gi)
		var flap := cos(TAU * time * (1.9 + 0.3 * gi) + gi)
		for wing in [gull.get_node("gull%d_wl" % gi), gull.get_node("gull%d_wr" % gi)]:
			wing.scale = Vector2(1.0, 0.25 + 0.75 * flap)
		gi += 1

	# Rauch: Puffs steigen, wachsen, werden blasser; der Wind weht wie bei Schal, Wolken und Möwen nach links
	var origin: Vector2 = n["cottage/smoke_origin"].global_position
	for i in PUFF_N:
		var age := fposmod(time + i * PUFF_LIFE / PUFF_N, PUFF_LIFE)
		var u := age / PUFF_LIFE
		var p: Polygon2D = puffs[i]
		p.position = origin + Vector2(-10.0 * u - 26.0 * u * u + 3.0 * sin(age * 2.0 + i) - 30.0 * gs * u, -78.0 * u - 6.0)
		p.scale = Vector2.ONE * (0.45 + 1.1 * u)
		p.modulate.a = 0.85 * smooth(u / 0.12) * (1.0 - u)

	# Hinweisring am Paket: läuft nach außen; nach der Auswahl heller
	var hs: Node2D = n["hotspot"]
	var hu := fposmod(time, 1.5) / 1.5
	hs.scale = Vector2.ONE * (0.55 + 0.75 * hu)
	var sel := smooth((time - SEL_AT) / 0.25)
	hs.modulate.a = (1.0 - hu) * (0.45 + 0.55 * sel)


func _make_puffs() -> void:
	var pts := PackedVector2Array()
	for i in 28:
		var a := TAU * i / 28.0
		pts.append(Vector2(cos(a), sin(a)) * 11.0)
	var smoke: Node2D = hb.get_node("cottage")
	for i in PUFF_N:
		var p := Polygon2D.new()
		p.polygon = pts
		p.color = Color("#d9b8cf")
		p.name = "puff%d" % i
		smoke.add_child(p)
		smoke.move_child(p, 0)      # hinter dem Häuschen (Schornstein deckt den Ansatz)
		puffs.append(p)


# ------------------------------------------------------------------ Oberfläche
func _font(weight: int, spacing := 0) -> FontVariation:
	var base: FontFile = load("res://fonts/Montserrat-wght.ttf")
	var fv := FontVariation.new()
	fv.base_font = base
	fv.variation_opentype = {TextServerManager.get_primary_interface().name_to_tag("wght"): weight}
	fv.spacing_glyph = spacing
	return fv


func _flat(bg: Color, radius: int) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.set_corner_radius_all(radius)
	sb.anti_aliasing = true
	sb.corner_detail = 12
	return sb


func _label(parent: Control, text: String, font: Font, size: int, col: Color, pos: Vector2) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	l.position = pos
	parent.add_child(l)
	return l


func _make_ui() -> void:
	var layer := CanvasLayer.new()
	layer.name = "ui"
	add_child(layer)
	# Ortsschild oben links
	var chip := Panel.new()
	chip.position = Vector2(28, 24)
	chip.size = Vector2(286, 40)
	chip.add_theme_stylebox_override("panel", _flat(Color(0.09, 0.08, 0.22, 0.78), 20))
	layer.add_child(chip)
	var dot := Panel.new()
	dot.position = Vector2(14, 13)
	dot.size = Vector2(14, 14)
	dot.add_theme_stylebox_override("panel", _flat(AMBER, 7))
	chip.add_child(dot)
	_label(chip, "HAFEN VON LORNHOLM", _font(600, 2), 15, CREAM, Vector2(38, 10))

	# Karte unten
	var card := Panel.new()
	card.position = Vector2(28, 602)
	card.size = Vector2(1224, 100)
	card.add_theme_stylebox_override("panel", _flat(Color(0.075, 0.07, 0.19, 0.88), 22))
	layer.add_child(card)
	_label(card, "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich.", _font(500), 20, CREAM, Vector2(26, 14))
	var x := 26.0
	var fb := _font(600)
	for i in 3:
		var txt: String = ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"][i]
		var w := fb.get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x + 40.0
		var pill := Panel.new()
		pill.position = Vector2(x, 52)
		pill.size = Vector2(w, 34)
		pill.add_theme_stylebox_override("panel", _flat(Color(1, 1, 1, 0.09), 17))
		card.add_child(pill)
		var l := _label(pill, txt, fb, 16, Color(CREAM, 0.88), Vector2(20, 7))
		choice_panels.append(pill)
		choice_labels.append(l)
		x += w + 12.0
	var field := Panel.new()
	field.position = Vector2(1224 - 26 - 230, 52)
	field.size = Vector2(230, 34)
	field.add_theme_stylebox_override("panel", _flat(Color(0, 0, 0, 0.28), 17))
	card.add_child(field)
	parser_label = _label(field, "", _font(500), 16, AMBER, Vector2(18, 7))
	caret = ColorRect.new()
	caret.color = AMBER
	caret.size = Vector2(2, 18)
	caret.position = Vector2(18, 8)
	field.add_child(caret)


func _ui(time: float) -> void:
	# getippte Eingabe: ein Zeichen je 3 Bilder (0,1 s), über die Bildnummer, damit die Haltezeiten gleich sind
	var frames := int(round((time - TYPE_AT) * 30.0))
	var shown := clampi(1 + frames / 3, 1, PARSER.length()) if frames >= 0 else 1
	parser_label.text = PARSER.substr(0, shown)
	var fnt: Font = parser_label.get_theme_font("font")
	caret.position.x = 18.0 + fnt.get_string_size(parser_label.text, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x + 3.0
	caret.visible = (fposmod(time, 1.0) < 0.6 or (frames >= 0 and shown < PARSER.length())) and not no_caret
	var sel := smooth((time - SEL_AT) / 0.25)
	for i in 3:
		var sb: StyleBoxFlat = choice_panels[i].get_theme_stylebox("panel")
		if i == 1:
			sb.bg_color = Color(1, 1, 1, 0.09).lerp(CORAL, sel)
			choice_labels[i].add_theme_color_override("font_color", Color(CREAM, 0.88).lerp(Color.WHITE, sel))
		elif i == 0:
			sb.bg_color = Color(1, 1, 1, 0.09)


func _apply(time: float) -> void:
	if probe_static:
		time = 4.6
	_badger(time)
	_ambient(time)
	_ui(time)
