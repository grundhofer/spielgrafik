extends Node2D
## Horizontebene: unendlich fern, verschiebt sich nur mit dem Kurs (x = 160 + (Azimut − Kurs)·D).
## Sterne, zwei Wolkenreihen (die hintere mit 0,7-fachem Versatz und Wind), Inseln und Möwen per _draw,
## Felsnase mit Leuchtturm als Sprite-Kind mit Palettenanimation der Lampe.

var main: Node2D
var clouds: Array = []     # [Textur, Azimut, Unterkante y, Faktor, Wind px/s]
var islands: Texture2D
var headland: Sprite2D
var stars: Array = []
var gulls: Array = []      # [Azimut, y, Flügelphase, Geschwindigkeit rad/s]
var gull_tex: Array = []
var tt := 0.0
var lamp_pos := Vector2.ZERO

const AZ_HEADLAND := 0.12
const AZ_ISLANDS := -0.62


func setup(m: Node2D) -> void:
	main = m
	var spec := [[1, -0.95, 64, 0.7, 2.0], [3, 0.35, 60, 0.7, 2.0], [5, 1.4, 66, 0.7, 2.0],
		[2, -0.2, 84, 1.0, 0.0], [0, 0.95, 88, 1.0, 0.0], [4, 2.1, 86, 1.0, 0.0]]
	for c in spec:
		clouds.append([load("res://art/cloud_%d.png" % c[0]), c[1], c[2], c[3], c[4]])
	islands = load("res://art/hz_islands.png")
	headland = Sprite2D.new()
	headland.texture = load("res://art/hz_headland.png")
	headland.centered = false
	var mat := ShaderMaterial.new()
	mat.shader = preload("res://shaders/prop.gdshader")
	var k: Color = main.key_lh
	mat.set_shader_parameter("key1", Vector3(k.r, k.g, k.b))
	headland.material = mat
	add_child(headland)
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	for i in 46:
		stars.append([rng.randf_range(-PI, PI), rng.randi_range(42, 78), rng.randf()])
	for g in [[0.05, 70.0, 0.0, 0.035], [0.3, 62.0, 0.4, 0.028], [-0.35, 76.0, 0.7, -0.03]]:
		gulls.append(g)
	_make_gulls()


func _make_gulls() -> void:
	var rows := [
		["#.......#", ".##...##.", "...#.#...", "....#...."],
		[".........", "..##.##..", ".#..#..#.", "#.......#"],
	]
	for fr in rows:
		var img := Image.create(9, 4, false, Image.FORMAT_RGBA8)
		img.fill(Color(0, 0, 0, 0))
		for y in 4:
			for x in 9:
				if fr[y][x] == "#":
					var c := Color8(250, 240, 246) if y < 3 else Color8(60, 40, 80)
					if x == 0 or x == 8:
						c = Color8(60, 40, 80)
					img.set_pixel(x, y, main.q5(c))
		gull_tex.append(ImageTexture.create_from_image(img))


func sx(az: float, factor := 1.0) -> float:
	var d := wrapf(az - main.heading * factor, -PI, PI)
	return main.W * 0.5 + d * main.D


func refresh(t: float) -> void:
	tt = t
	var w := headland.texture.get_width()
	var h := headland.texture.get_height()
	var x := roundf(sx(AZ_HEADLAND) - w * 0.5)
	headland.position = Vector2(x, main.HY - h)
	var lp: Array = main.spr["points"]["lighthouse_lamp"]
	lamp_pos = Vector2(x + roundf(lp[0]), main.HY - h + roundf(lp[1]))
	var lc: Color = main.q5(Color8(170, 80, 30).lerp(Color8(255, 255, 230), main.lh_level))
	(headland.material as ShaderMaterial).set_shader_parameter("key1_col", Vector3(lc.r, lc.g, lc.b))
	queue_redraw()


func _draw() -> void:
	# Sterne: zwei Helligkeiten, funkeln mit 3 Hz-Takt
	for s in stars:
		var x := roundf(sx(s[0]))
		if x < 0 or x >= main.W:
			continue
		var on := fmod(tt * 3.0 + s[2] * 7.0, 3.0) < 2.4
		var c: Color = main.q5(Color8(255, 240, 220) if on else Color8(150, 130, 190))
		draw_rect(Rect2(x, s[1], 1, 1), c)
	# Wolken: hintere Reihe zuerst
	for c in clouds:
		var t2: Texture2D = c[0]
		var x := roundf(sx(c[1], c[3]) - t2.get_width() * 0.5 + tt * c[4])
		draw_texture(t2, Vector2(x, c[2] - t2.get_height()))
	# Inseln links
	var ix := roundf(sx(AZ_ISLANDS) - islands.get_width() * 0.5)
	draw_texture(islands, Vector2(ix, main.HY - islands.get_height()))
	# Möwen: kreisen langsam, Flügelschlag 6 Bilder/s
	for g in gulls:
		var az: float = g[0] + g[3] * tt
		var x := roundf(sx(az))
		var y := roundf(g[1] + sin(tt * 1.3 + g[2] * 5.0) * 3.0)
		var f := int(floor(tt * 6.0 + g[2] * 4.0)) % 2
		draw_texture(gull_tex[f], Vector2(x - 4, y))
