// Jalousienlicht des Fensters: gemeinsame Geometrie für Pflaster (scene.gdshader), Schlagschatten
// (badger_fx.gdshader) und Figur (badger.gdshader). Alle Angaben in Bildschirmpixeln (1280×720).
//
// Lichtfleck auf dem Pflaster = Viereck A-B-C-D: AB ist die Kante zur Hauswand (Fensterunterkante),
// DC die zur Kamera (Fensteroberkante); AB und DC laufen parallel zum Wandfuß. Die Lamellenschatten sind
// Streifen parallel zu AB, gleichmäßig zwischen AB und DC verteilt (Parameter s von 0 bis 1).

uniform vec2 win_a = vec2(95.0, 566.0);
uniform vec2 win_b = vec2(205.0, 543.0);
uniform vec2 win_c = vec2(560.0, 705.0);
uniform vec2 win_d = vec2(300.0, 760.0);
uniform float win_slats = 9.0;       // Lamellenzwischenräume im Fleck
uniform float win_duty = 0.52;       // Anteil Licht je Lamellenperiode
uniform float win_gain = 1.0;        // Helligkeit des Fensterlichts (Szene setzt sie)

float win_side(vec2 a, vec2 b, vec2 p) {
	vec2 d = normalize(b - a);
	return d.x * (p.y - a.y) - d.y * (p.x - a.x);   // > 0: rechts der Richtung a->b (Bildschirm-y nach unten)
}

// Fleckmaske mit weichem Rand (Halbschatten des Fensterrahmens) und Parameter s (0 an der Wand, 1 vorn).
float win_patch(vec2 p, out float s) {
	float depth = win_side(win_a, win_b, win_d);
	s = clamp(win_side(win_a, win_b, p) / depth, 0.0, 1.0);
	float in_ab = smoothstep(-2.0, 3.0, win_side(win_a, win_b, p) * sign(depth));
	float in_dc = smoothstep(-2.0, 3.0, win_side(win_c, win_d, p) * sign(depth));
	float in_ad = smoothstep(-3.0, 4.0, win_side(win_d, win_a, p) * sign(depth));
	float in_bc = smoothstep(-3.0, 4.0, win_side(win_b, win_c, p) * sign(depth));
	return in_ab * in_dc * in_ad * in_bc;
}

// Lamellenmuster: 1 im Licht, 0 im Lamellenschatten, kantengeglättet über die Bildschirmableitung.
float win_bands(float f) {
	float w = max(fwidth(f), 0.02);
	float x = fract(f);
	return smoothstep(0.0, w, x) * (1.0 - smoothstep(win_duty - w, win_duty, x));
}

// Zusätzliches Licht auf dem Pflaster (wird zu bg addiert): Streifen, zur Wand hin heller.
vec3 win_floor_light(vec2 p, vec3 bg) {
	float s;
	float m = win_patch(p, s);
	if (m <= 0.0) return vec3(0.0);
	float bands = win_bands(s * win_slats + 0.18);
	float fall = mix(1.0, 0.62, s);
	return m * bands * fall * win_gain * (bg * 3.0 + vec3(0.14));
}
