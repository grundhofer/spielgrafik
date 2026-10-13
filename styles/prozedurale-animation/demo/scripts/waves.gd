extends RefCounted
## Eine Wellenfunktion für alles: Wasser-Shader, Boote und Seile lesen dieselbe Höhe h(X, Z, t).
## Ebene Wasserfläche, Kamera in 2 m Höhe (D/F), Horizont in Bildzeile HORIZON.
## Bildschirm -> Welt: Z = D / (y - HORIZON), X = (x - CX) * Z / F; Hebung um h verschiebt um -F*h/Z Pixel.

const F := 500.0
const D := 1000.0
const CX := 640.0
const G := 9.81
## Wellenlänge (m), Amplitude (m), Laufrichtung in der Ebene (x nach rechts, z vom Betrachter weg), Phase
const SPEC := [
	[9.0, 0.062, Vector2(0.38, -0.925), 0.0],
	[5.5, 0.038, Vector2(-0.55, -0.835), 1.7],
	[3.2, 0.018, Vector2(0.85, -0.527), 4.1],
]
static var horizon := 369.1


## [kx, kz, omega, amp] je Welle (Tiefwasser: omega = sqrt(g k)).
static func comp(i: int) -> Vector4:
	var s: Array = SPEC[i]
	var k: float = TAU / float(s[0])
	var d: Vector2 = s[2]
	d = d.normalized()
	return Vector4(k * d.x, k * d.y, sqrt(G * k), float(s[1]))


static func phase(i: int) -> float:
	var s: Array = SPEC[i]
	return float(s[3])


static func height(x_w: float, z_w: float, t: float) -> float:
	var h := 0.0
	for i in SPEC.size():
		var c := comp(i)
		h += c.w * sin(c.x * x_w + c.y * z_w - c.z * t + phase(i))
	return h


static func z_of_y(y: float) -> float:
	return D / maxf(y - horizon, 0.5)


static func y_of_z(z_w: float) -> float:
	return horizon + D / z_w


static func x_of(sx: float, z_w: float) -> float:
	return (sx - CX) * z_w / F


## Bildschirmverschiebung der Oberfläche an Bildspalte sx in Tiefe z_w (negativ = nach oben).
static func screen_dy(sx: float, z_w: float, t: float) -> float:
	return -F * height(x_of(sx, z_w), z_w, t) / z_w


static func apply_uniforms(mat: ShaderMaterial, t: float) -> void:
	mat.set_shader_parameter("w0", comp(0))
	mat.set_shader_parameter("w1", comp(1))
	mat.set_shader_parameter("w2", comp(2))
	mat.set_shader_parameter("ph", Vector3(phase(0), phase(1), phase(2)))
	mat.set_shader_parameter("t", t)
	mat.set_shader_parameter("horizon", horizon)
