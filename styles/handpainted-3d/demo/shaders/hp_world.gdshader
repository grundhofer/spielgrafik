// Handbemalte Oberfläche für den Hafen (Eintrag handpainted-3d).
//
// Farbe kommt aus einer gemalten Kacheltextur (Licht, Kanten und Fugen sind aufgemalt), getönt je Material.
// Die Projektion hängt vom Objekt ab, weil die UVs aus Smart UV Project beliebig gedreht sind:
//   0 = eben, an der Fläche ausgerichtet (Welt): Wände und Dächer liegen waagrecht in Reihen, Böden in x/z;
//       für Häuschen, Kai, Steg, Kisten, Laternenpfahl
//   1 = dreiachsig überblendet (Welt): Fels, Gras, Sand, Poller
//   2 = zylindrisch um die lokale y-Achse: Fässer (Dauben senkrecht), Leuchtturm
//   3 = dreiachsig überblendet (lokal): Boote, die schaukeln (Welt-Projektion würde schwimmen)
// Steinflächen (Eckquader, Sockel, Gewände, Simse, Kantensteine): build_harbor_hp.py legt je Fläche UV in
// Metern ab der Ecke und UV2 = Flächengröße an. Ist use_block an und UV2.x > 0, malt der Shader je Fläche
// einen Stein (lange Flächen in mehrere Steine geteilt): Grundfarbe mit Pinselstruktur, helle Oberkante,
// dunkle Unterkante, dunkle Fuge am Rand, Helligkeit je Stein leicht verschieden.
// Licht: Umgebungsverdeckung aus Blender als Vertexfarbe (R nah, G fern) wird violett getönt in die Farbe
// gemalt; Sonne mit weichem Umgreifen (half-Lambert), kein Glanz. Zeit/Effekte: keine.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_lambert, specular_disabled;

uniform sampler2D tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec3 tint = vec3(1.0);
uniform float tile_m = 1.0;            // Meter je Kachel
uniform int mapping = 0;
uniform bool rotate90 = false;         // Textur um 90° drehen (Dauben senkrecht)
uniform float cyl_radius = 0.3;        // Mapping 2: Umfang in Metern = Winkel * Radius
uniform vec2 offset = vec2(0.0);
uniform float tri_sharp = 6.0;
uniform float ao_near = 0.75;          // Stärke der Nahverdeckung (Fugen, Kontaktschatten)
uniform float ao_far = 0.45;           // Stärke der Fernverdeckung
uniform vec3 ao_tint : source_color = vec3(0.42, 0.32, 0.55);   // Farbe der gemalten Verdeckung
uniform bool has_ao = true;
uniform float top_light = 0.10;        // nach oben zeigende Flächen etwas wärmer und heller
uniform float wrap = 0.45;             // Umgreifen des Sonnenlichts
uniform vec3 shadow_tint : source_color = vec3(0.62, 0.55, 0.85);  // Farbe im Schlagschatten
uniform vec3 emission_color : source_color = vec3(0.0);
uniform float emission_energy = 0.0;
uniform float dim = 1.0;               // Vergleichsschalter / Feinabgleich
uniform bool use_block = false;
uniform sampler2D block_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;  // Pinselstruktur
uniform vec3 block_color = vec3(0.15);   // Grundfarbe des Steins, linear (Mittel der Mauertextur, getönt)
uniform vec3 block_det_mean = vec3(0.8);    // Mittelfarbe von block_tex (Struktur um 1 zentriert)
uniform float block_detail = 1.1;
uniform float block_tile_m = 1.1;
uniform vec3 block_light : source_color = vec3(1.0, 0.86, 0.66);
uniform vec3 block_dark : source_color = vec3(0.34, 0.26, 0.42);

varying vec3 world_pos;
varying vec3 local_pos;
varying vec3 local_normal;
varying vec3 world_normal;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	local_pos = VERTEX;
	local_normal = NORMAL;
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec2 rot(vec2 uv) {
	return rotate90 ? vec2(uv.y, -uv.x) : uv;
}

vec3 tri_sample(vec3 p, vec3 n) {
	vec3 w = pow(abs(n), vec3(tri_sharp));
	w /= (w.x + w.y + w.z);
	vec3 cx = texture(tex, rot(vec2(p.z, -p.y) / tile_m + offset)).rgb;
	vec3 cy = texture(tex, rot(vec2(p.x, p.z) / tile_m + offset)).rgb;
	vec3 cz = texture(tex, rot(vec2(p.x, -p.y) / tile_m + offset)).rgb;
	return cx * w.x + cy * w.y + cz * w.z;
}

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

