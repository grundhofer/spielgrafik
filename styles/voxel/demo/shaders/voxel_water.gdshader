// Voxelwasser: jede Instanz des MultiMesh ist eine Wassersäule (Würfel mit Schürze nach unten).
// Die Säule hebt und senkt sich in ganzen Voxelstufen (step_h) nach einer Wellenfunktion der Zellmitte.
// INSTANCE_CUSTOM: r = Abstand zum Ufer (0..1 = 0..12 Zellen), g = 1 unter einem Bootsrumpf.
// Zeit kommt als Uniform aus dem Skript (aufsummiertes delta): reproduzierbare Aufnahme.
shader_type spatial;
render_mode cull_back;

uniform float time_s = 0.0;
uniform float step_h = 0.1;
uniform float amp = 0.17;
uniform vec3 deep : source_color = vec3(0.12, 0.33, 0.44);
uniform vec3 mid : source_color = vec3(0.17, 0.44, 0.54);
uniform vec3 shallow : source_color = vec3(0.28, 0.60, 0.64);
uniform vec3 crest : source_color = vec3(0.52, 0.78, 0.80);
uniform vec3 foam : source_color = vec3(0.90, 0.93, 0.92);
uniform float foam_on = 1.0;
uniform vec3 glint_a_pos = vec3(4.1, 1.79, -0.12);     // Laterne
uniform vec3 glint_a_col : source_color = vec3(1.0, 0.75, 0.42);
uniform float glint_a_power = 1.0;
uniform vec3 glint_b_pos = vec3(10.2, 12.58, -25.6);   // Leuchtfeuer
uniform vec3 glint_b_col : source_color = vec3(1.0, 0.88, 0.62);
uniform float glint_b_power = 1.0;

varying vec3 v_cell;     // Zellmitte (Welt)
varying float v_shore;
varying float v_top;
varying float v_level;   // Stufe der Säule (-n..n)

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

float waves(vec2 p) {
	float t = time_s;
	// Dünung läuft in +z auf den Kai zu: Kämme fast parallel zu x, damit die Stufen breite, achsparallele
	// Bänder bilden (bei flachem Blick sieht man vor allem die Stufenkanten; schräge Kämme ergaben Treppen
	// aus einzelnen Säulen, die wie senkrechte Nadeln wirkten). Die langsamen x-Terme biegen die Kämme nur
	// über viele Meter.
	float h = 0.75 * sin(p.y * 1.25 - t * 1.9 + 0.35 * sin(p.x * 0.21 + 0.7))
		+ 0.30 * sin(p.y * 2.3 - t * 2.6 + 1.3 + 0.5 * sin(p.x * 0.13 - t * 0.4))
		+ 0.15 * sin(p.x * 0.35 + p.y * 0.2 - t * 1.1 + 4.0);
	return h;
}

void vertex() {
	vec3 org = MODEL_MATRIX[3].xyz;
	float sc = length(MODEL_MATRIX[0].xyz);
	v_cell = org + vec3(0.5 * sc, 0.0, 0.5 * sc);
	v_shore = INSTANCE_CUSTOM.r;
	float boat = INSTANCE_CUSTOM.g;
	float w = waves(v_cell.xz);
	// am Ufer etwas unruhiger (Brandung): Phase je 0,4-m-Block und nach Uferabstand, damit ganze Blöcke als
	// Band zum Ufer laufen (eine Zufallsphase je Säule ließ einzelne Säulen wie Grashalme stehen)
	float blk = hash12(floor(v_cell.xz / 0.4));
	w += (1.0 - smoothstep(0.0, 0.25, v_shore)) * 0.5 * sin(time_s * 3.1 + v_shore * 9.0 + blk * 1.2);
	float lvl = round(w * amp / step_h);
	v_level = lvl;
	float h = lvl * step_h - boat * 0.45;
	VERTEX.y += h / sc;
	v_top = NORMAL.y;
}

void fragment() {
	vec2 ci = floor(v_cell.xz / 0.1);
	float n = hash12(ci);
	vec3 c = mix(shallow, mid, smoothstep(0.0, 0.35, v_shore));
	c = mix(c, deep, smoothstep(0.35, 1.0, v_shore));
	// Farbabwandlung je Säule nur auf der Oberseite; auf den Seitenflächen ergab sie senkrechte Striche
	c *= 1.0 + (n - 0.5) * 0.10 * v_top;
	// Stufen sichtbar machen: jede Höhenstufe einen Ton heller (Wellen als wandernde Voxelbänder); die
	// Seitenflächen einer Stufe im Ton der Oberseite eine Stufe tiefer (statt pauschal abgedunkelt)
	float tone = v_level - step(v_top, 0.5);
	c *= 0.78 + 0.13 * (tone + 2.0);
	c = mix(c, crest, step(1.5, v_level) * 0.6 * v_top);
	// Schaum am Ufer und an den Booten: einzelne Voxel, die im 1/6-s-Takt auf- und abtauchen
	float tick = floor(time_s * 6.0);
	float fp = (1.0 - smoothstep(0.04, 0.2, v_shore)) * 0.7;
	float fo = step(hash12(ci + tick * 17.31), fp) * foam_on * step(0.5, v_top);
	c = mix(c, foam, fo);
	ALBEDO = c;
	ROUGHNESS = 0.55;
	SPECULAR = 0.2;
	// Glitzern: Spiegelbild der Lichter auf den Oberseiten (senkrechter Streifen unter dem Licht),
	// flackernd je Voxel im 1/10-s-Takt
	if (v_top > 0.5) {
		vec3 cam = CAMERA_POSITION_WORLD;
		vec3 b = normalize(v_cell - cam);
		vec3 em = vec3(0.0);
		for (int k = 0; k < 2; k++) {
			vec3 L = k == 0 ? glint_a_pos : glint_b_pos;
			vec3 a = normalize(vec3(L.x, 2.0 * v_cell.y - L.y, L.z) - cam);
			float daz = abs(atan(a.x, -a.z) - atan(b.x, -b.z));
			float del = abs(asin(a.y) - asin(b.y));
			float spread = k == 0 ? 0.03 : 0.010;
			float g = (1.0 - smoothstep(spread * 0.5, spread, daz)) * (1.0 - smoothstep(spread * 5.0, spread * 9.0, del));
			float flick = step(0.5, hash12(ci + floor(time_s * 10.0) * 3.7 + float(k) * 91.0));
			em += g * flick * (k == 0 ? glint_a_col * glint_a_power : glint_b_col * glint_b_power);
		}
		EMISSION = em * 3.0;
	}
}
