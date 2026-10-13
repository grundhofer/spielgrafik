extends RefCounted
## Hafen von Lornholm als Vektorbühne 550×400 (Koordinaten der Bühne, y nach unten).
## build() legt alle Formen als Polygon2D an und gibt die animierten Teile zurück.

const V = preload("res://vec.gd")
const M = preload("res://morph.gd")

const HORIZON := 172.0
const QUAY := 284.0


static func C(hex: String) -> Color:
	return Color(hex)


static func build(stage: Node2D) -> Dictionary:
	var R := {}
	_sky(stage, R)
	_sea(stage, R)
	_headland(stage, R)
	_boats_and_jetty(stage, R)
	_cottage(stage, R)
	_quay(stage, R)
	_props(stage, R)
	return R


# ------------------------------------------------------------------ Himmel
static func _sky(stage: Node2D, R: Dictionary) -> void:
	var g := V.group(stage, "Sky")
	V.fill(g, PackedVector2Array([Vector2(-4, -4), Vector2(554, -4), Vector2(554, HORIZON + 2), Vector2(-4, HORIZON + 2)]),
		{"lin": [[0.0, C("1c1745")], [0.36, C("3a2b6f")], [0.64, C("8b3f86")], [0.85, C("e2667a")], [1.0, C("ffb560")]],
		 "from": Vector2(0, 0), "to": Vector2(0, HORIZON)}, "SkyGradient")
	# Sterne: vierzackige Funkel-Formen (eine Form, beim Funkeln skaliert)
	var stars := []
	for s in [[Vector2(38, 22), 3.2], [Vector2(118, 46), 2.4], [Vector2(196, 16), 3.6], [Vector2(262, 58), 2.2],
			[Vector2(318, 26), 3.0], [Vector2(372, 12), 2.4], [Vector2(408, 52), 2.0], [Vector2(152, 92), 1.8]]:
		var sg := V.group(g, "Star", s[0])
		var r: float = s[1]
		var pts := PackedVector2Array()
		for i in 8:
			var a := TAU * i / 8.0 - PI / 2
			var rr := r if i % 2 == 0 else r * 0.28
			pts.append(Vector2(cos(a), sin(a)) * rr)
		V.fill(sg, pts, C("fff3c4"))
		stars.append(sg)
	R["stars"] = stars
	# Wolken: eine Form je Wolke, unten vom Abendlicht angestrahlt (helle Form statt Verlauf)
	var clouds := []
	for c in [[Vector2(92, 72), 1.0], [Vector2(318, 98), 1.25], [Vector2(214, 140), 0.7]]:
		var cg := V.group(g, "Cloud", c[0])
		var k: float = c[1]
		var body := []
		for p in [Vector2(-52, 6), Vector2(-46, -4), Vector2(-30, -8), Vector2(-22, -18), Vector2(-4, -20), Vector2(8, -12),
				Vector2(22, -16), Vector2(38, -8), Vector2(54, 0), Vector2(50, 7), Vector2(0, 9)]:
			body.append(p * Vector2(k, 0.9 if k < 0.9 else 1.0))
		var poly := V.smooth(body, true, 8)
		V.fill(cg, poly, C("6b4383"))
		var lit := []
		for p in [Vector2(-48, 5), Vector2(-30, 1), Vector2(-6, 2), Vector2(20, 0), Vector2(46, 2), Vector2(50, 7), Vector2(0, 9.5), Vector2(-46, 8)]:
			lit.append(p * Vector2(k, 1.0))
		V.fill(cg, V.smooth(lit, true, 6), C("ee8a82"))
		var hi := []
		for p in [Vector2(-26, -10), Vector2(-14, -16), Vector2(-4, -16), Vector2(-14, -12)]:
			hi.append(p * Vector2(k, 1.0))
		V.fill(cg, V.smooth(hi, true, 6), C("8a5a9c"))
		V.ink(cg, poly, 1.2, 0.35, [], C("2a1c46"))
		clouds.append(cg)
	R["clouds"] = clouds
	# Strahl des Leuchtturms (hinter dem Turm, additiv), dreht über scale.x
	var beam_pivot := V.group(stage, "BeamPivot", Vector2(486, 38))
	var beam := PackedVector2Array([Vector2(0, -3), Vector2(-250, -24), Vector2(-250, 22), Vector2(0, 3)])
	var bp := V.fill(beam_pivot, beam, {"lin": [[0.0, Color(1, 0.93, 0.62, 0.55)], [0.55, Color(1, 0.85, 0.55, 0.22)], [1.0, Color(1, 0.8, 0.5, 0.0)]],
		"from": Vector2(0, 0), "to": Vector2(-250, 0)}, "Beam")
	V.add_glow(bp)
	R["beam"] = beam_pivot
	# ferne Inseln am Horizont
	var isl := V.group(stage, "Islands")
	for pts in [[Vector2(118, HORIZON + 1), Vector2(146, HORIZON - 7), Vector2(178, HORIZON - 13), Vector2(214, HORIZON - 9),
				Vector2(250, HORIZON - 4), Vector2(268, HORIZON + 1)],
			[Vector2(330, HORIZON + 1), Vector2(346, HORIZON - 5), Vector2(366, HORIZON - 6), Vector2(384, HORIZON + 1)]]:
		var poly := V.smooth(pts, false, 8)
		poly.append(Vector2(pts[-1].x, HORIZON + 2))
		poly.append(Vector2(pts[0].x, HORIZON + 2))
		V.fill(isl, poly, C("4a3271"))
		var top := V.smooth(pts, false, 8)
		V.stroke(isl, top, 1.1, 0.25, 0.25, 0.0, C("281b45"))


