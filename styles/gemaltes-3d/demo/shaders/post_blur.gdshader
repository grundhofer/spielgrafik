// Nachbearbeitung: Gauß-Weichzeichner in einer Richtung (zwei Durchgänge: waagrecht, dann senkrecht).
// Für den Strukturtensor und für die weiche Fassung des gemalten Bildes (Randabdunklung).
shader_type canvas_item;

uniform sampler2D src : filter_nearest, repeat_disable;
uniform vec2 dir = vec2(1.0, 0.0);
uniform float sigma = 2.0;

void fragment() {
	ivec2 sz = textureSize(src, 0);
	ivec2 p = ivec2(UV * vec2(sz));
	int r = int(ceil(2.5 * sigma));
	vec4 acc = vec4(0.0);
	float wsum = 0.0;
	ivec2 d = ivec2(dir);
	for (int i = -r; i <= r; i++) {
		float w = exp(-float(i * i) / (2.0 * sigma * sigma));
		acc += w * texelFetch(src, clamp(p + d * i, ivec2(0), sz - 1), 0);
		wsum += w;
	}
	COLOR = acc / wsum;
}
