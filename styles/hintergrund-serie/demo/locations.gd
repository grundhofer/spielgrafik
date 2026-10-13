extends RefCounted
## Daten der vier Orte (Lage der Lichter, Rauch, Glanzlichter usw. in Bildschirmpixeln 1280x720).
## Gemessen in den geschnittenen Hintergründen demo/art/bg_*.png (Codex-Bilder, Schnitt laut prep.py CROP_TOP,
## Horizont überall auf Zeile 256); tools/lights.py hat Kandidaten vorgeschlagen, die Lagen sind im Bild geprüft.

const NAMES := {
	"hafen": "Hafen von Lornholm",
	"leuchtturm": "Im Leuchtturm",
	"stube": "Stube des Hafenmeisters",
	"klippe": "Klippenpfad",
}

const LOCATIONS := {
	"hafen": {
		"glows": [
			# Fenster des Hafenmeisterhäuschens, Laterne am Pfosten, Fenster am Leuchtturmhaus
			{"pos": Vector2(99, 238), "size": 130.0, "alpha": 0.32, "flicker": 0.12},
			{"pos": Vector2(274, 222), "size": 150.0, "alpha": 0.55, "flicker": 0.35},
			{"pos": Vector2(1189, 140), "size": 34.0, "alpha": 0.45, "flicker": 0.1},
			{"pos": Vector2(1216, 140), "size": 30.0, "alpha": 0.45, "flicker": 0.1},
		],
		# Kein Rauch: Die Schornsteinkrone liegt über dem Bildrand (Schnitt für die Leuchtturmlampe), ein Versuch
		# mit Rauch am oberen Rand war vor dem blaugrauen Himmel nicht zu sehen.
		"beams": [{"pos": Vector2(1149, 27), "period": 6.0, "phase": 2.2, "length": 640.0, "width": 64.0,
			"alpha": 0.32, "flare_size": 80.0, "flare_alpha": 0.85}],
		"glints": [
			{"rect": Rect2(250, 262, 300, 40), "count": 14},     # Abendrot auf dem Wasser
			{"rect": Rect2(600, 262, 360, 20), "count": 8},
			{"rect": Rect2(1110, 320, 80, 120), "count": 7, "size": 0.8},   # Spiegelung der Leuchtturmlampe
		],
		"gulls": [
			{"from": Vector2(380, 70), "to": Vector2(980, 40), "duration": 11.0, "phase": 0.08},
			{"from": Vector2(860, 110), "to": Vector2(420, 90), "duration": 14.0, "phase": 0.3, "scale": 0.4},
		],
		# Dachs auf der Oberkante der Kaimauer (Poller stehen dort mit dem Fuß bei 492); hält vor dem Steg an
		"badger": {"stop_x": 520.0, "feet_y": 492.0, "walk_time": 1.7, "fps": 10.0, "shadow_w": 86.0,
			"tint": Color(0.84, 0.8, 0.9)},
	},
	"leuchtturm": {
		"glows": [
			{"pos": Vector2(380, 115), "size": 420.0, "alpha": 0.28, "flicker": 0.05},
			{"pos": Vector2(330, 470), "size": 360.0, "alpha": 0.1, "flicker": 0.05, "squash": 0.35},
		],
		# Linse dreht sich: ein heller Streifen wandert über das Glas, ein Lichtfleck über die Wand rechts
		"sweeps": [
			{"pos": Vector2(380, 110), "half_width": 80.0, "period": 3.0, "phase": 0.0, "alpha": 0.5,
				"w": 60.0, "h": 220.0},
			{"pos": Vector2(780, 220), "half_width": 260.0, "period": 3.0, "phase": 0.0, "alpha": 0.3,
				"w": 180.0, "h": 300.0},
		],
		"motes": [{"rect": Rect2(250, 40, 300, 380), "count": 16}],
	},
	"stube": {
		"glows": [
			{"pos": Vector2(110, 385), "size": 440.0, "alpha": 0.38, "flicker": 0.45},
			{"pos": Vector2(230, 480), "size": 520.0, "alpha": 0.2, "flicker": 0.45, "squash": 0.4},  # Feuerschein am Boden
			{"pos": Vector2(527, 292), "size": 120.0, "alpha": 0.4, "flicker": 0.25},
			{"pos": Vector2(928, 186), "size": 26.0, "alpha": 0.6, "flicker": 0.3},   # Leuchtturm im Fenster
		],
		# Flammen additiv: auf der gemalten Glut (schon orange) wären deckende Flammen kaum zu sehen
		"flames": [
			{"pos": Vector2(76, 410), "height": 44.0, "add": true, "alpha": 0.85},
			{"pos": Vector2(116, 412), "height": 56.0, "add": true, "alpha": 0.85},
			{"pos": Vector2(156, 410), "height": 40.0, "add": true, "alpha": 0.85},
			{"pos": Vector2(527, 302), "height": 18.0},      # Kerze auf dem Tisch
		],
	},
	"klippe": {
		"glows": [
			{"pos": Vector2(170, 334), "size": 44.0, "alpha": 0.4, "flicker": 0.15},
			{"pos": Vector2(210, 318), "size": 36.0, "alpha": 0.4, "flicker": 0.15},
			{"pos": Vector2(242, 333), "size": 36.0, "alpha": 0.4, "flicker": 0.15},
			{"pos": Vector2(280, 342), "size": 36.0, "alpha": 0.4, "flicker": 0.15},
			{"pos": Vector2(308, 336), "size": 44.0, "alpha": 0.4, "flicker": 0.15},
		],
		"beams": [{"pos": Vector2(1166, 128), "period": 6.0, "phase": 2.0, "length": 420.0, "width": 40.0,
			"alpha": 0.3, "flare_size": 46.0, "flare_alpha": 0.85}],
		"glints": [{"rect": Rect2(420, 262, 320, 60), "count": 14}],
		"gulls": [{"from": Vector2(900, 90), "to": Vector2(300, 140), "duration": 12.0, "phase": 0.35}],
	},
}
