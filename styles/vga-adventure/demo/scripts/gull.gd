extends Node2D
## Möwe: zwei Flügelstellungen als Pixelmuster, fliegt von rechts nach links über den Himmel.

const UP := ["X.......X", ".XX...XX.", "...XXX..."]
const DOWN := ["...XXX...", ".XX...XX.", "X.......X"]
const GLIDE := ["XXX...XXX", "...XXX..."]

@onready var main: Node = get_parent()


func _draw() -> void:
	var t: float = main.t
	var x := roundi(276.0 - 24.0 * t)
	var y := roundi(50.0 + 3.0 * sin(t * 1.6))
	var phase := int(floor(t * 5.0)) % 4
	var pat: Array = UP if phase == 0 else (DOWN if phase == 2 else GLIDE)
	var col: Color = main.color(int(main.meta["ui_colors"]["weiss"]))
	for row in pat.size():
		var line: String = pat[row]
		for i in line.length():
			if line[i] == "X":
				draw_rect(Rect2(x + i, y + row, 1, 1), col)
