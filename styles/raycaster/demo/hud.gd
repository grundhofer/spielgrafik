extends Control
## Oberfläche wie in den Sektor-Shootern: Meldungen oben links (rote Schrift mit Schatten, Großbuchstaben),
## Statusleiste unten (320 x 32): Paketzähler mit großer Ziffer, Auswahl 1–3 wie die Waffenleiste,
## Ort und Inventarfeld. Schrift zeichnet Godot ohne Kantenglättung; Farben stammen aus der Palette
## (Verläufe in ui/grad_*.png, je Bildzeile eine Farbe).

const BAR_Y := 168
const LINE := "DIE LATERNE FLACKERT IM WIND."
const LINE2 := "AM KAI WARTET EIN PAKET AUF DICH."
const PARSER := "> NIMM PAKET"
const PICKUP := "DU NIMMST DAS PAKET."
const CHOICES := ["ZUM LEUCHTTURM GEHEN", "DAS PAKET ANSEHEN", "MIT DEM DACHS SPRECHEN"]

var font_s: FontFile      # Silkscreen Bold, 8 px (Statusleiste)
var font_m: FontFile      # Press Start 2P, 8 px (Meldungen)
var font_l: FontFile      # Jersey 20, 20 px (große Ziffer)
var main: Node
var items := {}


class TextItem extends Control:
	var text := ""
	var font: Font
	var size_px := 10
	var cap_top := 0          # Abstand Grundlinie -> oberste Zeile der Großbuchstaben
	var shadow := true
	var shadow_color := Color.BLACK
	var grad_tex: Texture2D
	var _fg: Control

	func setup(p_font: Font, p_size: int, p_grad: Texture2D, p_shadow: Color, mat_shader: Shader) -> void:
		font = p_font
		size_px = p_size
		grad_tex = p_grad
		shadow_color = p_shadow
		_fg = Control.new()
		_fg.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var m := ShaderMaterial.new()
		m.shader = mat_shader
		m.set_shader_parameter("grad", grad_tex)
		_fg.material = m
		_fg.draw.connect(_draw_fg)
		add_child(_fg)

	func set_text(s: String) -> void:
		if s != text:
			text = s
			queue_redraw()
			_fg.queue_redraw()

	func set_top(y: int) -> void:
		(_fg.material as ShaderMaterial).set_shader_parameter("top_y", float(y))

	func _draw() -> void:
		if shadow and text != "":
			draw_string(font, Vector2(1, 1), text, HORIZONTAL_ALIGNMENT_LEFT, -1, size_px, shadow_color)

	func _draw_fg() -> void:
		if text != "":
			_fg.draw_string(font, Vector2(0, 0), text, HORIZONTAL_ALIGNMENT_LEFT, -1, size_px, Color.WHITE)


func _pixel_font(path: String) -> FontFile:
	var f := FontFile.new()
	f.data = FileAccess.get_file_as_bytes(path)
	f.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	f.hinting = TextServer.HINTING_NONE
	f.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	f.generate_mipmaps = false
	return f


func _ready() -> void:
	main = get_parent()
	font_s = _pixel_font("res://fonts/Silkscreen-Bold.ttf")
	font_m = _pixel_font("res://fonts/PressStart2P-Regular.ttf")
	font_l = _pixel_font("res://fonts/Jersey20-Regular.ttf")
	var shader := preload("res://shaders/text.gdshader")
	var red := preload("res://ui/grad_red.png")
	var gold := preload("res://ui/grad_gold.png")
	var gray := preload("res://ui/grad_gray.png")
	var shadow_col: Color = preload("res://ui/shadow.png").get_image().get_pixel(0, 0)
	var bar := TextureRect.new()
	bar.texture = preload("res://ui/statusbar.png")
	bar.position = Vector2(0, BAR_Y)
	add_child(bar)
	# Meldungen oben links (Grundlinie, Abstand 10 Zeilen)
	for i in 3:
		_item("msg%d" % i, font_m, 8, red, shadow_col, shader, Vector2(2, 9 + 10 * i), 7)
	# Statusleiste
	_item("paket_label", font_s, 8, gray, shadow_col, shader, Vector2(8, BAR_Y + 10), 5)
	_item("paket_num", font_l, 20, red, shadow_col, shader, Vector2(19, BAR_Y + 27), 13)
	for i in 3:
		_item("num%d" % i, font_s, 8, gold, shadow_col, shader, Vector2(52, BAR_Y + 10 + 8 * i), 5)
		_item("choice%d" % i, font_s, 8, gray, shadow_col, shader, Vector2(61, BAR_Y + 10 + 8 * i), 5)
	_item("ort1", font_s, 8, gold, shadow_col, shader, Vector2(214, BAR_Y + 12), 5)
	_item("ort2", font_s, 8, gold, shadow_col, shader, Vector2(214, BAR_Y + 22), 5)
	var icon := TextureRect.new()
	icon.name = "icon"
	icon.texture = preload("res://ui/parcel_icon.png")
	icon.position = Vector2(299, BAR_Y + 16)
	add_child(icon)
	items["icon"] = icon
	items["paket_label"].set_text("PAKET")
	for i in 3:
		items["num%d" % i].set_text(str(i + 1))
		items["choice%d" % i].set_text(CHOICES[i])
	items["ort1"].set_text("HAFEN VON")
	items["ort2"].set_text("LORNHOLM")


func _item(key: String, f: Font, sz: int, grad: Texture2D, sh: Color, shader: Shader, baseline: Vector2,
		cap: int) -> void:
	var it := TextItem.new()
	it.mouse_filter = Control.MOUSE_FILTER_IGNORE
	it.setup(f, sz, grad, sh, shader)
	it.position = baseline
	it.set_top(int(baseline.y) - cap)
	add_child(it)
	items[key] = it


func _process(_delta: float) -> void:
	var t: float = main.t
	items["msg0"].set_text(LINE if t >= 0.4 else "")
	items["msg1"].set_text(LINE2 if t >= 1.4 else "")
	var line3 := ""
	if t >= main.pickup_t:
		line3 = PICKUP
	elif t >= 3.9:
		var n := clampi(int((t - 3.9) / 0.07), 0, PARSER.length())
		var cursor := "_" if int(t * 4.0) % 2 == 0 or n < PARSER.length() else ""
		line3 = PARSER.substr(0, n) + cursor
	items["msg2"].set_text(line3)
	items["paket_num"].set_text("1" if t >= main.pickup_t else "0")
	items["icon"].visible = t >= main.pickup_t
