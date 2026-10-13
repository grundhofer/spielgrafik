// Jugendstil – Hafen von Lornholm: Plakatbild mit fließenden Wellenornamenten, Goldschimmer, pulsierendem
// Nimbus um das Leuchtfeuer, flackernder Laterne und funkelnden Sternen.
// Koordinaten: p = Weltpixel des Plakatbildes (bg.png, 1536x1064). Das Sprite trägt je Einstellung eine andere
// Textur (Totale: vorab verkleinert, Nahaufnahme: 1:1); UV ist in beiden gleich.
// Maske (art/mask.png, nearest): R = Code*32 (0 Himmel, 1 Wolken, 2 Sonne, 3 Wasser, 4 Boote, 5 Lichter, 6 Rest),
// G = Licht*64 (1 Fenster, 2 Laterne, 3 Leuchtfeuer), B = Abstand im Wasser zum Rand in px*16.
// Alle Texturen werden vor den Fallunterscheidungen abgetastet.
shader_type canvas_item;

uniform sampler2D mask : filter_nearest;
uniform vec2 world_size = vec2(1536.0, 1064.0);
uniform float t = 0.0;
uniform float horizon_y = 501.0;
uniform float quay_y = 789.0;
uniform vec2 lamp = vec2(1277.0, 230.0);
uniform vec2 lantern = vec2(661.0, 509.0);
uniform float pulse_front = -100.0;   // Radius der Lichtwelle des Leuchtfeuers (Weltpixel)
uniform float lamp_gain = 1.0;
uniform float lantern_gain = 1.0;
uniform float window_gain = 1.0;
uniform float wave_gain = 1.0;        // Prüfschalter: 0 = Wellen stehen
uniform vec3 key_col = vec3(0.129, 0.122, 0.055);
uniform vec3 gold_col = vec3(0.839, 0.627, 0.259);
uniform vec3 pale_gold = vec3(0.98, 0.86, 0.56);
uniform vec3 ochre_col = vec3(0.66, 0.50, 0.26);
uniform sampler2D stars : filter_linear;   // Sternmaske (R Gewicht, G Phase), siehe build_bg.py
uniform float nim_disc = 64.0;             // Radius der Ockerscheibe (Weltpixel)
uniform float nim_ring = 82.0;             // Radius des äußeren Goldrings
uniform float nim_key = 3.0;               // Konturbreite im Nimbus (Weltpixel, wie die Schlüssellinie)

float code_of(vec4 m) { return floor(m.r * 255.0 / 32.0 + 0.5); }

// Vorzeichenbehafteter Abstand zu einer Vesica (Spitzblatt) mit Spitzen auf der y-Achse (nach I. Quilez)
// Distanzfunktion Vesica nach Inigo Quilez – Copyright (c) Inigo Quilez, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt), https://iquilezles.org/articles/distfunctions2d/
float sd_vesica(vec2 q, float rad, float d) {
	q = abs(q);
	float b = sqrt(rad * rad - d * d);
	return ((q.y - b) * d > q.x * b) ? length(q - vec2(0.0, b)) : length(q - vec2(-d, 0.0)) - rad;
}

// Ring mit Goldlinie und dunkler Kontur beiderseits, Breiten in Weltpixeln; aa = Pixelbreite in Weltpixeln
vec2 ring(float r, float R, float w_gold, float w_key, float aa) {
	float d = abs(r - R);
	float gold = 1.0 - smoothstep(w_gold * 0.5 - aa * 0.5, w_gold * 0.5 + aa * 0.5, d);
	float key = 1.0 - smoothstep(w_gold * 0.5 + w_key - aa * 0.5, w_gold * 0.5 + w_key + aa * 0.5, d);
	return vec2(gold, key);
}

