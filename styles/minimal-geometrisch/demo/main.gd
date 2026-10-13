extends Node2D
## Minimalistisch-geometrisch: der Hafen von Lornholm aus nur drei Grundformen
## (Rechteck, Kreis, Linie; dazu Kreisabschnitte als Teil eines Kreises) in acht flachen Farben.
## Keine Bilder, keine Texturen, keine Verläufe, keine Transparenz in der Szene.
## Alles wird jedes Bild in _draw() neu gezeichnet; die Zeit ist die Summe der delta-Werte
## (mit --fixed-fps 30 genau 1/30 s je Bild), Zufall nur aus einem RNG mit fester Saat.
##
## Prüfschalter (nach "--"):
##   --probe-no-badger      zeichnet alles außer dem Dachs (Differenzmessung der Füße)
##   --probe-construction   zeichnet zusätzlich die Umrisse jeder Grundform (Konstruktionsansicht)
##   --probe-count          gibt bei t = 4,4 s die Zahl der Grundformen je Art aus
##   --probe-timing         misst die CPU-Zeit von _draw() und gibt am Ende Mittel und Maximum aus

const W := 1280.0
const H := 720.0

# Palette: acht Farben, jede mit fester Bedeutung (siehe style.json).
const NIGHT := Color("#191a32")   # Dunkelstes: Fell, Augenband, Linien, Fugen, Dachabschlüsse, Oberfläche
const INDIGO := Color("#2b2d5c")  # oberer Himmel, Meer, Kai-Front, Schatten
const VIOLET := Color("#4a4381")  # Himmelsband, Fels, Inseln, Kai-Fläche, hinteres Boot (Ferne)
const ROSE := Color("#a35d80")    # Horizonthimmel, Holz, Mauerwerk
const AMBER := Color("#f5a54a")   # Licht: Horizont, Lampen, Fenster, das Paket
const CREAM := Color("#f2e8d4")   # Leuchtturm, Mond, Sterne, Gesicht, Text
const RED := Color("#e4473b")     # Akzent: Schal, gewählte Handlung; einzige Motivfarbe: Leuchtturmband
const GREEN := Color("#2f6153")   # Mütze und Weste, Gras

const HORIZON := 360.0
const QUAY_TOP := 552.0
const GROUND := 578.0       # Fußlinie des Dachses
const QUAY_FRONT := 586.0
const UI_TOP := 598.0

# Gang des Dachses (Seitenansicht, nach rechts). Standfuß steht fest, die Hüfte schwingt
# als umgekehrtes Pendel darüber: Hüfthöhe = sqrt(LEG² - dx²) über dem Standfuß.
const B_START := 280.0      # Hüfte bei t = 0 (Tasche liegt dann schon rechts der Rose-Hauswand, x < 240)
const STEP := 34.0          # Schrittlänge (px)
const STEP_T := 0.34        # Zeit je Schritt (s) -> 100 px/s
const N_STEPS := 8
const LEG := 36.0           # Hüfte bis Knöchel
const FOOT_R := 5.0
const GAP := 4.0            # Abstand der Füße im Stand
const LIFT := 8.0

# Lichtpuls des Leuchtturms
const BEAM_P := 3.2
const FLASH_AT := 1.7
const LAMP := Vector2(1150, 147)
const LANTERN := Vector2(676, 446)
const PARCEL := Vector2(640, 574)   # Mitte unten
const CHIMNEY := Vector2(160, 310)

var t := 0.0
var no_badger := false
var construction := false
var count_shapes := false
var counted := false
var counts := {}
var timing := false
var draw_us: Array[int] = []
var aa := false      # Kantenglättung je Aufruf: nur im Compatibility-Renderer, der kein 2D-MSAA anwendet
const GUIDE := Color(0.25, 1.0, 0.85)   # nur Konstruktionsansicht, nicht Teil der Palette
var stars: Array[Vector4] = []      # x, y, Radius, Funkelphase (<0: funkelt nicht)
var glints: Array[Dictionary] = []
var f_text: FontVariation
var f_caps: FontVariation
var f_choice: FontVariation
var f_mono: FontVariation


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	no_badger = "--probe-no-badger" in args
	construction = "--probe-construction" in args
	count_shapes = "--probe-count" in args
	aa = RenderingServer.get_current_rendering_method() == "gl_compatibility"
	timing = "--probe-timing" in args
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261011
	while stars.size() < 16:
		var p := Vector2(rng.randf_range(10, W - 10), rng.randf_range(10, 200))
		if p.distance_to(Vector2(430, 96)) < 52 or (p.x > 1040 and p.y > 100):
			continue
		var r: float = [1.3, 1.3, 1.7, 2.2][rng.randi_range(0, 3)]
		var tw := rng.randf_range(0, TAU) if rng.randf() < 0.22 else -1.0
		stars.append(Vector4(p.x, p.y, r, tw))
	# Wasserglitzern: kurze waagrechte Linien in wenigen Reihen, die auf- und abtauchen
	var y := HORIZON + 6.0
	var row := 0
	while y < QUAY_TOP - 4:
		var depth := (y - HORIZON) / (QUAY_TOP - HORIZON)
		var n := 4 + row % 2
		for i in n:
			var c := ROSE
			if depth > 0.22:
				c = VIOLET
			elif rng.randf() < 0.35:
				c = AMBER
			glints.append({
				"x": rng.randf_range(0, W), "y": y, "len": rng.randf_range(14, 54) * (1.0 + depth),
				"v": rng.randf_range(3, 9) * (1 if row % 2 == 0 else -1), "f": rng.randf_range(0.8, 1.8),
				"ph": rng.randf_range(0, TAU), "c": c, "w": 2.0 if depth < 0.4 else 3.0,
			})
		y += 16.0 + depth * 36.0
		row += 1
	var base: FontFile = load("res://fonts/Jost-wght.ttf")
	f_text = _font(base, 430, 0)
	f_caps = _font(base, 600, 3)
	f_choice = _font(base, 480, 0)
	f_mono = _font(base, 500, 1)


