shader_type canvas_item;
// Randfigur: nur das Gold der Trompete wird beleuchtet (gleiches Licht wie Seite und Miniatur).
#include "res://shaders/gold.gdshaderinc"

uniform sampler2D gold_mask : filter_linear;    // R = Gold, B = Relief
uniform vec2 origin = vec2(0.0);
uniform vec2 size = vec2(100.0);

void fragment() {
	vec4 base = texture(TEXTURE, UV);
	vec3 m = texture(gold_mask, UV).rgb;
	vec2 p = origin + UV * size;
	COLOR = vec4(mix(base.rgb, gold_light(base.rgb, m.b, 0.3, p), m.r), base.a);
}
