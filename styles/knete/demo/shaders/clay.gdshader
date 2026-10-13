// Knetmasse (Plastilin) für Hafen und Figur: ein Shader, Unterschiede über Uniforms je Materialname (main.gd).
// - Oberfläche: Fingerabdrücke (Mulde, Randwulst, Rillen), feine Beulen, Poren; nur über die Normale.
//   Die Höhe wird an drei Punkten ausgewertet (Pixel, ein Pixel rechts, ein Pixel unten), daraus die
//   Normale ohne Tangenten (Oberflächengradient nach Mikkelsen). So bleibt das Muster ohne UVs fest am Objekt.
// - Farbe: leichte Marmorierung (nicht ganz durchgeknetet), Krümel, Schmutz in den Mulden.
// - Licht: weiches Umgreifen am Schattenrand mit warmem Saum (Licht dringt etwas in die Masse ein),
//   breiter, matter Glanz wie Wachs.
// - Figur: Muster in der Ruhelage (CUSTOM0, von main.gd geschrieben), sonst schwimmt es beim Laufen;
//   "Kochen" (Formrauschen) je Animationsbild über boil_seed, nicht je gerendertem Bild.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back;

#include "res://shaders/clay_noise.gdshaderinc"

uniform vec3 albedo : source_color = vec3(0.6, 0.6, 0.6);
uniform float roughness : hint_range(0.0, 1.0) = 0.62;
uniform float spec : hint_range(0.0, 2.0) = 0.45;
uniform float sheen : hint_range(0.0, 1.0) = 0.18;
uniform float wrap : hint_range(0.0, 1.0) = 0.38;
uniform vec3 terminator_tint : source_color = vec3(1.0, 0.55, 0.38);
uniform float terminator_amt = 0.35;

// Fingerabdrücke und Oberfläche (Maße in Metern der Szene; Figur 1 m = Puppe etwa 20 cm)
uniform float print_cell = 0.12;
uniform float print_density = 0.55;
uniform float print_depth = 0.0025;
uniform float ridge_amp = 0.00045;
uniform float ridge_len = 0.011;
uniform float bump_amp = 0.0012;
uniform float bump_wave = 0.05;
uniform float pore_cell = 0.035;
uniform float pore_depth = 0.0012;
uniform float bump_scale = 1.0;      // Gesamtstärke der Normalenstörung

// Farbe
uniform float mottle = 0.07;
uniform float streak = 0.05;
uniform float speck_amount = 0.6;
uniform float speck_cell = 0.03;
uniform float cavity_dark = 0.25;

// Art: 0 Knete, 1 Gras (gestupft), 2 Strick (Rippen), 3 Perle (Auge, Nase), 4 Gelände (Fels/Sand/Gras
// aus Neigung und Höhe, mit welligen Rändern wie aufgedrückte Knetstücke statt Polygonkanten)
uniform int kind = 0;
uniform vec3 rock_color : source_color = vec3(0.52, 0.49, 0.45);
uniform vec3 sand_color : source_color = vec3(0.84, 0.73, 0.51);
uniform vec3 grass_color : source_color = vec3(0.44, 0.61, 0.28);

// Leuchten (Fenster, Laterne, Lampe: Knete vor einer Lampe)
uniform vec3 emission_color : source_color = vec3(0.0);
uniform float emission_energy = 0.0;

// Figur
uniform bool use_rest = false;
uniform float boil_seed = 0.0;
uniform float boil_amp = 0.0;        // m, Verschiebung der Form je Animationsbild
uniform float boil_shift = 0.0;      // m, Verrutschen des Oberflächenmusters je Animationsbild
uniform float boil_prints = 0.0;     // Dichte der Abdrücke, die je Animationsbild neu liegen

instance uniform vec3 noise_offset = vec3(0.0);
// Ferne Teile sind wie im echten Set kleinere Modelle (erzwungene Perspektive): Abdrücke relativ größer
instance uniform float detail_scale = 1.0;

varying vec3 p_obj;
varying vec3 n_world;
varying vec3 p_world;