func _font(base: FontFile, weight: int, spacing: int) -> FontVariation:
	var f := FontVariation.new()
	f.base_font = base
	f.variation_opentype = {"wght": weight}
	f.spacing_glyph = spacing
	return f


func _process(delta: float) -> void:
	t += delta
	queue_redraw()


# ---------------------------------------------------------------------------
# Grundformen. Alle Formen entstehen aus diesen Aufrufen (nur der Text kommt über draw_string).
# ---------------------------------------------------------------------------
func _count(kind: String) -> void:
	counts[kind] = int(counts.get(kind, 0)) + 1


func R(x: float, y: float, w: float, h: float, c: Color) -> void:
	_count("Rechteck")
	draw_rect(Rect2(x, y, w, h), c)
	if construction:
		draw_rect(Rect2(x, y, w, h), GUIDE, false, 1.0)


func frame_rect(x: float, y: float, w: float, h: float, c: Color, w_line: float) -> void:
	_count("Rechteck (Rahmen)")
	draw_rect(Rect2(x, y, w, h), c, false, w_line)


func C(p: Vector2, r: float, c: Color) -> void:
	_count("Kreis")
	draw_circle(p, r, c, true, -1.0, aa)
	if construction:
		draw_arc(p, r, 0.0, TAU, 48, GUIDE, 1.0)


func ring(p: Vector2, r: float, w: float, c: Color) -> void:
	_count("Kreis (Ring)")
	draw_arc(p, r, 0.0, TAU, 96, c, w, aa)


func arc(p: Vector2, r: float, a0: float, a1: float, w: float, c: Color) -> void:
	_count("Kreisbogen")
	draw_arc(p, r, a0, a1, 24, c, w, aa)


func L(a: Vector2, b: Vector2, c: Color, w := 2.0) -> void:
	_count("Linie")
	draw_line(a, b, c, w, aa)
	if construction and w >= 3.0:
		draw_line(a, b, GUIDE, 1.0)


func cap(a: Vector2, b: Vector2, r: float, c: Color) -> void:
	# Linie mit runden Enden (Gliedmaßen, Wolken, Schal): eine Linie und zwei Kreise
	L(a, b, c, r * 2.0)
	C(a, r, c)
	C(b, r, c)


func rrect(x: float, y: float, w: float, h: float, r: float, c: Color) -> void:
	R(x + r, y, w - 2 * r, h, c)
	R(x, y + r, w, h - 2 * r, c)
	for p in [Vector2(x + r, y + r), Vector2(x + w - r, y + r), Vector2(x + r, y + h - r), Vector2(x + w - r, y + h - r)]:
		C(p, r, c)


func segment(cx: float, chord_y: float, chord: float, sag: float, c: Color, up := false) -> void:
	# Kreisabschnitt unter (Bootsrumpf) oder über einer Sehne (Insel, Kuppel)
	var rad := (chord * chord / 4.0 + sag * sag) / (2.0 * sag)
	var s := -1.0 if up else 1.0
	var center := Vector2(cx, chord_y + s * (sag - rad))
	var alpha := asin(clampf(chord / 2.0 / rad, -1.0, 1.0))
	var pts := PackedVector2Array()
	for i in 49:
		var a := PI / 2.0 - alpha + 2.0 * alpha * i / 48.0
		pts.append(center + Vector2(cos(a), s * sin(a)) * rad)
	_count("Kreisabschnitt")
	draw_colored_polygon(pts, c)
	if aa:
		draw_polyline(pts, c, 1.0, true)
	if construction:
		pts.append(pts[0])
		draw_polyline(pts, GUIDE, 1.0)