void fragment() {
	vec2 p = UV * world_size;
	vec4 m0 = texture(mask, UV);
	vec4 st = texture(stars, UV);
	float code0 = code_of(m0);
	float light_id = floor(m0.g * 255.0 / 64.0 + 0.5);
	float dist = m0.b * 255.0 / 16.0;

	// --- Wasser: Wellenlinien wandern als Welle die Bänder entlang (senkrechter Versatz, der nach rechts läuft)
	//     und die Bänder gleiten waagrecht gegeneinander; ausgeblendet an Horizont, Kai, Booten und Pfählen.
	float depth = clamp((p.y - horizon_y) / (quay_y - horizon_y), 0.0, 1.0);
	float fade = clamp((dist - 1.0) / 6.0, 0.0, 1.0) * wave_gain;
	float lam = mix(120.0, 320.0, depth);
	float k = 6.2831853 / lam;
	float c = mix(14.0, 38.0, depth);
	float amp = mix(1.2, 5.5, depth) * fade;
	float dy = amp * (0.7 * sin(k * (p.x - c * t) + p.y * 0.015)
			+ 0.3 * sin(1.9 * k * (p.x + 0.6 * c * t) + 1.7 + p.y * 0.031));
	float dx = mix(1.0, 4.0, depth) * fade * sin(0.9 * t + p.y * 0.085);
	vec2 uvq = (p + vec2(dx, dy)) / world_size;
	vec4 c0 = texture(TEXTURE, UV);
	vec4 cq = texture(TEXTURE, uvq);
	vec4 mq = texture(mask, uvq);
	float is_w = 1.0 - step(0.5, abs(code0 - 3.0));
	float q_w = 1.0 - step(0.5, abs(code_of(mq) - 3.0));
	vec3 col = mix(c0.rgb, cq.rgb, is_w * q_w);

	// --- Gold auf dem Wasser schimmert: Lichtwelle läuft die Goldlinien entlang
	float goldish = step(0.55, col.r) * step(col.b + 0.18, col.r) * step(col.b + 0.08, col.g);
	float glint = smoothstep(0.62, 1.0, sin(p.x * 0.026 - t * 2.3 + p.y * 0.12));
	col = mix(col, pale_gold, is_w * goldish * glint * 0.75);

	// --- Sterne funkeln: eigene Sternmaske (art/stars.png, aus build_bg.py: kleine isolierte Goldflecken des
	//     Plakats; R = Gewicht, G = Phase je Stern). Nur dort ändert sich der Himmel; Wolken bleiben ruhig.
	float sw = st.r;
	float sph = st.g;
	float tw = 0.5 + 0.5 * sin(t * (1.6 + sph * 1.8) + sph * 6.2831853 * 7.0);
	vec3 star_col = mix(col * 0.5, mix(col, pale_gold, 0.55), tw);
	col = mix(col, star_col, sw * step(0.002, sph));

	// --- Lichter
	col = mix(col, min(col * window_gain, vec3(1.0)), 1.0 - step(0.5, abs(light_id - 1.0)));
	col = mix(col, min(col * lantern_gain, vec3(1.0)), 1.0 - step(0.5, abs(light_id - 2.0)));
	col = mix(col, min(col * lamp_gain, vec3(1.0)), 1.0 - step(0.5, abs(light_id - 3.0)));

	// --- Nimbus um das Leuchtfeuer als flache, deckende Plakatform (nur auf Himmel, Wolken, Sonne: hinter Turm,
	//     Haus und Bäumen): Ockerscheibe mit Kontur, darauf ein Kranz aus 12 spitzen Goldblättern mit Kontur, in
	//     der Mitte eine blassgoldene Scheibe, außen ein kräftiger Goldring mit Kontur beiderseits. Die Lichtwelle
	//     (pulse_front) hellt nacheinander Mitte, Blätter und Ring zu Blassgold auf.
	float sky_layer = 1.0 - step(2.5, code0);
	vec2 dl = p - lamp;
	float r = length(dl);
	float aa = max(fwidth(r), 0.5);
	float act0 = 1.0 - smoothstep(0.0, 16.0, abs(pulse_front - 12.0));
	float act1 = 1.0 - smoothstep(0.0, 18.0, abs(pulse_front - 44.0));
	float act2 = 1.0 - smoothstep(0.0, 16.0, abs(pulse_front - nim_ring));
	vec3 halo = col;
	// äußerer Goldring
	vec2 g_ring = ring(r, nim_ring, 5.0 + 1.5 * act2, nim_key, aa);
	halo = mix(halo, key_col, g_ring.y);
	halo = mix(halo, mix(gold_col, pale_gold, act2), g_ring.x);
	// Ockerscheibe mit Kontur
	float disc_in = 1.0 - smoothstep(nim_disc - aa * 0.5, nim_disc + aa * 0.5, r);
	float disc_k = 1.0 - smoothstep(nim_disc + nim_key - aa * 0.5, nim_disc + nim_key + aa * 0.5, r);
	halo = mix(halo, key_col, disc_k);
	halo = mix(halo, mix(ochre_col, gold_col, 0.35 * act1), disc_in);
	// Kranz aus 12 spitzen Blättern (Vesica, Achse radial), Gold mit Kontur
	float ang = atan(dl.y, dl.x);
	float sct = fract(ang * 12.0 / 6.2831853 + 0.5) - 0.5;
	vec2 lp = vec2(sct * 6.2831853 * r / 12.0, r - 44.0);
	float pd = sd_vesica(lp, 21.0, 14.0);
	float pet_in = 1.0 - smoothstep(-nim_key - aa * 0.5, -nim_key + aa * 0.5, pd);
	float pet_k = 1.0 - smoothstep(-aa * 0.5, aa * 0.5, pd);
	halo = mix(halo, key_col, pet_k);
	halo = mix(halo, mix(gold_col, pale_gold, act1), pet_in);
	// blassgoldene Mitte mit Kontur
	float mid_in = 1.0 - smoothstep(24.0 - aa * 0.5, 24.0 + aa * 0.5, r);
	float mid_k = 1.0 - smoothstep(24.0 + nim_key - aa * 0.5, 24.0 + nim_key + aa * 0.5, r);
	halo = mix(halo, key_col, mid_k);
	halo = mix(halo, mix(vec3(0.93, 0.76, 0.42), vec3(1.0, 0.95, 0.78), act0), mid_in);
	col = mix(col, halo, sky_layer);

	// --- Lichthof der Laterne: ein deckender Goldring mit Kontur beiderseits (nicht auf Pfosten, Laterne und Kai);
	//     beim Flackern wird er heller (Gold → Blassgold) und etwas breiter
	float rl = length(p - lantern);
	float aal = max(fwidth(rl), 0.5);
	float not_rest = 1.0 - step(5.5, code0);
	float fl = clamp((lantern_gain - 1.0) * 3.0, 0.0, 1.0);
	vec2 g1 = ring(rl, 36.0, 3.0 + 1.5 * fl, nim_key * 0.6, aal);
	col = mix(col, key_col, g1.y * not_rest);
	col = mix(col, mix(gold_col, pale_gold, fl), g1.x * not_rest);

	COLOR = vec4(col, c0.a);
}
