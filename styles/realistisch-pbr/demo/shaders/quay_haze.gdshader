shader_type fog;
// Feuchter Dunst um Laterne und Fenster auf dem Kai (lokales FogVolume, Ellipsoid). Dichter als der
// Grundnebel der Umgebung (0,004), damit die Lichter sichtbare Lichthöfe und Lichtkegel in den Dunst
// werfen; nach oben dünner, am Rand weich (SDF), leicht fleckig und mit dem Wind treibend.
// Zeit als Uniform aus main.gd (reproduzierbar).

uniform float time_s = 0.0;
uniform float density = 0.04;
uniform vec3 albedo : source_color = vec3(0.9, 0.9, 0.92);
uniform float floor_y = 0.0;
uniform float falloff_m = 2.5;      // Höhe über dem Kai, auf der die Dichte auf 1/e fällt
uniform float edge_m = 1.5;         // Breite des weichen Rands
uniform float scale_m = 2.5;        // Größe der Flecken
uniform vec3 wind = vec3(0.35, 0.0, 0.12);

float hash3(vec3 p) {
	p = fract(p * 0.3183099 + vec3(0.1, 0.2, 0.3));
	p *= 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float vnoise(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = mix(mix(hash3(i), hash3(i + vec3(1, 0, 0)), f.x), mix(hash3(i + vec3(0, 1, 0)), hash3(i + vec3(1, 1, 0)), f.x), f.y);
	float b = mix(mix(hash3(i + vec3(0, 0, 1)), hash3(i + vec3(1, 0, 1)), f.x), mix(hash3(i + vec3(0, 1, 1)), hash3(i + vec3(1, 1, 1)), f.x), f.y);
	return mix(a, b, f.z);
}

void fog() {
	vec3 p = WORLD_POSITION;
	float vert = exp(-max(p.y - floor_y, 0.0) / falloff_m);
	vec3 q = (p - wind * time_s) / scale_m;
	float n = 0.65 * vnoise(q) + 0.35 * vnoise(q * 2.1 + 5.3);
	float edge = smoothstep(0.0, edge_m, -SDF);
	DENSITY = density * vert * edge * mix(0.45, 1.25, n);
	ALBEDO = albedo;
}
