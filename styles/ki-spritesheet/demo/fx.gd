extends Node2D
## Umgebungseffekte, gezeichnet nur aus der aufsummierten Zeit (main.gd setzt t und die Flackerwerte).
##   kind = "smoke": Rauchballen aus dem Schornstein als flache Formen wie der Hintergrund: zwei Tonstufen
##                   (Schatten unten rechts), dünne halbtransparente dunkle Kontur nur am Umriss (normal gemischt)
##   kind = "glow":  Fensterschein, Laterne, Leuchtfeuer mit Strahl, der um den Turm kreist (additiv)
##   kind = "gulls": zwei Möwen als Linienzug mit Flügelschlag; main.tscn beschneidet sie mit dem Himmelskanal
##                   der Maske (shaders/sky_clip.gdshader), damit sie hinter Haus, Laterne und Felsen fliegen

@export var kind := "smoke"

const CHIMNEY := Vector2(114, 76)
const WINDOW := Vector2(117, 384)
const LANTERN := Vector2(891, 326)
const LAMP := Vector2(1112, 69)
const POOL := Vector2(896, 612)
const BEAM_PERIOD := 6.0
const SMOKE_LINE := Color(0.10, 0.05, 0.08, 0.45)     # Konturfarbe des Hintergrunds, halbtransparent
const SMOKE_DARK := Color(0.47, 0.47, 0.60)           # Schattenstufe
const SMOKE_LIGHT := Color(0.63, 0.63, 0.75)          # Lichtstufe

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
	# Ballen alle 0,4 s, Lebensdauer 3,4 s; vorgewärmt (negative Startzeiten), Wind nach rechts.
	# Flach statt Verlauf: erst alle Konturringe, dann alle Schattenflächen, dann alle Lichtflächen (deckend);
	# so bleibt die Kontur nur am äußeren Umriss stehen. Die Ballen wachsen und schrumpfen am Ende zu nichts.
	var period := 0.4
	var life := 3.4
	var first := int(floor((t - life) / period)) - 1
	var last := int(floor(t / period))
	var puffs := []
	for i in range(first, last + 1):
		var a := t - i * period
		if a < 0.0 or a > life:
			continue
		var k := a / life
		var rnd := fmod(abs(sin(i * 12.9898) * 43758.5453), 1.0)
		var rise := 40.0 * (1.0 - exp(-a * 1.2)) + 5.0 * a
		var drift := 16.0 * a + 5.0 * a * a + sin(a * 1.7 + rnd * 6.0) * 3.0
		var p := (CHIMNEY + Vector2(drift + (rnd - 0.5) * 3.0, -rise + (rnd - 0.5) * 4.0 * k)).round()
		var r := (3.0 + 19.0 * sqrt(k)) * (1.0 - smoothstep(0.62, 1.0, k)) * (0.88 + 0.24 * rnd)
		if r < 1.5:
			continue
		puffs.append([p, r])
	for q in puffs:
		draw_circle(q[0], q[1] + 1.6, SMOKE_LINE, true, -1.0, true)
	for q in puffs:
		draw_circle(q[0], q[1], SMOKE_DARK, true, -1.0, true)
	for q in puffs:
		var rr: float = q[1]
		draw_circle(q[0] + Vector2(-0.22, -0.26) * rr, rr * 0.74, SMOKE_LIGHT, true, -1.0, true)


