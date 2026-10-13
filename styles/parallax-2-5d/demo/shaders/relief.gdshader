// Relief aus Gemälde + Tiefenkarte: ein Gitter (PlaneMesh, 769×513 Punkte) wird im Vertex-Shader entlang der
// Sehstrahlen der Gemälde-Kamera auf die Entfernung aus der Tiefenkarte geschoben. Von der Ausgangsposition
// aus gesehen deckt sich das Relief exakt mit dem Gemälde; bewegt sich die Kamera, entsteht echte Parallaxe.
//
// Vordere Schicht (front = true): Gitterpunkte tragen die nächste Disparität ihrer 5×5-Umgebung, damit dünne
// Dinge (Masten, Taue, Laternenpfahl) Geometrie bekommen. Im Fragment wird verworfen, was nicht zur Tiefe des
// eigenen Texels passt: so werden die über Tiefensprünge gestreckten Dreiecke auf Texelgenauigkeit
// ausgeschnitten, und dahinter erscheint die hintere Schicht.
// Hintere Schicht (front = false): aufgefülltes Gemälde (Ränder hinter Vordergrundkanten nach hinten
// fortgesetzt), durchgehend, etwas weiter hinten (depth_push), mit Rand über das Bild hinaus (skirt).
// Mittlere Schicht (front = true, sparse = true): Zwischenfüllung, nur wo die Tiefentextur einen Wert hat (fernere
// Gegenstandsfläche hinter einer näheren fortgesetzt), sonst verworfen; verwirft gestreckte Dreiecke wie vorn.
// fill_mode 0 (Vergleich „Streckung“): vordere Schicht verwirft nichts, mittlere und hintere Schicht aus.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque, shadows_disabled, fog_disabled;

uniform sampler2D color_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform sampler2D depth_tex : filter_nearest, repeat_disable;
uniform sampler2D vtx_tex : filter_nearest, repeat_disable;

uniform bool front = true;
uniform bool sparse = false;        // mittlere Schicht: Texel ohne Tiefe (0) verwerfen
uniform int fill_mode = 1;
uniform float f = 1236.0;
uniform float cx = 768.0;
uniform float yh = 421.0;
uniform vec2 img = vec2(1536.0, 1024.0);
uniform vec2 grid = vec2(769.0, 513.0);
uniform float grid_step = 2.0;
uniform float z_min = 3.0;
uniform float depth_push = 1.0;
uniform float skirt = 0.0;          // Randverlängerung in UV-Einheiten (nur hintere Schicht)
uniform float tol_rel = 0.10;
uniform float tol_abs = 0.0015;
uniform float stretch_max = 0.008;  // Disparität je Texel, darüber gilt ein Dreieck als gestreckt

// Wasser: waagerechtes Wogen und Glitzern nur in der Wassermaske (Kanal B der Tiefenkarte)
uniform float time = 0.0;
uniform float wave_amp = 1.6;       // Quellpixel nahe der Kaikante, nach hinten kleiner
uniform float glitter = 1.0;
uniform vec4 lamp_gain = vec4(1.0);    // Helligkeit von Laterne, Fenster, Wandlampe, Leuchtfeuer (Flackern)
uniform float star_twinkle = 1.0;
uniform vec3 debug_tint = vec3(1.0);
uniform float debug_flat = 0.0;        // Prüfmodus: alle Punkte in dieser Entfernung (0 = aus)

varying float v_s;
varying vec2 v_px;
varying float v_ok;                    // mittlere Schicht: 1 = Gitterpunkt mit Zwischenfüllung

float dec(vec4 t) {
	return (t.r * 255.0 * 256.0 + t.g * 255.0) / 65535.0;
}

void vertex() {
	vec2 uv = UV;
	if (!front) {
		uv = uv * (1.0 + 2.0 * skirt) - vec2(skirt);
	}
	vec2 g = clamp(uv, 0.0, 1.0) * (grid - 1.0);
	ivec2 gi = ivec2(round(g));
	vec4 vt = texelFetch(vtx_tex, gi, 0);
	float s = max(dec(vt), 1e-5);
	v_ok = vt.b;
	if (debug_flat > 0.0) s = z_min / debug_flat;
	float z = z_min / s * depth_push;
	vec2 px = vec2(0.5) + uv * grid_step * (grid - 1.0);   // stetige Pixelkoordinate (Mitte von Pixel 0 = 0,5)
	VERTEX = vec3((px.x - cx) * z / f, -(px.y - yh) * z / f, -z);
	v_s = s;
	v_px = px;
}

