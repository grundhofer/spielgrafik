extends Node2D
## Möwen als Neonstriche: Lage in Weltkoordinaten (kreisen über dem Hafen), mit der Kamera des ID-Puffers
## projiziert und als geknickte Linie mit Flügelschlag gezeichnet. Liegen im Himmel; der Bildschirm-Shader
## verdeckt sie nicht, deshalb laufen die Bahnen frei vom Leuchtturm.

## [Mitte der Kreisbahn, Radius, Umlaufzeit in s, Phase, Spannweite in m]
const BIRDS := [
	[Vector3(0.6, 6.4, -13.0), 2.2, 11.0, 0.4, 1.0],
	[Vector3(3.2, 10.6, -24.0), 3.4, 14.0, 2.6, 1.1],
]

var t := 0.0
var cam: Camera3D
var scale_px := 0.5          # ID-Puffer ist doppelt so groß wie das Bild


func _draw() -> void:
	if cam == null:
		return
	var col := Color("dff8ff").srgb_to_linear() * 1.25
	for b in BIRDS:
		var c: Vector3 = b[0]
		var r: float = b[1]
		var ang: float = TAU * t / b[2] + b[3]
		var p := c + Vector3(r * cos(ang), 0.35 * sin(ang * 2.0), r * sin(ang) * 0.5)
		if cam.is_position_behind(p):
			continue
		var span: float = b[4]
		var flap := sin(t * 7.5 + b[3] * 3.0)
		# Flügel: Spitze, Bug, Körper — in der Bildebene der Kamera, damit die Form lesbar bleibt
		var right := cam.global_basis.x
		var up := cam.global_basis.y
		var pts := PackedVector3Array([
			p - right * span * 0.5 + up * (0.12 + 0.22 * flap),
			p - right * span * 0.22 + up * (0.14 + 0.05 * flap),
			p - up * 0.04,
			p + right * span * 0.22 + up * (0.14 + 0.05 * flap),
			p + right * span * 0.5 + up * (0.12 + 0.22 * flap),
		])
		var sp := PackedVector2Array()
		for q in pts:
			sp.append(cam.unproject_position(q) * scale_px)
		draw_polyline(sp, col, 2.0, true)
