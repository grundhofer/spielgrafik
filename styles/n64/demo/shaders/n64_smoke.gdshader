// Rauchwolke als Billboard: 32er-Textur mit weichem Alpha (3-Punkt-Filter), Licht wie die Umgebung
// (Himmelslicht plus Abendsonne), Deckkraft je Wölkchen aus main.gd, Nebel.
shader_type spatial;
render_mode blend_mix, unshaded, cull_disabled, depth_draw_never, shadows_disabled, specular_disabled;

#include "res://shaders/n64_common.gdshaderinc"

uniform sampler2D tex : source_color, filter_nearest, repeat_disable;
uniform float opacity = 1.0;
uniform vec4 tint : source_color = vec4(1.0);

varying float v_fog;
varying vec3 v_light;

void vertex() {
	float s = length(MODEL_MATRIX[0].xyz);
	vec4 c = VIEW_MATRIX * vec4(MODEL_MATRIX[3].xyz, 1.0);
	vec3 v = c.xyz + vec3(VERTEX.xy * s, 0.0);
	POSITION = PROJECTION_MATRIX * vec4(v, 1.0);
	v_fog = n64_fog(length(c.xyz));
	v_light = n64_sky_light.rgb * 1.1 + n64_sun_color.rgb * n64_sun_energy * 0.45;
}

void fragment() {
	vec4 t = n64_filter_level(tex, UV, 0);
	ALBEDO = mix(t.rgb * tint.rgb * v_light, n64_fog_color.rgb, v_fog);
	ALPHA = t.a * opacity;
}
