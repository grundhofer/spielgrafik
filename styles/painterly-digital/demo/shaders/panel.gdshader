// Dialogfeld: dunkle, weich auslaufende Fläche mit leichter Pinseltextur, feine Goldlinie oben und unten
// mit Raute in der Mitte (Ornament wie in gemalten Abenteuer- und Erkundungsspielen).
shader_type canvas_item;

uniform vec2 size = vec2(620.0, 250.0);
uniform vec4 fill : source_color = vec4(0.03, 0.05, 0.07, 0.78);
uniform vec4 line_color : source_color = vec4(0.86, 0.72, 0.48, 0.85);
uniform float fade = 1.0;
uniform float feather = 26.0;

float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
float vnoise(vec2 p) {
	vec2 i = floor(p); vec2 f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}

float hline(vec2 p, float y, float half_w) {
	// dünne Linie, zur Mitte hin voll, zu den Enden auslaufend
	float d = abs(p.y - y);
	float along = 1.0 - smoothstep(half_w * 0.55, half_w, abs(p.x - size.x * 0.5));
	return (1.0 - smoothstep(0.4, 1.3, d)) * along;
}

float diamond(vec2 p, vec2 c, float r) {
	vec2 d = abs(p - c);
	return 1.0 - smoothstep(r - 0.8, r + 0.8, d.x + d.y);
}

void fragment() {
	vec2 p = UV * size;
	// weiche Ränder: Abstand zum Rechteck, mit Rauschen ausgefranst
	float dx = min(p.x, size.x - p.x);
	float dy = min(p.y, size.y - p.y);
	float n = vnoise(p * vec2(0.035, 0.12)) * 0.6 + vnoise(p * 0.11) * 0.4;
	float edge = smoothstep(0.0, feather, dx + n * 14.0 - 4.0) * smoothstep(0.0, feather * 0.7, dy + n * 10.0 - 3.0);
	float tex = 0.92 + 0.08 * vnoise(p * vec2(0.02, 0.3));
	vec4 c = vec4(fill.rgb * tex, fill.a * edge);
	// Ornament
	float top_y = 12.0;
	float bot_y = size.y - 12.0;
	float l = max(hline(p, top_y, size.x * 0.42), hline(p, bot_y, size.x * 0.30));
	float dm = max(diamond(p, vec2(size.x * 0.5, top_y), 5.0), diamond(p, vec2(size.x * 0.5, bot_y), 4.0));
	float dm_hole = diamond(p, vec2(size.x * 0.5, top_y), 2.2);
	float orn = max(l, dm * (1.0 - dm_hole * 0.85));
	c.rgb = mix(c.rgb, line_color.rgb, orn * line_color.a);
	c.a = max(c.a, orn * line_color.a);
	c.a *= fade;
	COLOR = c;
}
