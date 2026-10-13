// Blattgold: ein breiter Lichtstreif wandert schräg über die ganze Seite (wie beim Kippen des Buchs), dazu blitzt
// jedes Goldelement für sich kurz auf (Phase aus der Maske). Erhabene Stellen (Relief) fangen mehr Licht.
uniform float t = 0.0;
uniform float sweep_period = 5.0;
uniform float sweep_width = 150.0;

float gold_sweep(vec2 p) {
	vec2 dir = normalize(vec2(1.0, 0.42));
	float d = dot(p, dir);
	float ph = fract(t / sweep_period + 0.22);
	float pos = mix(-320.0, 1720.0, ph);
	float x = (d - pos) / sweep_width;
	return exp(-x * x);
}

vec3 gold_light(vec3 base, float relief, float phase, vec2 p) {
	float s = gold_sweep(p);
	float glint = pow(max(0.0, sin(t * 2.1 + phase * 6.2831853)), 14.0);
	float hl = s * (0.45 + 0.9 * relief) + glint * (0.25 + 0.5 * relief);
	return base * (0.84 + 0.42 * hl) + vec3(1.0, 0.86, 0.52) * hl * 0.30;
}
