// Eine Schicht eines Sprite-Stacks: Datenblatt (Material, Verdeckung, Muster, Eigenschatten) + Normalenblatt
// -> Tonstufe aus Licht in Weltkoordinaten -> Farbe aus der Farbleiter des Materials (ramps.png).
// Die Normale liegt im Modellraum und wird mit der Drehung der Schicht (MODEL_MATRIX) und der Kamera gedreht;
// so bleibt das Licht beim Drehen der Kamera an der Welt fest.
shader_type canvas_item;
render_mode unshaded;

uniform sampler2D normal_tex : filter_nearest, repeat_disable;
uniform sampler2D ramp_tex : filter_nearest, repeat_disable;
uniform int glow_start = 32;
uniform float dither = 0.0;               // Stärke der geordneten Rasterung zwischen zwei Tonstufen (je Modell)
uniform float portrait = 0.0;             // 1 = Ansichtsfenster der Oberfläche: nur Sonne, keine Weltlage

// Höhe der Schicht kommt über self_modulate.r (= Höhe / 255), Schicht im Modell über self_modulate.g.
// Keine "instance uniform": Godot reserviert je Instanz 16 Plätze, bei 1000 Schichten zu viel (Compatibility: 4096).

global uniform vec2 cam_cs;               // cos/sin der Kameradrehung
global uniform vec2 cam_pivot;            // Weltpunkt in der Bildmitte
global uniform vec2 cam_center;           // Bildmitte
global uniform vec3 sun_dir;              // zur Sonne, Welt (x Osten, y Süden, z oben)
global uniform vec4 light_lantern;        // xyz Welt (z in px), w Stärke
global uniform vec4 light_window;
global uniform vec4 light_lamp;
global uniform vec3 glow_levels;          // Fenster, Laterne, Leuchtfeuer (0..1)
global uniform float flat_light;          // Vergleich: 1 = ohne Normalenlicht (feste Stufe je Material)
global uniform float mask_mode;           // Messbild: R = Höhe, G = Schicht im Modell (aus self_modulate.r)

const float LAYER_H = 0.75;

varying vec2 v_canvas;
varying vec2 v_rot;
varying float v_local;
varying float v_layer;

vec2 rot(vec2 v, vec2 cs) { return vec2(cs.x * v.x - cs.y * v.y, cs.y * v.x + cs.x * v.y); }

float bayer4(ivec2 p) {
	int x = p.x & 3, y = p.y & 3;
	int m[16] = int[](0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5);
	return (float(m[y * 4 + x]) + 0.5) / 16.0;
}

// Punktlicht mit Lichtkreis am Boden: Höhenabstand zählt nur zu 35 % (sonst bliebe unter der hoch hängenden
// Laterne kaum Licht), Abfall weich, Halbschatten über "wrap" statt harter Kante.
float point_light(vec4 L, vec3 wp, vec3 n, float radius) {
	vec3 d = L.xyz - wp;
	float dist = length(vec3(d.xy, d.z * 0.35));
	float a = clamp(1.0 - dist / radius, 0.0, 1.0);
	float wrap = max(dot(n, normalize(d)), 0.0) * 0.7 + 0.3;
	return L.w * pow(a, 1.6) * wrap;
}

void vertex() {
	v_canvas = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
	v_rot = normalize(MODEL_MATRIX[0].xy);
	v_layer = round(COLOR.r * 255.0);
	v_local = COLOR.g;
}

void fragment() {
	vec4 d = texture(TEXTURE, UV);
	float layer_z = v_layer;
	if (d.a < 0.5) {
		discard;
	}
	if (mask_mode > 0.5) {
		COLOR = vec4(layer_z / 255.0, v_local, 0.0, 1.0);
	} else {
	int m = int(round(d.r * 255.0));
	int bits = int(round(d.b * 255.0));
	float var = float(bits & 15) - 8.0;
	bool shadowed = (bits & 16) != 0;
	ivec2 texel = ivec2(floor(UV * vec2(textureSize(TEXTURE, 0))));
	if (m >= glow_start) {
		float lvl = glow_levels[clamp(m - glow_start, 0, 2)];
		int gi = clamp(int(floor(lvl * 7.0 + var * 0.5 + 0.5)), 0, 7);
		COLOR = texelFetch(ramp_tex, ivec2(gi, m), 0);
	} else {
		vec3 n = texture(normal_tex, UV).xyz * 2.0 - 1.0;
		vec2 ns = rot(n.xy, v_rot);                          // Bildraum
		vec3 nw;
		vec3 wp;
		if (portrait > 0.5) {
			nw = vec3(ns, n.z);
			wp = vec3(0.0);
		} else {
			vec2 inv = vec2(cam_cs.x, -cam_cs.y);
			nw = vec3(rot(ns, inv), n.z);                     // Welt
			vec2 ground = v_canvas + vec2(0.0, layer_z);
			wp = vec3(cam_pivot + rot(ground - cam_center, inv), layer_z * LAYER_H);
		}
		nw = normalize(nw);
		float ao = d.g;
		float sky = mix(0.25, 0.40, clamp(nw.z * 0.5 + 0.5, 0.0, 1.0)) * mix(0.5, 1.0, ao);
		float sun = max(dot(nw, sun_dir), 0.0) * (shadowed ? 0.0 : 0.82);
		float pts = 0.0;
		if (portrait < 0.5) {
			pts += point_light(light_lantern, wp, nw, 54.0);
			pts += point_light(light_window, wp, nw, 38.0);
			pts += point_light(light_lamp, wp, nw, 30.0);
		}
		float b = sky + sun + pts;
		float s = b * 5.0 + var * 0.85;
		if (dither > 0.0) {
			s += (bayer4(texel) - 0.5) * dither;
		}
		if (flat_light > 0.5) {
			s = 3.5 + var * 0.85;
		}
		int idx = clamp(int(floor(s + 0.5)), 0, 7);
		COLOR = texelFetch(ramp_tex, ivec2(idx, m), 0);
	}
}
}
