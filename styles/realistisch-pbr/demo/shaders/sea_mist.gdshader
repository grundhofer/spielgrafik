shader_type fog;
// Seenebel über dem Hafenbecken als FogVolume im volumetrischen Nebel: dicht an der Wasserlinie,
// nach oben schnell dünner, in Fetzen (3D-Wertrauschen), treibt langsam mit dem Wind.
// Zeit als Uniform aus main.gd (reproduzierbar).

uniform float time_s = 0.0;
uniform float density = 0.08;
uniform vec3 albedo : source_color = vec3(0.86, 0.86, 0.9);
uniform float water_y = -0.8;
uniform float falloff_m = 1.1;      // Höhe, auf der die Dichte auf 1/e fällt
uniform float scale_m = 7.0;        // Größe der Fetzen
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
	float h = max(p.y - water_y, 0.0);
	float vert = exp(-h / falloff_m);
	vec3 q = (p - wind * time_s) / scale_m * vec3(1.0, 2.5, 1.0);
	float n = 0.55 * vnoise(q) + 0.3 * vnoise(q * 2.03 + 7.1) + 0.15 * vnoise(q * 4.1 + 3.3);
	float wisps = smoothstep(0.32, 0.72, n);
	// weicher Rand der Box
	float edge = clamp(-SDF / 4.0, 0.0, 1.0);
	DENSITY = density * vert * wisps * edge;
	ALBEDO = albedo;
}