func ease_io(x: float) -> float:
	x = clampf(x, 0.0, 1.0)
	return x * x * (3.0 - 2.0 * x)


func gust(time: float) -> float:
	# Windstoß zwischen 4,7 und 5,9 s (0..1): Schal hebt sich, Laterne flackert stärker, Windlinien
	return pow(sin(PI * clampf((time - 4.7) / 1.2, 0.0, 1.0)), 2.0)


func flicker(time: float) -> float:
	# deterministisches Flackern in [-1, 1]
	return 0.5 * sin(time * 13.0) + 0.3 * sin(time * 23.7 + 1.3) + 0.2 * sin(time * 41.3 + 2.1)


# ---------------------------------------------------------------------------
func _draw() -> void:
	var t0 := Time.get_ticks_usec()
	counts = {}
	_sky()
	_beam()
	_sea()
	_headland()
	_lighthouse()
	_boats_and_jetty()
	_gulls()
	_cottage()
	_quay()
	_props()
	_wind()
	if not no_badger:
		_badger()
	_ui()
	if count_shapes and not counted and t >= 4.4:
		counted = true
		var total := 0
		for k in counts:
			total += int(counts[k])
		print("GRUNDFORMEN t=%.2f gesamt=%d %s" % [t, total, JSON.stringify(counts)])
	if timing:
		draw_us.append(Time.get_ticks_usec() - t0)


func _exit_tree() -> void:
	if timing and draw_us.size() > 0:
		var total := 0
		for v in draw_us:
			total += v
		print("DRAW_US mittel=%d max=%d bilder=%d" % [total / draw_us.size(), draw_us.max(), draw_us.size()])


func _sky() -> void:
	R(0, 0, W, 196, INDIGO)
	R(0, 196, W, 92, VIOLET)
	R(0, 288, W, 52, ROSE)
	R(0, 340, W, HORIZON - 340, AMBER)
	for s in stars:
		var r: float = s.z
		if s.w >= 0.0:
			var k := 0.5 + 0.5 * sin(t * 2.6 + s.w)
			r = lerpf(0.6, 2.6, k * k)
			if k > 0.8:
				var arm := 3.0 + 5.0 * (k - 0.8) / 0.2
				L(Vector2(s.x - arm, s.y), Vector2(s.x + arm, s.y), CREAM, 1.0)
				L(Vector2(s.x, s.y - arm), Vector2(s.x, s.y + arm), CREAM, 1.0)
		C(Vector2(s.x, s.y), r, CREAM)
	# Mondsichel: zwei Kreise
	C(Vector2(430, 96), 27, CREAM)
	C(Vector2(441, 89), 24, INDIGO)
	# tiefe Wolken: lange Kapseln, die langsam ziehen
	var clouds := [
		[120.0, 232.0, 210.0, 7.0, ROSE, 6.0], [470.0, 262.0, 330.0, 6.0, ROSE, 4.0],
		[860.0, 222.0, 180.0, 6.0, ROSE, 7.0], [260.0, 312.0, 260.0, 5.0, VIOLET, 5.0],
		[700.0, 322.0, 200.0, 5.0, VIOLET, 3.5], [40.0, 176.0, 160.0, 5.0, VIOLET, 5.0],
	]
	for cl in clouds:
		var x: float = fposmod(cl[0] + cl[5] * t + 300.0, W + 600.0) - 300.0
		cap(Vector2(x, cl[1]), Vector2(x + cl[2], cl[1]), cl[3], cl[4])
	# ferne Inseln auf dem Horizont
	segment(520, HORIZON, 190, 15, VIOLET, true)
	segment(640, HORIZON, 80, 8, VIOLET, true)
	segment(34, HORIZON, 160, 22, VIOLET, true)


func _beam() -> void:
	# Drehfeuer von der Seite: der Strahl wird als Linienbündel kürzer und länger und wechselt
	# die Seite; zeigt er zum Betrachter, blitzt die Lampe und ein Ring läuft nach außen.
	var th := TAU * (t - FLASH_AT) / BEAM_P + PI / 2.0
	var c := cos(th)
	var reach := 760.0 * c
	if absf(reach) > 4.0:
		var dir := Vector2(-1, 0.035)
		var tip := LAMP + dir * reach
		L(LAMP, tip, AMBER, 4.0)
		for k in [[-8.0, 0.74, 3.0], [8.0, 0.74, 3.0], [-16.0, 0.42, 2.0], [16.0, 0.42, 2.0]]:
			var o := LAMP + Vector2(0, k[0])
			L(o, o + dir * reach * k[1], AMBER, k[2])
	# Ringe, die nach jedem Blitz nach außen laufen; vor dem Turm gezeichnet, damit der Schaft sie verdeckt.
	# der Zyklus läuft auch vor t = 0 weiter: bei t = 0 läuft noch der Ring des Blitzes von -1,5 s aus
	var age := fposmod(t - FLASH_AT, BEAM_P)
	var life := 1.6
	if age < life:
		var u := age / life
		ring(LAMP, 22.0 + 104.0 * (1.0 - pow(1.0 - u, 2.0)), maxf(0.6, 3.0 * (1.0 - u)), AMBER)


