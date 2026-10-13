extends Node
## Prüfszene für scripts/measure_badger.py: die echte Hauptszene, aber nur die Figur (ohne Schatten) auf Magenta.

func _ready() -> void:
	RenderingServer.set_default_clear_color(Color(1, 0, 1))
	var main: Node = load("res://main.tscn").instantiate()
	add_child(main)
	for p in ["World/Bg", "World/Sky", "World/Water", "World/Boats", "World/Lights", "UI", "Paper"]:
		var n := main.get_node(p)
		if n is CanvasItem:
			(n as CanvasItem).visible = false
		elif n is CanvasLayer:
			(n as CanvasLayer).visible = false
	main.shadow.visible = false
