extends Node
## Prüfszene für tools/measure_walk.py: lädt die Demo, blendet alles außer dem Dachs aus (auch das
## Nachbearbeitungs-Flimmern und die Oberfläche) und zeichnet auf Magenta. So lassen sich Füße und Kopf
## in den gerenderten Bildern messen, inklusive Boil-Shader, Rundung und Bildfolge aus main.gd.

func _ready() -> void:
	RenderingServer.set_default_clear_color(Color(1, 0, 1))
	var main: Node = load("res://main.tscn").instantiate()
	add_child(main)
	for c in main.get_node("World").get_children():
		if c.name != "Badger":
			c.visible = false
	main.get_node("UI").visible = false
	# Mit OEL_NO_BOIL=1 springen die Texel der Figur nicht: misst nur Platzierung und Bildfolge
	if OS.get_environment("OEL_NO_BOIL") == "1":
		(main.get_node("World/Badger").material as ShaderMaterial).set_shader_parameter("boil_texels", 0.0)