# ------------------------------------------------------------------ Meer
static func _sea(stage: Node2D, R: Dictionary) -> void:
	var g := V.group(stage, "Sea")
	V.fill(g, PackedVector2Array([Vector2(-4, HORIZON), Vector2(554, HORIZON), Vector2(554, 304), Vector2(-4, 304)]),
		{"lin": [[0.0, C("d47a8e")], [0.1, C("6c4f9c")], [0.42, C("353b86")], [1.0, C("1c1e50")]],
		 "from": Vector2(0, HORIZON), "to": Vector2(0, 304)}, "SeaGradient")
	V.stroke(g, PackedVector2Array([Vector2(-4, HORIZON), Vector2(554, HORIZON)]), 1.2, 0.0, 0.0, 1.0, C("2a1c46"))
	# Sonnenspiegelung: waagrechte Pillen, die per Form-Tween länger und kürzer werden
	var streaks := []
	var specs := [[Vector2(236, 180), 30.0, 2.6], [Vector2(222, 189), 44.0, 2.4], [Vector2(244, 198), 26.0, 2.2],
		[Vector2(214, 208), 36.0, 2.0], [Vector2(240, 219), 22.0, 1.8], [Vector2(226, 231), 30.0, 1.6]]
	for i in specs.size():
		var s = specs[i]
		var c: Vector2 = s[0]
		var L: float = s[1]
		var h: float = s[2]
		var dx := 6.0 if i % 2 == 0 else -6.0
		var ka := [c + Vector2(-L * 0.5, 0), c + Vector2(0, -h * 0.5), c + Vector2(L * 0.5, 0), c + Vector2(0, h * 0.5)]
		var kb := [c + Vector2(-L * 0.35 + dx, 0), c + Vector2(dx, -h * 0.45), c + Vector2(L * 0.62 + dx, 0), c + Vector2(dx, h * 0.45)]
		var m = M.make_shape(g, ka, kb, Color(1.0, 0.78, 0.5, 0.85 - i * 0.09), 0.0, 6)
		streaks.append(m)
	R["streaks"] = streaks
	# Wellenkämme: spitz auslaufende Bögen, Form-Tween zwischen flach und gekrümmt
	var waves := []
	var rng := RandomNumberGenerator.new()
	rng.seed = 4711
	var rows := [[190.0, 0.55, 14.0], [206.0, 0.7, 18.0], [226.0, 0.85, 22.0], [252.0, 1.0, 26.0], [274.0, 1.0, 28.0]]
	for row in rows:
		var y: float = row[0]
		var k: float = row[1]
		var L: float = row[2]
		var x := rng.randf_range(130, 160)
		while x < 400:
			var c := Vector2(x, y + rng.randf_range(-2, 2))
			var ka := [c + Vector2(-L * 0.5, 1.5 * k), c + Vector2(-L * 0.15, -1.2 * k), c + Vector2(L * 0.2, -1.6 * k), c + Vector2(L * 0.5, 0.5 * k)]
			var kb := [c + Vector2(-L * 0.4 + 3, 0.6 * k), c + Vector2(-L * 0.05 + 3, -2.6 * k), c + Vector2(L * 0.3 + 3, -2.2 * k), c + Vector2(L * 0.6 + 3, 1.2 * k)]
			var m = M.make_stroke(g, ka, kb, 1.5 * k + 0.3, Color(0.72, 0.78, 1.0, 0.75), 6, 0.45, 0.45)
			waves.append(m)
			x += L + rng.randf_range(20, 46)
	R["waves"] = waves


