// Lichthof als Billboard (additiv), wie die Lichtsprites der Zeit: 32er-Textur, 3-Punkt-Filter.
// Der Mittelpunkt wird um pull Meter zur Kamera gezogen, damit Glas und Gehäuse ihn nicht anschneiden.
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, shadows_disabled, specular_disabled;

#include "res://shaders/n64_common.gdshaderinc"

uniform sampler2D tex : source_color, filter_nearest, repeat_disable;
uniform vec4 tint : source_color = vec4(1.0, 0.75, 0.4, 1.0);
uniform float strength = 1.0;
uniform float pull = 0.4;

varying float v_fog;

void vertex() {
	float s = length(MODEL_MATRIX[0].xyz);
	vec4 c = VIEW_MATRIX * vec4(MODEL_MATRIX[3].xyz, 1.0);
	float dist = length(c.xyz);
	c.xyz += normalize(-c.xyz) * min(pull, dist * 0.5);
	vec3 v = c.xyz + vec3(VERTEX.xy * s, 0.0);
	POSITION = PROJECTION_MATRIX * vec4(v, 1.0);
	v_fog = n64_fog(dist);
}

void fragment() {
	vec3 g = n64_filter_level(tex, UV, 0).rgb;
	ALBEDO = g * tint.rgb * strength * (1.0 - 0.6 * v_fog);
}
