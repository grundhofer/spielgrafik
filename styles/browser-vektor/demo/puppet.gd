extends Node2D
## Teilebogen der Symbol-Puppe (nur für die Doku, nicht Teil der Demo):
##   godot --path demo --write-movie out.png --fixed-fps 30 --quit-after 1 res://puppet.tscn
## Links die Puppe zusammengesetzt, rechts auseinandergezogen mit Drehpunkten.

const V = preload("res://vec.gd")
const B = preload("res://badger.gd")


func _ready() -> void:
	RenderingServer.set_default_clear_color(Color("e9e4dc"))
	var font: FontFile = load("res://fonts/Baloo2-wght.ttf")
	var whole = B.new()
	whole.position = Vector2(250, 560)
	whole.scale = Vector2(4.4, 4.4)
	add_child(whole)
	whole.x0 = -(B.N_STEPS * B.S + B.S * 0.25)
	whole.walk_pose(B.N_STEPS + 1)
	var ex = B.new()
	ex.position = Vector2(860, 560)
	ex.scale = Vector2(4.4, 4.4)
	add_child(ex)
	ex.x0 = -(B.N_STEPS * B.S + B.S * 0.25)
	ex.walk_pose(B.N_STEPS + 1)
	ex.shadow.visible = false
	# auseinanderziehen (in Puppen-Koordinaten)
	ex.head.position += Vector2(10, -16)
	ex.near_arm.position += Vector2(30, 2)
	ex.far_arm.position += Vector2(-50, -4)
	ex.scarf_end.position += Vector2(-30, 16)
	ex.near_leg.position += Vector2(14, 14)
	ex.far_leg.position += Vector2(-14, 14)
	ex.near_foot.position += Vector2(22, 14)
	ex.far_foot.position += Vector2(-22, 14)
	# Drehpunkte markieren
	var marks := V.group(self, "Marks")
	for n in [ex.head, ex.near_arm, ex.far_arm, ex.scarf_end, ex.near_leg, ex.far_leg, ex.near_foot, ex.far_foot, ex.body]:
		var p: Vector2 = (n as Node2D).get_global_transform() * Vector2.ZERO
		V.fill(marks, V.ellipse(p, 7, 7, 20), Color("e0483e"))
		V.ink(marks, V.ellipse(p, 7, 7, 20), 2.0, 1.0)
	var labels := [["Kopf", Vector2(770, 132)], ["Arm fern", Vector2(540, 262)], ["Schal", Vector2(552, 530)], ["Arm nah", Vector2(1095, 290)],
		["Rumpf", Vector2(985, 462)], ["Bein", Vector2(1000, 530)], ["Fuß", Vector2(1010, 596)]]
	for l in labels:
		var lab := Label.new()
		lab.text = l[0]
		lab.position = l[1]
		lab.add_theme_font_override("font", font)
		lab.add_theme_font_size_override("font_size", 30)
		lab.add_theme_color_override("font_color", Color("2a2030"))
		add_child(lab)
	var t := Label.new()
	t.text = "Symbol-Puppe: 9 Teile mit Drehpunkt (rot), jede Form ein Polygon2D, Konturen als Bänder mit veränderlicher Breite"
	t.position = Vector2(30, 660)
	t.add_theme_font_override("font", font)
	t.add_theme_font_size_override("font_size", 24)
	t.add_theme_color_override("font_color", Color("2a2030"))
	add_child(t)