# ------------------------------------------------------------------ Felsnase mit Leuchtturm
static func _headland(stage: Node2D, R: Dictionary) -> void:
	var g := V.group(stage, "Headland")
	var rock := [Vector2(560, 106), Vector2(528, 104), Vector2(500, 110), Vector2(474, 114), Vector2(452, 124),
		Vector2(440, 142), Vector2(428, 164), Vector2(414, 190), Vector2(404, 218), Vector2(396, 248), Vector2(392, 276),
		Vector2(404, 290), Vector2(470, 294), Vector2(560, 294)]
	var poly := V.smooth(rock, true, 8)
	V.fill(g, poly, C("56466f"))
	# Schattenflächen (flach, ohne Kontur)
	for sh in [[Vector2(470, 160), Vector2(500, 150), Vector2(560, 150), Vector2(560, 294), Vector2(480, 294), Vector2(462, 250), Vector2(476, 210)],
			[Vector2(420, 230), Vector2(436, 226), Vector2(440, 262), Vector2(430, 292), Vector2(404, 290), Vector2(398, 270)]]:
		V.fill(g, V.smooth(sh, true, 6), C("3b3054"))
	# Lichtkanten oben links
	for hl in [[Vector2(446, 136), Vector2(458, 124), Vector2(470, 122), Vector2(456, 134), Vector2(444, 156)],
			[Vector2(414, 200), Vector2(424, 182), Vector2(430, 184), Vector2(420, 204), Vector2(408, 236)]]:
		V.fill(g, V.smooth(hl, true, 6), C("7b6996"))
	# Facettenlinien (Pinselstriche mit spitzen Enden)
	for ln in [[Vector2(452, 150), Vector2(466, 176), Vector2(462, 206)], [Vector2(426, 214), Vector2(446, 222), Vector2(458, 246)],
			[Vector2(486, 170), Vector2(506, 196), Vector2(498, 230), Vector2(512, 262)], [Vector2(420, 262), Vector2(440, 268), Vector2(452, 290)],
			[Vector2(520, 130), Vector2(536, 160), Vector2(530, 186)]]:
		V.stroke(g, V.smooth(ln, false, 6), 1.5, 0.4, 0.4)
	# Grasdecke oben
	var grass := [Vector2(560, 100), Vector2(530, 98), Vector2(500, 104), Vector2(472, 108), Vector2(450, 118), Vector2(444, 128),
		Vector2(456, 126), Vector2(466, 132), Vector2(478, 124), Vector2(492, 130), Vector2(508, 122), Vector2(524, 128), Vector2(540, 120), Vector2(560, 126)]
	var gp := V.smooth(grass, true, 6)
	V.fill(g, gp, C("2f5a4c"))
	V.fill(g, V.smooth([Vector2(458, 116), Vector2(476, 108), Vector2(500, 106), Vector2(490, 112), Vector2(470, 116)], true, 6), C("4d7f5f"))
	V.ink(g, gp, 1.6, 0.4)
	V.ink(g, poly, 2.2, 0.4, [0.62])
	# Felsbrocken an der Wasserlinie
	for bo in [[Vector2(401, 279), 13.0, 9.0, C("5d4c78")], [Vector2(424, 281), 11.0, 6.0, C("4d3e66")]]:
		var c: Vector2 = bo[0]
		var rx: float = bo[1]
		var ry: float = bo[2]
		var bp := V.smooth([c + Vector2(-rx, 2), c + Vector2(-rx * 0.8, -ry * 0.7), c + Vector2(-rx * 0.1, -ry), c + Vector2(rx * 0.7, -ry * 0.75),
			c + Vector2(rx, 2)], false, 6)
		bp.append(c + Vector2(rx, 4))
		bp.append(c + Vector2(-rx, 4))
		V.fill(g, bp, bo[3])
		V.fill(g, V.smooth([c + Vector2(-rx * 0.6, -ry * 0.5), c + Vector2(-rx * 0.1, -ry * 0.85), c + Vector2(rx * 0.2, -ry * 0.8), c + Vector2(-rx * 0.2, -ry * 0.55)], true, 5), C("7b6996"))
		V.stroke(g, V.smooth([c + Vector2(-rx, 2), c + Vector2(-rx * 0.8, -ry * 0.7), c + Vector2(-rx * 0.1, -ry), c + Vector2(rx * 0.7, -ry * 0.75), c + Vector2(rx, 2)], false, 6), 1.7, 0.2, 0.2, 0.3)
		V.stroke(g, PackedVector2Array([c + Vector2(-rx - 3, 2.5), c + Vector2(rx + 4, 2.5)]), 1.2, 0.3, 0.3, 0.0, Color(0.75, 0.8, 1.0, 0.8))
	# Leuchtturm
	var lh := V.group(stage, "Lighthouse")
	var tower := V.rpoly([Vector2(470, 116), Vector2(475, 50), Vector2(497, 50), Vector2(502, 116)], [2, 1, 1, 2])
	V.fill(lh, tower, C("f2ede4"))
	V.fill(lh, PackedVector2Array([Vector2(489, 50), Vector2(497, 50), Vector2(502, 116), Vector2(492, 116)]), C("c3b9d3"))
	var band := PackedVector2Array([Vector2(473.2, 74), Vector2(498.8, 74), Vector2(499.9, 88), Vector2(472.1, 88)])
	V.fill(lh, band, C("d3343c"))
	V.fill(lh, PackedVector2Array([Vector2(490.4, 74), Vector2(498.8, 74), Vector2(499.9, 88), Vector2(491.2, 88)]), C("9e2430"))
	V.stroke(lh, PackedVector2Array([Vector2(473.2, 74), Vector2(498.8, 74)]), 1.0, 0.2, 0.2, 0.3)
	V.stroke(lh, PackedVector2Array([Vector2(472.1, 88), Vector2(499.9, 88)]), 1.0, 0.2, 0.2, 0.3)
	V.fill(lh, V.rpoly([Vector2(483, 116), Vector2(483, 104), Vector2(489, 104), Vector2(489, 116)], [0, 3, 3, 0]), C("2b2537"))
	V.fill(lh, V.rpoly([Vector2(484.5, 60), Vector2(487.5, 60), Vector2(487.5, 66), Vector2(484.5, 66)], 1.2), C("2b2537"))
	V.fill(lh, V.rpoly([Vector2(484.5, 94), Vector2(487.5, 94), Vector2(487.5, 99), Vector2(484.5, 99)], 1.2), C("2b2537"))
	V.ink(lh, tower, 1.8, 0.4)
	# Galerie, Laternenraum, Haube
	V.shape(lh, V.rpoly([Vector2(468, 46), Vector2(504, 46), Vector2(504, 51), Vector2(468, 51)], 1.0), C("2b2537"), 1.2)
	for x in [471.0, 477.0, 483.0, 489.0, 495.0, 501.0]:
		V.stroke(lh, PackedVector2Array([Vector2(x, 41), Vector2(x, 46)]), 0.9, 0.0, 0.0, 1.0)
	V.stroke(lh, PackedVector2Array([Vector2(469, 41.5), Vector2(503, 41.5)]), 1.0, 0.1, 0.1, 0.5)
	var glass := V.rpoly([Vector2(477, 30), Vector2(495, 30), Vector2(495, 46), Vector2(477, 46)], 1.0)
	V.fill(lh, glass, C("ffe27a"))
	V.fill(lh, V.rpoly([Vector2(479, 32), Vector2(482, 32), Vector2(480.5, 44), Vector2(478.6, 44)], 0.6), C("fffbe6"))
	V.stroke(lh, PackedVector2Array([Vector2(486, 30), Vector2(486, 46)]), 0.9, 0.0, 0.0, 1.0)
	V.ink(lh, glass, 1.3, 0.5)
	var cap := V.smooth([Vector2(474, 31), Vector2(478, 23), Vector2(486, 19), Vector2(494, 23), Vector2(498, 31)], false, 6)
	cap.append(Vector2(498, 31))
	V.fill(lh, cap, C("c33540"))
	V.fill(lh, V.smooth([Vector2(479, 26), Vector2(484, 21.5), Vector2(488, 21), Vector2(483, 25)], true, 4), C("e86a6e"))
	V.ink(lh, cap, 1.4, 0.4)
	V.shape(lh, V.ellipse(Vector2(486, 17), 2.2, 2.2, 16), C("2b2537"), 0.8)
	# Lampenschein (additiv, pulsiert)
	var lamp := V.group(stage, "LampGlow", Vector2(486, 38))
	var lg := V.fill(lamp, V.ellipse(Vector2.ZERO, 30, 30, 40), {"rad": [[0.0, Color(1, 0.95, 0.7, 0.9)], [0.35, Color(1, 0.85, 0.45, 0.45)], [1.0, Color(1, 0.7, 0.3, 0.0)]],
		"c": Vector2.ZERO, "r": Vector2(30, 30)})
	V.add_glow(lg)
	R["lamp"] = lamp
	R["lighthouse_hotspot"] = Vector2(486, 60)


