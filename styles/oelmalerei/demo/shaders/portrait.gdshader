// Porträt im Dialogpanel: ausgefranster, gemalter Rand statt Rahmen; das Laternenlicht flackert mit.
shader_type canvas_item;
#include "res://shaders/noise.gdshaderinc"

uniform vec2 size = vec2(300.0, 320.0);
uniform float flicker = 0.0;          // -1..1 vom Skript, gleiche Kurve wie die Laterne
uniform float time_s = 0.0;

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	vec2 p = UV * size;
	float d = min(min(p.x, size.x - p.x), min(p.y, size.y - p.y));
	float st = floor(time_s * 6.0);
	float n = vnoise(vec2(p.x + p.y, p.y - p.x) * vec2(0.07, 0.35) + st * 0.0) * 16.0 + vnoise(p * 0.25) * 6.0;
	float a = smoothstep(n, n + 2.0, d);
	// Warmes Licht von rechts flackert mit der Laterne
	float side = smoothstep(0.35, 1.0, UV.x);
	c.rgb *= 1.0 + flicker * side * vec3(0.10, 0.06, 0.015);
	COLOR = vec4(c.rgb, c.a * a);
}
