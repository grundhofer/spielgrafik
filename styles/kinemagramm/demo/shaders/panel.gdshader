shader_type canvas_item;
// Textfeld: dunkle, durchscheinende Lasur mit weich auslaufenden Rändern und einer feinen warmen Linie
// unter dem Ortsnamen. Kein harter Rahmen, damit das Gemälde ringsum ungestört bleibt.

uniform vec2 rect_size = vec2(560.0, 210.0);
uniform vec4 base_col = vec4(0.03, 0.035, 0.06, 0.80);
uniform vec4 line_col = vec4(0.84, 0.66, 0.38, 0.85);
uniform float feather = 14.0;
uniform float line_y = 44.0;
uniform float line_x0 = 28.0;
uniform float reveal = 1.0;

void fragment() {
	vec2 p = UV * rect_size;
	float d = min(min(p.x, rect_size.x - p.x), min(p.y, rect_size.y - p.y));
	float a = smoothstep(0.0, feather, d) * base_col.a;
	vec3 c = base_col.rgb * mix(1.15, 0.85, UV.y);
	// feine Linie unter dem Ortsnamen, an den Enden ausgeblendet
	float ly = 1.0 - smoothstep(0.0, 1.0, abs(p.y - line_y));
	float lx = smoothstep(line_x0, line_x0 + 40.0, p.x) * (1.0 - smoothstep(rect_size.x * 0.55, rect_size.x * 0.9, p.x));
	float l = ly * lx * line_col.a;
	c = mix(c, line_col.rgb, l);
	a = max(a, l);
	COLOR = vec4(c, a * reveal);
}
