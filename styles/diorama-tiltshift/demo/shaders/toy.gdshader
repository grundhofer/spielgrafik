// Spielzeug- und Modellbaumaterialien des Dioramas (ein Shader, Art über "kind"):
//   0 Kunststoff (glatt, leichte Lichtdurchlässigkeit, Klarlack)    5 Fels (Schaumstoff/Gips, Lasur + Trockenbürste)
//   1 Filz/Wolle (Fasern, Samtglanz am Rand)                         6 Metall (lackiert, seidenmatt)
//   2 Holz (Maserung entlang UV.x, optional Klarlack)                7 Leuchtdiode (Glas, emissiv)
//   3 Gips/Stein bemalt (Schwammtupfen, Plattenton)                  8 Papier (Packpapier, Fasern)
//   4 Streusand (einzelne Körner)
// Rauschen im Objektraum (bewegte Boote nehmen das Muster mit) bzw. bei use_uv in UV-Metern (geriggte Figur,
// sonst schwimmt das Muster beim Laufen). UVs aus shared/3d: 1 UV-Einheit = 1 m.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

#include "res://shaders/dio_noise.gdshaderinc"

uniform int kind = 0;
uniform vec4 albedo : source_color = vec4(0.8, 0.8, 0.8, 1.0);
uniform vec4 albedo2 : source_color = vec4(0.6, 0.6, 0.6, 1.0);   // Zweitton (Maserung, Lasur, Fasern)
uniform float roughness : hint_range(0.0, 1.0) = 0.4;
uniform float metallic : hint_range(0.0, 1.0) = 0.0;
uniform float specular : hint_range(0.0, 1.0) = 0.5;
uniform float clearcoat : hint_range(0.0, 1.0) = 0.0;
uniform float clearcoat_gloss : hint_range(0.0, 1.0) = 0.8;
uniform float sss : hint_range(0.0, 1.0) = 0.0;
uniform float rim : hint_range(0.0, 1.0) = 0.0;
uniform float scale = 1.0;                 // Musterdichte (1 = Standard je Art)
uniform bool use_uv = false;
uniform vec4 emission_color : source_color = vec4(1.0, 0.75, 0.4, 1.0);
uniform float emission_energy = 0.0;
uniform float grain_axis = 0.0;            // Holz: 0 = Maserung entlang UV.x, 1 = entlang UV.y

varying vec3 obj_pos;
varying vec3 world_n;

void vertex() {
	obj_pos = VERTEX;
	world_n = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec3 p = use_uv ? vec3(UV, 0.0) : obj_pos;
	p *= scale;
	vec3 n = normalize(world_n);
	float up = n.y;
	vec3 col = albedo.rgb;
	float rough = roughness;
	float spec = specular;
	float cc = clearcoat;
	float rim_amt = rim;

	if (kind == 0) {
		// Kunststoff: fast einfarbig, nur ein Hauch Wolkigkeit wie gespritztes Plastik
		col *= 0.97 + 0.06 * dio_vnoise(p * 3.0);
	} else if (kind == 1) {
		// Filz/Wolle: verfilzte Fasern (gestrecktes Rauschen in zwei Richtungen) und einzelne helle/dunkle Fasern
		float f1 = dio_vnoise(p * vec3(55.0, 9.0, 55.0));
		float f2 = dio_vnoise(p.zxy * vec3(48.0, 8.0, 48.0) + 3.1);
		float speck = dio_hash13(floor(p * 140.0));
		float fib = 0.5 * f1 + 0.5 * f2;
		col = mix(albedo2.rgb, albedo.rgb, smoothstep(0.15, 0.85, fib));
		col *= 0.9 + 0.2 * dio_vnoise(p * 7.0);
		col *= speck > 0.93 ? 1.18 : (speck < 0.05 ? 0.78 : 1.0);
		rough = 1.0;
		spec = 0.15;
	} else if (kind == 2) {
		// Holz: Jahresringe als gewellte Streifen quer zur Faser, feine Poren entlang der Faser
		vec2 g = grain_axis > 0.5 ? UV.yx : UV;
		g *= scale;
		float wob = dio_fbm2(vec2(g.x * 0.35, g.y * 2.0)) * 3.5;
		float ring = fract(g.y * 7.0 + wob);
		float lines = smoothstep(0.0, 0.35, ring) * (1.0 - smoothstep(0.55, 1.0, ring));
		float pores = dio_vnoise2(vec2(g.x * 6.0, g.y * 160.0));
		col = mix(albedo2.rgb, albedo.rgb, 0.35 + 0.65 * lines);
		col *= 0.92 + 0.12 * pores;
		col *= 0.94 + 0.12 * dio_vnoise2(g * vec2(0.6, 3.0) + 11.0);
	} else if (kind == 3) {
		// bemalter Gips: Plattenton (ein Ton je Pflasterstein), Schwammtupfen, helle Trockenbürste auf Oberseiten
		float slab = dio_hash13(floor(p * vec3(1.1, 4.0, 1.4)));
		float sponge = dio_fbm(p * 5.0);
		float fine = dio_vnoise(p * 70.0);
		col *= 0.9 + 0.18 * slab;
		col = mix(col * 0.82, col * 1.1, smoothstep(0.3, 0.7, sponge));
		col *= 0.95 + 0.1 * fine;
		col = mix(col, col * 1.14, smoothstep(0.6, 0.95, up));
	} else if (kind == 4) {
		// Streusand: einzelne Körner (Zellen ~1,5 cm im Modellmaß) mit eigener Helligkeit
		vec2 c = dio_cells(p * 60.0);
		float grain = c.y;
		col *= 0.78 + 0.4 * grain;
		col *= mix(0.85, 1.0, smoothstep(0.0, 0.35, c.x));
		col *= 0.92 + 0.16 * dio_vnoise(p * 4.0);
		rough = 0.95;
	} else if (kind == 5) {
		// Fels: dunkle Lasur in Vertiefungen (Rauschen), Trockenbürste auf nach oben weisenden Flächen
		float cav = dio_fbm(p * 1.6);
		float dry = smoothstep(0.1, 0.8, up) * smoothstep(0.35, 0.65, dio_fbm(p * 4.0 + 7.0));
		col = mix(albedo2.rgb, albedo.rgb, smoothstep(0.25, 0.7, cav));
		col = mix(col, col * 1.35 + 0.04, dry * 0.75);
		col *= 0.94 + 0.12 * dio_vnoise(p * 30.0);
	} else if (kind == 6) {
		// lackiertes Metall: seidenmatt, Kanten leicht abgegriffen (zum Zweitton hin)
		col = mix(albedo.rgb, albedo2.rgb, 0.25 * dio_vnoise(p * 12.0));
	} else if (kind == 8) {
		// Packpapier: kurze Fasern, wolkig
		float fib = dio_vnoise(p * vec3(140.0, 20.0, 140.0));
		col *= 0.9 + 0.12 * fib + 0.06 * dio_vnoise(p * 6.0);
		rough = 0.95;
		spec = 0.2;
	}

	ALBEDO = col;
	ROUGHNESS = rough;
	METALLIC = metallic;
	SPECULAR = spec;
	if (cc > 0.0) {
		CLEARCOAT = cc;
		CLEARCOAT_ROUGHNESS = 1.0 - clearcoat_gloss;
	}
	if (rim_amt > 0.0) {
		RIM = rim_amt;
		RIM_TINT = 0.7;
	}
	if (sss > 0.0) {
		SSS_STRENGTH = sss;
	}
	if (emission_energy > 0.0) {
		EMISSION = emission_color.rgb * emission_energy;
	}
}