func _headland() -> void:
	# Felsnase aus übereinanderliegenden abgerundeten Blöcken; das Abendlicht von links
	# setzt auf jeden Block eine kurze Kante (Rose), oben Gras
	var blocks := [
		[1074.0, 300.0, 260.0, 60.0, 20.0], [1038.0, 336.0, 290.0, 80.0, 24.0],
		[1000.0, 392.0, 320.0, 96.0, 28.0], [956.0, 452.0, 360.0, 130.0, 30.0],
		[924.0, 506.0, 70.0, 60.0, 22.0],
	]
	for b in blocks:
		rrect(b[0], b[1], b[2], b[3], b[4], VIOLET)
	# Lichtkante als Viertelkreis auf der oberen linken Ecke jedes Blocks
	for b in blocks:
		arc(Vector2(b[0] + b[4], b[1] + b[4]), b[4] - 1.5, PI * 1.02, PI * 1.5, 3.0, ROSE)
	R(1094, 296, 200, 5, GREEN)


func _lighthouse() -> void:
	var x := LAMP.x
	R(x - 22, 166, 44, 142, CREAM)
	R(x - 22, 218, 44, 24, RED)
	R(x - 4, 186, 8, 12, NIGHT)
	R(x - 4, 262, 8, 12, NIGHT)
	R(x - 10, 282, 20, 26, NIGHT)
	R(x - 32, 158, 64, 8, NIGHT)
	L(Vector2(x - 30, 152), Vector2(x + 30, 152), NIGHT, 2.0)
	R(x - 16, 132, 32, 26, AMBER)
	segment(x, 132, 40, 16, NIGHT, true)
	L(Vector2(x, 116), Vector2(x, 104), NIGHT, 2.0)
	# Lampe: Blitz, wenn der Strahl zum Betrachter zeigt
	var th := TAU * (t - FLASH_AT) / BEAM_P + PI / 2.0
	var face := maxf(0.0, sin(th))
	var flash := pow(face, 10.0)
	C(LAMP, 7.0 + 13.0 * flash, CREAM)
	L(Vector2(x - 8, 132), Vector2(x - 8, 158), NIGHT, 2.0)
	L(Vector2(x + 8, 132), Vector2(x + 8, 158), NIGHT, 2.0)
	if flash > 0.3:
		C(LAMP, 7.0 + 13.0 * flash, CREAM)


func _sea() -> void:
	R(0, HORIZON, W, QUAY_TOP - HORIZON, INDIGO)
	# Spiegelung der Mondsichel: senkrechte Reihe kurzer Linien
	for i in 3:
		var y := HORIZON + 10.0 + i * 16.0
		var w := (26.0 - i * 6.0) * (0.75 + 0.25 * sin(t * 3.1 + i * 1.7))
		L(Vector2(430 - w / 2, y), Vector2(430 + w / 2, y), CREAM if i < 2 else VIOLET, 2.0)
	for g in glints:
		var gx: float = g.x
		var k := sin(t * float(g.f) + float(g.ph))
		var vis := clampf(k * 1.6 + 0.4, 0.0, 1.0)
		if vis <= 0.05:
			continue
		var x: float = fposmod(gx + float(g.v) * t, W + 120.0) - 60.0
		var ln: float = float(g.len) * vis
		L(Vector2(x - ln / 2, g.y), Vector2(x + ln / 2, g.y), g.c, g.w)


func _boat(cx: float, gun_y: float, chord: float, depth: float, mast_h: float, rock: float, cabin: bool, hull := ROSE) -> void:
	# Rumpf = Rechteck (Bordwand) + Kreisabschnitt (Kiel); dreht sich um die Wasserlinie
	var pivot := Vector2(cx, gun_y + depth * 0.7)
	draw_set_transform(pivot, deg_to_rad(rock), Vector2.ONE)
	var o := -pivot
	var mx := cx - chord * 0.12
	var top := Vector2(mx, gun_y - mast_h) + o
	L(Vector2(mx, gun_y) + o, top, NIGHT, 3.0)
	if cabin:
		var kx := cx + chord * 0.06
		R(kx + o.x, gun_y - 30 + o.y, 44, 30, CREAM)
		R(kx + 8 + o.x, gun_y - 22 + o.y, 12, 10, NIGHT)
		R(kx + 26 + o.x, gun_y - 22 + o.y, 10, 10, NIGHT)
		R(kx - 4 + o.x, gun_y - 35 + o.y, 52, 6, NIGHT)   # Kajütdach: Night, Rot bleibt Kurier und Auswahl
	var side := depth * 0.45
	R(cx - chord / 2 + o.x, gun_y + o.y, chord, side, hull)
	segment(cx + o.x, gun_y + side + o.y - 0.5, chord, depth - side, hull)
	R(cx - chord / 2 + o.x, gun_y + o.y, chord, 4, CREAM)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	# Wasserlinie: zwei kurze Linien, gegenläufig zum Schaukeln
	var wl := gun_y + depth * 0.8
	var dx := sin(t * 1.4 + cx) * 6.0
	L(Vector2(cx - chord * 0.58 + dx, wl), Vector2(cx - chord * 0.28 + dx, wl), VIOLET, 3.0)
	L(Vector2(cx + chord * 0.22 - dx, wl + 4), Vector2(cx + chord * 0.54 - dx, wl + 4), VIOLET, 3.0)