# ------------------------------------------------------------------ Steg und Boote
static func _boats_and_jetty(stage: Node2D, R: Dictionary) -> void:
	# Boot B (rechts, weiter hinten, mit Segel)
	var bB := V.group(stage, "BoatB", Vector2(338, 224))
	var hullB := V.smooth([Vector2(-30, -8), Vector2(-24, -8), Vector2(0, -7), Vector2(26, -9), Vector2(31, -12),
		Vector2(28, -4), Vector2(18, 4), Vector2(-16, 5), Vector2(-27, -1)], true, 6)
	V.stroke(bB, PackedVector2Array([Vector2(-2, -8), Vector2(-2, -46)]), 1.8, 0.0, 0.15, 0.6, C("4a2f1c"))
	var sailB = M.make_shape(bB, [Vector2(0, -44), Vector2(3, -30), Vector2(4, -16), Vector2(2, -10), Vector2(22, -11), Vector2(14, -26)],
		[Vector2(0, -44), Vector2(7, -30), Vector2(9, -16), Vector2(5, -10), Vector2(25, -11), Vector2(20, -27)], C("f2e7cc"), 1.3, 6)
	V.fill(bB, hullB, C("c24a3a"))
	V.fill(bB, V.smooth([Vector2(-28, -6), Vector2(0, -4.5), Vector2(29, -8), Vector2(28, -5), Vector2(0, -1.5), Vector2(-27, -3)], true, 5), C("f1e6cf"))
	V.fill(bB, V.smooth([Vector2(-20, 2), Vector2(0, 1), Vector2(22, 0), Vector2(16, 4), Vector2(-14, 5)], true, 5), C("8e3028"))
	V.ink(bB, hullB, 1.6, 0.4)
	R["boatB"] = bB
	R["sailB"] = sailB
	# Steg (führt vom Kai zum Horizont, leicht verkürzt)
	var j := V.group(stage, "Jetty")
	var deck := PackedVector2Array([Vector2(262, QUAY + 2), Vector2(322, QUAY + 2), Vector2(306, 214), Vector2(282, 214)])
	for px in [[262.0, QUAY + 2, 10.0, 3.4], [322.0, QUAY + 2, 10.0, 3.4], [270.0, 254.0, 8.0, 2.8], [314.0, 254.0, 8.0, 2.8],
			[277.0, 228.0, 6.0, 2.2], [309.0, 228.0, 6.0, 2.2]]:
		var p := Vector2(px[0], px[1])
		var hh: float = px[2]
		var ww: float = px[3]
		V.shape(j, V.rpoly([p + Vector2(-ww, -hh * 0.4), p + Vector2(ww, -hh * 0.4), p + Vector2(ww, hh), p + Vector2(-ww, hh)], [1, 1, 0, 0]), C("5e3b22"), 1.2)
	V.fill(j, deck, C("9b6a40"))
	for k in 9:
		var t := float(k + 1) / 10.0
		var y := lerpf(QUAY + 2, 214.0, t)
		var xl := lerpf(262.0, 282.0, t)
		var xr := lerpf(322.0, 306.0, t)
		V.stroke(j, PackedVector2Array([Vector2(xl + 1, y), Vector2(xr - 1, y)]), lerpf(1.1, 0.6, t), 0.2, 0.2, 0.2, C("5a3820"))
	V.fill(j, PackedVector2Array([Vector2(292, QUAY + 2), Vector2(322, QUAY + 2), Vector2(306, 214), Vector2(296, 214)]), Color(0.3, 0.15, 0.1, 0.22))
	V.ink(j, deck, 1.5, 0.45)
	for pp in [[Vector2(264, 246), 22.0, 3.2], [Vector2(320, 246), 22.0, 3.2], [Vector2(281, 214), 12.0, 2.2], [Vector2(307, 214), 12.0, 2.2]]:
		var p: Vector2 = pp[0]
		var hh: float = pp[1]
		var ww: float = pp[2]
		var post := V.rpoly([p + Vector2(-ww, -hh), p + Vector2(ww, -hh), p + Vector2(ww, 2), p + Vector2(-ww, 2)], [1.5, 1.5, 0, 0])
		V.shape(j, post, C("7a4d2c"), 1.3)
		V.fill(j, V.rpoly([p + Vector2(-ww + 0.8, -hh + 1), p + Vector2(-ww + 2.0, -hh + 1), p + Vector2(-ww + 2.0, 0), p + Vector2(-ww + 0.8, 0)], 0.5), C("a8754a"))
	# Boot A (links vom Steg, näher, mit Wimpel)
	var bA := V.group(stage, "BoatA", Vector2(232, 246))
	V.stroke(bA, PackedVector2Array([Vector2(4, -10), Vector2(4, -50)]), 2.0, 0.0, 0.1, 0.6, C("4a2f1c"))
	var pennant = M.make_shape(bA, [Vector2(5, -49), Vector2(14, -47), Vector2(24, -45), Vector2(14, -43.5), Vector2(5, -42)],
		[Vector2(5, -49), Vector2(13, -49.5), Vector2(23, -50), Vector2(13, -46), Vector2(5, -42)], C("e0483e"), 1.1, 5)
	var hullA := V.smooth([Vector2(-40, -14), Vector2(-30, -11), Vector2(0, -10), Vector2(30, -11), Vector2(40, -15),
		Vector2(36, -4), Vector2(24, 5), Vector2(-24, 6), Vector2(-36, -3)], true, 6)
	V.fill(bA, hullA, C("2e7d86"))
	V.fill(bA, V.smooth([Vector2(-38, -11), Vector2(0, -7.5), Vector2(38, -12), Vector2(37, -8), Vector2(0, -4), Vector2(-37, -7)], true, 5), C("f1e6cf"))
	V.fill(bA, V.smooth([Vector2(-26, 3), Vector2(0, 2), Vector2(28, 0), Vector2(22, 5), Vector2(-22, 6)], true, 5), C("1f5158"))
	V.fill(bA, V.smooth([Vector2(-30, -10), Vector2(-18, -9.4), Vector2(-20, -8), Vector2(-31, -8.6)], true, 4), C("7fc0c4"))
	V.ink(bA, hullA, 1.8, 0.4)
	for x in [-14.0, 16.0]:
		V.shape(bA, V.ellipse(Vector2(x, -1), 2.2, 2.2, 12), C("f1e6cf"), 0.9)
	R["boatA"] = bA
	R["pennantA"] = pennant
	# Wasserlinien an den Rümpfen (Form-Tween)
	var wl := []
	for spec in [[Vector2(232, 251), 46.0], [Vector2(338, 229), 34.0]]:
		var c: Vector2 = spec[0]
		var L: float = spec[1]
		var ka := [c + Vector2(-L, 0), c + Vector2(-L * 0.4, -1.2), c + Vector2(L * 0.2, 0.6), c + Vector2(L, -0.4)]
		var kb := [c + Vector2(-L + 3, -0.6), c + Vector2(-L * 0.3, 0.8), c + Vector2(L * 0.35, -1.0), c + Vector2(L + 3, 0.4)]
		wl.append(M.make_stroke(stage, ka, kb, 1.4, Color(0.75, 0.8, 1.0, 0.8), 6, 0.3, 0.3))
	R["waterlines"] = wl


