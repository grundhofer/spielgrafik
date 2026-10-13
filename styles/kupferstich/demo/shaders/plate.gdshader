// Druckplatte: der Stich als Tuschedichte auf Papier, alle Umgebungsanimationen als Änderung der Linien.
// TEXTURE: R = Tusche, G = Kammfeld (für Licht), B = helle Spiegelungen im Wasser (Glitzern)
// mask_tex: R = Himmel, G = Wasser, B = Boote (aus der KI-Farbcode-Maske, scripts/build_scene.py)
// Ausgabe: Druckfarbe mit Tusche als Deckung; das Papier liegt darunter (Sprite2D im Hintergrund).
shader_type canvas_item;
#include "res://shaders/inklight.gdshaderinc"

uniform sampler2D mask_tex : filter_linear;
uniform vec4 ink_color : source_color = vec4(0.169, 0.125, 0.09, 1.0);
uniform vec2 plate_size = vec2(1120.0, 525.0);
uniform float t = 0.0;
uniform float horizon_y = 248.0;
uniform float near_y = 440.0;

// Laterne: Lichtkreis um das Glas und ein Lichtfleck auf dem Kai
uniform vec2 lantern_pos = vec2(315.0, 97.0);
uniform float lantern_k = 1.0;
uniform float lantern_r = 70.0;
uniform vec2 pool_pos = vec2(300.0, 470.0);
uniform vec2 pool_r = vec2(150.0, 34.0);
// Fenster des Häuschens
uniform vec2 window_pos = vec2(138.0, 217.0);
uniform float window_k = 0.5;
// Leuchtturm: Strahl als Keil im Himmel, Aufblitzen zur Kamera
uniform vec2 lamp_pos = vec2(966.0, 84.0);
uniform float beam_dir = -1.0;
uniform float beam_len = 0.0;
uniform float beam_k = 0.0;
uniform float flash_k = 0.0;
// Rauch: bis zu 12 Ballen (x, y, Radius, Deckung)
uniform vec4 puffs[12];
uniform int puff_count = 0;
// Glitzern: Takt (springt 6-mal pro Sekunde)
uniform float glint_step = 0.0;

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash21(vec2 p) {
	// ohne sin: in allen Renderern gleich
	p = fract(p * vec2(0.1031, 0.1030));
	p += dot(p, p.yx + 33.33);
	return fract((p.x + p.y) * p.x);
}

// Deckung einer Linie mit halber Breite hw (px) im Abstand d (px) von ihrer Mitte, über ein Pixel gemittelt.
// hw <= 0: keine Linie. Dünner als 1 px wird die Linie heller statt breiter (wie ausgedünnte Linien der Platte).
float line_cov(float d, float hw) {
	hw = max(hw, 0.0);
	return clamp(min(2.0 * hw, hw + 0.5 - d), 0.0, 1.0);
}

