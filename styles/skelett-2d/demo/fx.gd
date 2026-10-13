extends Node2D
## Umgebungseffekte, gezeichnet aus der aufsummierten Zeit (main.gd setzt t und Flackerwerte).
##   kind = "smoke": Rauchballen aus dem Schornstein (normal gemischt)
##   kind = "glow":  Fensterschein, Laterne mit Lichtfleck, Leuchtfeuer mit drehendem Strahl (additiv)
##   kind = "gulls": zwei Möwen mit Flügelschlag

@export var kind := "smoke"

const CHIMNEY := Vector2(147, 84)
const WINDOW := Vector2(196, 428)
const LANTERN := Vector2(848, 362)
const LAMP := Vector2(1118, 95)
const POOL := Vector2(858, 598)
const BEAM_PERIOD := 7.0

var t := 0.0
var flicker := 1.0          # Laterne
var flicker_w := 1.0        # Fenster
var soft: GradientTexture2D


func _ready() -> void:
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(1, 1, 1, 0))
	g.add_point(0.45, Color(1, 1, 1, 0.55))
	soft = GradientTexture2D.new()
	soft.gradient = g
	soft.fill = GradientTexture2D.FILL_RADIAL
	soft.fill_from = Vector2(0.5, 0.5)
	soft.fill_to = Vector2(1.0, 0.5)
	soft.width = 128
	soft.height = 128
	if kind == "glow":
		var m := CanvasItemMaterial.new()
		m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		material = m


func _process(_d: float) -> void:
	queue_redraw()


func blob(c: Vector2, r: float, col: Color, squash := 1.0) -> void:
	draw_texture_rect(soft, Rect2(c - Vector2(r, r * squash), Vector2(2 * r, 2 * r * squash)), false, col)


func _draw() -> void:
	match kind:
		"smoke":
			draw_smoke()
		"glow":
			draw_glow()
		"gulls":
			draw_gulls()


func draw_smoke() -> void:
	# Ballen alle 0,42 s, Lebensdauer 3,6 s; vorgewärmt (negative Startzeiten)
	var period := 0.42
	var life := 3.6
	var first := int(floor((t - life) / period)) - 1
	var last := int(floor(t / period))
	for i in range(first, last + 1):
		var a := t - i * period
		if a < 0.0 or a > life:
			continue
		var k := a / life
		var rnd := fmod(abs(sin(i * 12.9898) * 43758.5453), 1.0)
		var rise := 70.0 * (1.0 - exp(-a * 0.9)) + 6.0 * a
		var drift := 9.0 * a + 4.0 * a * a + sin(a * 1.7 + rnd * 6.0) * 3.0
		var p := CHIMNEY + Vector2(drift + (rnd - 0.5) * 3.0, -rise)
		var r := 6.0 + 22.0 * sqrt(k)
		var alpha := smoothstep(0.0, 0.05, k) * (1.0 - smoothstep(0.40, 1.0, k)) * 0.45
		var shade := 0.74 + 0.08 * rnd
		blob(p, r, Color(shade, shade, shade + 0.1, alpha))


func draw_glow() -> void:
	# Fenster
	blob(WINDOW, 78.0, Color(1.0, 0.68, 0.34, 0.20 * flicker_w))
	blob(WINDOW, 34.0, Color(1.0, 0.75, 0.45, 0.16 * flicker_w))
	# Laterne: Hof, Kern, Lichtfleck auf dem Kai
	blob(LANTERN, 120.0, Color(1.0, 0.62, 0.30, 0.30 * flicker))
	blob(LANTERN, 36.0, Color(1.0, 0.80, 0.50, 0.45 * flicker))
	blob(POOL, 190.0, Color(1.0, 0.62, 0.32, 0.20 * flicker), 0.16)
	# Leuchtfeuer: Strahl dreht sich um die senkrechte Achse; seitlich lang, zur Kamera hin Aufblitzen
	var th := TAU * t / BEAM_PERIOD + 0.9
	var side := sin(th)
	var toward := cos(th)
	var flare := pow(max(toward, 0.0), 6.0)
	for dir: float in [-1.0, 1.0]:
		var s := side * dir
		if s <= 0.02:
			continue
		var length := 900.0 * pow(s, 0.8)
		draw_beam(LAMP, Vector2(-1.0 if dir > 0.0 else 1.0, 0.03), length, 0.26 * pow(s, 0.6))
	blob(LAMP, 30.0 + 22.0 * flare, Color(1.0, 0.85, 0.55, 0.45 + 0.25 * flare))
	blob(LAMP, 10.0, Color(1.0, 0.95, 0.80, 0.8))


func draw_beam(origin: Vector2, dir: Vector2, length: float, alpha: float) -> void:
	# Keil aus Streifen: Alpha längs und quer weich bis 0
	var n := dir.normalized()
	var perp := Vector2(-n.y, n.x)
	var steps := 10
	var pts := PackedVector2Array()
	var cols := PackedColorArray()
	var core := Color(1.0, 0.92, 0.72, alpha)
	var edge := Color(1.0, 0.92, 0.72, 0.0)
	for i in steps + 1:
		var k := float(i) / steps
		var c := origin + n * length * k
		var w := 4.0 + 46.0 * k
		var fade := (1.0 - k) * (1.0 - k)
		# drei Punkte quer: Rand, Mitte, Rand
		pts.append(c + perp * w)
		cols.append(edge)
		pts.append(c)
		cols.append(Color(core.r, core.g, core.b, core.a * fade))
		pts.append(c - perp * w)
		cols.append(edge)
	for i in steps:
		var a := i * 3
		var b := (i + 1) * 3
		for q in [[a, a + 1, b + 1, b], [a + 1, a + 2, b + 2, b + 1]]:
			draw_polygon(PackedVector2Array([pts[q[0]], pts[q[1]], pts[q[2]], pts[q[3]]]),
				PackedColorArray([cols[q[0]], cols[q[1]], cols[q[2]], cols[q[3]]]))


func draw_gulls() -> void:
	# Strecken wiederholen sich (Möwen kommen nach dem Bildrand wieder), damit die Szene beliebig lange läuft
	gull(Vector2(fposmod(600.0 + 46.0 * t + 80.0, 1500.0) - 80.0, 236.0 + 6.0 * sin(t * 0.9)), 1.0, 0.0)
	gull(Vector2(1360.0 - fposmod(350.0 + 30.0 * t, 1500.0), 196.0 + 4.0 * sin(t * 1.1 + 1.0)), 0.7, 1.7)


func gull(p: Vector2, s: float, ph: float) -> void:
	var flap := sin(t * 5.2 + ph)
	var glide := 0.5 + 0.5 * sin(t * 0.8 + ph)          # zeitweise gleiten
	var lift: float = lerpf(flap, 0.35, glide) * 6.0 * s
	var span := 15.0 * s
	var pts := PackedVector2Array([
		p + Vector2(-span, -lift * 0.6 + 2.0 * s),
		p + Vector2(-span * 0.45, -lift - 2.0 * s),
		p + Vector2(0, 1.5 * s),
		p + Vector2(span * 0.45, -lift - 2.0 * s),
		p + Vector2(span, -lift * 0.6 + 2.0 * s),
	])
	draw_polyline(pts, Color(0.20, 0.19, 0.28, 0.9), 2.2 * s, true)
