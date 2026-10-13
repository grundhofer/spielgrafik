// Rundschatten unter der Figur (wie bei Figuren der Zeit): weiche Scheibe aus einer 32er-Textur, die den
// Kaiboden darunter abdunkelt (Multiplikation mit 1 − Deckkraft), liegt knapp über dem Boden.
shader_type spatial;
render_mode blend_mul, unshaded, cull_back, depth_draw_never, shadows_disabled, specular_disabled;

#include "res://shaders/n64_common.gdshaderinc"

uniform sampler2D tex : filter_nearest, repeat_disable;
uniform float strength = 0.6;

varying float v_fog;

void vertex() {
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_fog = n64_fog(-(VIEW_MATRIX * vec4(wp, 1.0)).z);
}

void fragment() {
	float a = n64_filter_level(tex, UV, 0).a * strength * (1.0 - v_fog);
	ALBEDO = vec3(1.0 - a);
}
