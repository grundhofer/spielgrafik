extends Node2D
## Rauch aus dem Schornstein: Ballen aus ganzen Pixeln, steigen auf und treiben nach rechts.
## Rein aus der Zeit berechnet (keine Partikel-Zufälle), daher in jeder Aufnahme gleich.

const ORIGIN := Vector2(24, 8)      # Schornstein (Häuschen-Fußpunkt 54, 84)
const EVERY := 0.42      # neuer Ballen alle 0,42 s
const LIFE := 2.6
var t := 0.0


func set_time(v: float) -> void:
	t = v
	queue_redraw()


func _draw() -> void:
	var first := int(floor((t - LIFE) / EVERY)) + 1
	var last := int(floor(t / EVERY))
	for i in range(maxi(first, -10), last + 1):
		var age := t - i * EVERY
		if age < 0.0 or age > LIFE:
			continue
		var u := age / LIFE
		var wob := sin(i * 1.7 + age * 2.0) * 1.5
		var p := ORIGIN + Vector2(age * 12.0 + wob, -age * 4.5)   # Wind von links
		var r := 1.0 + u * 3.5
		var a := 0.9 * (1.0 - u * u)
		var col := Color(1.0, 1.0, 1.0, a)
		_disc(p.round(), roundi(r), col)


func _disc(c: Vector2, r: int, col: Color) -> void:
	for y in range(-r, r + 1):
		var w := int(floor(sqrt(float(r * r - y * y)) + 0.35))
		draw_rect(Rect2(c.x - w, c.y + y, 2 * w + 1, 1), col)
