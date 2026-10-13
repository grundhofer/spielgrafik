// Druckstock des Hafens: Platten des KI-Hintergrunds (R Schwarz, G Petrol, B Zinnober) plus alle Umgebungs-
// animationen, die mit Schnitten arbeiten. Ausgabe sind wieder Plattendeckungen; Farbe, Papier und Druckfehler
// macht erst print.gdshader. Alles hier läuft stufig (t_anim springt 10-mal je Sekunde).
shader_type canvas_item;
render_mode unshaded, blend_mix;

uniform sampler2D regions_tex : filter_nearest, repeat_disable;   // R Wasser, G Himmel, B Lichtcode
uniform float t_anim = 0.0;
uniform float horizon = 266.0;
uniform float wave_ax = 3.0;       // waagerechtes Wiegen der Wellenschnitte (px)
uniform float wave_ay = 1.5;       // senkrechtes Heben (px)

uniform vec2 lamp_pos = vec2(1046.0, 75.5);
uniform float beam_phase = 0.0;    // Umlaufwinkel des Leuchtfeuers
uniform float beam_len = 900.0;
uniform float flash = 0.0;         // 0..1, Strahl zeigt zur Kamera

uniform vec2 lantern_pos = vec2(351.5, 143.0);
uniform float flicker = 0.5;       // 0..1
uniform float flicker_seed = 0.0;

uniform vec4 puffs[10];            // Rauch: x, y, Radius, Alter 0..1 (Radius 0 = aus)


// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash11(float p) {
	p = fract(p * 0.1031);
	p *= p + 33.33;
	p *= p + p;
	return fract(p);
}

// Strahlenkranz aus spitz auslaufenden Schnitten um einen Punkt (1 = geschnitten)
float ray_crown(vec2 d, float n, float r0, float len_min, float len_var, float w0, float seed, float grow) {
	float r = length(d);
	float a = atan(d.y, d.x);
	float idx = floor(a / TAU * n + 0.5);
	float ca = idx * TAU / n + (hash11(idx * 3.7 + 11.0) - 0.5) * 0.9 * TAU / n;
	float da = abs(mod(a - ca + PI, TAU) - PI);
	float rl = r0 + (len_min + len_var * hash11(idx * 7.13 + seed)) * grow;
	float u = clamp((r - r0) / max(rl - r0, 1.0), 0.0, 1.0);
	float half_w = w0 * (1.0 - u);
	return step(r0, r) * step(r, rl) * step(da * r, half_w);
}