// ein gemalter Stein je Fläche; f = Meter in der Zelle, cell = Zellgröße, vertical = senkrechte Fläche
vec3 paint_block(vec3 det, vec2 id, vec2 f, vec2 cell, bool vertical) {
	float rnd = hash12(id * 7.13 + floor(cell * 37.0));
	vec3 col = block_color * mix(vec3(1.0), det / block_det_mean, block_detail);
	col *= 0.9 + 0.2 * rnd;
	col = mix(col, col * vec3(1.06, 0.98, 0.92), step(0.5, fract(rnd * 7.0)));   // warm/kühl je Stein
	float w = clamp(0.2 * min(cell.x, cell.y), 0.012, 0.05);   // Breite der gemalten Kante
	float e_l = f.x, e_r = cell.x - f.x, e_b = f.y, e_t = cell.y - f.y;
	if (vertical) {
		col *= mix(0.84, 1.08, smoothstep(0.0, cell.y, f.y));   // gemalter Verlauf: unten dunkler
		col = mix(col, col * 1.45 * block_light, (1.0 - smoothstep(0.0, w, e_t)) * 0.85);
		col = mix(col, col * 1.2 * block_light, (1.0 - smoothstep(0.0, w * 0.8, e_l)) * 0.5);
		col = mix(col, col * block_dark * 1.3, (1.0 - smoothstep(0.0, w * 1.4, e_b)) * 0.8);
		col = mix(col, col * block_dark * 1.6, (1.0 - smoothstep(0.0, w, e_r)) * 0.55);
	} else {
		float e = min(min(e_l, e_r), min(e_b, e_t));
		col = mix(col, col * 1.35 * block_light, (1.0 - smoothstep(0.0, w, e)) * 0.7);
	}
	float j = min(min(e_l, e_r), min(e_b, e_t));
	col = mix(col, block_dark * 0.45, (1.0 - smoothstep(0.004, 0.011, j)) * 0.9);   // Fuge
	return col;
}

void fragment() {
	// Steinfläche (vor jeder Verzweigung abtasten; Ableitungen aus den stetigen Flächen-UVs)
	vec2 bsize = max(UV2, vec2(1e-3));
	vec2 bcnt = max(vec2(1.0), round(bsize / vec2(0.95, 0.55)));
	vec2 bcell = bsize / bcnt;
	vec2 bq = UV / bcell;
	vec2 bid = clamp(floor(bq), vec2(0.0), bcnt - 1.0);
	vec2 bf = (bq - bid) * bcell;
	vec2 boff = vec2(hash12(bid + 3.1), hash12(bid + 8.7));
	vec3 bdet = textureGrad(block_tex, UV / block_tile_m + boff, dFdx(UV) / block_tile_m, dFdy(UV) / block_tile_m).rgb;
	bool is_block = use_block && UV2.x > 0.001;

	vec3 col;
	if (mapping == 0) {
		// geometrische Flächennormale aus den Ableitungen (UV-Achsen je Fläche konstant)
		vec3 dpx = dFdx(world_pos);
		vec3 dpy = dFdy(world_pos);
		vec3 n = normalize(cross(dpy, dpx));
		vec2 uv, gx, gy;
		if (abs(n.y) > 0.93) {
			uv = world_pos.xz;
			gx = dpx.xz;
			gy = dpy.xz;
		} else {
			vec3 t = normalize(cross(vec3(0.0, 1.0, 0.0), n));
			vec3 b = cross(n, t);
			if (b.y < 0.0) { b = -b; t = -t; }
			uv = vec2(dot(world_pos, t), -dot(world_pos, b));
			// Ableitungen über die stetige Weltposition: an Kanten keine falsche Mip-Stufe
			gx = vec2(dot(dpx, t), -dot(dpx, b));
			gy = vec2(dot(dpy, t), -dot(dpy, b));
		}
		vec2 u = rot(uv / tile_m + offset);
		col = textureGrad(tex, u, rot(gx / tile_m), rot(gy / tile_m)).rgb;
	} else if (mapping == 1) {
		col = tri_sample(world_pos, world_normal);
	} else if (mapping == 2) {
		float a = atan(local_pos.z, local_pos.x);
		vec2 uv = vec2(a * cyl_radius, -local_pos.y);
		vec2 gx = vec2(dFdx(a), -dFdx(local_pos.y));
		vec2 gy = vec2(dFdy(a), -dFdy(local_pos.y));
		gx.x -= round(gx.x / 6.2831853) * 6.2831853;
		gy.x -= round(gy.x / 6.2831853) * 6.2831853;
		gx.x *= cyl_radius;
		gy.x *= cyl_radius;
		col = textureGrad(tex, rot(uv / tile_m + offset), rot(gx / tile_m), rot(gy / tile_m)).rgb;
	} else {
		col = tri_sample(local_pos, normalize(local_normal));
	}
	col *= tint;
	if (is_block) {
		col = paint_block(bdet, bid, bf, bcell, abs(world_normal.y) < 0.7);
	}

	// gemalte Umgebungsverdeckung (Vertexfarbe aus Blender): dunkler und violetter in Fugen und Ecken
	if (has_ao) {
		float occ = mix(1.0, COLOR.r, ao_near) * mix(1.0, COLOR.g, ao_far);
		col *= mix(ao_tint, vec3(1.0), occ);
	}
	// Oberseiten fangen das Himmelslicht: etwas heller und wärmer
	float up = clamp(world_normal.y, 0.0, 1.0);
	col *= 1.0 + top_light * up * vec3(1.0, 0.92, 0.78);

	ALBEDO = col * dim;
	ROUGHNESS = 1.0;
	METALLIC = 0.0;
	EMISSION = emission_color * emission_energy;
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	if (LIGHT_IS_DIRECTIONAL) {
		float d = clamp((ndl + wrap) / (1.0 + wrap), 0.0, 1.0);
		d = d * d * (3.0 - 2.0 * d) * 0.85 + d * 0.15;   // weicher, aber gemalter Übergang
		// Schlagschatten nicht schwarz, sondern violett getönt (gemalter Schatten)
		vec3 sh = mix(shadow_tint, vec3(1.0), ATTENUATION);
		DIFFUSE_LIGHT += LIGHT_COLOR / PI * d * sh;
	} else {
		float d = clamp(ndl * 0.6 + 0.4, 0.0, 1.0);
		DIFFUSE_LIGHT += LIGHT_COLOR / PI * d * ATTENUATION;
	}
}
