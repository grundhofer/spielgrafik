// Dialogpanel: fast schwarze Fläche mit gemalter, ausgefranster linker Kante und Trockenpinsel-Streifen.
shader_type canvas_item;
#include "res://shaders/noise.gdshaderinc"

uniform vec2 size = vec2(360.0, 720.0);
uniform vec4 base : source_color = vec4(0.047, 0.047, 0.055, 0.96);
uniform float edge_px = 30.0;

void fragment() {
	vec2 p = UV * size;
	float e = edge_px * (0.3 + 0.7 * vnoise(vec2(p.y * 0.035, 1.7))) + 7.0 * vnoise(vec2(p.y * 0.45, 3.0));
	float a = smoothstep(e - 1.0, e + 1.0, p.x);
	// Trockenpinsel: nahe der Kante reißt die Farbe in waagerechten Streifen auf
	float dry = vnoise(vec2(p.x * 0.06, p.y * 0.9)) * 0.7 + vnoise(vec2(p.x * 0.2, p.y * 2.3)) * 0.3;
	float inner = smoothstep(0.0, 34.0, p.x - e);
	a *= mix(step(0.42, dry), 1.0, inner);
	float streak = vnoise(vec2(p.x * 0.015, p.y * 0.5)) * 0.6 + vnoise(vec2(p.x * 0.05, p.y * 1.6)) * 0.4;
	vec3 col = base.rgb * (0.8 + 0.5 * streak);
	COLOR = vec4(col, a * base.a);
}
