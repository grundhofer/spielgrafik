extends Node2D
## Rauch aus dem Schornstein, nur aus Code: Partikelzug mit festem Schritt (1/120 s wie alles andere).
## Jedes Teilchen steigt mit abnehmendem Auftrieb, nimmt den gemeinsamen Wind (Grundwind + Böen, dieselbe
## Funktion wie Schal und Laterne) mit Verzögerung an und wird von 1D-Rauschen seitlich versetzt; es wächst und
## blasst aus. Gezeichnet als weiche Scheiben (radialer Verlauf). Kein Zufall außer Hash-Rauschen mit festem Seed.

const Util := preload("res://scripts/util.gd")
const Badger := preload("res://scripts/badger.gd")
const EMIT := 0.11          # s zwischen zwei Teilchen
const LIFE := 4.0           # s
const RISE := 26.0          # Auftrieb in Bildpixeln/s am Anfang
const WS := 0.6667          # Wind in Texturpixeln/s des Dachses -> Bildpixel/s

var src := Vector2(112, 63)
var pos := PackedVector2Array()
var vel := PackedVector2Array()
var age := PackedFloat32Array()
var pid := PackedInt32Array()
var n_emitted := 0
var next_emit := 0.0
var tex: Texture2D


func setup(pot_top: Vector2, t_start: float) -> void:
	src = pot_top
	next_emit = t_start
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.5, 1.0])
	g.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 0.55), Color(1, 1, 1, 0)])
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill = GradientTexture2D.FILL_RADIAL
	gt.fill_from = Vector2(0.5, 0.5)
	gt.fill_to = Vector2(1.0, 0.5)
	gt.width = 64
	gt.height = 64
	tex = gt


func step(tt: float, dt: float) -> void:
	while tt >= next_emit:
		var j := n_emitted
		pos.append(src + Vector2((Util.hash1(j, 61) - 0.5) * 3.0, 0.0))
		vel.append(Vector2(0.0, -RISE))
		age.append(tt - next_emit)
		pid.append(j)
		n_emitted += 1
		next_emit += EMIT
	var wind := Badger.wind_at(tt) * WS
	for i in pos.size():
		age[i] += dt
		var a := age[i]
		var u := minf(a / LIFE, 1.0)
		var turb := Vector2(Util.vnoise(a * 1.4 + pid[i] * 0.37, 71), 0.4 * Util.vnoise(a * 1.1 + pid[i] * 0.53, 73)) * 9.0
		var want := Vector2(wind.x, -RISE * (1.0 - 0.4 * u) + 0.5 * wind.y) + turb
		var follow := minf(1.0, dt * (0.6 + 1.6 * minf(a, 1.0)))   # junger Rauch folgt dem Wind träger
		vel[i] += (want - vel[i]) * follow
		pos[i] += vel[i] * dt
	while age.size() > 0 and age[0] > LIFE:
		pos.remove_at(0)
		vel.remove_at(0)
		age.remove_at(0)
		pid.remove_at(0)


func _draw() -> void:
	for i in pos.size():
		var u := age[i] / LIFE
		var r := 4.0 + 20.0 * sqrt(u)
		var al := 0.30 * smoothstep(0.0, 0.07, u) * (1.0 - smoothstep(0.4, 1.0, u))
		draw_texture_rect(tex, Rect2(pos[i] - Vector2(r, r), Vector2(2.0 * r, 2.0 * r)), false, Color(0.70, 0.68, 0.77, al))
