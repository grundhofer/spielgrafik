// Toon-Licht für Hafen, Figur und Rauch: drei harte Töne statt weicher Verläufe.
// Sonne: Schatten (nur Umgebungslicht) | Mittelton | Licht, Schwellen auf N·L, Schlagschatten hart.
// Punktlichter (Laterne, Fenster, Leuchtfeuer): zwei harte Ringe statt Abfall.
// Konturen, Kantenlicht, Nebel und die Palette kommen später (p3d_post, palette).
shader_type spatial;
render_mode cull_back, depth_draw_opaque, diffuse_lambert, specular_disabled;

uniform vec4 albedo : source_color = vec4(1.0);
uniform vec4 emission : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform float emission_energy = 0.0;
uniform float band_lo = 0.02;       // N·L: Schatten -> Mittelton
uniform float band_hi = 0.42;       // N·L: Mittelton -> Licht
uniform float mid_level = 0.5;      // Anteil des Sonnenlichts im Mittelton
uniform float point_lo = 0.10;      // Punktlicht: äußerer Ring
uniform float point_hi = 0.38;      // Punktlicht: innerer Ring
uniform float point_gain = 1.0;
uniform float smooth_light = 0.0;   // Vergleichsschalter --no-toon: weiches Lambert
uniform bool flat_normals = false;  // Flächennormale statt geglätteter (Felsen: Facetten in Stufen)
uniform float pattern = 0.0;        // Fels: dunklere Schichtflecken in Weltkoordinaten (0 = aus)
uniform vec3 pattern_scale = vec3(0.9, 2.2, 0.9);  // Zellen je Meter (y feiner: Schichten)

varying vec3 world_pos;

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash13(vec3 p) {
	p = fract(p * 0.1031);
	p += dot(p, p.zyx + 31.32);
	return fract((p.x + p.y) * p.z);
}

float vnoise3(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(hash13(i), hash13(i + vec3(1, 0, 0)), f.x),
			mix(hash13(i + vec3(0, 1, 0)), hash13(i + vec3(1, 1, 0)), f.x), f.y),
		mix(mix(hash13(i + vec3(0, 0, 1)), hash13(i + vec3(1, 0, 1)), f.x),
			mix(hash13(i + vec3(0, 1, 1)), hash13(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	if (flat_normals) {
		NORMAL = normalize(cross(dFdy(VERTEX), dFdx(VERTEX)));
	}
	ALBEDO = albedo.rgb;
	if (pattern > 0.0) {
		float n = vnoise3(world_pos * pattern_scale) * 0.7 + vnoise3(world_pos * pattern_scale * 2.3 + 7.0) * 0.3;
		ALBEDO *= 1.0 - pattern * step(0.6, n);
	}
	ROUGHNESS = 1.0;
	METALLIC = 0.0;
	SPECULAR = 0.0;
	EMISSION = emission.rgb * emission_energy;
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	if (LIGHT_IS_DIRECTIONAL) {
		float sh = step(0.5, ATTENUATION);
		float stepped = (step(band_lo, ndl) * mid_level + step(band_hi, ndl) * (1.0 - mid_level)) * sh;
		float soft = max(ndl, 0.0) * ATTENUATION;
		DIFFUSE_LIGHT += LIGHT_COLOR / PI * mix(stepped, soft, smooth_light);
	} else {
		float a = ATTENUATION * clamp(ndl * 1.5 + 0.25, 0.0, 1.0);
		float b = step(point_lo, a) * 0.5 + step(point_hi, a) * 0.5;
		DIFFUSE_LIGHT += LIGHT_COLOR / PI * mix(b, a, smooth_light) * point_gain;
	}
}
