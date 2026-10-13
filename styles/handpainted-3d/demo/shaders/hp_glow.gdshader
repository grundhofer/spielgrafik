// Lichthof (Laterne, Leuchtfeuer, Fenster) als Billboard: weicher Kern und ein gemalter, leicht
// welliger Ring, additiv. Größe und Stärke setzt main.gd (Flackern).
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, fog_disabled, shadows_disabled;

uniform vec3 color : source_color = vec3(1.0, 0.75, 0.4);
uniform float intensity = 1.0;

void vertex() {
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	MODELVIEW_MATRIX = MODELVIEW_MATRIX * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0),
		vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0), vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0),
		vec4(0.0, 0.0, 0.0, 1.0));
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	float a = atan(p.y, p.x);
	float core = exp(-r * r * 9.0);
	float halo = (1.0 - smoothstep(0.0, 1.0, r)) * 0.35;
	float ring_r = 0.62 + 0.03 * sin(a * 5.0);
	float ring = (1.0 - smoothstep(0.0, 0.12, abs(r - ring_r))) * 0.18;
	ALBEDO = color * intensity * (core + halo + ring) * (1.0 - smoothstep(0.85, 1.0, r));
}
