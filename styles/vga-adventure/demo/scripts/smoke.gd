extends Node2D
## Rauch aus dem Schornstein aus handgesetzten Puff-Sprites in den 4 Rauchfarben der Palette (40..43),
## deterministisch aus der Zeit berechnet. Jedes Wölkchen ist ein kleines Pixelmuster mit drei Tönen:
## H = helle Kante oben links, B = Körper, S = dunklere Unterkante rechts. Mit dem Alter wächst das Wölkchen
## über vier Stufen (klein, mittel, groß, zerfallend) und rückt in den Tönen eine Stufe dunkler, bis es fast
## die Himmelsfarbe hat. Der Wind biegt die Fahne nach rechts (passt zur Zeile "Die Laterne flackert im Wind").
## Erste Fassung waren einfarbige Scheiben (draw_rect je Pixel aus einem Kreis) und wirkte wie Programmierergrafik.
## Zweite Fassung stieg mit 11 px/s und lief nach etwa 2,5 s noch hell über den oberen Bildrand; jetzt steigt der
## Rauch langsamer, biegt stärker mit dem Wind ab und zerfällt vollständig im Bild (Mitte bleibt bei y >= 3).

const ORIGIN := Vector2(22.5, 19.0)   # Mitte des jüngsten Wölkchens am Schornsteintopf (Topf ab y=20, x 19..26); es quillt über den Rand
const PERIOD := 0.5
const LIFE := 3.0
# Altersgrenzen der vier Sprite-Stufen und der Tonverschiebung (Sekunden)
const STAGE_AT := [0.0, 0.35, 1.0, 1.9]
const TONE_AT := [0.0, 1.2, 2.3]
const RISE := 9.0                   # Steiggeschwindigkeit (px/s), wird aus dem Stand erreicht ...
const RISE_TAU := 0.4               # ... mit dieser Zeitkonstante: das Wölkchen quillt erst am Topf auf

# Puff-Sprites, je Stufe zwei Varianten. Gezeichnet auf 320x200; Lichtkante oben links wie beim Hintergrund.
const PUFFS := [
	[
		[".HB.",
		 "HBBS",
		 ".SS."],
		["..H.",
		 ".HBB",
		 "HBBS",
		 ".SS."],
	],
	[
		[".HHB..",
		 "HBBBBS",
		 "BBBBSS",
		 ".SSS.."],
		["..HH..",
		 ".HBBB.",
		 "HBBBBS",
		 ".BBBSS",
		 "..SS.."],
	],
	[
		["..HHH....",
		 ".HBBBHH..",
		 "HBBBBBBB.",
		 "HBBBBBBSS",
		 ".BBBBSSS.",
		 "...SSS..."],
		["...HH...",
		 "..HBBH..",
		 ".HBBBBB.",
		 "HBBBBBBS",
		 "BBBBBSS.",
		 ".SSSS..."],
	],
	[
		["...HH.....",
		 ".HHBB.HB..",
		 "HBB.BBBBB.",
		 ".BBBB.BBS.",
		 "..BSS.SS..",
		 "....S....."],
		["....H......",
		 ".H.HBB..H..",
		 "HB.BBBB.BB.",
		 ".BBB.BBBBS.",
		 "..B.SBB.S..",
		 "...S...S..."],
	],
]

@onready var main: Node = get_parent()


func _stage(age: float, limits: Array) -> int:
	var s := 0
	for k in limits.size():
		if age >= float(limits[k]):
			s = k
	return s


func _draw() -> void:
	var t: float = main.t + LIFE      # vorgewärmt: bei t=0 steht schon eine Rauchfahne
	var first := int(floor((t - LIFE) / PERIOD))
	var last := int(floor(t / PERIOD))
	var smoke0: int = int(main.meta["ranges"]["smoke"][0])
	for i in range(first, last + 1):   # älteste zuerst, junge Wölkchen liegen vorn
		var age := t - i * PERIOD
		if age < 0.0 or age > LIFE:
			continue
		var rng := RandomNumberGenerator.new()
		rng.seed = 5000 + i
		var variant := rng.randi_range(0, 1)
		var jx := rng.randf_range(-0.9, 0.9)
		var stage := _stage(age, STAGE_AT)
		var tone := _stage(age, TONE_AT)
		var x := ORIGIN.x + age * 2.0 + age * age * 2.4 + sin(age * 2.1 + i * 1.3) * 0.7 + jx * age * 0.6
		var rise := RISE * age - RISE * RISE_TAU * (1.0 - exp(-age / RISE_TAU))
		var y := ORIGIN.y - rise + age * age * 0.9   # der Wind drückt die Fahne flach
		var pat: Array = PUFFS[stage][variant]
		var cols := {
			"H": main.color(smoke0 + tone) as Color,
			"B": main.color(smoke0 + mini(tone + 1, 3)) as Color,
			"S": main.color(smoke0 + mini(tone + 2, 3)) as Color,
		}
		var w: int = String(pat[0]).length()
		var h: int = pat.size()
		var x0 := roundi(x - w / 2.0)
		var y0 := roundi(y - h / 2.0)
		for row in h:
			var line: String = pat[row]
			for col in w:
				var ch := line[col]
				if cols.has(ch):
					draw_rect(Rect2(x0 + col, y0 + row, 1, 1), cols[ch])
