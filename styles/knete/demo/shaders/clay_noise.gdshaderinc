// Gemeinsame Rausch- und Musterfunktionen für die Knete-Shader (ohne Texturen, deterministisch).

// Hash ohne Sinus (Dave Hoskins), stabil auf allen Renderern
// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
vec3 kn_hash33(vec3 p) {
	p = fract(p * vec3(0.1031, 0.1030, 0.0973));
	p += dot(p, p.yxz + 33.33);
	return fract((p.xxy + p.yxx) * p.zyx);
}

float kn_hash13(vec3 p) {
	p = fract(p * 0.1031);
	p += dot(p, p.zyx + 31.32);
	return fract((p.x + p.y) * p.z);
}

float kn_hash11(float p) {
	p = fract(p * 0.1031);
	p *= p + 33.33;
	p *= p + p;
	return fract(p);
}

// Wertrauschen 3D mit Quintik-Glättung, Ergebnis -1..1
float kn_vnoise(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	vec3 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
	float a = kn_hash13(i);
	float b = kn_hash13(i + vec3(1, 0, 0));
	float c = kn_hash13(i + vec3(0, 1, 0));
	float d = kn_hash13(i + vec3(1, 1, 0));
	float e = kn_hash13(i + vec3(0, 0, 1));
	float g = kn_hash13(i + vec3(1, 0, 1));
	float h = kn_hash13(i + vec3(0, 1, 1));
	float k = kn_hash13(i + vec3(1, 1, 1));
	float v = mix(mix(mix(a, b, u.x), mix(c, d, u.x), u.y), mix(mix(e, g, u.x), mix(h, k, u.x), u.y), u.z);
	return v * 2.0 - 1.0;
}

float kn_fbm(vec3 p, int oct) {
	float s = 0.0;
	float a = 0.5;
	for (int i = 0; i < oct; i++) {
		s += a * kn_vnoise(p);
		p = p * 2.03 + vec3(11.7, 3.1, 7.9);
		a *= 0.5;
	}
	return s;
}

// Fingerabdrücke: in einem 3D-Zellraster liegt je Zelle mit Wahrscheinlichkeit 'density' ein Abdruck
// (flache Mulde plus konzentrische Rillen, leicht oval und verzogen). Geprüft werden die 2×2×2 nächsten
// Zellen; Mittelpunkte liegen bei 0,3..0,7 der Zelle, Radius höchstens 0,5 Zellen, damit nichts abgeschnitten wird.
// cell: Zellgröße (m), depth: Muldentiefe (m), ridge_amp: Rillenhöhe (m), ridge_len: Rillenabstand (m),
// ridge_vis: 0..1 (Rillen ausblenden, wenn sie kleiner als ein paar Pixel sind), seed: verschiebt die Auswahl.
float kn_prints(vec3 p, float cell, float density, float depth, float ridge_amp, float ridge_len, float ridge_vis, float seed) {
	vec3 g = p / cell;
	vec3 i0 = floor(g - 0.5);
	float h = 0.0;
	for (int z = 0; z < 2; z++) {
		for (int y = 0; y < 2; y++) {
			for (int x = 0; x < 2; x++) {
				vec3 c = i0 + vec3(float(x), float(y), float(z));
				vec3 r = kn_hash33(c + seed * 17.13);
				float pick = kn_hash13(c * 1.37 + seed * 5.71 + 4.2);
				if (pick < density) {
					vec3 ctr = c + 0.3 + 0.4 * r;
					vec3 d = (g - ctr) * cell;                       // m
					vec3 ax = normalize(kn_hash33(c + 91.7) - 0.5);  // Längsachse des Abdrucks
					float along = dot(d, ax);
					// oval bis langgezogen (Daumen gerollt bzw. mit dem Finger verstrichen)
					float elong = mix(0.45, 1.2, r.y * r.y);
					vec3 dd = d - ax * along * (1.0 - elong);
					float rad = 0.30 + 0.20 * r.x;                   // Radius in Zellen
					float q = length(dd) / (rad * cell);             // 0 Mitte, 1 Rand
					if (q < 1.0) {
						float bowl = 1.0 - q * q;
						bowl *= bowl;
						float warp = 1.6 * kn_vnoise(d / cell * 6.0 + c);
						float ridges = sin(6.2831853 * length(dd) / ridge_len + warp);
						float edge = 1.0 - smoothstep(0.6, 1.0, q);
						// Randwulst: weggedrückte Masse hebt den Rand leicht an
						float rim = smoothstep(0.55, 0.85, q) * (1.0 - smoothstep(0.85, 1.0, q));
						h += -depth * bowl + 0.35 * depth * rim + ridge_amp * ridge_vis * ridges * edge;
					}
				}
			}
		}
	}
	return h;
}

// Kleine Poren und Krümel: Abstand zum nächsten Zufallspunkt im Raster (Worley F1), 3×3×3 nicht nötig,
// weil die Punkte klein sind: 2×2×2 genügt.
float kn_worley(vec3 p, float seed) {
	vec3 i0 = floor(p - 0.5);
	float best = 9.0;
	for (int z = 0; z < 2; z++) {
		for (int y = 0; y < 2; y++) {
			for (int x = 0; x < 2; x++) {
				vec3 c = i0 + vec3(float(x), float(y), float(z));
				vec3 q = c + 0.25 + 0.5 * kn_hash33(c + seed);
				best = min(best, length(p - q));
			}
		}
	}
	return best;
}