# ------------------------------------------------------------------ Häuschen des Hafenmeisters
static func _cottage(stage: Node2D, R: Dictionary) -> void:
	var smoke := V.group(stage, "Smoke")
	R["smoke"] = smoke
	var g := V.group(stage, "Cottage")
	# Schornstein
	var ch := V.rpoly([Vector2(64, 96), Vector2(66, 60), Vector2(88, 60), Vector2(90, 96)], 1.0)
	V.fill(g, ch, C("9a4c3c"))
	V.fill(g, PackedVector2Array([Vector2(81, 60), Vector2(88, 60), Vector2(90, 96), Vector2(82, 96)]), C("76352b"))
	V.ink(g, ch, 1.7, 0.4)
	V.shape(g, V.rpoly([Vector2(62, 54), Vector2(92, 54), Vector2(92, 61), Vector2(62, 61)], 1.5), C("5b2e26"), 1.6)
	R["chimney_top"] = Vector2(77, 54)
	# Dach (Schiefer)
	var roof := V.rpoly([Vector2(-12, 150), Vector2(130, 150), Vector2(108, 84), Vector2(-12, 84)], [0, 3, 3, 0])
	V.fill(g, roof, C("43476c"))
	V.fill(g, PackedVector2Array([Vector2(-12, 84), Vector2(108, 84), Vector2(110, 90), Vector2(-12, 90)]), C("5d628c"))
	for row in [[100.0, 0.0], [116.0, 10.0], [132.0, 4.0]]:
		var y: float = row[0]
		var xr := lerpf(108.0, 130.0, (y - 84.0) / 66.0)
		V.stroke(g, PackedVector2Array([Vector2(-12, y), Vector2(xr - 4, y)]), 1.0, 0.0, 0.3, 0.4, C("2a2b48"))
		var x: float = 6.0 + row[1]
		while x < xr - 14:
			V.stroke(g, PackedVector2Array([Vector2(x, y), Vector2(x - 1, y + 9)]), 0.9, 0.3, 0.3, 0.0, C("2a2b48"))
			x += 22.0
	V.fill(g, V.smooth([Vector2(10, 92), Vector2(60, 90), Vector2(100, 91), Vector2(60, 94), Vector2(10, 95)], true, 4), C("7a80aa"))
	V.ink(g, roof, 2.2, 0.4)
	# Wand
	var wall := V.rpoly([Vector2(-12, 148), Vector2(118, 148), Vector2(118, 292), Vector2(-12, 292)], 0.0)
	V.fill(g, wall, C("b7a493"))
	V.fill(g, PackedVector2Array([Vector2(-12, 148), Vector2(118, 148), Vector2(118, 158), Vector2(-12, 162)]), C("8c7a70"))
	V.fill(g, PackedVector2Array([Vector2(106, 158), Vector2(118, 156), Vector2(118, 292), Vector2(108, 292)]), C("9c8a7e"))
	var rng := RandomNumberGenerator.new()
	rng.seed = 99
	for st in [[Vector2(8, 172), 14.0, 8.0], [Vector2(70, 170), 16.0, 8.0], [Vector2(16, 236), 18.0, 9.0], [Vector2(48, 252), 14.0, 8.0],
			[Vector2(4, 270), 16.0, 9.0], [Vector2(56, 280), 18.0, 7.0], [Vector2(96, 182), 10.0, 7.0], [Vector2(36, 166), 12.0, 6.0]]:
		var c: Vector2 = st[0]
		var w: float = st[1]
		var h: float = st[2]
		var sp := V.rpoly([c + Vector2(-w * 0.5, -h * 0.5), c + Vector2(w * 0.5, -h * 0.5), c + Vector2(w * 0.5, h * 0.5), c + Vector2(-w * 0.5, h * 0.5)], 3.0, 3)
		V.fill(g, sp, C("a6927f"))
		V.ink(g, sp, 1.0, 0.25, [rng.randf_range(0.1, 0.4)], C("5a4840"))
	V.ink(g, wall, 2.2, 0.4)
	# Fenster mit Schein
	var wglow := V.group(stage, "WindowGlow", Vector2(44, 196))
	var wg := V.fill(wglow, V.ellipse(Vector2.ZERO, 38, 32, 40), {"rad": [[0.0, Color(1, 0.86, 0.45, 0.55)], [1.0, Color(1, 0.7, 0.3, 0.0)]],
		"c": Vector2.ZERO, "r": Vector2(38, 32)})
	V.add_glow(wg)
	R["window_glow"] = wglow
	var win := V.rpoly([Vector2(28, 180), Vector2(60, 180), Vector2(60, 212), Vector2(28, 212)], 1.5)
	V.fill(g, win, {"rad": [[0.0, C("fff0a8")], [1.0, C("ffbe4a")]], "c": Vector2(44, 196), "r": Vector2(22, 22)})
	V.stroke(g, PackedVector2Array([Vector2(44, 181), Vector2(44, 211)]), 2.2, 0.0, 0.0, 1.0, C("5b3a26"))
	V.stroke(g, PackedVector2Array([Vector2(29, 196), Vector2(59, 196)]), 2.2, 0.0, 0.0, 1.0, C("5b3a26"))
	V.fill(g, PackedVector2Array([Vector2(31, 183), Vector2(36, 183), Vector2(31, 191)]), C("fffbe6"))
	V.ink(g, win, 2.0, 0.5)
	V.shape(g, V.rpoly([Vector2(24, 212), Vector2(64, 212), Vector2(66, 218), Vector2(22, 218)], 1.0), C("d8c8b4"), 1.4)
	# Tür
	var door := V.rpoly([Vector2(74, 292), Vector2(74, 216), Vector2(89, 206), Vector2(104, 216), Vector2(104, 292)], [0, 8, 8, 8, 0])
	V.fill(g, door, C("8a5430"))
	V.fill(g, PackedVector2Array([Vector2(97, 212), Vector2(104, 216), Vector2(104, 292), Vector2(97, 292)]), C("6a3c20"))
	for x in [82.0, 90.0, 97.0]:
		V.stroke(g, PackedVector2Array([Vector2(x, 216), Vector2(x, 288)]), 0.9, 0.2, 0.2, 0.0, C("4a2814"))
	V.shape(g, V.ellipse(Vector2(99, 252), 2.0, 2.0, 12), C("e3b440"), 0.9)
	V.ink(g, door, 2.0, 0.45)
	V.shape(g, V.rpoly([Vector2(70, 290), Vector2(108, 290), Vector2(110, 296), Vector2(68, 296)], 1.0), C("8e8090"), 1.4)
	R["door_hotspot"] = Vector2(89, 250)


