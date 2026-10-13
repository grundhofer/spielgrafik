shader_type canvas_item;
// Namensfeld / Auswahlknopf: Pille mit waagerechtem Verlauf, weißer Kante, weicher Schatten.
// hover blendet zwischen Grundfarben (a) und Hervorhebung (b).
uniform vec2 size = vec2(220.0, 40.0);
uniform float radius = 20.0;
uniform vec4 left_a : source_color = vec4(0.95, 0.47, 0.47, 1.0);
uniform vec4 right_a : source_color = vec4(0.99, 0.70, 0.42, 1.0);
uniform vec4 left_b : source_color = vec4(0.95, 0.47, 0.47, 1.0);
uniform vec4 right_b : source_color = vec4(0.99, 0.70, 0.42, 1.0);
uniform vec4 edge_color : source_color = vec4(1.0, 0.97, 0.94, 1.0);
uniform float edge_w = 2.0;
uniform float hover = 0.0;
uniform float shadow = 0.35;
uniform float pad = 6.0;  // Rand für den Schatten (Rechteck ist um pad größer als die Form)

// Distanzfunktion abgerundetes Rechteck nach Inigo Quilez – Copyright (c) Inigo Quilez, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt), https://iquilezles.org/articles/distfunctions2d/
float sd_box(vec2 p, vec2 b, float r) {
	vec2 q = abs(p) - b + vec2(r);
	return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

void fragment() {
	vec2 p = UV * size - size * 0.5;
	vec2 b = size * 0.5 - vec2(pad);
	float d = sd_box(p, b, radius);
	float ds = sd_box(p - vec2(2.0, 3.0), b, radius);
	float fill = clamp(0.5 - d, 0.0, 1.0);
	float sh = (1.0 - smoothstep(-2.0, 4.0, ds)) * shadow;
	float u = clamp((p.x + b.x) / (2.0 * b.x), 0.0, 1.0);
	vec4 c = mix(mix(left_a, right_a, u), mix(left_b, right_b, u), hover);
	c.rgb += vec3(0.08) * smoothstep(0.0, -b.y, p.y);   // obere Hälfte heller
	float edge = clamp(1.0 - abs(d + edge_w * 0.5) / (edge_w * 0.5 + 0.5), 0.0, 1.0);
	c = mix(c, edge_color, edge);
	vec3 rgb = mix(vec3(0.04, 0.03, 0.12), c.rgb, fill);
	float a = mix(sh, c.a, fill);
	COLOR = vec4(rgb, a * COLOR.a);
}
