// Abendhimmel für HD-2D: Verlauf vom tiefen Blau zum orangen Band am Horizont, warmer Schein um die eben
// untergegangene Sonne, flache Wolkenbänder und die ersten Sterne. Stufen im Verlauf (wie gemalte
// Pixel-Hintergründe), Sterne als helle Punkte (die Tiefenunschärfe macht sie zu weichen Lichtscheiben).
shader_type sky;

global uniform float time_s;

uniform vec3 top : source_color = vec3(0.05, 0.07, 0.20);
uniform vec3 mid : source_color = vec3(0.24, 0.20, 0.42);
uniform vec3 low : source_color = vec3(0.78, 0.40, 0.30);
uniform vec3 band : source_color = vec3(1.00, 0.62, 0.30);
uniform vec3 sun_dir = vec3(-0.35, 0.02, -0.94);
uniform vec3 cloud_lit : source_color = vec3(0.95, 0.52, 0.36);
uniform vec3 cloud_dark : source_color = vec3(0.20, 0.17, 0.32);
uniform float steps = 14.0;
uniform float star_energy = 3.0;

float hash(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float noise(vec2 p) {
	vec2 i = floor(p), f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}

void sky() {
	vec3 d = normalize(EYEDIR);
	float el = d.y;
	float az = atan(d.x, -d.z);
	// gestufter Verlauf
	float h = clamp(el / 0.55, 0.0, 1.0);
	h = floor(h * steps) / steps;
	vec3 c = mix(low, mid, smoothstep(0.0, 0.35, h));
	c = mix(c, top, smoothstep(0.3, 1.0, h));
	// oranges Band und Sonnenschein am Horizont
	float sd = max(dot(normalize(vec3(d.x, 0.0, d.z)), normalize(vec3(sun_dir.x, 0.0, sun_dir.z))), 0.0);
	float glow = pow(sd, 6.0) * exp(-max(el, 0.0) * 9.0);
	glow = floor(glow * 8.0) / 8.0;
	c += band * (exp(-max(el, 0.0) * 28.0) * 0.9 + glow * 1.4);
	// Wolkenbänder knapp über dem Horizont (gestreckte Rauschfelder, in drei Tönen)
	vec2 cp = vec2(az * 6.0, el * 60.0);
	float cl = noise(cp * vec2(0.6, 0.35)) * 0.65 + noise(cp * vec2(1.7, 0.9)) * 0.35;
	float mask = smoothstep(0.02, 0.06, el) * (1.0 - smoothstep(0.16, 0.28, el));
	float cm = step(0.58, cl) * mask;
	vec3 ccol = mix(cloud_dark, cloud_lit, clamp(glow * 2.0 + step(0.66, cl) * 0.35, 0.0, 1.0));
	c = mix(c, ccol, cm);
	// Sterne: Zellen in Kugelkoordinaten, je Zelle höchstens ein Stern, Funkeln mit festem Takt
	vec2 sp = vec2(az * 70.0, el * 70.0);
	vec2 cell = floor(sp);
	float r = hash(cell);
	vec2 off = vec2(hash(cell + 3.1), hash(cell + 7.7)) * 0.6 + 0.2;
	float dd = length(fract(sp) - off);
	float star = step(0.93, r) * step(dd, 0.09) * smoothstep(0.18, 0.4, el) * (1.0 - cm);
	float tw = 0.65 + 0.35 * sin(time_s * (2.0 + r * 4.0) + r * 40.0);
	c += vec3(0.9, 0.92, 1.0) * star * star_energy * tw;
	COLOR = c;
}