# ------------------------------------------------------------------ Kai
static func _quay(stage: Node2D, R: Dictionary) -> void:
	var g := V.group(stage, "Quay")
	var top := PackedVector2Array([Vector2(-4, QUAY), Vector2(554, QUAY), Vector2(554, 404), Vector2(-4, 404)])
	V.fill(g, top, {"lin": [[0.0, C("a796a8")], [1.0, C("6a5c74")]], "from": Vector2(0, QUAY), "to": Vector2(0, 336)}, "QuayTop")
	var coping := V.rpoly([Vector2(-4, QUAY - 3), Vector2(554, QUAY - 3), Vector2(554, QUAY + 5), Vector2(-4, QUAY + 5)], 0.0)
	V.fill(g, coping, C("bcaebb"))
	V.fill(g, PackedVector2Array([Vector2(-4, QUAY + 2.5), Vector2(554, QUAY + 2.5), Vector2(554, QUAY + 5), Vector2(-4, QUAY + 5)]), C("8f8191"))
	V.stroke(g, PackedVector2Array([Vector2(-4, QUAY - 3), Vector2(554, QUAY - 3)]), 1.8, 0.0, 0.0, 1.0)
	V.stroke(g, PackedVector2Array([Vector2(-4, QUAY + 5), Vector2(554, QUAY + 5)]), 1.3, 0.0, 0.0, 1.0)
	for x in [40.0, 132.0, 228.0, 340.0, 452.0]:
		V.stroke(g, PackedVector2Array([Vector2(x, QUAY - 2.5), Vector2(x, QUAY + 4.5)]), 1.0, 0.1, 0.1, 0.4)
	# Pflasterfugen: lockere Pinselstriche, nicht jede Fuge
	var rng := RandomNumberGenerator.new()
	rng.seed = 2006
	for row in [[300.0, 0.0], [314.0, 22.0], [328.0, 8.0]]:
		var y: float = row[0]
		var x: float = 6.0 + row[1]
		while x < 545:
			var w := rng.randf_range(26, 44)
			V.stroke(g, PackedVector2Array([Vector2(x, y), Vector2(x + w * 0.5, y + 0.4), Vector2(x + w - 4, y - 0.2)]), 1.0, 0.3, 0.3, 0.0, Color(0.23, 0.17, 0.28, 0.55))
			V.stroke(g, PackedVector2Array([Vector2(x + w, y - 12), Vector2(x + w + 0.6, y - 1)]), 0.9, 0.3, 0.3, 0.0, Color(0.23, 0.17, 0.28, 0.45))
			x += w + rng.randf_range(4, 10)


