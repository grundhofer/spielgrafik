// Abendhimmel aus Code: Farbverlauf (Glutband am Horizont, Rosa, Violett, Nachtblau), Glut hinter
// dem Hafen und lange, flache Wolkenbänder, unten von der Glut angestrahlt. Bewusst große, weiche
// Formen mit etwas Struktur: Der Kuwahara-Filter der Nachbearbeitung macht daraus Pinselflächen.
// Dieselbe Funktion nutzt das Wasser für die Spiegelung.

global uniform float paint_time;

const vec3 SKY_GLOW_DIR = vec3(-0.32, 0.0, -0.95);   // Richtung der Glut (Sonne knapp unter dem Horizont)

float sky_fbm(vec2 p) {
	float s = 0.0;
	float a = 0.5;
	for (int i = 0; i < 5; i++) {
		s += a * vnoise2(p);
		p = mat2(vec2(1.7, 1.1), vec2(-1.1, 1.7)) * p + vec2(5.2, 1.3);
		a *= 0.5;
	}
	return s / 0.96875;
}

vec3 sky_gradient(vec3 d) {
	float h = d.y;
	vec3 g = normalize(SKY_GLOW_DIR);
	float toward = clamp(dot(normalize(vec3(d.x, 0.0, d.z)), g) * 0.5 + 0.5, 0.0, 1.0);   // 1 = zur Glut
	vec3 band = mix(vec3(1.0, 0.54, 0.26), vec3(1.0, 0.76, 0.42), pow(toward, 3.0));
	vec3 pink = mix(vec3(0.84, 0.50, 0.46), vec3(0.97, 0.66, 0.50), pow(toward, 2.0));
	vec3 violet = vec3(0.33, 0.35, 0.56);
	vec3 night = vec3(0.08, 0.12, 0.30);
	vec3 c = mix(band, pink, smoothstep(0.0, 0.07, h));
	c = mix(c, violet, smoothstep(0.05, 0.22, h));
	c = mix(c, night, smoothstep(0.18, 0.62, h));
	// unter dem Horizont (nur für Spiegelungen): wie das Glutband
	c = mix(band, c, smoothstep(-0.02, 0.0, h));
	return c;
}

// Wolken auf einer gedachten Ebene über dem Meer; gibt Farbe (rgb) und Deckung (a) zurück.
// Große Massen plus Ballen; die zur Glut (nach unten, zum Horizont) zeigenden Ränder sind angestrahlt.
float cloud_density(vec2 q) {
	return sky_fbm(q * 0.55 + vec2(3.0, 11.0)) * 0.78 + sky_fbm(q * 1.7 + vec2(17.0, 4.0)) * 0.32;
}

vec4 sky_clouds(vec3 d) {
	float h = max(d.y, 0.0);
	vec2 q = d.xz / (h + 0.05);
	q *= vec2(0.28, 0.62);
	q.x += paint_time * 0.012;                   // sehr langsamer Zug nach rechts
	float dens = cloud_density(q);
	float cover = smoothstep(0.50, 0.64, dens);
	// Nachbar zum Horizont hin (q.y weiter negativ = weiter weg = tiefer am Himmel)
	float dens_low = cloud_density(q + vec2(0.0, -0.22));
	float lit = clamp((dens - dens_low) * 5.0 + 0.35, 0.0, 1.0);
	vec3 g = normalize(SKY_GLOW_DIR);
	float toward = clamp(dot(normalize(vec3(d.x, 0.0, d.z)), g) * 0.5 + 0.5, 0.0, 1.0);
	float low = 1.0 - smoothstep(0.03, 0.40, h);
	vec3 shadow_col = mix(vec3(0.20, 0.21, 0.35), vec3(0.42, 0.31, 0.42), low * 0.8);
	vec3 lit_col = mix(vec3(0.88, 0.52, 0.50), vec3(1.0, 0.70, 0.40), pow(toward, 1.5) * low);
	vec3 c = mix(shadow_col, lit_col, lit * (0.45 + 0.55 * low));
	// zum Horizont hin dünner (Dunst), ganz oben weniger Wolken
	cover *= smoothstep(0.015, 0.06, h) * (1.0 - smoothstep(0.55, 0.85, h));
	return vec4(c, cover);
}

// Farben oben sind als sRGB-Werte gewählt; der Shader rechnet linear
vec3 sky_color(vec3 d) {
	vec3 c = sky_gradient(d);
	vec4 cl = sky_clouds(d);
	return pow(mix(c, cl.rgb, cl.a * 0.92), vec3(2.2));
}
