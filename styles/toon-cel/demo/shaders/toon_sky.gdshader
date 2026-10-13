// Abendhimmel im Toon-Stil: Verlauf in wenigen klaren Zonen (Glutband am Horizont, Koralle,
// Violett, Indigo), Sterne als kleine harte Punkte mit Funkeln. Farben als globale Uniforms,
// damit Wasser (Spiegelung) und Nebel dieselben Töne nutzen. Wolken sind eigene 3D-Körper.
shader_type sky;

global uniform float toon_time;
global uniform vec4 sky_top : source_color;
global uniform vec4 sky_mid : source_color;
global uniform vec4 sky_low : source_color;
global uniform vec4 sky_glow : source_color;

uniform vec4 sea_far : source_color = vec4(0.36, 0.3, 0.5, 1.0);
uniform float star_cells = 90.0;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(41.3, 289.1))) * 45758.5453);
}

void sky() {
	vec3 d = normalize(EYEDIR);
	float e = d.y;
	vec3 c = sky_glow.rgb;
	c = mix(c, sky_low.rgb, smoothstep(0.012, 0.045, e));
	c = mix(c, sky_mid.rgb, smoothstep(0.06, 0.16, e));
	c = mix(c, sky_top.rgb, smoothstep(0.17, 0.36, e));
	// unter dem Horizont: Meeresfarbe (verdeckt die Kante des Meeresgitters)
	c = mix(c, sea_far.rgb, smoothstep(0.0, -0.01, e));

	// Sterne: ein Punkt je Zelle auf einer Kugelabbildung, nur im oberen Himmel
	vec2 uv = vec2(atan(d.x, -d.z), asin(clamp(e, -1.0, 1.0))) * star_cells / 3.14159;
	vec2 cell = floor(uv);
	vec2 f = fract(uv);
	float h = hash(cell);
	vec2 pos = vec2(hash(cell + 7.1), hash(cell + 3.7)) * 0.7 + 0.15;
	float size = mix(0.05, 0.11, hash(cell + 1.3));
	float tw = 0.65 + 0.35 * sin(toon_time * (2.0 + 3.0 * h) + h * 40.0);
	float star = step(0.86, h) * (1.0 - smoothstep(size * tw * 0.8, size * tw, length(f - pos)));
	star *= smoothstep(0.14, 0.24, e);
	c = mix(c, vec3(1.0, 0.95, 0.85), star);
	COLOR = c;
}