void vertex() {
	p_obj = ((use_rest ? CUSTOM0.xyz : VERTEX) + noise_offset) / detail_scale;
	n_world = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	p_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	if (boil_amp > 0.0) {
		vec3 q = p_obj * 7.0 + kn_hash33(vec3(boil_seed, 3.1, 7.7)) * 40.0;
		VERTEX += vec3(kn_vnoise(q), kn_vnoise(q + 31.7), kn_vnoise(q + 71.3)) * boil_amp;
	}
}

// Gelände: 0 Fels, 1 Gras, 2 Sand (weiche, wellige Grenzen); Regeln wie in shared/3d (Neigung > 37° Fels,
// bis 0,5 m über dem Wasser Sand, sonst Gras)
vec3 terrain_weights(vec3 p) {
	float slope = 1.0 - clamp(n_world.y, 0.0, 1.0);
	float wob = 0.07 * kn_vnoise(p * 1.7) + 0.03 * kn_vnoise(p * 6.0);
	float rock = smoothstep(-0.015, 0.015, slope - (0.2 + wob));
	float sand = (1.0 - smoothstep(-0.12, 0.12, p_world.y - (-0.3 + 3.0 * wob))) * (1.0 - rock);
	float grass = (1.0 - rock) * (1.0 - sand);
	return vec3(rock, grass, sand);
}

float clay_height(vec3 p, float fw) {
	// Rillen nur, wenn ein Rillenabstand mindestens etwa 3 Pixel breit ist (sonst Moiré)
	float ridge_vis = 1.0 - smoothstep(0.22 * ridge_len, 0.4 * ridge_len, fw);
	vec3 pb = p;
	if (boil_shift > 0.0) {
		pb += (kn_hash33(vec3(boil_seed, 11.0, 5.0)) - 0.5) * boil_shift;
	}
	float h = 0.0;
	if (kind != 3) {
		h += kn_prints(pb, print_cell, print_density, print_depth, ridge_amp, ridge_len, ridge_vis, 0.0);
		if (boil_prints > 0.0) {
			h += kn_prints(p, print_cell * 0.8, boil_prints, print_depth * 0.8, ridge_amp, ridge_len, ridge_vis, boil_seed + 1.0);
		}
		h += bump_amp * kn_fbm(pb / bump_wave, 3);
		// Poren nur, wenn sie mindestens etwa ein Pixel groß sind (sonst Rauschen)
		float pore_vis = smoothstep(0.6, 1.4, 0.12 * pore_cell / max(fw, 1e-6));
		float w = kn_worley(pb / pore_cell, 7.0) * pore_cell;
		h -= pore_depth * pore_vis * (1.0 - smoothstep(0.08 * pore_cell, 0.16 * pore_cell, w));
	}
	float grass_w = kind == 1 ? 1.0 : 0.0;
	if (kind == 4) {
		vec3 tw = terrain_weights(p);
		grass_w = tw.y;
		// Grasstücke liegen als eigene Knetschicht etwas höher auf dem Fels
		h += 0.01 * smoothstep(0.0, 1.0, tw.y);
	}
	if (grass_w > 0.0) {
		// Gras: mit einem Holzstäbchen gestupft (dichte, schräge Kerben)
		float g = kn_worley(pb / 0.024 + vec3(0.0, pb.x * 9.0, 0.0), 2.0) * 0.024;
		h -= grass_w * 0.0035 * (1.0 - smoothstep(0.003, 0.0075, g));
		h += grass_w * 0.0012 * kn_vnoise(pb * vec3(70.0, 30.0, 70.0));
	}
	if (kind == 2) {
		// Strick: gerillte Wülste quer zum Schal, mit dem Modellierholz eingedrückt
		h += 0.0013 * sin(6.2831853 * pb.y / 0.024 + 2.5 * sin(pb.x * 45.0 + pb.z * 31.0));
	}
	return h;
}

