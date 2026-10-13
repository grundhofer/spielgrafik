shader_type canvas_item;
// Ausgewaschenes Licht: Farbe wird zum (warm getönten) Papier hin aufgehellt, normale Mischung.
// Nur innerhalb der bemalten Fläche.
uniform sampler2D paint_mask : filter_linear, hint_default_white;

void fragment() {
	vec4 c = COLOR;
	c.a *= texture(paint_mask, SCREEN_UV).a;
	COLOR = c;
}
