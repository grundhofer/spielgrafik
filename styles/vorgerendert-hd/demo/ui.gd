extends Control
## HD dialog in the same placement and fonts as the retro comparison.
var t := 0.0
var shot := "totale"
var title_font := FontFile.new()
var text_font := FontFile.new()
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
func _ready() -> void:
    title_font.load_dynamic_font("res://fonts/Cinzel-wght.ttf")
    text_font.load_dynamic_font("res://fonts/FiraSans-Medium.ttf")
    for font in [title_font, text_font]:
        font.antialiasing = TextServer.FONT_ANTIALIASING_GRAY
        font.hinting = TextServer.HINTING_LIGHT
        font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_AUTO
    var ts := TextServerManager.get_primary_interface()
    title_font.set_variation_coordinates(0, {ts.name_to_tag("wght"): 600})
func _draw() -> void:
    if shot == "totale":
        var alpha := smoothstep(0.25, 0.75, t) * (1 - smoothstep(1.85, 2.1, t))
        draw_string(title_font, Vector2(648, 810), "Hafen von Lornholm", HORIZONTAL_ALIGNMENT_LEFT, -1, 40, Color(0.97, 0.93, 0.84, alpha))
        return
    var alpha := smoothstep(2.15, 2.4, t)
    var box := Rect2(40, 680, 1200, 264)
    draw_style_box(_panel(alpha), box)
    var shown := int(maxf(0, t - 2.45) * 38)
    for i in LINES.size():
        var line: String = LINES[i]
        var n := clampi(shown, 0, line.length())
        shown -= line.length()
        draw_string(text_font, Vector2(76, 733 + i * 44), line.substr(0, n), HORIZONTAL_ALIGNMENT_LEFT, -1, 36, Color(0.96, 0.95, 0.9, alpha))
    var done := 2.45 + float(LINES[0].length() + LINES[1].length()) / 38
    var ca := smoothstep(done + 0.15, done + 0.4, t) * alpha
    for i in CHOICES.size():
        var color := Color(1, 0.86, 0.55, ca) if i == 0 else Color(0.78, 0.8, 0.86, ca)
        draw_string(text_font, Vector2(124, 832 + i * 40), CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 32, color)
    draw_colored_polygon(PackedVector2Array([Vector2(84, 808), Vector2(100, 819), Vector2(84, 830)]), Color(1, 0.86, 0.55, ca))
func _panel(alpha: float) -> StyleBoxFlat:
    var panel := StyleBoxFlat.new()
    panel.bg_color = Color(0.035, 0.045, 0.07, 0.87 * alpha)
    panel.border_color = Color(0.72, 0.74, 0.8, alpha)
    panel.set_border_width_all(2)
    panel.set_corner_radius_all(8)
    return panel