void fragment() {
	vec3 p = p_obj;
	vec3 dpx = dFdx(p);
	vec3 dpy = dFdy(p);
	float fw = max(length(dpx), length(dpy));
	float h0 = clay_height(p, fw);
	float hx = (clay_height(p + dpx, fw) - h0) * detail_scale;
	float hy = (clay_height(p + dpy, fw) - h0) * detail_scale;

	// Oberflächengradient ohne Tangenten (Mikkelsen 2010), alles im Kameraraum
	vec3 n = normalize(NORMAL);
	vec3 sx = dFdx(VERTEX);
	vec3 sy = dFdy(VERTEX);
	vec3 r1 = cross(sy, n);
	vec3 r2 = cross(n, sx);
	float det = dot(sx, r1);
	vec3 grad = sign(det) * (hx * r1 + hy * r2) * bump_scale;
	NORMAL = normalize(abs(det) * n - grad);

	// Farbe
	vec3 c = albedo;
	if (kind == 4) {
		vec3 tw = terrain_weights(p);
		c = rock_color * tw.x + grass_color * tw.y + sand_color * tw.z;
	}
	float m = kn_fbm(p * 3.5 + 2.0, 2);
	c *= 1.0 + mottle * m;
	vec3 sdir = normalize(vec3(0.7, 0.35, 0.6));
	float marb = sin(dot(p, sdir) * 31.0 + 7.0 * kn_fbm(p * 2.2, 3));
	c *= 1.0 + streak * smoothstep(0.55, 1.0, marb) - 0.5 * streak * smoothstep(0.6, 1.0, -marb);
	if (kind != 3) {
		float sw = kn_worley(p / speck_cell, 19.0) * speck_cell;
		float sp = 1.0 - smoothstep(0.05 * speck_cell, 0.09 * speck_cell, sw);
		float speck_vis = smoothstep(0.7, 1.6, 0.07 * speck_cell / max(fw, 1e-6));
		c = mix(c, c * 0.35, sp * speck_amount * speck_vis);
		c *= 1.0 - cavity_dark * clamp(-h0 / max(print_depth, 1e-5), 0.0, 1.0) * 0.5;
	}
	ALBEDO = clamp(c, 0.0, 1.0);
	ROUGHNESS = kind == 3 ? 0.14 : roughness;
	SPECULAR = 0.5;
	EMISSION = emission_color * emission_energy;
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	// Umgreifendes Diffuslicht: Knete ist leicht durchscheinend, der Schattenrand ist weich
	float d = clamp((ndl + wrap) / (1.0 + wrap), 0.0, 1.0);
	float term = d * (1.0 - smoothstep(0.0, 0.45, ndl + 0.1)) * terminator_amt;
	vec3 lc = LIGHT_COLOR * ATTENUATION / PI;
	DIFFUSE_LIGHT += lc * (d + term * (terminator_tint - 1.0) * 0.6 + term * terminator_tint * 0.2);

	// Breiter Wachsglanz (GGX) plus Samtsaum an streifenden Kanten
	float nl = max(ndl, 0.0);
	float nv = max(dot(NORMAL, VIEW), 0.001);
	vec3 hv = normalize(VIEW + LIGHT);
	float nh = max(dot(NORMAL, hv), 0.0);
	float r = kind == 3 ? 0.14 : ROUGHNESS;
	float a = r * r;
	float a2 = a * a;
	float dd = nh * nh * (a2 - 1.0) + 1.0;
	float D = a2 / (PI * dd * dd);
	float k = a * 0.5;
	float G = (nl / (nl * (1.0 - k) + k)) * (nv / (nv * (1.0 - k) + k));
	float F = 0.04 + 0.96 * pow(1.0 - max(dot(hv, VIEW), 0.0), 5.0);
	float s = kind == 3 ? 1.6 : spec;
	SPECULAR_LIGHT += LIGHT_COLOR * ATTENUATION * (D * G * F / (4.0 * nv * max(nl, 0.001) + 0.0001)) * nl * s;
	SPECULAR_LIGHT += lc * pow(1.0 - nv, 4.0) * sheen * d;
}
