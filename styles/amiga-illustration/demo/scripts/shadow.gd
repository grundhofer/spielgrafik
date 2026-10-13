extends Node2D
## Kontaktschatten des Dachses als Blitter-Objekt: zwei Zeilen Schachbrett in einem dunklen Bildregister (wie bei
## 32 Farben ohne Transparenz), in der Sohlenzeile 2 px breiter als die Füße, darunter so breit wie die Füße.
## Raster fest am Bildschirm ((x + y) gerade), damit das Muster beim Laufen nicht mit der Figur wandert.

@onready var main: Node = get_node("../../..")


func _draw() -> void:
	var m: Dictionary = main.meta
	if not m.has("shadow"):
		return
	var bj: Dictionary = main.bj
	var frames: Array = bj["frames"]
	var k := mini(int(floor(main.t * float(bj["fps"]) + 1e-4)), frames.size() - 1)
	var fr: Dictionary = frames[k]
	if not fr.has("feet"):
		return
	var col: Color = main.reg(int(m["shadow"]))
	var left := int(m["stop_x"]) + int(fr["left"])
	var x0 := left + int(fr["feet"][0])
	var x1 := left + int(fr["feet"][1])
	var y := int(m["feet_line"]) - 1
	for row in [[y, 2], [y + 1, 0]]:
		var yy: int = row[0]
		var ext: int = row[1]
		for x in range(x0 - ext, x1 + ext + 1):
			if (x + yy) % 2 == 0:
				draw_rect(Rect2(x, yy, 1, 1), col)
