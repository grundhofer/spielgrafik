// Möwe als gemalte Figur auf einem Billboard (fliegt nach links): Rumpf mit Kopf, Schnabel und Schwanz,
// zwei kräftige, geknickte Flügel mit gemalter Lichtkante oben, violetter Schattenkante unten und dunklen
// Flügelspitzen. Flügelschlag über flap (-1..1). Koordinaten gleichmäßig: x -1..1, y -0,5..0,5 (Quad 2:1).
shader_type spatial;
render_mode blend_mix, unshaded, cull_disabled, depth_draw_never, shadows_disabled;

uniform vec3 body : source_color = vec3(0.97, 0.93, 0.90);
uniform vec3 light : source_color = vec3(1.0, 0.90, 0.72);     // Abendlicht auf Oberkanten
uniform vec3 shade : source_color = vec3(0.52, 0.46, 0.68);    // gemalter Schatten unten
uniform vec3 tip : source_color = vec3(0.24, 0.21, 0.30);      // dunkle Flügelspitzen
uniform vec3 beak : source_color = vec3(0.98, 0.70, 0.22);
instance uniform float flap = 0.0;

void vertex() {
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	MODELVIEW_MATRIX = MODELVIEW_MATRIX * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0),
		vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0), vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0),
		vec4(0.0, 0.0, 0.0, 1.0));
}

float cover(float d, float w) {
	// weiche, aber pixelgenaue Kante: d < 0 innen
	return 1.0 - smoothstep(-w, w, d);
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	p.y = -p.y * 0.5;
	float f = mix(-0.35, 0.65, flap * 0.5 + 0.5);
	float x = abs(p.x);
	// Flügel: Mittellinie mit Knick (Arm steigt mit dem Schlag, Hand fällt zur Spitze ab)
	float yc = 0.5 * (f * 1.6 * min(x, 0.55) + (f * 0.6 - 0.35) * max(x - 0.55, 0.0)) - 0.02;
	float th = 0.085 * pow(max(1.0 - x, 0.0), 0.7) + 0.016;
	float dw = p.y - yc;
	float s = clamp(dw / th, -1.0, 1.0);                // -1 Unterkante, +1 Oberkante
	float aa = fwidth(dw) * 0.75;
	float w = cover(abs(dw) - th, aa) * cover(x - 0.97, fwidth(x) * 0.75);
	vec3 wc = mix(body, light, smoothstep(0.35, 0.85, s));
	wc = mix(wc, shade, smoothstep(-0.15, -0.75, s));
	wc = mix(wc, tip, smoothstep(0.74, 0.84, x));
	wc = mix(wc, wc * vec3(0.78, 0.74, 0.9), smoothstep(0.8, 1.0, abs(s)) * 0.6);   // gemalte Randlinie

	// Rumpf, Kopf (links), Schwanz (rechts), Schnabel
	vec2 q = p - vec2(0.02, -0.03);
	float rb = length(q / vec2(0.27, 0.075)) - 1.0;
	float rh = length(p - vec2(-0.27, -0.005)) / 0.068 - 1.0;
	float rt = max(abs(p.y + 0.035) - 0.04 * (1.0 + (p.x - 0.2) * 3.0), abs(p.x - 0.33) - 0.11);
	float bd = min(min(rb * 0.07, rh * 0.068), rt);
	float b = cover(bd, fwidth(bd) * 0.75);
	float by = clamp((p.y + 0.03) / 0.08, -1.0, 1.0);
	vec3 bc = mix(body, light, smoothstep(0.2, 0.9, by));
	bc = mix(bc, shade, smoothstep(-0.1, -0.8, by));
	vec2 kb = p - vec2(-0.35, -0.012);
	float beak_d = max(abs(kb.y) - 0.018 * (1.0 + kb.x / 0.06), abs(kb.x) - 0.06);
	float k = cover(beak_d, fwidth(beak_d) * 0.75);
	float eye = cover(length(p - vec2(-0.29, 0.012)) - 0.012, 0.004);

	vec3 col = wc;
	float a = w;
	col = mix(col, bc, b);
	a = max(a, b);
	col = mix(col, beak, k);
	a = max(a, k);
	col = mix(col, vec3(0.1, 0.07, 0.1), eye * b);
	ALBEDO = col;
	ALPHA = a;
}