func _boats_and_jetty() -> void:
	# kleines Boot hinter dem Steg: Violett (Ferne), sonst verschmilzt sein Kiel mit der Rose-Planke davor
	_boat(800, 480, 100, 22, 80, 2.4 * sin(t * 1.25 + 0.7), false, VIOLET)
	# Steg: Planke auf Pfählen, vom Kai zur Felsnase
	for x in [736, 784, 832, 880, 928]:
		R(x, 506, 7, 46, NIGHT)
	R(726, 500, 240, 7, ROSE)
	# Fischerboot vor dem Steg
	_boat(864, 508, 168, 34, 112, 1.8 * sin(t * 1.05), true)


func _gulls() -> void:
	for gdef in [[1010.0, 110.0, -46.0, 0.0], [1120.0, 150.0, -38.0, 1.9]]:
		var x: float = gdef[0] + gdef[2] * t
		var y: float = gdef[1] + 6.0 * sin(t * 1.3 + gdef[3])
		var flap := sin(t * 7.0 + gdef[3])
		var p := Vector2(x, y)
		var tip_y := -9.0 * flap - 2.0
		L(p, p + Vector2(-17, tip_y), CREAM, 3.0)
		L(p, p + Vector2(17, tip_y), CREAM, 3.0)
		C(p, 2.0, CREAM)


func _cottage() -> void:
	# Schornsteinrauch als Ringe, die steigen, wachsen und vom Wind versetzt werden
	for i in 5:
		var a := fposmod(t / 2.6 + i / 5.0, 1.0)
		var p := CHIMNEY + Vector2(10 + (46.0 + 40.0 * gust(t)) * a * a + 6.0 * sin(a * 7.0 + i), -8.0 - 120.0 * a)
		var r := 4.0 + 13.0 * a
		var w := 2.6 * (1.0 - a) + 0.6
		if a > 0.04:
			ring(p, r, w, CREAM)
	# Schornstein steht ganz auf der obersten Stufe (x 90–180)
	R(150, 300, 22, 42, NIGHT)
	R(144, 296, 34, 6, NIGHT)
	# Treppengiebel aus gestaffelten Rechtecken. Drei Stufen: Keine Rose-Fläche darf vor dem
	# Rose-Himmelsband (y 288–340) liegen, sonst verschwindet sie; der Dachabschluss (Night)
	# überdeckt die Bandgrenze bei y = 340.
	R(30, 404, 210, 150, ROSE)
	R(50, 382, 170, 22, ROSE)
	R(70, 360, 130, 22, ROSE)
	R(90, 338, 90, 22, ROSE)
	for s in [[30.0, 404.0, 20.0], [50.0, 382.0, 20.0], [70.0, 360.0, 20.0]]:
		R(s[0], s[1], s[2], 4, NIGHT)
		R(240.0 - (s[0] - 30.0) - s[2], s[1], s[2], 4, NIGHT)
	R(90, 338, 90, 4, NIGHT)
	C(Vector2(135, 360), 10, AMBER)
	L(Vector2(125, 360), Vector2(145, 360), NIGHT, 2.0)
	R(160, 462, 40, 92, NIGHT)
	C(Vector2(168, 508), 2.5, AMBER)
	R(52, 442, 70, 54, AMBER)
	L(Vector2(87, 442), Vector2(87, 496), NIGHT, 3.0)
	L(Vector2(52, 469), Vector2(122, 469), NIGHT, 3.0)
	R(46, 496, 82, 5, NIGHT)


