// Rauchballen aus dem Schornstein: Billboard mit weichem, beuligem Umriss, links (zur Abendsonne)
// warm angestrahlt, rechts kühl violett. Deckung je Ballen als Instanz-Uniform (Alter).
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_disabled, shadows_disabled;

#include "res://shaders/paint_common.gdshaderinc"

uniform vec3 lit_color : source_color = vec3(0.86, 0.66, 0.62);
uniform vec3 shade_color : source_color = vec3(0.42, 0.38, 0.52);
instance uniform float opacity = 0.0;
instance uniform float seed = 0.0;

void vertex() {
	// Billboard: zur Kamera drehen, Größe aus der Modellmatrix
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	MODELVIEW_MATRIX = MODELVIEW_MATRIX * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0),
			vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0), vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0),
			vec4(0.0, 0.0, 0.0, 1.0));
}

void fragment() {
	vec2 c = UV * 2.0 - 1.0;
	float ang = atan(c.y, c.x);
	float bump = 0.13 * vnoise2(vec2(ang * 1.6 + seed * 7.0, seed * 3.0)) + 0.07 * vnoise2(vec2(ang * 4.0, seed * 5.0 + 9.0));
	float r = length(c) / (0.8 + bump);
	float a = 1.0 - smoothstep(0.55, 1.0, r);
	// Licht von links oben
	float lit = clamp(0.5 - 0.6 * c.x - 0.25 * c.y, 0.0, 1.0);
	ALBEDO = mix(shade_color, lit_color, smoothstep(0.25, 0.75, lit));
	ALPHA = a * opacity;
}
