// Textkarte der Oberfläche: ein Stück Aquarellpapier mit gerissenem Rand, leichter Körnung, einem
// blassen Farbauftrag (Lasur) und dunklerem Pigmentrand, darunter ein weicher Schatten.
// Das Rechteck des ColorRect ist um "margin" Pixel größer als die Karte (Platz für Schatten und Rand).
shader_type canvas_item;

#include "res://shaders/paint_common.gdshaderinc"

uniform vec2 rect_size = vec2(636.0, 146.0);   // Karte ohne Rand
uniform float margin = 16.0;
uniform vec3 paper : source_color = vec3(0.96, 0.925, 0.85);
uniform vec3 wash : source_color = vec3(0.80, 0.70, 0.86);
uniform float opacity = 1.0;
uniform float seed = 3.0;

float box_dist(vec2 x, vec2 lo, vec2 hi) {
	vec2 d = max(lo - x, x - hi);
	return max(d.x, d.y);   // < 0 innen
}

void fragment() {
	vec2 full = rect_size + 2.0 * margin;
	vec2 x = UV * full - margin;                 // Pixel relativ zur Karte
	float rag = (fbm2(x / 7.0 + seed) - 0.5) * 7.0 + (vnoise2(x / 2.2 + seed * 3.0) - 0.5) * 2.5;
	float d = box_dist(x, vec2(0.0), rect_size) + rag;
	float inside = 1.0 - smoothstep(-0.8, 0.8, d);
	// Schatten: weich, nach rechts unten versetzt
	float ds = box_dist(x - vec2(4.0, 6.0), vec2(0.0), rect_size);
	float shadow = (1.0 - smoothstep(-6.0, 10.0, ds)) * 0.35;
	// Papierkörnung
	float g = 0.62 * fbm2(x / 5.5) + 0.38 * vnoise2(x / 1.7 + 13.0);
	float gx = 0.62 * fbm2((x + vec2(1.0, 0.0)) / 5.5) + 0.38 * vnoise2((x + vec2(1.0, 0.0)) / 1.7 + 13.0);
	vec3 col = paper * (1.0 + (g - gx) * 0.9 - (1.0 - g) * 0.05);
	// Lasur: blasser Farbfleck hinter dem Ortsnamen, auslaufend, mit Pigmentrand
	vec2 wc = (x - vec2(150.0, 26.0)) / vec2(190.0, 34.0);
	float wd = length(wc) - 1.0 + (fbm2(x / 16.0 + 5.0) - 0.5) * 0.55;
	float w = 1.0 - smoothstep(-0.04, 0.0, wd);
	float wash_edge = smoothstep(-0.25, -0.01, wd) * w;
	float wash_amt = w * (0.20 + 0.12 * fbm2(x / 24.0 + 2.0)) + wash_edge * 0.22;
	col = mix(col, col * wash, wash_amt);
	// Rand der Karte etwas dunkler (Papierfaser)
	col *= 1.0 - 0.10 * smoothstep(-5.0, 0.0, d);
	vec4 card = vec4(col, inside);
	vec4 sh = vec4(0.08, 0.05, 0.12, shadow * (1.0 - inside));
	COLOR = vec4(mix(sh.rgb, card.rgb, card.a), max(card.a, sh.a) * opacity);
}