void fragment() {
	vec2 p = UV * plate_size;
	vec3 m = texture(mask_tex, UV).rgb;
	float sky = m.r;
	float water = m.g;

	// Wasser: die waagerechten Linien wellen sich (Versatz in y, vorn stärker als am Horizont)
	vec2 off = vec2(0.0);
	if (water > 0.001) {
		float depth = clamp((p.y - horizon_y) / (near_y - horizon_y), 0.0, 1.0);
		float a = mix(0.5, 2.2, depth);
		float w1 = sin(p.x * mix(0.09, 0.035, depth) + p.y * 0.61 - t * 2.3);
		float w2 = sin(p.x * mix(0.17, 0.07, depth) - p.y * 0.27 + t * 1.6 + 1.3);
		off = vec2(0.0, a * (0.7 * w1 + 0.3 * w2)) * smoothstep(0.2, 0.9, water);
	}
	vec4 s = texture(TEXTURE, UV + off / plate_size);
	float ink = s.r;
	float ridge = s.g;
	if (water > 0.001) {
		// nach dem Versatz wieder als Linie drucken (bilineares Abtasten macht sonst Grau)
		float crisp = smoothstep(0.18, 0.78, ink);
		ink = mix(ink, crisp, smoothstep(0.2, 0.9, water));
	}

	// Licht sammeln
	float L = 0.0;
	float dl = length(p - lantern_pos);
	// im Himmel voll, auf Gegenständen (Laternengestell, Pfahl) schwach, damit deren Linien stehen bleiben.
	// Fast linearer Abfall von 0,2 R bis 1,3 R: Die dichten Himmelslinien (Kammfeld 0,4–0,6) verschwinden nur in
	// einem schmalen Band von L; ein steiler Abfall ergab dort einen harten Kreisrand.
	float fall = clamp((1.3 * lantern_r - dl) / (1.1 * lantern_r), 0.0, 1.0);
	L = max(L, lantern_k * mix(0.3, 0.85, smoothstep(0.3, 0.9, sky)) * fall);
	vec2 dp = (p - pool_pos) / pool_r;
	L = max(L, 0.55 * lantern_k * (1.0 - smoothstep(0.25, 1.0, length(dp))));
	float dw = length((p - window_pos) / vec2(1.0, 1.3));
	L = max(L, window_k * (1.0 - smoothstep(3.0, 16.0, dw)));

	// Leuchtturmstrahl: Keil vom Leuchtfeuer weg, nur im Himmel
	vec2 d = p - lamp_pos;
	float along = d.x * beam_dir;
	if (along > 0.0 && beam_len > 1.0) {
		float hw = 3.0 + along * 0.085;
		float edge = 1.0 - smoothstep(hw - 1.5, hw + 0.5, abs(d.y - along * 0.015));
		float fade = pow(clamp(1.0 - along / beam_len, 0.0, 1.0), 0.6);
		L = max(L, 0.92 * beam_k * edge * fade * smoothstep(0.3, 0.9, sky));
	}
	float dl2 = length(p - lamp_pos);
	L = max(L, flash_k * (1.0 - smoothstep(4.0, 46.0, dl2)) * max(sky, step(dl2, 9.0)));

	// Glitzern: kurze waagerechte Lichtstriche in den hellen Spiegelungen, springen 6-mal pro Sekunde
	vec2 cell = vec2(floor(p.x / 16.0), floor(p.y / 3.0));
	float r = hash21(cell + vec2(glint_step * 7.0, glint_step * 3.0));
	float inx = fract(p.x / 16.0);
	float dash = step(0.18, inx) * step(inx, 0.82);
	L = max(L, step(0.8, r) * dash * s.b * 1.1);

	ink = thin_lines(ink, ridge, clamp(L, 0.0, 1.0));

	// Rauch: gestochene Ballen. Eigene waagerechte Linien im Abstand der Himmelslinien (3 px), leicht nach der Form
	// gewölbt, deren Stärke zur Schattenseite (unten rechts) zunimmt, dazu eine Kontur, die auf der Schattenseite
	// anschwillt. Der Ballen verdeckt die Himmelslinien, indem er sie ausdünnt. Ein alternder Ballen wird nicht
	// durchsichtig: Eine steigende Schwelle dünnt Kontur und eigene Linien aus (Lichtseite zuerst), und die
	// Himmelslinien gewinnen ihre Stärke zurück.
	if (puff_count > 0) {
		float dist = 1e5;
		float alpha = 0.0;
		vec2 cn = vec2(0.0);
		float rn = 1.0;
		float best = 1e5;
		for (int i = 0; i < 12; i++) {
			if (i >= puff_count) break;
			vec4 pf = puffs[i];
			if (pf.w <= 0.001) continue;
			float di = length(p - pf.xy) - pf.z;
			dist = min(dist, di);              // harte Vereinigung: gebogte Umrisse wie gestochene Wolken
			if (di < best) { best = di; cn = pf.xy; rn = max(pf.z, 1.0); alpha = pf.w; }
		}
		if (dist < 3.0) {
			vec2 q = (p - cn) / rn;
			vec2 ldir = normalize(vec2(0.45, 0.9));
			float shade = smoothstep(-0.6, 0.85, dot(q, ldir));          // innen: Verlauf über den ganzen Ballen
			float shade_c = smoothstep(-0.6, 0.85, dot(normalize(q + vec2(1e-4)), ldir));   // am Umriss
			float thr = (1.0 - alpha) * 1.3;                               // Ausdünnen mit dem Alter (px)
			float inside = 1.0 - smoothstep(-1.2, -0.2, dist);
			// Himmelslinien unter dem Ballen ausdünnen (junger Ballen: fast ganz; sie kehren zurück, bevor die eigenen
			// Linien ganz verschwunden sind, sonst bleibt eine leere Papierscheibe)
			float sky_in = mix(ink, thin_lines(ink, ridge, 0.9 * smoothstep(0.7, 1.0, alpha)), inside);
			// eigene Linien: waagerecht, zur Mitte des Ballens leicht nach oben gewölbt
			float yy = p.y + 0.22 * rn * sqrt(max(0.0, 1.0 - q.x * q.x));
			float dl3 = abs(fract(yy / 3.0) - 0.5) * 3.0;
			float own = line_cov(dl3, mix(0.3, 0.9, shade) - thr) * step(dist, -1.2);
			float contour = line_cov(abs(dist + 0.7), mix(0.45, 1.0, shade_c) - thr);
			ink = max(sky_in, max(own, contour) * 0.95);
		}
	}

	COLOR = vec4(ink_color.rgb, clamp(ink, 0.0, 1.0) * ink_color.a);
}
