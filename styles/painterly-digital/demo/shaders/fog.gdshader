// Nebelband: zwei Lagen Wertrauschen (fbm), die gegeneinander driften; oben und unten weich ausgeblendet.
// Rein eine Funktion von UV und time_s, damit die Aufnahme reproduzierbar bleibt.
shader_type canvas_item;

uniform vec4 fog_color : source_color = vec4(0.62, 0.70, 0.74, 0.5);
uniform float time_s = 0.0;
uniform vec2 scale = vec2(5.0, 1.6);
uniform vec2 speed_a = vec2(0.012, 0.0);
uniform vec2 speed_b = vec2(-0.007, 0.003);
uniform float top_soft = 0.35;
uniform float bottom_soft = 0.35;
uniform float coverage = 0.45;
uniform float seed = 0.0;

float hash(vec2 p) { return fract(sin(dot(p + seed, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) {
	float v = 0.0;
	float a = 0.55;
	for (int i = 0; i < 5; i++) {
		v += a * vnoise(p);
		p = p * 2.03 + vec2(1.7, 9.2);
		a *= 0.5;
	}
	return v;
}

void fragment() {
	vec2 p = UV * scale;
	float n = 0.6 * fbm(p + time_s * speed_a * scale) + 0.4 * fbm(p * 1.7 + vec2(5.1, 2.3) + time_s * speed_b * scale);
	float body = smoothstep(coverage - 0.18, coverage + 0.22, n);
	float v = smoothstep(0.0, top_soft, UV.y) * smoothstep(0.0, bottom_soft, 1.0 - UV.y);
	float edge = smoothstep(0.0, 0.08, UV.x) * smoothstep(0.0, 0.08, 1.0 - UV.x);
	COLOR = vec4(fog_color.rgb, fog_color.a * body * v * edge);
}
