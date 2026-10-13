extends Node2D
## Leuchtfeuer: Lichtkegel als Keil (additiv, harte Kanten), dreht sich alle 5 s einmal. Zeigt er zur Kamera,
## blitzt die Lampe (Palettenfarbe in der Felsnase) und ein Lichtkreuz auf.

var main: Node2D
var tt := 0.0
const PERIOD := 5.0


func setup(m: Node2D) -> void:
	main = m
	var mat := CanvasItemMaterial.new()
	mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	material = mat


func refresh(t: float) -> void:
	tt = t
	var th := TAU * (t + 1.2) / PERIOD
	main.lh_level = clampf(pow(maxf(cos(th), 0.0), 6.0), 0.25, 1.0)
	queue_redraw()


func _draw() -> void:
	var th := TAU * (tt + 1.2) / PERIOD
	var sn := sin(th)
	var cs := cos(th)
	var lp: Vector2 = main.backdrop.lamp_pos
	var len := 150.0 * absf(sn)
	if len > 3.0 and cs < 0.6:
		var dir := 1.0 if sn > 0.0 else -1.0
		var spread := 2.0 + 7.0 * absf(sn)
		var outer := PackedVector2Array([lp + Vector2(0, -1), lp + Vector2(dir * len, -spread - 1.0),
			lp + Vector2(dir * len, spread * 0.6), lp + Vector2(0, 1)])
		draw_colored_polygon(outer, main.q5(Color8(92, 74, 34)))
		var inner := PackedVector2Array([lp + Vector2(0, -1), lp + Vector2(dir * len * 0.7, -spread * 0.45 - 1.0),
			lp + Vector2(dir * len * 0.7, spread * 0.25), lp + Vector2(0, 1)])
		draw_colored_polygon(inner, main.q5(Color8(82, 72, 38)))
	if cs > 0.85:
		var k := (cs - 0.85) / 0.15
		var r := roundi(2 + 5 * k)
		var c: Color = main.q5(Color8(120, 110, 70) * k)
		draw_rect(Rect2(lp.x - r, lp.y, 2 * r + 1, 1), c)
		draw_rect(Rect2(lp.x, lp.y - r, 1, 2 * r + 1), c)
		draw_rect(Rect2(lp.x - 1, lp.y - 1, 3, 3), c)
