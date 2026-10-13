extends RichTextEffect
## Weiches Einblenden Zeichen für Zeichen: [reveal]…[/reveal]. Jedes Zeichen blendet in `ramp` Sekunden
## ein und hebt sich dabei um 3 px; Zeitpunkt aus `start` und `cps`. Die Zeit `t` setzt das Skript der Oberfläche.

var bbcode := "reveal"
var t := 0.0
var start := 0.0
var cps := 45.0
var ramp := 0.28


func _process_custom_fx(char_fx: CharFXTransform) -> bool:
	var appear := start + float(char_fx.relative_index) / cps
	var a := clampf((t - appear) / ramp, 0.0, 1.0)
	a = a * a * (3.0 - 2.0 * a)
	char_fx.color.a *= a
	char_fx.offset = Vector2(0.0, round((1.0 - a) * 3.0))
	return true
