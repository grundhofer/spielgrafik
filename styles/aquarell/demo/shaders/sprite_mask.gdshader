shader_type canvas_item;
// Figur: nur innerhalb der bemalten Fläche sichtbar (läuft aus dem Papierrand ins Bild), mit Abendtönung.
uniform sampler2D paint_mask : filter_linear, hint_default_white;
uniform vec3 tint = vec3(1.0);
uniform float breath = 1.0;   // Höhe relativ zur Fußlinie (lokales y = 0)

void vertex() {
	VERTEX.y *= breath;
}

void fragment() {
	vec4 c = COLOR;
	c.rgb *= tint;
	c.a *= smoothstep(0.15, 0.85, texture(paint_mask, SCREEN_UV).a);
	COLOR = c;
}
