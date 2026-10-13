extends Node2D
## Zeichenknoten: ruft in _draw() die übergebene Funktion mit sich selbst auf (Ebenen der Szene und der Figur).

var fn: Callable


func _draw() -> void:
	if fn.is_valid():
		fn.call(self)
