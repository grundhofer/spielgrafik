shader_type canvas_item;
// Der freigestellte Dachs als "Darsteller" vor dem Foto. Die Grundangleichung (Weißabgleich, Belichtung, Schärfe)
// steckt schon in actor.png; hier kommt dazu, was sich mit der Szene bewegt:
//  - Atmen und Gewicht verlagern (vertex: Strecken und Scheren ab den Füßen, die Füße bleiben stehen)
//  - Kopfdrehung: harter Wechsel zur zweiten Fassung (Kopf nach rechts) mit einem Zwischenbild (look = 0,5)
//  - actor_tex und look_tex liegen in tex_scale-facher Auflösung (2x) vor und werden mit 9 Abtastpunkten je
//    Bildschirmpixel verkleinert: Atmen und Gewichtsverlagerung verschieben die Figur um Bruchteile eines Pixels, mit
//    einer 1x-Textur und linearer Filterung pumpte die Schärfe dabei mit (Laplace im Gesicht 14,7-34,8).
//  - wehendes Schalende (Verschiebung quer zur Schalachse, Gewicht aus actor_aux2.g)
//  - Kantenlicht aus zwei Richtungen über die Randnormale (actor_aux.rg) im Randband (actor_aux.b): warm von der
//    Laterne links oben (folgt dem Flackern), kühl vom hellen Abendhimmel hinter der Figur (Gegenlicht)
//  - Lichtsaum: heller Hintergrund (Wasser) scheint am Rand ein (actor_aux2.r), wie bei gefilmten Darstellern
// integrate = false zeigt den Dachs ohne Kantenlicht und Lichtsaum (Vergleichsschalter --raw).

uniform sampler2D aux_tex : filter_linear, repeat_disable;   // R/G Randnormale, B Randband
uniform sampler2D aux2_tex : filter_linear, repeat_disable;  // R Lichtsaum-Band, G Schalgewicht
// Figur als Uniform statt TEXTURE: Godot erlaubt in einer Funktion (tap9) nicht Built-in und Uniform zugleich.
// Die Sprite-Textur (gleiche Datei) bestimmt nur die Größe des Rechtecks.
uniform sampler2D actor_tex : filter_linear, repeat_disable;  // Figur (Kopf zur Kamera), 2x
uniform sampler2D look_tex : filter_linear, repeat_disable;  // zweite Fassung (Kopf nach rechts), gleiche Größe
uniform sampler2D bg_blur : filter_linear, repeat_disable;   // weichgezeichnetes Foto (1280x720)
uniform vec2 screen_size = vec2(1280.0, 720.0);
uniform vec2 tex_size = vec2(185.0, 257.0);  // Größe der Figur in Bildschirmpixeln (1x); alle px-Werte beziehen sich darauf
uniform float tex_scale = 2.0;               // Texel von actor_tex/look_tex je Bildschirmpixel (Sprite-Skalierung 1/tex_scale)
uniform vec2 feet_px = vec2(92.5, 250.0);   // Fußpunkt in Bildschirmpixeln der Figur (Ursprung des Sprites)
uniform float t = 0.0;
uniform float look = 0.0;
// Kopfdrehung: Im Zwischenbild wandern die Gesichtszüge beider Fassungen halb zur Lage der anderen (Nase um
// head_shift), der Hinterkopf (head_back_x) bleibt stehen; nur innerhalb der Kopfellipse. Deckend ist nur, was eine
// verschobene Fassung bedeckt UND innerhalb der unverschobenen Umrisse liegt: kein durchscheinender zweiter Kopf.
uniform vec2 head_shift = vec2(26.0, -1.0);
uniform float head_back_x = 45.0;
uniform float head_nose_x = 82.0;
uniform vec2 head_c = vec2(85.0, 38.0);
uniform vec2 head_r = vec2(74.0, 52.0);
uniform bool integrate = true;
uniform bool animate = true;
// Atmen, Gewicht
uniform float breath_amp = 0.010;
uniform float breath_period = 3.4;
uniform float sway_px = 1.3;
uniform float sway_period = 6.4;
// Schal
uniform vec2 scarf_root = vec2(119.0, 77.0);
uniform vec2 scarf_tip = vec2(181.0, 97.0);
uniform float scarf_amp = 3.6;
uniform float gust = 1.0;
// Licht
uniform float lantern = 1.0;
uniform vec3 lantern_col = vec3(1.0, 0.58, 0.28);
uniform vec2 lantern_dir = vec2(-0.88, -0.48);   // vom Dachs zur Laterne (Bildschirm)
uniform float rim_k = 0.30;
uniform vec3 sky_col = vec3(0.60, 0.70, 0.90);
uniform vec2 sky_dir = vec2(0.10, -1.0);
uniform float sky_rim_k = 0.40;
uniform float side_k = 0.10;
uniform float wrap_k = 0.35;

varying vec2 world;

