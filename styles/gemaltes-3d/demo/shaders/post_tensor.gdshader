// Nachbearbeitung 1: Strukturtensor des Farbbilds (Sobel je Farbkanal, summiert).
// Ausgabe (Gleitkomma): r = gx·gx, g = gx·gy, b = gy·gy. Daraus liest der Kuwahara-Filter nach dem
// Weichzeichnen die Richtung der Kanten und wie gerichtet die Stelle ist (Kyprianidis u. a. 2009).
shader_type canvas_item;

uniform sampler2D src : filter_nearest, repeat_disable;

vec3 px(ivec2 p, ivec2 sz) {
	return texelFetch(src, clamp(p, ivec2(0), sz - 1), 0).rgb;
}

void fragment() {
	ivec2 sz = textureSize(src, 0);
	ivec2 p = ivec2(UV * vec2(sz));
	vec3 gx = (px(p + ivec2(1, -1), sz) + 2.0 * px(p + ivec2(1, 0), sz) + px(p + ivec2(1, 1), sz)
			- px(p + ivec2(-1, -1), sz) - 2.0 * px(p + ivec2(-1, 0), sz) - px(p + ivec2(-1, 1), sz)) / 4.0;
	vec3 gy = (px(p + ivec2(-1, 1), sz) + 2.0 * px(p + ivec2(0, 1), sz) + px(p + ivec2(1, 1), sz)
			- px(p + ivec2(-1, -1), sz) - 2.0 * px(p + ivec2(0, -1), sz) - px(p + ivec2(1, -1), sz)) / 4.0;
	COLOR = vec4(dot(gx, gx), dot(gx, gy), dot(gy, gy), 1.0);
}
