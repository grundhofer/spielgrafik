shader_type canvas_item;
// Figur in der Abendszene: Tönung (Dämmerlicht) und warmer Schein der Laterne nach Bildschirmabstand.
// Die Farbe kommt schon gewichtet aus Polygon2D (COLOR = Textur × Polygonfarbe); Licht nur über
// Bildschirmkoordinaten, damit es von der Knochenverformung unabhängig ist.

uniform vec3 ambient = vec3(0.84, 0.82, 0.92);
uniform vec2 light_pos = vec2(848.0, 358.0);   // Bildschirm-Pixel (Laterne)
uniform vec3 light_col = vec3(1.0, 0.70, 0.40);
uniform float light_radius = 520.0;
uniform float light_amount = 0.0;
uniform float scr_scale = 1.0;                  // Fensterpixel je Viewport-Pixel (Aufnahme 1280×720 = 1)

void fragment() {
	vec4 c = COLOR;
	float d = distance(FRAGCOORD.xy / scr_scale, light_pos);
	float l = light_amount * (1.0 - smoothstep(0.0, light_radius, d));
	c.rgb = c.rgb * ambient + c.rgb * light_col * l;
	COLOR = c;
}
