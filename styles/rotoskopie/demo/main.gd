extends Node2D
## Hafen von Lornholm mit dem rotoskopierten Dachs-Kurier.
## Die Bewegung kommt aus der 3D-Vorlage (blender/rotoscope.py), das Aussehen aus der KI-Übermalung
## (assets/raw/sheet.png, scripts/build_ai_sprites.py). Platzierung nur aus den 3D-Daten: Der Laufzyklus läuft in
## Blender auf der Stelle, der Standfuß wandert je Phase 0,367 m/s × 1/8 s = 6,79 px nach hinten; genau so weit
## rückt der Fußpunkt der Figur je Phasenwechsel vor (art/anim.json). Kein Messen oder Nachschieben je Bild.
##
## Ablauf (Videobilder bei 30 fps): 0–95 Laufen, 8 Phasen auf Zweien (15 Bilder/s, 6 Zyklen);
## 96 Stand (Fußpunkt so versetzt, dass der rechte Standfuß liegen bleibt), 104 Ausholen, 110/114 Paket nach vorn,
## 118 Verbeugung, 134 Paket hingehalten bis zum Ende.
##
## Benutzerargumente (nach "--"):
##   --t0=<s>            Startzeit (Langzeitprüfung)
##   --badger-only       nur der Dachs vor einer Grundfarbe (Fußmessung); --key=<rrggbb> wählt sie (Standard ff00ff)
##   --variant=classic   in der Szene die Skript-Fassung ohne KI statt der KI-Übermalung
##   --variant=template  in der Szene die Graustufen-Vorlage

const FPS := 30
const GROUND_Y := 640.0          # Bodenzeile: Projektion von z = 3,9 m mit der Szenenkamera (style.json → camera)
const X0 := 100.0                # Fußpunkt beim ersten Bild
const WALK_FRAMES := 96
const GIVE_PLAN := [[96, 8], [104, 9], [110, 10], [114, 11], [118, 12], [134, 13]]
const LINE := "Die Laterne flackert im Wind.\nAm Kai wartet ein Paket auf dich."
const TYPE_START := 0.4
const CPS := 34.0
const PARSER := "> nimm paket"
const PARSER_START := 4.2
const TINT := Color(0.92, 0.90, 0.98)

var t := 0.0
var meta: Dictionary
var badger_only := false
var variant := "ai"

@onready var bg: Sprite2D = $Bg
@onready var badger: Sprite2D = $Badger
@onready var shadow: Polygon2D = $Shadow
@onready var fx := [$Smoke, $Light, $Gulls]
@onready var panel = $UI/Panel
@onready var line_label: Label = $UI/Dialog/Line
@onready var parser_label: Label = $UI/Dialog/Parser
@onready var cursor: ColorRect = $UI/Dialog/Cursor
@onready var pill: Panel = $UI/Dialog/Pill


func _ready() -> void:
	var key := Color(1, 0, 1)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t = float(a.substr(5))
		elif a == "--badger-only":
			badger_only = true
		elif a.begins_with("--key="):
			key = Color("#" + a.substr(6))
		elif a.begins_with("--variant="):
			variant = a.substr(10)
	var f := FileAccess.open("res://art/anim.json", FileAccess.READ)
	meta = JSON.parse_string(f.get_as_text())
	var files := {"ai": "res://art/badger_ai.png", "classic": "res://art/badger_classic.png",
			"template": "res://art/badger_template.png"}
	badger.texture = load(files[variant])
	badger.region_enabled = true
	badger.modulate = TINT if variant != "template" else Color.WHITE
	var pts := PackedVector2Array()
	for i in 24:
		var a := TAU * i / 24.0
		pts.append(Vector2(cos(a) * 36.0, sin(a) * 6.5))
	shadow.polygon = pts
	panel.setup(meta)
	if badger_only:
		RenderingServer.set_default_clear_color(key)
		for n in [bg, shadow, $UI] + fx:
			n.hide()
		badger.modulate = Color.WHITE
	_update()


func _process(delta: float) -> void:
	t += delta
	_update()


func pose_at(n: int) -> Array:
	## [Posennummer, Fußpunkt x, Phasentext]
	var step: float = meta["step_px"]
	if n < WALK_FRAMES:
		var p := n / 2
		return [p % 8, X0 + p * step, "Laufen · Phase %d/8 · 15 Bilder/s" % (p % 8 + 1)]
	var x: float = X0 + (WALK_FRAMES / 2 - 1) * step + float(meta["stand_offset_px"])
	var idx := 8
	for g in GIVE_PLAN:
		if n >= g[0]:
			idx = g[1]
	return [idx, x, "Paket überreichen · Phase %d/6" % (idx - 7)]


func _update() -> void:
	var n := int(round(t * FPS))
	var info := pose_at(n)
	var idx: int = info[0]
	var fw: float = meta["frame"][0]
	var fh: float = meta["frame"][1]
	var root_x := roundf(info[1])
	badger.region_rect = Rect2(idx * fw, 0, fw, fh)
	badger.position = Vector2(root_x - float(meta["anchor"][0]), GROUND_Y - float(meta["anchor"][1]))
	shadow.position = Vector2(root_x + 2.0, GROUND_Y + 1.0)
	(bg.material as ShaderMaterial).set_shader_parameter("t", t)
	for node in fx:
		node.t = t
		node.queue_redraw()
	panel.pose = idx
	panel.phase_text = info[2]
	panel.iou = meta["iou_placed"][idx]
	panel.queue_redraw()
	var chars := int(maxf(0.0, t - TYPE_START) * CPS)
	line_label.visible_characters = chars
	var pchars := int(maxf(0.0, t - PARSER_START) * 12.0)
	parser_label.text = PARSER.substr(0, mini(pchars, PARSER.length()))
	cursor.visible = fmod(t, 0.8) < 0.5
	cursor.position.x = parser_label.position.x + parser_label.get_minimum_size().x + 2.0
	pill.visible = n >= 118
