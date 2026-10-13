extends Node2D
## Abdunkeln der Szene nur in der Einblendung (visibility_layer 2), damit Figur und Linien hervortreten.

func _draw() -> void:
	draw_rect(Rect2(-200, -200, 1680, 1120), Color(0.03, 0.04, 0.08, 0.66))
