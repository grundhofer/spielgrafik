shader_type canvas_item;
// Lasur: multipliziert die eigene Farbe auf das Bild darunter (wie eine transparente Farbschicht).
// Alpha der Textur = Deckung. Optional begrenzt auf eine Bildschirmmaske (z. B. Himmel oder Wasser)
// und immer auf die bemalte Fläche (Alpha des Gemäldes), damit nichts auf das freie Papier gerät.
render_mode blend_mul;

uniform sampler2D region_mask : filter_linear, hint_default_white;
uniform float use_region = 0.0;
uniform sampler2D paint_mask : filter_linear, hint_default_white;
uniform float strength = 1.0;

void fragment() {
	vec4 c = COLOR;
	float m = mix(1.0, texture(region_mask, SCREEN_UV).r, use_region);
	m *= texture(paint_mask, SCREEN_UV).a;
	float a = clamp(c.a * strength * m, 0.0, 1.0);
	COLOR = vec4(mix(vec3(1.0), c.rgb, a), 1.0);
}