# ------------------------------------------------------------------ Laterne, Fässer, Kisten, Tau, Paket
static func _props(stage: Node2D, R: Dictionary) -> void:
	var g := V.group(stage, "LanternPost", Vector2(30, 0))
	# Laternenpfahl
	var post := V.rpoly([Vector2(354, 324), Vector2(354, 206), Vector2(361, 206), Vector2(361, 324)], [0, 1, 1, 0])
	V.fill(g, post, C("6a4630"))
	V.fill(g, PackedVector2Array([Vector2(358, 206), Vector2(361, 206), Vector2(361, 324), Vector2(358, 324)]), C("4a2f20"))
	V.ink(g, post, 1.6, 0.4)
	var arm := V.rpoly([Vector2(356, 210), Vector2(386, 210), Vector2(386, 214), Vector2(356, 214)], 1.0)
	V.shape(g, arm, C("4a2f20"), 1.3)
	V.stroke(g, V.smooth([Vector2(360, 228), Vector2(368, 218), Vector2(378, 213)], false, 6), 1.6, 0.2, 0.2, 0.5)
	V.shape(g, V.rpoly([Vector2(350, 320), Vector2(365, 320), Vector2(367, 326), Vector2(348, 326)], 1.0), C("4a2f20"), 1.4)
	# Laterne hängt am Haken und pendelt
	var lan := V.group(stage, "Lantern", Vector2(411, 214))
	V.stroke(lan, PackedVector2Array([Vector2(0, 0), Vector2(0, 6)]), 1.2, 0.0, 0.0, 1.0)
	var glow := V.group(lan, "LanternGlow", Vector2(0, 18))
	var gl := V.fill(glow, V.ellipse(Vector2.ZERO, 44, 44, 40), {"rad": [[0.0, Color(1, 0.86, 0.48, 0.7)], [0.3, Color(1, 0.72, 0.32, 0.32)], [1.0, Color(1, 0.6, 0.2, 0.0)]],
		"c": Vector2.ZERO, "r": Vector2(44, 44)})
	V.add_glow(gl)
	var top := V.smooth([Vector2(-7, 9), Vector2(0, 5), Vector2(7, 9)], false, 4)
	top.append(Vector2(7, 9))
	V.shape(lan, V.rpoly([Vector2(-7, 9), Vector2(-3, 5.5), Vector2(3, 5.5), Vector2(7, 9)], 1.0), C("2b2730"), 1.2)
	var glass := V.rpoly([Vector2(-6, 9), Vector2(6, 9), Vector2(5, 25), Vector2(-5, 25)], 1.0)
	var flame_glass := V.fill(lan, glass, {"rad": [[0.0, C("fff6c0")], [1.0, C("ffb840")]], "c": Vector2(0, 18), "r": Vector2(9, 10)})
	var flame := V.group(lan, "Flame", Vector2(0, 21))
	V.fill(flame, V.smooth([Vector2(0, -7), Vector2(2.4, -1.5), Vector2(1.6, 1.5), Vector2(-1.6, 1.5), Vector2(-2.4, -1.5)], true, 5), C("ffffff"))
	V.stroke(lan, PackedVector2Array([Vector2(0, 9.5), Vector2(0, 24.5)]), 1.0, 0.0, 0.0, 1.0, C("2b2730"))
	V.ink(lan, glass, 1.4, 0.5)
	V.shape(lan, V.rpoly([Vector2(-7, 25), Vector2(7, 25), Vector2(6, 28.5), Vector2(-6, 28.5)], 1.0), C("2b2730"), 1.2)
	R["lantern"] = lan
	R["lantern_glow"] = glow
	R["flame"] = flame
	R["lantern_glass"] = flame_glass
	R["lantern_hotspot"] = Vector2(411, 232)
	# Tau-Rolle
	var rope := V.group(stage, "Rope", Vector2(352, 325))
	for k in 3:
		var rx := 15.0 - k * 4.5
		var ry := 5.0 - k * 1.4
		var e := V.ellipse(Vector2(0, -k * 1.8), rx, ry, 28)
		V.fill(rope, e, C("c9a46a") if k % 2 == 0 else C("b08a50"))
		V.ink(rope, e, 1.3, 0.35)
	V.fill(rope, V.ellipse(Vector2(0, -3.6), 3.0, 1.0, 12), C("4a3a28"))
	V.stroke(rope, V.smooth([Vector2(14, -1), Vector2(20, 1), Vector2(28, 0.5)], false, 5), 2.6, 0.0, 0.5, 0.6, C("b08a50"))
	# Fässer
	for spec in [[Vector2(446, 322), 15.0, 38.0], [Vector2(478, 326), 15.0, 38.0]]:
		_barrel(stage, spec[0], spec[1], spec[2])
	# Kisten
	_crate(stage, Vector2(503, 290), Vector2(549, 328))
	_crate(stage, Vector2(509, 258), Vector2(545, 291))
	# Paket auf dem Kai (Klickpunkt)
	var parcel := V.group(stage, "Parcel", Vector2(304, 324))
	var pinner := V.group(parcel, "Art")
	_parcel_art(pinner)
	R["parcel"] = parcel
	R["parcel_art"] = pinner