void fragment() {
	vec2 sz = 1.0 / TEXTURE_PIXEL_SIZE;
	vec2 p = UV * sz;
	vec4 base = texture(TEXTURE, UV);
	vec3 reg = texture(regions_tex, UV).rgb;

	// --- Wasser: die Wellenschnitte wiegen waagerecht und heben sich; vorn stärker als am Horizont.
	float depth = clamp((p.y - horizon) / (580.0 - horizon), 0.0, 1.0);
	// Versatz ändert sich über die Höhe nur langsam (Wellenlänge > 100 px), sonst zerreißen die Schnitte
	vec2 off = vec2(wave_ax * (0.35 + 0.65 * depth) * sin(p.y * 0.045 + t_anim * 2.2),
	                wave_ay * (0.3 + 0.7 * depth) * sin(p.x * 0.028 - t_anim * 2.6 + p.y * 0.035));
	vec2 q = (p + off) / sz;
	vec4 wv = texture(TEXTURE, q);
	float wq = texture(regions_tex, q).r;
	vec3 pl = mix(base.rgb, wv.rgb, reg.r * wq);

	float sky = step(0.5, reg.g);

	// --- Leuchtfeuer: Fächer aus fünf langen, spitz auslaufenden Schnitten (Papier) durch den Nachthimmel.
	float s = sin(beam_phase);
	float dir = s < 0.0 ? -1.0 : 1.0;
	float blen = beam_len * abs(s) + 30.0;
	vec2 d = p - lamp_pos;
	vec2 ax = normalize(vec2(dir, 0.07));
	float along = dot(d, ax);
	float across = dot(d, vec2(-ax.y, ax.x));
	float ang = atan(across, max(along, 0.001));
	float half_cone = 0.10;
	float k = ang / half_cone;                       // -1..1 im Kegel
	float m = k * 1.5;                               // drei Strahlen: Mitten bei -2/3, 0, +2/3
	float fi = abs(fract(m + 0.5) - 0.5);            // Abstand zur nächsten Strahlmitte (Strahl-Einheiten)
	float taper = 1.0 - along / blen;
	float wray = 0.36 * taper * (1.0 - 0.3 * abs(k));
	float beam = step(4.0, along) * step(0.0, taper) * step(abs(k), 1.05) * step(fi, wray);
	beam = max(beam, step(4.0, along) * step(along, 46.0) * step(abs(k), 1.0));   // Kern am Licht
	beam *= sky;
	float beam_warm = beam * step(along, 0.18 * blen);

	// Aufblitzen: Kranz um die Lampe, wenn der Strahl zur Kamera zeigt
	float burst = ray_crown(p - lamp_pos, 18.0, 12.0, 22.0, 30.0, 3.4, 5.0, flash) * step(0.05, flash) * sky;

	// --- Laterne: Kranz aus kurzen Schnitten im Zinnober, Länge flackert je Druckfassung
	float crown = ray_crown(p - lantern_pos, 15.0, 31.0, 14.0, 24.0, 3.6, flicker_seed, 0.55 + 0.45 * flicker) * sky;
	// Flamme im Glas: Papierfleck, Größe flackert
	float glass = step(abs(reg.b - 0.251), 0.03);
	vec2 fd = (p - lantern_pos - vec2(0.0, 2.0)) / vec2(3.5 + 3.5 * flicker, 7.0 + 5.0 * flicker);
	float flame = glass * step(length(fd), 1.0);

	// --- Leuchtturmlampe: beim Aufblitzen Papier, sonst wie gedruckt (Zinnober)
	float lamp = step(abs(reg.b - 0.502), 0.03);

	// --- Rauch: Vereinigung weniger Kreise; junge Ballen Papier mit schwarzem Schnittrand, alte Petrol
	float sd = 1e5;
	float age = 0.0;
	vec2 pc = vec2(0.0);
	float pr = 1.0;
	for (int i = 0; i < 10; i++) {
		vec4 pf = puffs[i];
		float di = length(p - pf.xy) - pf.z;
		if (pf.z > 0.5 && di < sd) { sd = di; age = pf.w; pc = pf.xy; pr = pf.z; }
	}
	float smoke = step(sd, 0.0) * sky;
	float rim = smoke * step(-2.4, sd);
	// innerer Schnittbogen unten rechts im Ballen (gibt Rundung)
	vec2 dv = p - pc;
	float rr = length(dv);
	float arc = smoke * step(abs(rr - pr * 0.58), 1.1) * step(0.15, dv.x / max(rr, 0.001)) * step(0.0, dv.y);

	// --- Zusammensetzen (Reihenfolge: Rauch, Strahl, Kränze, Lichter)
	vec3 smoke_fill = age < 0.55 ? vec3(0.0) : vec3(0.0, 1.0, 0.0);
	pl = mix(pl, smoke_fill, smoke);
	pl = mix(pl, vec3(1.0, 0.0, 0.0), max(rim, arc));
	pl = mix(pl, vec3(0.0), beam);
	pl = mix(pl, vec3(0.0, 0.0, 1.0), beam_warm);
	pl = mix(pl, vec3(0.0), burst);
	pl = mix(pl, vec3(0.0, 0.0, 1.0), crown);
	pl = mix(pl, vec3(0.0), flame);
	pl = mix(pl, vec3(0.0), lamp * step(0.5, flash));
	COLOR = vec4(pl, 1.0);
}