func _quay() -> void:
	R(0, QUAY_TOP, W, QUAY_FRONT - QUAY_TOP, VIOLET)
	R(0, QUAY_TOP, W, 3, ROSE)
	for x in range(-20, int(W), 72):
		L(Vector2(x, QUAY_TOP + 12), Vector2(x, QUAY_TOP + 20), INDIGO, 2.0)
		L(Vector2(x + 36, QUAY_TOP + 24), Vector2(x + 36, QUAY_TOP + 32), INDIGO, 2.0)
	R(0, QUAY_FRONT, W, UI_TOP - QUAY_FRONT, INDIGO)
	for x in range(30, int(W), 96):
		L(Vector2(x, QUAY_FRONT), Vector2(x, UI_TOP), NIGHT, 2.0)
	# Poller und Festmacher zum Fischerboot
	R(738, 540, 12, 18, NIGHT)
	R(734, 536, 20, 5, NIGHT)
	L(Vector2(744, 540), Vector2(766, 534), NIGHT, 2.0)
	L(Vector2(766, 534), Vector2(784, 524), NIGHT, 2.0)


func _wind() -> void:
	# drei Windlinien ziehen mit dem Windstoß von links nach rechts durchs Bild
	for k in [[4.70, 452.0, 150.0], [4.86, 498.0, 110.0], [5.02, 418.0, 90.0]]:
		var u: float = (t - k[0]) / 0.9
		if u <= 0.0 or u >= 1.0:
			continue
		var head := -200.0 + 1700.0 * u
		var ln: float = k[2] * sin(PI * u) * 1.6
		var y: float = k[1] + 4.0 * sin(u * 9.0)
		L(Vector2(head - ln, y), Vector2(head, y), CREAM, 2.0)


func _shadow(x0: float, x1: float, y: float) -> void:
	cap(Vector2(x0, y), Vector2(x1, y), 3.0, INDIGO)


func _props() -> void:
	# Fässer
	for b in [[40.0, 534.0], [76.0, 538.0]]:
		_shadow(b[0] - 2, b[0] + 32, b[1] + 41)
		R(b[0], b[1], 30, 40, NIGHT)
		L(Vector2(b[0], b[1] + 9), Vector2(b[0] + 30, b[1] + 9), ROSE, 3.0)
		L(Vector2(b[0], b[1] + 31), Vector2(b[0] + 30, b[1] + 31), ROSE, 3.0)
	# Kisten
	_shadow(1046, 1150, 574)
	for k in [[1050.0, 534.0, 40.0], [1092.0, 534.0, 40.0], [1070.0, 494.0, 40.0], [1134.0, 548.0, 26.0]]:
		R(k[0], k[1], k[2], k[2], ROSE)
		frame_rect(k[0] + 1.5, k[1] + 1.5, k[2] - 3, k[2] - 3, NIGHT, 3.0)
	# Tauwerk: konzentrische Kreise
	_shadow(984, 1028, 574)
	for r in [18.0, 13.0, 8.0, 3.5]:
		ring(Vector2(1006, 554), r, 3.0, NIGHT if r != 13.0 else ROSE)
	# Laterne am Pfahl
	var n := flicker(t) * (1.0 + 0.9 * gust(t))
	_shadow(699, 717, 574)
	# Ringe zuerst: Pfahl und Ausleger liegen davor
	ring(LANTERN, 34.0 + 4.0 * n, 1.5 + 0.8 * n, AMBER)
	ring(LANTERN, 22.0 + 2.5 * n, 3.0, AMBER)
	L(Vector2(708, 572), Vector2(708, 420), NIGHT, 7.0)
	L(Vector2(711, 424), Vector2(670, 424), NIGHT, 4.0)
	L(Vector2(676, 424), Vector2(676, 434), NIGHT, 2.0)
	R(667, 434, 18, 26, NIGHT)
	R(664, 432, 24, 4, NIGHT)
	var fh := 13.0 + 4.0 * n
	R(671, 456 - fh, 10, fh, AMBER)
	# Paket auf dem Kai mit Zeigering (Bedeutung über Bewegung und Farbe)
	_parcel_marker()
	_shadow(PARCEL.x - 16, PARCEL.x + 16, PARCEL.y + 1)
	R(PARCEL.x - 14, PARCEL.y - 18, 28, 18, AMBER)
	L(Vector2(PARCEL.x, PARCEL.y - 18), Vector2(PARCEL.x, PARCEL.y), NIGHT, 2.0)
	L(Vector2(PARCEL.x - 14, PARCEL.y - 9), Vector2(PARCEL.x + 14, PARCEL.y - 9), NIGHT, 2.0)


func _choice_switch() -> float:
	return ease_io((t - 3.5) / 0.35)


const SEL_AT := 3.675   # _choice_switch() erreicht 0,5: Auswahltext und Zeigering wechseln im selben Bild


func _selected() -> bool:
	return t >= SEL_AT


