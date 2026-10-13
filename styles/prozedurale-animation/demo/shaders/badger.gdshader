shader_type canvas_item;
// Dämmerungstönung für alle Teile des Dachses und warmer Schein der Laterne nach Weltabstand.
uniform vec3 tint : source_color = vec3(0.86, 0.84, 0.95);
uniform vec2 lantern_pos = vec2(482.0, 332.0);
uniform float lantern_glow = 1.0;
uniform vec3 lantern_col : source_color = vec3(1.0, 0.70, 0.40);
uniform float lantern_radius = 430.0;
varying vec2 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	vec4 c = COLOR;
	float d = distance(wpos, lantern_pos);
	float k = (1.0 - smoothstep(0.0, lantern_radius, d)) * lantern_glow;
	c.rgb = c.rgb * tint + c.rgb * lantern_col * k * 0.5;
	COLOR = c;
}
