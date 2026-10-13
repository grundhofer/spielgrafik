// Gemeinsamer Teil der Tusche-Nachbearbeitung (ink_lines.gdshader für Forward+,
// ink_lines_depth.gdshader für Mobile/Compatibility): Tiefe lesen, Silhouetten finden, Strich
// leicht verwackeln, Papierkorn, Linie über das Bild legen.
// Silhouetten: 1/z ist auf einer Ebene im Bildraum linear. Weicht der Nachbar stark von der
// Vorhersage aus Mitte und Gegenseite ab und liegt er weiter hinten, liegt die Mitte auf der
// Vorderkante. So entstehen auf flach gesehenem Boden keine Fehllinien (Verfahren wie in toon-cel).

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest, repeat_disable;
uniform sampler2D screen_tex : hint_screen_texture, filter_nearest, repeat_disable;
uniform sampler2D grain_tex : filter_linear, repeat_enable;   // Papierkorn (NoiseTexture2D, fester Seed)
uniform sampler2D wobble_tex : filter_linear, repeat_enable;  // Strichzittern (NoiseTexture2D, fester Seed)

global uniform vec4 ink_color;   // linear (globale Farben werden nicht aus sRGB umgerechnet)

uniform float depth_threshold = 0.03;   // relativer Fehler der 1/z-Vorhersage
uniform float min_gap = 0.06;           // m, kleinster Tiefensprung für eine Silhouette
uniform float inner_alpha = 0.85;       // Deckkraft der Innenlinien (Knicke, Farbgrenzen)
uniform float sil_near = 2.2;           // Silhouettenbreite in Pixeln nah ...
uniform float sil_far = 1.1;            // ... und fern
uniform float sil_dist = 45.0;          // m, ab hier sil_far
uniform float far_begin = 80.0;         // m: ab hier werden Linien blasser ...
uniform float far_end = 700.0;          // ... bis far_alpha
uniform float far_alpha = 0.5;
uniform float wobble_px = 0.7;          // Strichzittern in Pixeln
uniform float grain = 0.05;             // Stärke des Papierkorns
uniform float lines_on = 1.0;           // Vergleichsschalter --no-lines

float depth_at(vec2 uv) {
	return texture(depth_tex, uv).r;
}

vec3 view_pos(vec2 uv, float d, mat4 inv_proj) {
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
	vec4 v = inv_proj * vec4(uv * 2.0 - 1.0, d * 2.0 - 1.0, 1.0);   // OpenGL: NDC-z von -1 bis 1
#else
	vec4 v = inv_proj * vec4(uv * 2.0 - 1.0, d, 1.0);
#endif
	return v.xyz / v.w;
}

float lin_z(vec2 uv, mat4 inv_proj) {
	return -view_pos(uv, depth_at(uv), inv_proj).z;
}

// Bildpunktmitte, auf der die Tiefe tatsächlich abgetastet wird (filter_nearest)
vec2 snap_uv(vec2 uv, vec2 vp) {
	return (floor(uv * vp) + 0.5) / vp;
}

// Tiefensprung in Richtung off (in Pixeln): Mitte vorn, Nachbar hinten, Vorhersage aus der Gegenseite.
// Alle drei Punkte liegen auf Pixelmitten; die Vorhersage nutzt die echten Abstände a und b, sonst
// ergeben ungleich gerundete Abstände nahe dem Horizont (1/z ändert sich dort stark je Pixel)
// flächige Fehllinien.
float depth_edge(vec2 c, vec2 off, vec2 vp, float izc, mat4 inv_proj, float gap) {
	vec2 un = snap_uv(c + off / vp, vp);
	vec2 uo = snap_uv(c - off / vp, vp);
	float a = length((un - c) * vp);
	float b = max(length((c - uo) * vp), 0.5);
	float zn = lin_z(un, inv_proj);
	float zo = lin_z(uo, inv_proj);
	float pred = izc + (izc - 1.0 / zo) * a / b;
	float err = abs(1.0 / zn - pred) / izc;
	// Nachbar muss mindestens min_gap weiter hinten liegen: flache Stufen (Pflaster 8 mm) bleiben ohne Kontur
	float zc = 1.0 / izc;
	float behind = step(zc + max(gap, 0.004 * zc), zn);
	return smoothstep(depth_threshold, depth_threshold * 1.6, err) * behind;
}

// Silhouetten in acht Richtungen (diagonal etwas kürzer, damit schräge Kanten gleich breit wirken).
// c ist eine Pixelmitte (snap_uv), zc ihr Abstand, gap der kleinste Tiefensprung in Metern.
float silhouette(vec2 c, vec2 vp, float zc, mat4 inv_proj, float gap) {
	float w = max(mix(sil_near, sil_far, smoothstep(3.0, sil_dist, zc)), 1.0);
	float izc = 1.0 / zc;
	float e = 0.0;
	vec2 dirs[8] = {vec2(1.0, 0.0), vec2(-1.0, 0.0), vec2(0.0, 1.0), vec2(0.0, -1.0),
		vec2(0.72, 0.72), vec2(-0.72, 0.72), vec2(0.72, -0.72), vec2(-0.72, -0.72)};
	for (int k = 0; k < 8; k++) {
		e = max(e, depth_edge(c, dirs[k] * w, vp, izc, inv_proj, gap));
	}
	return e;
}

// Strichzittern: Abtastpunkt um Bruchteile eines Pixels verschieben (feste Rauschtextur), damit
// gerade Kanten nicht wie mit dem Lineal gezogen aussehen.
vec2 wobble_uv(vec2 uv, vec2 px, vec2 frag) {
	vec2 n = texture(wobble_tex, frag / 380.0).rg * 2.0 - 1.0;
	return uv + n * px * wobble_px;
}

// Linie und Papier auf das Bild legen. sky = Himmel (keine Geometrie, Abstand über 2900 m).
vec4 compose(vec2 uv, vec2 frag, float e, float zc, float sky) {
	vec3 under = texture(screen_tex, uv).rgb;
	float g = texture(grain_tex, frag / 512.0).r - 0.5;
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
	g *= 0.45;   // Compatibility rechnet hier nicht linear: dasselbe Korn wirkte gut doppelt so stark
#endif
	vec3 paper = under * (1.0 + grain * g);
	float a = e * lines_on * (1.0 - sky);
	a *= mix(1.0, far_alpha, smoothstep(far_begin, far_end, zc));
	return vec4(mix(paper, ink_color.rgb, clamp(a, 0.0, 1.0)), 1.0);
}
