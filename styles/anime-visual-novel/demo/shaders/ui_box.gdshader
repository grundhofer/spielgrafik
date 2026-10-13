shader_type canvas_item;
// VN-Textfenster: abgerundetes Rechteck, halbtransparenter Verlauf, doppelte helle Kante,
// feine Schrägstreifen und ein heller Glanz an der Oberkante.
uniform vec2 size = vec2(1168.0, 160.0);
uniform float radius = 18.0;
uniform vec4 top_color : source_color = vec4(0.13, 0.13, 0.32, 0.80);
uniform vec4 bottom_color : source_color = vec4(0.06, 0.06, 0.18, 0.90);
uniform vec4 edge_color : source_color = vec4(0.98, 0.90, 0.96, 0.85);
uniform vec4 inner_color : source_color = vec4(1.0, 0.86, 0.80, 0.40);
uniform float inner_inset = 7.0;
uniform float stripes = 0.035;

// Distanzfunktion abgerundetes Rechteck nach Inigo Quilez – Copyright (c) Inigo Quilez, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt), https://iquilezles.org/articles/distfunctions2d/
float sd_box(vec2 p, vec2 b, float r) {
	vec2 q = abs(p) - b + vec2(r);
	return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

void fragment() {
	vec2 p = UV * size - size * 0.5;
	float d = sd_box(p, size * 0.5 - vec2(1.0), radius);
	float fill = clamp(0.5 - d, 0.0, 1.0);
	vec4 col = mix(top_color, bottom_color, UV.y);
	// Schrägstreifen
	float s = step(0.5, fract((p.x + p.y) / 7.0));
	col.rgb += vec3(s * stripes);
	// Glanz oben
	col.rgb += vec3(0.10, 0.08, 0.14) * smoothstep(0.35, 0.0, UV.y);
	// äußere Kante (2 px) und innere Linie (1 px)
	float edge = clamp(1.0 - abs(d + 1.5) / 1.5, 0.0, 1.0);
	float d2 = sd_box(p, size * 0.5 - vec2(inner_inset), max(radius - inner_inset, 2.0));
	float inner = clamp(1.0 - abs(d2) / 0.8, 0.0, 1.0);
	col = mix(col, edge_color, edge * edge_color.a);
	col = mix(col, vec4(inner_color.rgb, max(col.a, inner_color.a)), inner * inner_color.a);
	COLOR = vec4(col.rgb, col.a * fill) * COLOR.a;
}