static func _barrel(stage: Node2D, base: Vector2, rx: float, h: float) -> void:
	var g := V.group(stage, "Barrel", base)
	var body := V.smooth([Vector2(-rx, 0), Vector2(-rx - 2.5, -h * 0.5), Vector2(-rx, -h), Vector2(rx, -h), Vector2(rx + 2.5, -h * 0.5), Vector2(rx, 0)], true, 6)
	V.fill(g, body, C("a8662e"))
	V.fill(g, V.smooth([Vector2(rx * 0.35, -1), Vector2(rx * 0.55, -h * 0.5), Vector2(rx * 0.35, -h + 1), Vector2(rx, -h), Vector2(rx + 2.5, -h * 0.5), Vector2(rx, 0)], true, 6), C("834a1f"))
	V.fill(g, V.smooth([Vector2(-rx * 0.62, -h * 0.2), Vector2(-rx * 0.82, -h * 0.5), Vector2(-rx * 0.62, -h * 0.8), Vector2(-rx * 0.42, -h * 0.5)], true, 6), C("d99a5e"))
	for y in [-h * 0.22, -h * 0.78]:
		var bw := rx + 2.0
		V.fill(g, V.rpoly([Vector2(-bw, y - 2), Vector2(bw, y - 2), Vector2(bw, y + 2), Vector2(-bw, y + 2)], 1.0), C("4b4752"))
		V.stroke(g, PackedVector2Array([Vector2(-bw + 1, y - 2), Vector2(bw - 1, y - 2)]), 0.8, 0.2, 0.2, 0.2)
	var lid := V.ellipse(Vector2(0, -h), rx, 3.2, 24)
	V.shape(g, lid, C("c07a3a"), 1.2)
	V.ink(g, body, 1.9, 0.4, [0.08])


static func _crate(stage: Node2D, a: Vector2, b: Vector2) -> void:
	var g := V.group(stage, "Crate")
	var box := V.rpoly([a, Vector2(b.x, a.y), b, Vector2(a.x, b.y)], 1.5)
	V.fill(g, box, C("c48c4c"))
	V.fill(g, PackedVector2Array([Vector2(b.x - 7, a.y + 1), Vector2(b.x - 1, a.y + 1), Vector2(b.x - 1, b.y - 1), Vector2(b.x - 7, b.y - 1)]), C("93622f"))
	var m := 4.0
	V.stroke(g, PackedVector2Array([Vector2(a.x + m, a.y + m), Vector2(b.x - m, b.y - m)]), 2.6, 0.15, 0.15, 0.5, C("6e4420"))
	V.stroke(g, PackedVector2Array([Vector2(a.x + m, a.y + m), Vector2(b.x - m, a.y + m)]), 1.0, 0.15, 0.15, 0.3, C("6e4420"))
	V.stroke(g, PackedVector2Array([Vector2(a.x + m, b.y - m), Vector2(b.x - m, b.y - m)]), 1.0, 0.15, 0.15, 0.3, C("6e4420"))
	V.fill(g, PackedVector2Array([Vector2(a.x + 2, a.y + 2), Vector2(a.x + 9, a.y + 2), Vector2(a.x + 2, a.y + 8)]), C("e2b27a"))
	V.ink(g, box, 1.9, 0.4)


static func _parcel_art(g: Node2D) -> void:
	# Ursprung = Mitte der Unterkante
	var box := V.rpoly([Vector2(-12, -15), Vector2(12, -15), Vector2(12, 0), Vector2(-12, 0)], 2.0)
	V.fill(g, box, C("c99a5c"))
	V.fill(g, PackedVector2Array([Vector2(5, -14), Vector2(11, -14), Vector2(11, -1), Vector2(5, -1)]), C("a5773f"))
	V.stroke(g, PackedVector2Array([Vector2(-1, -14.5), Vector2(-1, -0.5)]), 1.3, 0.0, 0.0, 1.0, C("f3e5c2"))
	V.stroke(g, PackedVector2Array([Vector2(-11.5, -8), Vector2(11.5, -8)]), 1.3, 0.0, 0.0, 1.0, C("f3e5c2"))
	V.stroke(g, V.smooth([Vector2(-1, -15), Vector2(-5, -20), Vector2(-7, -17), Vector2(-1, -15)], false, 5), 1.1, 0.1, 0.1, 0.6, C("f3e5c2"))
	V.stroke(g, V.smooth([Vector2(-1, -15), Vector2(3, -20), Vector2(5, -17), Vector2(-1, -15)], false, 5), 1.1, 0.1, 0.1, 0.6, C("f3e5c2"))
	V.fill(g, PackedVector2Array([Vector2(-10, -13), Vector2(-5, -13), Vector2(-10, -10)]), C("ead0a0"))
	V.ink(g, box, 1.5, 0.45)
