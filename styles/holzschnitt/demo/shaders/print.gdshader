// Der Abzug: drei Druckplatten aus dem Platten-Viewport (R Schwarz/Holz, G Petrol/Linol, B Zinnober/Linol)
// werden nacheinander auf Papier gedruckt. Je Druckfassung (6 je Sekunde) ändern sich Passer (Versatz je
// Platte), das Wackeln der Schnittkanten, die Einfärbung (wo die Walze zu wenig Farbe gab, bleibt der Papierzahn
// frei) und der Papierbogen. Holzmaserung und Linolsprenkel gehören zum Stock und wandern mit dessen Passer.
shader_type canvas_item;
render_mode unshaded;

uniform sampler2D plates_tex : filter_linear, repeat_disable;
uniform sampler2D paper_tex : filter_linear, repeat_enable;
uniform sampler2D grain_tex : filter_linear, repeat_enable;   // R Holzmaserung, G Linolsprenkel, B Papierzahn
uniform sampler2D noise_tex : filter_linear, repeat_enable;   // RG Kantenwackeln, B Einfärbung

uniform vec3 ink_k : source_color = vec3(0.075, 0.068, 0.062);
uniform vec3 ink_t : source_color = vec3(0.165, 0.405, 0.435);
uniform vec3 ink_o : source_color = vec3(0.905, 0.36, 0.11);
uniform float op_k = 0.95;
uniform float op_t = 0.94;
uniform float op_o = 0.95;

uniform vec2 view_size = vec2(1280.0, 720.0);
uniform vec2 reg_k = vec2(0.0);
uniform vec2 reg_t = vec2(2.0, -1.0);
uniform vec2 reg_o = vec2(-1.5, 2.0);
uniform vec2 seed = vec2(0.0);
uniform vec2 sheet = vec2(0.0);
uniform float wobble = 1.0;        // px
uniform float starve = 0.6;       // Fehlstellen in Vollflächen
uniform float wood = 0.4;          // Holzmaserung im Schwarzstock
uniform float lino = 0.3;         // Linolsprenkel in den Farbplatten
uniform int probe = 0;             // 1 = Platten roh (ohne Druckfehler), 2 = nur Passer

float crisp(float c) {
	return smoothstep(0.40, 0.60, c);
}

void fragment() {
	vec2 p = UV * view_size;
	vec2 px = 1.0 / view_size;
	float wob = probe == 1 ? 0.0 : wobble;
	vec2 rk = probe == 1 ? vec2(0.0) : reg_k;
	vec2 rt = probe == 1 ? vec2(0.0) : reg_t;
	vec2 ro = probe == 1 ? vec2(0.0) : reg_o;

	// Kantenwackeln: je Platte eigenes glattes Rauschfeld (Wellenlänge 10-40 px)
	vec2 nk = texture(noise_tex, p / 512.0 + seed).rg - 0.5;
	vec2 nt = texture(noise_tex, p / 512.0 + seed + vec2(0.37, 0.61)).rg - 0.5;
	vec2 no = texture(noise_tex, p / 512.0 + seed + vec2(0.73, 0.19)).rg - 0.5;
	vec2 qk = p - rk + nk * 2.0 * wob;
	vec2 qt = p - rt + nt * 2.0 * wob;
	vec2 qo = p - ro + no * 2.0 * wob;
	float k = texture(plates_tex, qk * px).r;
	float t = texture(plates_tex, qt * px).g;
	float o = texture(plates_tex, qo * px).b;
	// Vollfläche: auch 4 px daneben gedeckt (dünne Linien und Schrift bleiben satt)
	float sk = min(min(texture(plates_tex, (qk + vec2(4.0, 0.0)) * px).r, texture(plates_tex, (qk - vec2(4.0, 0.0)) * px).r),
	               min(texture(plates_tex, (qk + vec2(0.0, 4.0)) * px).r, texture(plates_tex, (qk - vec2(0.0, 4.0)) * px).r));
	float st = min(min(texture(plates_tex, (qt + vec2(4.0, 0.0)) * px).g, texture(plates_tex, (qt - vec2(4.0, 0.0)) * px).g),
	               min(texture(plates_tex, (qt + vec2(0.0, 4.0)) * px).g, texture(plates_tex, (qt - vec2(0.0, 4.0)) * px).g));
	float so = min(min(texture(plates_tex, (qo + vec2(4.0, 0.0)) * px).b, texture(plates_tex, (qo - vec2(4.0, 0.0)) * px).b),
	               min(texture(plates_tex, (qo + vec2(0.0, 4.0)) * px).b, texture(plates_tex, (qo - vec2(0.0, 4.0)) * px).b));

	// Struktur des Stocks (wandert mit dem Passer) und des Bogens (je Druckfassung neu)
	float g_wood = texture(grain_tex, (p - rk) * px).r;
	float g_lino_t = texture(grain_tex, (p - rt) * px + vec2(0.31, 0.17)).g;
	float g_lino_o = texture(grain_tex, (p - ro) * px + vec2(0.63, 0.41)).g;
	float tooth = texture(grain_tex, (p + sheet) * px).b;
	vec3 paper = texture(paper_tex, (p + sheet) * px).rgb;
	float load_k = texture(noise_tex, p / 1500.0 + seed * 0.71).b;
	float load_t = texture(noise_tex, p / 1500.0 + seed * 0.53 + vec2(0.5, 0.2)).b;
	float load_o = texture(noise_tex, p / 1500.0 + seed * 0.37 + vec2(0.1, 0.7)).b;

	k = crisp(k);
	t = crisp(t);
	o = crisp(o);
	if (probe != 1) {
		sk = crisp(sk);
		st = crisp(st);
		so = crisp(so);
		// Papierzahn: Täler bleiben frei, wo die Walze wenig Farbe gab (load klein)
		float miss_k = smoothstep(0.0, 0.05, (0.20 + 0.20 * (1.0 - load_k)) - tooth);
		float miss_t = smoothstep(0.0, 0.05, (0.16 + 0.22 * (1.0 - load_t)) - tooth);
		float miss_o = smoothstep(0.0, 0.05, (0.16 + 0.22 * (1.0 - load_o)) - tooth);
		k *= 1.0 - sk * max(starve * miss_k, wood * g_wood);
		t *= 1.0 - st * max(starve * miss_t, lino * g_lino_t);
		o *= 1.0 - so * max(starve * miss_o, lino * g_lino_o);
	}

	vec3 col = paper;
	col *= mix(vec3(1.0), ink_t, op_t * t);
	col *= mix(vec3(1.0), ink_o, op_o * o);
	col *= mix(vec3(1.0), ink_k, op_k * k);
	COLOR = vec4(col, 1.0);
}
