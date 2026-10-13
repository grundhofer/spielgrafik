extends Node2D
## Möwen als Scherenschnitt-Silhouetten: Rumpf und zwei Flügel als Polygone, Flügelschlag über den
## Flügelwinkel, Gleitphasen dazwischen. Flugbahnen wiederholen sich, damit die Szene beliebig lange läuft.

var t := 0.0
var birds := [
	# Start-x, y, Geschwindigkeit (px/s, negativ = nach links), Spannweite, Farbe, Phase, Periode der Bahn
	{"x0": 1150.0, "y": 160.0, "v": -62.0, "span": 50.0, "col": Color(0.07, 0.045, 0.09), "ph": 0.0, "loop": 26.0},
	{"x0": 930.0, "y": 196.0, "v": -34.0, "span": 20.0, "col": Color(0.25, 0.15, 0.27), "ph": 1.3, "loop": 40.0},
]


func _wing(c: Vector2, span: float, ang: float, dir: float) -> PackedVector2Array:
	# gebogener Flügel: Ansatz am Rumpf, Bug, Spitze; ang = Hebung (rad), dir = -1 links / +1 rechts
	var half := span * 0.5
	var tip := c + Vector2(dir * half * cos(ang), -half * sin(ang))
	var elbow := c + Vector2(dir * half * 0.45 * cos(ang * 0.6), -half * 0.45 * sin(ang * 0.6) - span * 0.06)
	var p := PackedVector2Array()
	p.append(c + Vector2(-dir * span * 0.03, -span * 0.02))
	p.append(elbow + Vector2(0, -span * 0.05))
	p.append(tip)
	p.append(elbow + Vector2(dir * span * 0.04, span * 0.03))
	p.append(c + Vector2(dir * span * 0.05, span * 0.04))
	return p


func _draw() -> void:
	for b in birds:
		var dist: float = fposmod(t * absf(b["v"]) + 0.0, b["loop"] * absf(b["v"]))
		var x: float = b["x0"] + signf(b["v"]) * dist
		if x < -60.0:
			continue
		var span: float = b["span"]
		var lt: float = t + b["ph"]
		# 1,3 s Schlagen (3 Hz), 1,1 s Gleiten
		var cyc := fposmod(lt, 2.4)
		var flap := sin(cyc * TAU * 3.0) if cyc < 1.3 else 0.25
		var ang := deg_to_rad(18.0 + 30.0 * flap)
		var y: float = b["y"] + 4.0 * sin(lt * 0.9) - (2.0 * flap if cyc < 1.3 else 0.0)
		var c := Vector2(round(x), round(y))
		var col: Color = b["col"]
		draw_colored_polygon(_wing(c, span, ang, -1.0), col)
		draw_colored_polygon(_wing(c, span, ang * 0.92, 1.0), col)
		# Rumpf: spitze Ellipse, Kopf in Flugrichtung (links)
		var body := PackedVector2Array()
		for i in 12:
			var a := TAU * i / 12.0
			body.append(c + Vector2(cos(a) * span * 0.2, sin(a) * span * 0.05))
		draw_colored_polygon(body, col)
		var tail := PackedVector2Array([c + Vector2(span * 0.16, -span * 0.03), c + Vector2(span * 0.3, -span * 0.05),
			c + Vector2(span * 0.3, span * 0.05), c + Vector2(span * 0.16, span * 0.04)])
		draw_colored_polygon(tail, col)