func _parcel_marker() -> void:
	var sel := _selected()
	var col := RED if sel else CREAM
	var c := PARCEL + Vector2(0, -9)
	for k in 2:
		var u := fposmod(t / 1.3 + k * 0.5, 1.0)
		if sel:
			u = fposmod((t - SEL_AT) / 1.0 + k * 0.5, 1.0)
		# Radius 18–30: bleibt über dem Oberflächenband (Mitte y 565 + 30 < 598)
		ring(c, 18.0 + 12.0 * u, maxf(0.5, 3.0 * (1.0 - u)), col)


# ---------------------------------------------------------------------------
# Dachs-Kurier: Rumpf als abgerundetes Rechteck, Kopf als Kreis, Glieder als Linien
# ---------------------------------------------------------------------------
func gait(time: float) -> Dictionary:
	var v := STEP / STEP_T
	var x0 := B_START + STEP * 0.5
	var t_walk := N_STEPS * STEP_T
	var settle := STEP * 0.5 + GAP * 0.5
	var t_settle := 2.0 * settle / v
	var gy := GROUND - FOOT_R
	var hip_x: float
	var stance_x: float
	var swing: Vector2
	var near_stance: bool
	var walk := 1.0
	var fN := x0 + N_STEPS * STEP
	if time < t_walk:
		var k := int(floor(time / STEP_T))
		var f := time / STEP_T - k
		stance_x = x0 + k * STEP
		hip_x = stance_x - STEP * 0.5 + STEP * f
		swing = Vector2(lerpf(stance_x - STEP, stance_x + STEP, ease_io(f)), gy - LIFT * sin(PI * f))
		near_stance = k % 2 == 0
	elif time < t_walk + t_settle:
		var u := (time - t_walk) / t_settle
		stance_x = fN
		hip_x = fN - STEP * 0.5 + settle * (1.0 - (1.0 - u) * (1.0 - u))
		swing = Vector2(lerpf(fN - STEP, fN + GAP, ease_io(u)), gy - LIFT * 0.7 * sin(PI * u))
		near_stance = N_STEPS % 2 == 0
		walk = 1.0 - u
	else:
		stance_x = fN
		hip_x = fN + GAP * 0.5
		swing = Vector2(fN + GAP, gy)
		near_stance = N_STEPS % 2 == 0
		walk = 0.0
	var dx := hip_x - stance_x
	var hip_y := gy - sqrt(LEG * LEG - dx * dx)
	var stance := Vector2(stance_x, gy)
	var t_stop := t_walk + t_settle
	var tilt := deg_to_rad(5.0) * walk
	if time > t_stop:
		tilt = deg_to_rad(-3.0) * sin(PI * clampf((time - t_stop) / 0.45, 0.0, 1.0))
	return {
		"hip": Vector2(hip_x, hip_y), "near": stance if near_stance else swing,
		"far": swing if near_stance else stance, "walk": walk, "tilt": tilt, "t_stop": t_stop,
	}


