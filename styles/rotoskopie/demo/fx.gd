extends Node2D
## Umgebungsanimationen, im Strich des gezeichneten Hintergrunds. main.gd setzt jedes Bild `t` und ruft
## queue_redraw(). kind = "light": Leuchtfeuerstrahl und Lichthöfe (additiv, Material im .tscn),
## kind = "smoke": Rauchballen mit Tuschekontur, kind = "gulls": zwei Möwen als Tuschestriche.
## Lagen der Lichter: im KI-Bild gemessen (assets/bg.json, prep_bg.py); sie liegen 0–6 px neben der
## Projektion aus 3D.

@export var kind := "light"

const LAMP := Vector2(966.9, 59.5)        # Leuchtfeuer
const LANTERN := Vector2(1214.0, 362.0)   # Laterne am Pfahl
const WINDOW := Vector2(279.0, 389.0)     # Seitenfenster des Häuschens
const CHIMNEY := Vector2(37.0, 112.0)     # Oberkante Schornstein
const INK := Color(0.16, 0.11, 0.12)
const SMOKE_LIGHT := Color(0.72, 0.70, 0.80)
const SMOKE_SHADE := Color(0.52, 0.52, 0.66)
const BEAM_PERIOD := 6.0                  # eine Umdrehung des Leuchtfeuers
const PUFFS := 40                         # Rauchballen je Umlauf; Umlauf 40 × 0,42 s = 16,8 s > Lebensdauer 4,2 s
const PUFF_GAP := 0.42

var t := 0.0
var noise := FastNoiseLite.new()
var puffs: Array = []                     # [Geburt, x-Streuung, Wachstum, Drift]


func _ready() -> void:
	noise.seed = 7
	noise.frequency = 1.8
	var rng := RandomNumberGenerator.new()
	rng.seed = 4242
	for i in PUFFS:
		puffs.append([i * PUFF_GAP, rng.randf_range(-3.0, 3.0), rng.randf_range(0.85, 1.2), rng.randf_range(0.7, 1.3)])


func _draw() -> void:
	match kind:
		"light":
			_draw_light()
		"smoke":
			_draw_smoke()
		"gulls":
			_draw_gulls()


func glow(p: Vector2, r: float, col: Color, rings := 8) -> void:
	# weicher Lichthof aus konzentrischen Kreisen (additiv)
	for i in rings:
		var k := 1.0 - float(i) / rings
		draw_circle(p, r * k, Color(col.r, col.g, col.b, col.a / rings))


func _draw_light() -> void:
	# Leuchtfeuer: Strahl dreht sich in der Waagerechten; im Bild ist nur cos sichtbar, zur Kamera blitzt die Lampe
	var phi := TAU * t / BEAM_PERIOD + 0.6
	var side := cos(phi)
	var toward := sin(phi)
	var reach := 560.0 * absf(side)
	if reach > 20.0:
		var dir := Vector2(signf(side), 0.035)
		var far := LAMP + dir * reach
		var w0 := 5.0
		var w1 := 26.0 + 30.0 * absf(side)
		var n := Vector2(0, 1)
		var pts := PackedVector2Array([LAMP - n * w0, far - n * w1, far + n * w1, LAMP + n * w0])
		var a := 0.30 * (0.55 + 0.45 * absf(side))
		var cols := PackedColorArray([Color(1.0, 0.86, 0.55, a), Color(1.0, 0.8, 0.5, 0.0),
				Color(1.0, 0.8, 0.5, 0.0), Color(1.0, 0.86, 0.55, a)])
		draw_polygon(pts, cols)
		# heller Kern
		var core := PackedVector2Array([LAMP - n * 2.0, far - n * w1 * 0.35, far + n * w1 * 0.35, LAMP + n * 2.0])
		draw_polygon(core, PackedColorArray([Color(1, 0.93, 0.7, a * 0.9), Color(1, 0.9, 0.6, 0.0),
				Color(1, 0.9, 0.6, 0.0), Color(1, 0.93, 0.7, a * 0.9)]))
	var flare := pow(clampf(toward, 0.0, 1.0), 6.0)
	glow(LAMP, 22.0 + 26.0 * flare, Color(1.0, 0.85, 0.5, 0.55 + 0.45 * flare))
	# Laterne und Fenster flackern
	var fl := 0.78 + 0.22 * noise.get_noise_1d(t * 3.1)
	glow(LANTERN, 44.0 * (0.9 + 0.1 * fl), Color(1.0, 0.72, 0.32, 0.55 * fl))
	glow(LANTERN, 14.0, Color(1.0, 0.9, 0.6, 0.35 * fl), 4)
	var fw := 0.85 + 0.15 * noise.get_noise_1d(t * 1.3 + 40.0)
	glow(WINDOW, 46.0, Color(1.0, 0.7, 0.35, 0.22 * fw))


func _draw_smoke() -> void:
	# Ballen steigen auf, treiben nach rechts, wachsen und lösen sich durch Schrumpfen auf (keine Transparenz,
	# sonst zeigen sich die Konturen gegenseitig). Erst alle Konturen, dann Schatten-, dann Lichtflächen.
	var live: Array = []
	for p in puffs:
		var age: float = fposmod(t - p[0], PUFFS * PUFF_GAP)
		if age > 4.2:
			continue
		var k := age / 4.2
		var pos := CHIMNEY + Vector2(p[1] + age * 9.0 * p[3] + 6.0 * sin(age * 1.3 + p[1]), -age * 24.0)
		var r: float = (5.0 + 15.0 * sqrt(k)) * p[2]
		if k > 0.7:
			r *= 1.0 - (k - 0.7) / 0.3
		if r > 1.0:
			live.append([pos, r])
	for q in live:
		draw_circle(q[0], q[1] + 2.0, INK)
	for q in live:
		draw_circle(q[0], q[1], SMOKE_SHADE)
	for q in live:
		draw_circle(q[0] + Vector2(-q[1] * 0.18, -q[1] * 0.22), q[1] * 0.72, SMOKE_LIGHT)


func _draw_gulls() -> void:
	# Lage läuft über 1500 px um (Langzeitlauf), Höhe schwingt leicht
	var gulls := [[Vector2(360.0, 262.0), Vector2(46.0, -1.0), 13.0, 0.0],
			[Vector2(1300.0, 214.0), Vector2(-40.0, 1.0), 10.0, 1.7]]
	for g in gulls:
		var p: Vector2 = g[0] + g[1] * t
		p.x = fposmod(p.x + 110.0, 1500.0) - 110.0
		p.y = g[0].y + 8.0 * sin(t * 0.5 + g[3])
		var s: float = g[2]
		var flap := sin(t * 7.0 + g[3])
		var tip_y := -s * 0.55 * flap
		var l := PackedVector2Array([p + Vector2(-s, tip_y), p + Vector2(-s * 0.45, -s * 0.25 - tip_y * 0.3), p])
		var r := PackedVector2Array([p, p + Vector2(s * 0.45, -s * 0.25 - tip_y * 0.3), p + Vector2(s, tip_y)])
		draw_polyline(l, INK, 2.2, true)
		draw_polyline(r, INK, 2.2, true)
