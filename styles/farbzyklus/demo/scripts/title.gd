extends Node2D
## Ortsname in Jacquarda Bastarda 9 (Pixel-Bastarda, ohne Kantenglättung). Die Farbe setzt ui_cycle.gdshader aus
## der rotierenden Goldrampe der Palette (Einträge 4..9): echter Farbzyklus in der Oberfläche.

const TITLE := "Hafen von Lornholm"
const SIZE := 13
var font: FontFile


func setup(c: Cycler, f: FontFile) -> void:
	font = f
	material.set_shader_parameter("palette_tex", c.texture)
	queue_redraw()


func _draw() -> void:
	if font == null:
		return
	draw_string(font, Vector2(8, 17), TITLE, HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE, Color.WHITE)