vec3 water_px(vec2 px, float s_here) {
	// Wogen: Zeilen waagerecht verschieben, nahe Zeilen stärker und langsamer
	float r = max(px.y - yh, 1.0);
	float k = clamp(r / 280.0, 0.05, 1.0);
	float ph = time * 1.3 + px.y * 0.21 + sin(px.y * 0.043 + time * 0.7) * 2.0;
	float dx = sin(ph) * wave_amp * k + sin(ph * 0.53 + 1.7) * wave_amp * 0.6 * k;
	vec2 q = px + vec2(dx, 0.0);
	// nur innerhalb des Wassers verschieben (sonst bliebe ein Bootsrand im Wasser hängen)
	vec4 dq = texelFetch(depth_tex, ivec2(clamp(q, vec2(0.0), img - 1.0)), 0);
	if (dq.b < 0.5) q = px;
	vec3 c = textureLod(color_tex, q / img, 0.0).rgb;
	// Glitzern: kurze helle Striche in Zellen, nur wo das Wasser schon hell und warm ist (Abendlicht)
	vec2 cell = floor(vec2(px.x / (6.0 + 10.0 * k), px.y / (2.0 + 2.0 * k)));
	float h = fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453);
	float tw = pow(max(0.0, sin(time * (2.0 + 3.0 * h) + h * 40.0)), 12.0);
	float warm = clamp((c.r - c.b) * 3.0 + (dot(c, vec3(0.33)) - 0.18) * 2.0, 0.0, 1.0);
	c += vec3(1.0, 0.75, 0.45) * tw * warm * 0.55 * glitter * step(0.72, h);
	return c;
}

void fragment() {
	vec2 px = v_px;
	ivec2 pi = ivec2(clamp(floor(px), vec2(0.0), img - 1.0));
	vec4 d = texelFetch(depth_tex, pi, 0);
	if (sparse && (dec(d) <= 0.0 || v_ok < 0.999)) {
		discard;
	}
	if (front && fill_mode == 1) {
		// 1. gestreckte Dreiecke (über einen Tiefensprung gespannt): Disparitätsänderung je Texel zu groß
		float per_texel = fwidth(v_s) / max(max(fwidth(px.x), fwidth(px.y)), 1e-4);
		if (per_texel > stretch_max) {
			discard;
		}
		// 2. Texel gehört nicht zur Tiefe des Dreiecks (Rand der aufgeweiteten Gitterpunkte)
		float st = dec(d);
		if (abs(v_s - st) > tol_rel * st + tol_abs) {
			discard;
		}
	}
	// Abtastung vor jeder Verzweigung (Mipmap-Ableitungen); Wasser tastet mit festem LOD ab
	vec3 c = texture(color_tex, clamp(px, vec2(0.5), img - 0.5) / img).rgb;
	if (d.b > 0.5) {
		c = water_px(px, v_s);
	}
	// Lampen und Sterne (Nummer im Alphakanal der Tiefenkarte, nur vordere Schicht)
	int id = int(round((1.0 - d.a) * 255.0));
	if (id >= 1 && id <= 4) {
		float g = lamp_gain[id - 1];
		float lum = dot(c, vec3(0.333));
		c = c * g + vec3(1.0, 0.7, 0.35) * max(g - 1.0, 0.0) * lum * 0.5;
	} else if (id == 9) {
		vec2 cell = floor(px / 3.0);
		float h = fract(sin(dot(cell, vec2(41.31, 17.77))) * 9631.17);
		float tw = 0.55 + 0.45 * sin(time * (1.7 + 2.9 * h) + h * 31.0);
		float lum = dot(c, vec3(0.333));
		c = mix(c, c * (0.45 + 0.9 * tw), star_twinkle * clamp((lum - 0.2) * 3.0, 0.0, 1.0));
	}
	ALBEDO = c * debug_tint;
}
