// Gemalter Rauchballen als Billboard: runde, an den Rändern ausgefranste Form, oben links hell
// (Abendlicht), unten rechts violett, weicher Rand. Alter (0..1) und Zufallswert je Instanz.
shader_type spatial;
render_mode blend_mix, unshaded, cull_disabled, depth_draw_never, shadows_disabled;

uniform vec3 light_col : source_color = vec3(0.96, 0.82, 0.78);
uniform vec3 mid_col : source_color = vec3(0.70, 0.62, 0.78);
uniform vec3 dark_col : source_color = vec3(0.42, 0.38, 0.58);
instance uniform float opacity = 1.0;
instance uniform float seed = 0.0;

float hash(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

void vertex() {
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	MODELVIEW_MATRIX = MODELVIEW_MATRIX * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0),
		vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0), vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0),
		vec4(0.0, 0.0, 0.0, 1.0));
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	p.y = -p.y;
	float a = atan(p.y, p.x);
	// Umriss aus drei Beulen (gemalte Wolkenform) und leichtem Rauschen
	float rr = 0.78 + 0.08 * sin(a * 3.0 + seed * 6.0) + 0.05 * sin(a * 5.0 + seed * 11.0)
		+ 0.06 * (vnoise(vec2(a * 2.0, seed * 9.0)) - 0.5);
	float r = length(p) / rr;
	float shape = 1.0 - smoothstep(0.82, 1.0, r);
	// gemalte Schattierung: Licht von oben links
	float lit = dot(normalize(vec2(-0.6, 0.8)), p) * 0.6 + 0.5 - 0.25 * r;
	vec3 col = mix(dark_col, mid_col, smoothstep(0.1, 0.45, lit));
	col = mix(col, light_col, smoothstep(0.5, 0.8, lit));
	ALBEDO = col;
	ALPHA = shape * opacity;
}
