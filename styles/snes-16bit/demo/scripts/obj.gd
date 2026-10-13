extends Node2D
## Sprite-Ebene (OBJ): zeichnet die OAM-Liste aus main.gd. Wie auf der Konsole hat der Eintrag mit dem
## kleineren Index Vorrang: gezeichnet wird von hinten nach vorn. Alle Sprite-Grafiken liegen in
## art/sprites.png und benutzen nur Farben ihrer OBJ-Palette (build_sprites.py); Positionen sind ganzzahlig.

var atlas: Texture2D = preload("res://art/sprites.png")
@onready var main: Node2D = get_parent()


func _draw() -> void:
	var oam: Array = main.oam
	for i in range(oam.size() - 1, -1, -1):
		var e: Dictionary = oam[i]
		var r: Rect2i = e["rect"]
		if e.get("flip", false):
			# H-Flip-Bit: Sprite gespiegelt, Zelle bleibt an derselben Stelle
			draw_set_transform(Vector2(e["x"] + r.size.x, e["y"]), 0.0, Vector2(-1, 1))
			draw_texture_rect_region(atlas, Rect2(Vector2.ZERO, Vector2(r.size)), Rect2(r))
			draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
		else:
			draw_texture_rect_region(atlas, Rect2(Vector2(e["x"], e["y"]), Vector2(r.size)), Rect2(r))
