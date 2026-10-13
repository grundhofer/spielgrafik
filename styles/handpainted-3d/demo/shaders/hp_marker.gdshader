// Goldenes Ausrufezeichen über der Figur (Auftrags-Markierung wie in Online-Rollenspielen), gemalt:
// Gold mit hellem Lichtrand oben links, dunkelbraune Kontur. Billboard, unbeleuchtet, leuchtet leicht.
shader_type spatial;
render_mode blend_mix, unshaded, cull_disabled, depth_draw_opaque, shadows_disabled, fog_disabled;

uniform float opacity = 1.0;
uniform float glow = 1.15;

void vertex() {
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	MODELVIEW_MATRIX = MODELVIEW_MATRIX * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0),
		vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0), vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0),
		vec4(0.0, 0.0, 0.0, 1.0));
}

// Abstand zum Ausrufezeichen (Balken als Trapez, Punkt als Kreis), UV-Raum -1..1, y nach oben
float sd_mark(vec2 p) {
	vec2 q = p - vec2(0.0, 0.22);
	float w = mix(0.13, 0.22, clamp((q.y + 0.42) / 1.0, 0.0, 1.0));
	// Balken: Distanzfunktion abgerundetes Rechteck nach Inigo Quilez – Copyright (c) Inigo Quilez, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt), https://iquilezles.org/articles/distfunctions2d/
	vec2 d = vec2(abs(q.x) - w, abs(q.y) - 0.52);
	float bar = length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - 0.05;
	float dot_ = length(p - vec2(0.0, -0.66)) - 0.17;
	return min(bar, dot_);
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	p.y = -p.y;
	p.x *= 0.5;   // Quad ist halb so breit wie hoch: gleiche Einheit in x und y
	float d = sd_mark(p);
	float aa = fwidth(d) * 0.8;
	float fill = 1.0 - smoothstep(-aa, aa, d);
	float outline = 1.0 - smoothstep(0.09 - aa, 0.09 + aa, d);
	// gemaltes Gold: unten dunkler, oben links Lichtkante
	float h = p.y * 0.5 + 0.5;
	vec3 gold = mix(vec3(0.85, 0.5, 0.08), vec3(1.0, 0.86, 0.25), h);
	float rim = smoothstep(-0.11, -0.03, d) * step(d, 0.0) * smoothstep(-0.2, 0.4, -p.x + p.y * 0.3);
	gold = mix(gold, vec3(1.0, 0.98, 0.78), rim * 0.8);
	vec3 col = mix(vec3(0.22, 0.10, 0.02), gold * glow, fill);
	ALBEDO = col;
	ALPHA = outline * opacity;
	ALPHA_SCISSOR_THRESHOLD = 0.5;
}
