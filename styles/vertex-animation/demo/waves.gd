class_name Waves
extends RefCounted
## Gerstner-Wellen: eine Quelle für Vertex-Shader (shaders/sea.gdshader) und Skript (Boote, Treibgut).
##
## Jede Welle i: Richtung d (2D, normiert), Höhe A (m), Wellenlänge L (m), Spitzigkeit Q, Phase φ.
## k = 2π/L, ω = sqrt(g·k) (Tiefwasser), θ = k·(d·p) − ω·t + φ  (p = Ruhelage x/z in Weltkoordinaten)
##   Versatz = ( Σ Q·A·d.x·cos θ,  Σ A·sin θ,  Σ Q·A·d.y·cos θ )
## Σ Q·k·A < 1, sonst überschlagen sich die Kämme (Schleifen im Gitter). Außerhalb des Hafens blendet `fade`
## die Wellen aus (das Gitter wird dort grob); Shader und Skript rechnen denselben Faktor.
## Zeit: Der Shader bekommt nicht t, sondern je Welle die Phase (φ − ω·t) mod 2π, in GDScript mit doppelter
## Genauigkeit gerechnet (set_time). So bleiben die Wellen auch nach Stunden Laufzeit ruckelfrei; mit einer
## float-Zeit im Shader wüchse der Rundungsfehler von ω·t mit der Laufzeit.

const G := 9.81

## d.x, d.y, A, L, Q, φ  (Hafen bei Wind: Dünung von See her, dazu kürzere Windsee aus anderen Richtungen)
const SPEC := [
	[0.20, 1.00, 0.110, 10.0, 0.85, 0.0],
	[-0.60, 1.00, 0.075, 6.4, 0.85, 1.7],
	[0.95, 0.30, 0.050, 4.1, 0.75, 4.1],
	[0.35, 1.00, 0.032, 2.6, 0.65, 2.3],
	[-0.90, 0.45, 0.020, 1.7, 0.55, 5.2],
]
## Kräuselung (nur Normale im Fragment-Shader): d.x, d.y, L
const RIPPLES := [[0.3, 1.0, 0.9], [-0.85, 0.5, 0.63], [0.9, -0.35, 0.47], [-0.25, -1.0, 1.21]]
const FADE_CENTER := Vector2(2.0, -12.0)
const FADE_INNER := 42.0
const FADE_OUTER := 66.0

var dirs: Array[Vector2] = []
var amps: Array[float] = []
var ks: Array[float] = []
var omegas: Array[float] = []
var qs: Array[float] = []
var phases: Array[float] = []


func _init() -> void:
	for w in SPEC:
		dirs.append(Vector2(w[0], w[1]).normalized())
		amps.append(w[2])
		ks.append(TAU / w[3])
		omegas.append(sqrt(G * TAU / w[3]))
		qs.append(w[4])
		phases.append(w[5])


func count() -> int:
	return dirs.size()


## Summe Q·k·A (muss < 1 sein) und Summe der Höhen (für Farbverlauf im Shader).
func steepness_sum() -> float:
	var s := 0.0
	for i in count():
		s += qs[i] * ks[i] * amps[i]
	return s


func amp_sum() -> float:
	var s := 0.0
	for a in amps:
		s += a
	return s


static func fade_at(p: Vector2) -> float:
	return 1.0 - smoothstep(FADE_INNER, FADE_OUTER, p.distance_to(FADE_CENTER))


## Phase der Welle i zur Zeit t, auf 0..2π gefaltet (gleich im Shader und im Skript).
func phase_at(i: int, t: float) -> float:
	return fposmod(phases[i] - omegas[i] * t, TAU)


## Versatz (dx, y, dz) eines Wasserteilchens mit Ruhelage p.
func displace(p: Vector2, t: float) -> Vector3:
	var o := Vector3.ZERO
	for i in count():
		var th := ks[i] * dirs[i].dot(p) + phase_at(i, t)
		var c := cos(th)
		o.x += qs[i] * amps[i] * dirs[i].x * c
		o.y += amps[i] * sin(th)
		o.z += qs[i] * amps[i] * dirs[i].y * c
	return o * fade_at(p)


## Punkt der Oberfläche über (x, z): Ruhelage p suchen, deren verschobenes x/z genau (x, z) trifft
## (Festpunkt-Iteration; der Shader verschiebt auch waagrecht). Rückgabe: Welt-Versatz an dieser Stelle,
## also y = Wasserhöhe über der Ruhe-Wasserlinie und x/z = waagrechte Teilchenbewegung.
func surface_at(x: float, z: float, t: float) -> Vector3:
	var target := Vector2(x, z)
	var p := target
	var d := Vector3.ZERO
	for _i in 4:
		d = displace(p, t)
		p = target - Vector2(d.x, d.z)
	return displace(p, t)


## Uniforms für shaders/sea.gdshader (Arrays vec4, Länge MAX_WAVES im Shader).
func apply(mat: ShaderMaterial) -> void:
	var a := PackedVector4Array()
	for i in count():
		a.append(Vector4(dirs[i].x, dirs[i].y, amps[i], qs[i]))
	mat.set_shader_parameter("wave_a", a)
	set_time(mat, 0.0)
	mat.set_shader_parameter("wave_count", count())
	mat.set_shader_parameter("amp_sum", amp_sum())
	mat.set_shader_parameter("fade_center", FADE_CENTER)
	mat.set_shader_parameter("fade_inner", FADE_INNER)
	mat.set_shader_parameter("fade_outer", FADE_OUTER)


## Je Bild: Phasen der Wellen und der Kräuselung zur Zeit t (doppelte Genauigkeit, gefaltet).
func set_time(mat: ShaderMaterial, t: float) -> void:
	var b := PackedVector4Array()
	for i in count():
		b.append(Vector4(ks[i], omegas[i], phase_at(i, t), 0.0))
	mat.set_shader_parameter("wave_b", b)
	var r := PackedVector4Array()
	for i in RIPPLES.size():
		var d := Vector2(RIPPLES[i][0], RIPPLES[i][1]).normalized()
		var k: float = TAU / RIPPLES[i][2]
		r.append(Vector4(d.x, d.y, k, fposmod(1.9 * i - sqrt(G * k) * t, TAU)))
	mat.set_shader_parameter("ripple", r)
