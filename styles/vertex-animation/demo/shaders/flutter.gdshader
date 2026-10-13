// Wimpel und Fischernetz: Flattern im Vertex-Shader aus Rauschen und einer laufenden Welle.
// Gewicht w = Abstand von der festen Kante (Wimpel: vom Mast entlang +x; Netz: von der Stange nach unten),
// normiert auf 0..1 und mit `weight_power` geformt: oben fest, unten frei.
// Die Meshes liegen in der lokalen x/y-Ebene (Normale +z). Normalen per Differenzen neu berechnet.
shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform float time_s = 0.0;
uniform int mode = 0;                         // 0 = Wimpel, 1 = Netz
uniform vec3 wind_world = vec3(0.97, 0.0, 0.24);
uniform float length_m = 0.9;                 // Länge entlang der Gewichtsachse
uniform float weight_power = 1.2;
uniform float amp = 0.10;                     // m bei w = 1
uniform float wave_len = 0.55;                // Wimpel: laufende Welle
uniform float wave_speed = 9.0;               // rad/s
uniform float noise_scale = 1.3;
uniform float noise_speed = 1.6;
uniform float seed = 0.0;

uniform vec3 albedo : source_color = vec3(0.7, 0.12, 0.1);
uniform vec3 albedo2 : source_color = vec3(0.9, 0.85, 0.7);
uniform float mesh_size = 0.10;               // Netz: Maschenweite (m)
uniform float twine = 0.11;                   // Netz: Anteil des Fadens an der Masche

float hash3(vec3 p) {
	p = fract(p * 0.3183099 + 0.1);
	p *= 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float vnoise(vec3 x) {
	vec3 i = floor(x);
	vec3 f = fract(x);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(hash3(i), hash3(i + vec3(1, 0, 0)), f.x), mix(hash3(i + vec3(0, 1, 0)), hash3(i + vec3(1, 1, 0)), f.x), f.y),
		mix(mix(hash3(i + vec3(0, 0, 1)), hash3(i + vec3(1, 0, 1)), f.x), mix(hash3(i + vec3(0, 1, 1)), hash3(i + vec3(1, 1, 1)), f.x), f.y), f.z) * 2.0 - 1.0;
}

float weight(vec3 p) {
	float d = mode == 0 ? p.x : -p.y;
	return pow(clamp(d / length_m, 0.0, 1.0), weight_power);
}

// Versatz in lokalen Koordinaten
vec3 disp(vec3 p, vec3 wind_local) {
	float w = weight(p);
	float t = time_s;
	if (mode == 0) {
		// Wimpel: Welle läuft vom Mast zur Spitze, Böen aus Rauschen verstärken sie
		float gust = 0.75 + 0.35 * vnoise(vec3(t * 0.7 + seed, seed, 0.0));
		float wave = sin(6.2831853 * p.x / wave_len - wave_speed * t + seed);
		float n = vnoise(vec3(p.x * noise_scale * 3.0 - t * noise_speed * 2.0, p.y * 4.0, seed));
		return vec3(0.0, -0.05 * w * w, (wave * 0.8 + n * 0.5) * amp * w * gust);
	}
	// Netz: Wind bläht den unteren Teil aus der Netzebene (lokal z, zur Leeseite), Rauschen (laufend in
	// Windrichtung) lässt ihn flattern; in der Ebene nur wenig Pendeln, damit das Netz nicht durch die Pfosten geht
	vec3 q = vec3(p.x * noise_scale, p.y * noise_scale, 0.0);
	float n1 = vnoise(q + vec3(-t * noise_speed * sign(wind_local.x), 0.0, seed));
	float n2 = vnoise(q * 1.9 + vec3(5.0, -t * noise_speed * 1.6, seed + 3.0));
	float push = 0.55 + 0.45 * vnoise(vec3(t * 0.55 + seed, 1.0, 2.0));
	float lee = wind_local.z < 0.0 ? -1.0 : 1.0;
	return (vec3(0.0, 0.0, lee) * (push + 0.6 * n1) + vec3(0.12 * n2, 0.08 * abs(n1), 0.0)) * amp * w;
}

void vertex() {
	vec3 wind_local = normalize((inverse(MODEL_MATRIX) * vec4(wind_world, 0.0)).xyz);
	vec3 p = VERTEX;
	float e = 0.02;
	vec3 p0 = p + disp(p, wind_local);
	vec3 px = p + vec3(e, 0.0, 0.0);
	vec3 py = p + vec3(0.0, e, 0.0);
	vec3 tx = px + disp(px, wind_local) - p0;
	vec3 ty = py + disp(py, wind_local) - p0;
	VERTEX = p0;
	NORMAL = normalize(cross(tx, ty));
}

void fragment() {
	vec3 c = albedo;
	if (mode == 1) {
		// Rautenmaschen: UV in Metern, um 45° gedreht; Faden über Alpha (Alpha-to-Coverage mit MSAA)
		vec2 q = vec2(UV.x + UV.y, UV.x - UV.y) / (mesh_size * 1.41421);
		vec2 g = abs(fract(q) - 0.5);
		float dist = min(0.5 - g.x, 0.5 - g.y);                    // Abstand zum nächsten Faden (Maschen)
		float aa = 0.5 * (fwidth(q.x) + fwidth(q.y));
		float line = 1.0 - smoothstep(twine * 0.5 - aa, twine * 0.5 + aa, dist);
		ALPHA = line;
		ALPHA_SCISSOR_THRESHOLD = 0.5;
		ALPHA_ANTIALIASING_EDGE = 0.25;
		c = mix(albedo, albedo2, 0.25 * vnoise(vec3(UV * 9.0, 0.0)));
	} else {
		// Wimpel: zwei Farben längs geteilt
		c = mix(albedo, albedo2, step(0.5, UV.y));
	}
	ALBEDO = c;
	ROUGHNESS = 0.9;
	SPECULAR = 0.2;
	BACKLIGHT = c * 0.3;
	if (!FRONT_FACING) {
		NORMAL = -NORMAL;
	}
}