func draw_glow() -> void:
	# Fenster
	blob(WINDOW, 76.0, Color(1.0, 0.68, 0.34, 0.18 * flicker_w))
	blob(WINDOW, 34.0, Color(1.0, 0.76, 0.46, 0.14 * flicker_w))
	# Laterne: Hof, Kern, Lichtfleck auf dem Kai
	blob(LANTERN, 110.0, Color(1.0, 0.62, 0.30, 0.26 * flicker))
	blob(LANTERN, 30.0, Color(1.0, 0.82, 0.52, 0.42 * flicker))
	blob(POOL, 170.0, Color(1.0, 0.62, 0.32, 0.16 * flicker), 0.18)
	# Leuchtfeuer: Strahl dreht sich um die senkrechte Achse; seitlich lang, zur Kamera hin Aufblitzen
	var th := TAU * t / BEAM_PERIOD + 1.1
	var side := sin(th)
	var toward := cos(th)
	var flare := pow(max(toward, 0.0), 6.0)
	for dir: float in [-1.0, 1.0]:
		var s := side * dir
		if s <= 0.02:
			continue
		draw_beam(LAMP, Vector2(-1.0 if dir > 0.0 else 1.0, 0.04), 760.0 * pow(s, 0.8), 0.36 * pow(s, 0.5))
	blob(LAMP, 26.0 + 22.0 * flare, Color(1.0, 0.86, 0.56, 0.40 + 0.30 * flare))
	blob(LAMP, 9.0, Color(1.0, 0.95, 0.80, 0.75))


func draw_beam(origin: Vector2, dir: Vector2, length: float, alpha: float) -> void:
	# Zwei flache Keile wie eine Lichtfläche mit Stufe (quer kein Verlauf): breiter Saum mit 40 % und schmaler
	# Kern mit voller Stärke; nur längs läuft das Licht zum Ende hin aus
	var n := dir.normalized()
	var perp := Vector2(-n.y, n.x)
	for layer in [[8.0, 66.0, 0.45], [4.0, 30.0, 1.0]]:
		var w0: float = layer[0]
		var w1: float = layer[1]
		var col := Color(1.0, 0.84, 0.55, alpha * float(layer[2]))
		var steps := 8
		for i in steps:
			var k0 := float(i) / steps
			var k1 := float(i + 1) / steps
			var c0 := origin + n * length * k0
			var c1 := origin + n * length * k1
			var a0 := col.a * pow(1.0 - k0, 1.3)
			var a1 := col.a * pow(1.0 - k1, 1.3)
			var e0 := w0 + (w1 - w0) * k0
			var e1 := w0 + (w1 - w0) * k1
			draw_polygon(PackedVector2Array([c0 + perp * e0, c1 + perp * e1, c1 - perp * e1, c0 - perp * e0]),
				PackedColorArray([Color(col, a0), Color(col, a1), Color(col, a1), Color(col, a0)]))


func draw_gulls() -> void:
	# Wege wiederholen sich (die Möwen kommen nach dem Bildrand wieder), damit die Szene beliebig lange läuft
	# Startlagen so, dass beide in den ersten 6 s frei am Himmel fliegen (Möwe 1 ab x 250, Möwe 2 ab x 840)
	gull(Vector2(fposmod(350.0 + 42.0 * t, 1500.0) - 100.0, 292.0 + 6.0 * sin(t * 0.9)), 1.0, 0.0)
	gull(Vector2(1380.0 - fposmod(540.0 + 30.0 * t, 1500.0), 274.0 + 4.0 * sin(t * 1.1 + 1.0)), 0.75, 1.7)


func gull(p: Vector2, s: float, ph: float) -> void:
	var flap := sin(t * 5.4 + ph)
	var glide := 0.5 + 0.5 * sin(t * 0.8 + ph)
	var lift: float = lerpf(flap, 0.35, glide) * 6.0 * s
	var span := 15.0 * s
	var pts := PackedVector2Array([
		p + Vector2(-span, -lift * 0.6 + 2.0 * s),
		p + Vector2(-span * 0.45, -lift - 2.0 * s),
		p + Vector2(0, 1.5 * s),
		p + Vector2(span * 0.45, -lift - 2.0 * s),
		p + Vector2(span, -lift * 0.6 + 2.0 * s),
	])
	draw_polyline(pts, Color(0.16, 0.13, 0.20, 0.95), 2.4 * s, true)