// 3x3 Abtastpunkte im Abstand von 1/3 Bildschirmpixel aus der 2x-Textur, vormultipliziert gemittelt: ein Filter von
// etwa 1 Bildschirmpixel, dessen Schärfe kaum von der Subpixel-Lage abhängt. Simuliert über 8x8 Subpixel-Lagen
// (Laplace im Gesicht, max/min): 1x bilinear 2,08, 2x mit 2x2 Punkten 1,35, 2x mit 3x3 Punkten 1,08.
vec4 tap9(sampler2D tx, vec2 uv) {
	vec2 o = (1.0 / 3.0) / tex_size;
	vec4 acc = vec4(0.0);
	for (int j = -1; j <= 1; j++) {
		for (int i = -1; i <= 1; i++) {
			vec4 s = texture(tx, uv + vec2(float(i), float(j)) * o);
			acc += vec4(s.rgb * s.a, s.a);
		}
	}
	return acc / 9.0;
}

void vertex() {
	if (animate) {
		// VERTEX: Ursprung am Fußpunkt (offset), y nach oben negativ, in Texeln (tex_scale je Bildschirmpixel)
		float hgt = clamp(-VERTEX.y / (feet_px.y * tex_scale), 0.0, 1.2);
		float br = sin(6.2831853 * t / breath_period);
		VERTEX.y *= 1.0 + breath_amp * br;
		VERTEX.x += hgt * sway_px * tex_scale * sin(6.2831853 * t / sway_period + 0.7);
	}
	world = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	vec2 px = UV * tex_size;
	vec4 ax0 = texture(aux2_tex, UV);
	// Schalende: Welle läuft von der Wurzel zur Spitze, Auslenkung quer zur Achse, wächst zur Spitze
	vec2 axis = scarf_tip - scarf_root;
	float alen = max(length(axis), 1.0);
	vec2 dir = axis / alen;
	vec2 nrm = vec2(-dir.y, dir.x);
	float s = clamp(dot(px - scarf_root, dir) / alen, 0.0, 1.5);
	float wave = sin(s * 4.2 - t * 6.3) * 0.65 + sin(s * 8.5 - t * 10.1 + 1.3) * 0.25 + sin(t * 1.7) * 0.25;
	vec2 d = animate ? nrm * wave * scarf_amp * gust * s * ax0.g : vec2(0.0);
	vec2 uv2 = (px - d) / tex_size;
	vec2 hq = (px - head_c) / head_r;
	float hw = (1.0 - smoothstep(0.35, 1.0, length(hq))) * smoothstep(head_back_x, head_nose_x, px.x);
	vec2 da = look * head_shift * hw;
	vec2 db = -(1.0 - look) * head_shift * hw;
	// alle Abtastungen vor jeder Verzweigung; a/b verschoben (Morph), a0/b0 unverschoben (Umrisse), vormultipliziert
	vec4 a = tap9(actor_tex, uv2 - da / tex_size);
	vec4 b = tap9(look_tex, uv2 - db / tex_size);
	vec4 a0 = tap9(actor_tex, uv2);
	vec4 b0 = tap9(look_tex, uv2);
	vec4 ax = texture(aux_tex, uv2);
	vec4 ax2 = texture(aux2_tex, uv2);
	vec3 bgc = texture(bg_blur, world / screen_size).rgb;
	// Farbe: gewichtetes Mittel der verschobenen Fassungen (wo nur eine deckt, deren Farbe)
	vec3 pm = mix(a.rgb, b.rgb, look);
	vec3 c = pm / max(mix(a.a, b.a, look), 1e-4);
	// Deckung: was eine (beteiligte) verschobene Fassung bedeckt, begrenzt auf die unverschobenen Umrisse; bei look 0
	// oder 1 genau die eine Fassung
	float wa = min(1.0, 2.0 - 2.0 * look);
	float wb = min(1.0, 2.0 * look);
	float al = min(max(wa * a.a, wb * b.a), max(wa * a0.a, wb * b0.a));
	if (integrate) {
		// Laternenseite (links) atmet mit dem Flackern, dazu das Kantenlicht
		float lside = 1.0 - smoothstep(0.15, 0.75, UV.x);
		c *= 1.0 + side_k * lside * (lantern - 1.0) * 3.0;
		vec2 n = ax.rg * 2.0 - 1.0;
		float lr = pow(clamp(dot(n, normalize(lantern_dir)), 0.0, 1.0), 1.5) * ax.b;
		float sr = pow(clamp(dot(n, normalize(sky_dir)), 0.0, 1.0), 1.5) * ax.b;
		c += lantern_col * lr * rim_k * lantern + sky_col * sr * sky_rim_k;
		// Lichtsaum: nur heller Hintergrund (Wasser, Himmel) scheint am Rand ein, nicht der dunkle Kai
		float bl = smoothstep(0.28, 0.45, dot(bgc, vec3(0.299, 0.587, 0.114)));
		c = mix(c, max(c, bgc), ax2.r * wrap_k * bl);
	}
	COLOR = vec4(c, al);
}
