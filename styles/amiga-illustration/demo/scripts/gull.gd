extends Node2D
## Möwe als kleines Blitter-Objekt (3 Flügelstellungen, 7x3 Pixel), fliegt langsam vor dem Abendhimmel.
## W = Körper (hellstes Register), L = Flügel (hellgrau), D = dunkle Flügelspitzen.

const SHAPES := [
	["L.....L", ".L...L.", "..LWL.."],    # Flügel oben
	[".......", "DLLWLLD", "......."],    # waagrecht
	["..LWL..", ".L...L.", "D.....D"],    # unten
]

@onready var main: Node = get_node("../../..")


func _draw() -> void:
	var m: Dictionary = main.meta
	if not m.has("gull"):
		return
	var regs: Array = m["gull"]
	var cols := {"W": main.reg(int(regs[0])), "L": main.reg(int(regs[1])), "D": main.reg(int(regs[2]))}
	var tt: float = main.t
	var x := roundi(float(m.get("gull_x0", 300)) - 16.0 * tt)
	var y := roundi(float(m["gull_y"]) + 2.5 * sin(tt * 1.3))
	var phase := int(floor(tt * 6.0)) % 4
	var shape: Array = SHAPES[[0, 1, 2, 1][phase]]
	for r in shape.size():
		var row: String = shape[r]
		for c in row.length():
			var ch := row[c]
			if cols.has(ch):
				draw_rect(Rect2(x + c, y + r, 1, 1), cols[ch])