func _badger() -> void:
	var g := gait(t)
	var hip: Vector2 = g.hip
	var walk: float = g.walk
	var xf := Transform2D(float(g.tilt), hip)
	var far_foot: Vector2 = g.far
	var near_foot: Vector2 = g.near
	# Schatten als Linie
	_shadow(hip.x - 26, hip.x + 30, GROUND + 1)
	# hinterer Arm schwingt gegen das hintere Bein
	var rel := clampf((far_foot.x - hip.x) / (STEP * 0.5), -1.0, 1.0) * walk
	var arm_a := deg_to_rad(-28.0) * rel
	draw_set_transform_matrix(xf)
	var sh := Vector2(-8, -50)
	cap(sh, sh + Vector2(sin(arm_a), cos(arm_a)) * 24.0, 5.5, NIGHT)
	# Beine in Weltkoordinaten (Füße stehen fest)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	for leg in [[Vector2(-4, -2), far_foot], [Vector2(4, -2), near_foot]]:
		var hj: Vector2 = xf * (leg[0] as Vector2)
		var ft: Vector2 = leg[1]
		cap(hj, ft, 6.0, NIGHT)
		cap(ft + Vector2(-2, 0), ft + Vector2(8, 0), FOOT_R, NIGHT)
	draw_set_transform_matrix(xf)
	# Rumpf
	rrect(-22, -24, 42, 30, 12, NIGHT)
	rrect(-25, -66, 48, 52, 17, GREEN)
	C(Vector2(19, -46), 2.2, AMBER)
	C(Vector2(19, -32), 2.2, AMBER)
	L(Vector2(12, -64), Vector2(-20, -22), NIGHT, 3.0)
	rrect(-36, -30, 15, 17, 3, ROSE)
	L(Vector2(-36, -24), Vector2(-21, -24), NIGHT, 2.0)
	# Schalende: Kette aus Kapseln, flattert im Wind und beim Laufen nach hinten
	var gu := gust(t)
	var droop := lerpf(lerpf(deg_to_rad(72.0), deg_to_rad(14.0), walk), deg_to_rad(8.0), gu)
	var p := Vector2(-14, -60)
	var w := 9.0 + 3.0 * maxf(walk, gu)
	for i in 7:
		var a := droop + sin(t * w - i * 0.85) * (0.10 + 0.05 * i) * (0.7 + 0.5 * maxf(walk, gu))
		var q := p + Vector2(-cos(a), sin(a)) * 7.5
		cap(p, q, 4.5, RED)
		p = q
	# Paket unter dem Arm, Arm davor
	R(2, -48, 28, 20, AMBER)
	L(Vector2(16, -48), Vector2(16, -28), NIGHT, 2.0)
	L(Vector2(2, -38), Vector2(30, -38), NIGHT, 2.0)
	cap(Vector2(-3, -52), Vector2(12, -30), 5.5, NIGHT)
	C(Vector2(14, -28), 6.5, NIGHT)
	# Kopf: dreht sich zum Paket, wenn der Dachs steht
	var t_stop: float = g.t_stop
	var look := ease_io((t - t_stop - 0.35) / 0.4) * deg_to_rad(10.0)
	var bob := 0.0
	var head_xf := xf * Transform2D(look, Vector2(6, -64)) * Transform2D(0.0, Vector2(-6, 64 + bob))
	draw_set_transform_matrix(head_xf)
	C(Vector2(-2, -96), 6.5, NIGHT)
	C(Vector2(-2, -96), 2.5, CREAM)
	C(Vector2(13, -84), 21, CREAM)
	cap(Vector2(22, -80), Vector2(40, -75), 9.0, CREAM)
	cap(Vector2(38, -77), Vector2(-5, -89), 5.5, NIGHT)
	C(Vector2(47, -74), 5.0, NIGHT)
	var blink := (t > 5.05 and t < 5.17) or (t > 1.6 and t < 1.7)
	if blink:
		L(Vector2(21, -82), Vector2(27, -82), CREAM, 1.5)
	else:
		C(Vector2(24, -82), 2.3, CREAM)
	rrect(-9, -115, 38, 15, 6, GREEN)
	L(Vector2(24, -101), Vector2(42, -99), NIGHT, 4.0)
	C(Vector2(25, -105), 2.2, AMBER)
	draw_set_transform_matrix(xf)
	# Schal um den Hals (vor Kopf und Rumpf)
	cap(Vector2(-16, -62), Vector2(16, -64), 7.0, RED)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


# ---------------------------------------------------------------------------
# Oberfläche: dunkles Band, Ort, Zeile, Eingabe, drei Handlungen mit Kreismarken
# ---------------------------------------------------------------------------
func _ui() -> void:
	R(0, UI_TOP, W, H - UI_TOP, NIGHT)
	R(0, UI_TOP, W, 2, AMBER)
	var x := 48.0
	C(Vector2(x + 4, 628), 4.0, AMBER)
	draw_string(f_caps, Vector2(x + 18, 634), "HAFEN VON LORNHOLM", HORIZONTAL_ALIGNMENT_LEFT, -1, 15, AMBER)
	draw_string(f_text, Vector2(x, 670), "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich.", HORIZONTAL_ALIGNMENT_LEFT, -1, 24, CREAM)
	# Eingabe: wird getippt, Schreibmarke blinkt
	var cmd := "nimm paket"
	# ein Zeichen je 3 Bilder (0,1 s), ab 0,5 s; über die Bildnummer, damit Rundung der delta-Summe
	# keine 2- oder 4-Bild-Haltezeiten erzeugt
	var frame := int(round(t * 30.0))
	var shown := cmd.substr(0, clampi(floori((frame - 15) / 3.0), 0, cmd.length()))
	var prompt := "> " + shown
	draw_string(f_mono, Vector2(x, 704), prompt, HORIZONTAL_ALIGNMENT_LEFT, -1, 19, ROSE)
	var pw := f_mono.get_string_size(prompt, HORIZONTAL_ALIGNMENT_LEFT, -1, 19).x
	if fposmod(t, 0.8) < 0.5 or shown.length() < cmd.length():
		R(x + pw + 3, 688, 9, 19, AMBER)
	# Trennlinie und Auswahl
	L(Vector2(868, UI_TOP + 22), Vector2(868, H - 20), VIOLET, 2.0)
	var choices := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
	var s := _choice_switch()
	var sel_y := lerpf(0.0, 1.0, s)
	for i in 3:
		var y := 636.0 + i * 31.0
		ring(Vector2(904, y - 7), 6.0, 2.0, VIOLET)
		var active := (i == 0 and not _selected()) or (i == 1 and _selected())
		draw_string(f_choice, Vector2(922, y), choices[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 20, CREAM if active else ROSE)
	C(Vector2(904, 636.0 + sel_y * 31.0 - 7), 6.0, RED)
