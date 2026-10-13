extends Node2D
## Rauch aus dem Schornstein als Blitter-Objekte in Bildregistern: Wölkchen mit hellem Kern und
## geditherter Kante; mit dem Alter nur noch Schachbrett und dann jedes vierte Pixel (gedithertes Ausblenden
## wie bei 32 Farben ohne Transparenz). Ganze Pixel, deterministisch aus der Zeit.

const EVERY := 0.38             # neues Wölkchen alle ... s
const LIFE := 3.6
const RISE := 2.2               # px/s nach oben (Schornstein sitzt im Hafenbild nur 6 Zeilen unter der Oberkante)
const DRIFT := 9.0              # px/s nach rechts (Wind drückt die Fahne flach über das Dach)

@onready var main: Node = get_node("../../..")


func _keep(x: int, y: int, level: int) -> bool:
	## level 0: alle Pixel, 1: Schachbrett, 2: jedes vierte Pixel
	if level == 0:
		return true
	if level == 1:
		return (x + y) % 2 == 0
	return x % 2 == 0 and y % 2 == 0


func _puff(cx: int, cy: int, r: float, core: Color, edge: Color, level: int) -> void:
	var ri := int(ceil(r))
	for dy in range(-ri, ri + 1):
		for dx in range(-ri, ri + 1):
			var d2 := dx * dx + dy * dy
			if d2 > r * r:
				continue
			var x := cx + dx
			var y := cy + dy
			var inner := d2 <= r * r * 0.35
			var lv := level if inner else mini(level + 1, 2)
			if _keep(x, y, lv):
				draw_rect(Rect2(x, y, 1, 1), core if inner else edge)


func _draw() -> void:
	var m: Dictionary = main.meta
	if not m.has("smoke"):
		return
	var regs: Array = m["smoke"]
	var c0 := Vector2(m["chimney_xy"][0], m["chimney_xy"][1])
	var tt: float = main.t + LIFE           # beim Start steht schon eine Fahne
	var light: Color = main.reg(int(regs[0]))
	var mid: Color = main.reg(int(regs[1]))
	for k in range(int(floor((tt - LIFE) / EVERY)), int(floor(tt / EVERY)) + 1):
		var age := tt - k * EVERY
		if age < 0.0 or age > LIFE:
			continue
		var wob := sin(k * 1.7 + age * 2.0) * 1.0
		var x := roundi(c0.x + DRIFT * age + wob + age * age * 0.6)
		var y := roundi(c0.y - RISE * age - 1.0 + sin(k * 2.3) * 0.6)
		var r := 1.3 + age * 1.0
		var level := 0 if age < 1.0 else (1 if age < 2.3 else 2)
		_puff(x, y, r, light if age < 1.6 else mid, mid, level)
