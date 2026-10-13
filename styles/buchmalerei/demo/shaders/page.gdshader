shader_type canvas_item;
// Seite (Pergament, Rahmen, Ranken): nur das Blattgold wird beleuchtet.
#include "res://shaders/gold.gdshaderinc"

uniform sampler2D gold_mask : filter_nearest;   // R = Deckung, G = Phase je Element, B = Relief
uniform vec2 origin = vec2(0.0);
uniform vec2 size = vec2(1280.0, 720.0);

void fragment() {
	vec4 base = texture(TEXTURE, UV);
	vec3 m = texture(gold_mask, UV).rgb;
	vec2 p = origin + UV * size;
	COLOR = vec4(mix(base.rgb, gold_light(base.rgb, m.b, m.g, p), m.r), base.a);
}
