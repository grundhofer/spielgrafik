extends Node
## Hintergrund-Serie: vier Orte von Lornholm im selben gemalten Stil und drei Szenenwechsel.
## Jeder Ort lebt in einer eigenen SubViewport (location.gd); der Übergangs-Shader auf "Screen" mischt
## zwei davon und wendet je Ort die Farb-LUT an. Die Textbox (CanvasLayer) bleibt stehen, nur der
## Ortsname wechselt. Alles hängt nur von der aufsummierten Zeit t ab; Zufall nur mit festen Seeds.

const LOC_SCRIPT := preload("res://location.gd")
const DATA := preload("res://locations.gd")
const ORDER := ["hafen", "leuchtturm", "stube", "klippe"]
const LUTS := {
	"hafen": preload("res://art/lut/lut_hafen.png"),
	"leuchtturm": preload("res://art/lut/lut_leuchtturm.png"),
	"stube": preload("res://art/lut/lut_stube.png"),
	"klippe": preload("res://art/lut/lut_klippe.png"),
}
# Zeitplan der Wechsel (Sekunden). mode: 1 nasse Überblendung, 2 Seitenumblättern, 3 Dither/Pixel
const TRANSITIONS := [
	{"start": 2.0, "end": 2.5, "mode": 1, "from": 0, "to": 1},
	{"start": 3.2, "end": 4.0, "mode": 2, "from": 1, "to": 2},
	{"start": 4.7, "end": 5.15, "mode": 3, "from": 2, "to": 3},
]
# Ortsname: der alte blendet im ersten Viertel des Wechsels aus, der neue im zweiten Viertel ein
const NAME_OUT := [0.0, 0.22]
const NAME_IN := [0.26, 0.5]

var t := 0.0
var views: Array = []
var locs: Array = []
var place_shown := -1

@onready var screen: ColorRect = $Screen
@onready var mat: ShaderMaterial = $Screen.material
@onready var place_a: Label = $UI/PlaceA
@onready var place_b: Label = $UI/PlaceB


func _ready() -> void:
	var badger_only := OS.get_cmdline_user_args().has("--badger-only")
	if badger_only:
		$UI.visible = false
		mat.set_shader_parameter("lut_amount", 0.0)
	if OS.get_cmdline_user_args().has("--no-lut"):
		# Vergleich: ohne Farbabgleich
		mat.set_shader_parameter("lut_amount", 0.0)
	for i in ORDER.size():
		var key: String = ORDER[i]
		var vp := SubViewport.new()
		vp.name = "View_" + key
		vp.size = Vector2i(1280, 720)
		vp.disable_3d = true
		vp.transparent_bg = false
		vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
		$Views.add_child(vp)
		var loc := Node2D.new()
		loc.set_script(LOC_SCRIPT)
		vp.add_child(loc)
		loc.setup(key, DATA.LOCATIONS[key], 20261010 + i, badger_only)
		views.append(vp)
		locs.append(loc)
	_apply()


func _process(delta: float) -> void:
	t += delta
	_apply()


func _state() -> Dictionary:
	## Welcher Ort ist zu sehen, welcher Übergang läuft gerade?
	var current := 0
	for tr in TRANSITIONS:
		if t < tr["start"]:
			return {"from": current, "to": current, "mode": 0, "p": 0.0}
		if t < tr["end"]:
			var p: float = (t - tr["start"]) / (tr["end"] - tr["start"])
			return {"from": tr["from"], "to": tr["to"], "mode": tr["mode"], "p": p, "tr": tr}
		current = tr["to"]
	return {"from": current, "to": current, "mode": 0, "p": 0.0}


func _apply() -> void:
	var st := _state()
	for i in views.size():
		var active: bool = i == st["from"] or i == st["to"]
		views[i].render_target_update_mode = SubViewport.UPDATE_ALWAYS if active else SubViewport.UPDATE_DISABLED
		if active:
			locs[i].update(t)
	mat.set_shader_parameter("from_tex", views[st["from"]].get_texture())
	mat.set_shader_parameter("to_tex", views[st["to"]].get_texture())
	mat.set_shader_parameter("from_lut", LUTS[ORDER[st["from"]]])
	mat.set_shader_parameter("to_lut", LUTS[ORDER[st["to"]]])
	mat.set_shader_parameter("mode", st["mode"])
	mat.set_shader_parameter("progress", st["p"])
	_update_place(st)


func _update_place(st: Dictionary) -> void:
	## Ortsname: Überblendung zwischen zwei Labels um die Mitte des Wechsels
	var a_idx: int = st["from"]
	var b_idx: int = st["to"]
	var out_a := 1.0
	var in_b := 0.0
	if st.has("tr"):
		var p: float = st["p"]
		out_a = 1.0 - smoothstep(NAME_OUT[0], NAME_OUT[1], p)
		in_b = smoothstep(NAME_IN[0], NAME_IN[1], p)
	place_a.text = DATA.NAMES[ORDER[a_idx]]
	place_b.text = DATA.NAMES[ORDER[b_idx]]
	place_a.modulate.a = out_a
	place_b.modulate.a = in_b
