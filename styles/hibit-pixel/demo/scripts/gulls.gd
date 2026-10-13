extends Node2D
## Zwei Möwen in der Ferne: 4 Flügelbilder (art/gull.png, 11×6), Bahn deterministisch aus der Zeit,
## Position auf ganze Pixel gerundet, Flügelschlag mit 10 Bildern/s (in 30 fps aufgehend).

var t := 0.0
var tex: Texture2D
const FW := 11
const FH := 6
var birds := [
	{"x0": 250.0, "y0": 68.0, "vx": 11.0, "amp": 5.0, "ph": 0.0, "flap": 0},
	{"x0": 330.0, "y0": 54.0, "vx": 8.0, "amp": 4.0, "ph": 1.7, "flap": 2},
]

func step(time: float) -> void:
	t = time
	queue_redraw()

func _draw() -> void:
	for b in birds:
		var x := roundf(fposmod(b.x0 + b.vx * t + 30.0, 700.0) - 30.0)
		var y := roundf(b.y0 + sin(t * 0.9 + b.ph) * b.amp)
		# Flügelschlag: 3 Schläge, dann gleiten (Bild 2)
		var k := int(floor(t * 10.0)) + int(b.flap)
		var cyc := k % 14
		var f: int = 2 if cyc >= 8 else [0, 1, 2, 3, 3, 2, 1, 0][cyc]
		draw_texture_rect_region(tex, Rect2(x, y, FW, FH), Rect2(f * FW, 0, FW, FH))
