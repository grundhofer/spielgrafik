// 1-Bit-Nachbearbeitung (eingebunden von onebit_post.gdshader für Forward+ mit USE_NR und von
// onebit_post_depth.gdshader für Mobile/Compatibility ohne).
//
// Ein bildschirmfüllendes Rechteck vor der Kamera liest Farbe und Tiefe der deckenden Geometrie und schreibt je
// Pixel 0 (Tinte) oder 1 (Papier). Die Oberflächen schreiben ihre Helligkeit in den Rotkanal und die Material-ID
// in den Blaukanal (onebit_surface.gdshader); so stehen die IDs in jedem Renderer zur Verfügung.
//  1. Helligkeit L: Rotkanal des Bildpuffers, Himmel aus sky.gdshaderinc, dazu Dunst, Lichtkegel des
//     Leuchtturms, Lichthöfe der Lampen und Rauch, alle analytisch entlang des Sehstrahls.
//  2. Tonkurve p = (L · exposure)^gamma, dazu S-Kurve (contrast).
//  3. Schwelle aus einem Muster: Oberflächen 8×8-Bayer, Luft (Himmel, Rauch) Blue Noise 64×64.
//     Die Musterkoordinaten hängen an der Blickrichtung (dither_mode 1): Der Sehstrahl wird in die Bildebene
//     einer festen Referenzkamera projiziert; steht die Kamera in der Referenzlage, ist das genau das
//     Pixelraster, dreht sie sich, läuft das Muster mit der Welt mit (kein Duschtür-Effekt beim Schwenken).
//     dither_mode 0 = Muster fest im Bildschirm (Vergleich).
//  4. Linien 1 px breit in der Gegenfarbe des Untergrunds (auf hellen Flächen Tinte, im Schatten Papier):
//     Silhouetten aus der Tiefe, Knicke aus den Normalen (Forward+: Normalenpuffer, sonst aus der Tiefe
//     rekonstruiert), Materialwechsel aus der ID. Leuchtendes Glas bleibt frei.
//  5. Figur (ID 10–14): in der Ferne ohne Raster, mit Tintenkontur und Papierrand (siehe figure_outline).

#include "res://shaders/sky.gdshaderinc"

global uniform float onebit_time;

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest, repeat_disable;
uniform sampler2D screen_tex : hint_screen_texture, filter_nearest, repeat_disable;
uniform sampler2D blue_noise : filter_nearest, repeat_enable;
#ifdef USE_NR
uniform sampler2D nr_tex : hint_normal_roughness_texture, filter_nearest, repeat_disable;
#endif

// --- Muster ---------------------------------------------------------------------------------------
uniform int dither_mode = 1;            // 0 Bildschirm, 1 Blickrichtung (Referenzkamera)
uniform mat3 ref_inv = mat3(1.0);       // Welt -> Referenzkamera (Basis invertiert)
uniform float ref_focal = 468.97;       // Brennweite der Referenzkamera in Pixeln (Bildhöhe/2 / tan(fov/2))
uniform int pattern_mode = 0;           // 0 Bayer + Blue Noise, 1 nur Bayer, 2 nur Blue Noise, 3 Schwelle 0,5, 4 Grau
uniform float exposure = 2.2;
uniform float gamma = 0.9;
uniform float contrast = 1.0;           // Anteil einer S-Kurve (smoothstep) auf p

// --- Linien ---------------------------------------------------------------------------------------
uniform float lines = 1.0;
uniform float depth_threshold = 0.035;  // relativer Fehler der 1/z-Vorhersage
uniform float normal_threshold = 0.25;  // 1 - N·N
uniform float crease_fade_begin = 18.0; // m: Knick- und Materiallinien blenden aus
uniform float crease_fade_end = 32.0;
uniform float line_fade_end = 700.0;    // m: Silhouetten
uniform float id_lines = 1.0;
uniform float id_fade_end = 60.0;
// Figur (Material-ID 10–14): innen Linien nur in der Nähe. In der Ferne (Totale, Figur ≈ 36 px hoch) ohne
// Rastermuster (Schwelle 0,5, also flache Papier- und Tintenflächen) mit Tintenkontur und Papierrand außen, wie
// die Maske eines 1-Bit-Symbols: Ein gerastertes Mittelgrau löst sich vor unruhigem Grund sonst auf.
uniform float figure_outline = 1.0;
uniform float figure_detail_end = 7.0;  // m

// --- Luft -----------------------------------------------------------------------------------------
uniform float haze_begin = 60.0;
uniform float haze_end = 420.0;
uniform float haze_max = 0.5;
uniform vec3 beam_origin = vec3(10.2, 12.58, -25.6);
uniform vec3 beam_dir = vec3(1.0, 0.0, 0.0);
uniform float beam_len = 42.0;
uniform float beam_r0 = 0.3;
uniform float beam_spread = 0.075;      // Radius wächst je Meter
uniform float beam_power = 0.55;
uniform vec4 halo[3];                   // xyz Lampe, w Radius (m)
uniform float halo_power[3];
uniform vec4 puffs[8];                  // xyz Mitte, w Radius (m); w = 0: aus
uniform float puff_alpha[8];
uniform float smoke_lum = 0.16;
uniform float stars = 1.0;

const int BAYER[64] = int[](
	0, 32, 8, 40, 2, 34, 10, 42,
	48, 16, 56, 24, 50, 18, 58, 26,
	12, 44, 4, 36, 14, 46, 6, 38,
	60, 28, 52, 20, 62, 30, 54, 22,
	3, 35, 11, 43, 1, 33, 9, 41,
	51, 19, 59, 27, 49, 17, 57, 25,
	15, 47, 7, 39, 13, 45, 5, 37,
	63, 31, 55, 23, 61, 29, 53, 21);

float depth_at(vec2 uv) {
	return texture(depth_tex, uv).r;
}

vec3 view_pos(vec2 uv, float d, mat4 inv_proj) {
	vec4 v = inv_proj * vec4(uv * 2.0 - 1.0, d, 1.0);
	return v.xyz / v.w;
}

vec3 screen_lin(vec2 uv) {
	return texture(screen_tex, uv).rgb;   // Forward+ und Mobile: linear, vor dem Tonemapping
}

// Material-ID aus dem Blaukanal: (ID + 0,5) / 16 als Eigenleuchten (onebit_surface.gdshader)
int id_at(vec2 uv) {
	return int(floor(screen_lin(uv).b * 16.0));
}

bool is_figure(int id) {
	return id >= 10 && id <= 14;
}

#ifdef USE_NR
vec3 normal_at(vec2 uv, vec2 px, mat4 inv_proj) {
	return normalize(texture(nr_tex, uv).xyz * 2.0 - 1.0);
}
#else
// Normale aus der Tiefe: Nachbarn auf der Seite mit dem kleineren Tiefensprung nehmen (sonst Fehllinien an
// Silhouetten); ergibt Flächennormalen (ohne Glättung der Modelle).
vec3 normal_at(vec2 uv, vec2 px, mat4 inv_proj) {
	vec3 c = view_pos(uv, depth_at(uv), inv_proj);
	vec3 r = view_pos(uv + vec2(px.x, 0.0), depth_at(uv + vec2(px.x, 0.0)), inv_proj);
	vec3 l = view_pos(uv - vec2(px.x, 0.0), depth_at(uv - vec2(px.x, 0.0)), inv_proj);
	vec3 d = view_pos(uv + vec2(0.0, px.y), depth_at(uv + vec2(0.0, px.y)), inv_proj);
	vec3 u = view_pos(uv - vec2(0.0, px.y), depth_at(uv - vec2(0.0, px.y)), inv_proj);
	vec3 dx = abs(r.z - c.z) < abs(c.z - l.z) ? r - c : c - l;
	vec3 dy = abs(d.z - c.z) < abs(c.z - u.z) ? d - c : c - u;
	return normalize(cross(dx, dy));
}
#endif

// Tiefensprung in Richtung off: Mitte vorn, Nachbar hinten, Vorhersage aus der Gegenseite
// (1/z ist auf Ebenen im Bildraum linear; so entstehen auf flach gesehenem Boden keine Fehllinien).
float depth_edge(vec2 uv, vec2 off, float izc, mat4 inv_proj) {
	float zn = -view_pos(uv + off, depth_at(uv + off), inv_proj).z;
	float zo = -view_pos(uv - off, depth_at(uv - off), inv_proj).z;
	float err = abs(1.0 / zn - (2.0 * izc - 1.0 / zo)) / izc;
	float behind = step(1.0 / izc * 1.002, zn);
	return step(depth_threshold, err) * behind;
}

// Schwellwert 0..1 aus dem Muster an der Zelle cell
float threshold_at(ivec2 cell, bool air) {
	if (pattern_mode == 3) {
		return 0.5;
	}
	bool bn = (pattern_mode == 2) || (pattern_mode == 0 && air);
	if (bn) {
		return (texelFetch(blue_noise, cell & ivec2(63), 0).r * 255.0 + 0.5) / 256.0;
	}
	ivec2 c = cell & ivec2(7);
	return (float(BAYER[c.y * 8 + c.x]) + 0.5) / 64.0;
}

// Zelle des Musters für diesen Sehstrahl
ivec2 dither_cell(vec3 dir_world, vec2 fragcoord, vec2 viewport) {
	if (dither_mode == 0) {
		return ivec2(floor(fragcoord));
	}
	vec3 r = ref_inv * dir_world;
	vec2 q = vec2(r.x, -r.y) / max(-r.z, 1e-4) * ref_focal + viewport * 0.5;
	return ivec2(floor(q));
}

// Lichtkegel des Leuchtturms: Abstand des Sehstrahls zur Kegelachse, weich nach außen und zum Ende hin
float beam_light(vec3 o, vec3 v, float scene_dist) {
	vec3 a = beam_dir;
	vec3 w0 = o - beam_origin;
	float b = dot(v, a);
	float dv = dot(v, w0);
	float da = dot(a, w0);
	float den = max(1.0 - b * b, 1e-5);
	float s = (b * da - dv) / den;
	float u = da + s * b;
	u = clamp(u, 0.0, beam_len);
	s = max(dot(beam_origin + u * a - o, v), 0.0);
	if (s > scene_dist) {
		return 0.0;
	}
	float dist = length(o + s * v - (beam_origin + u * a));
	float r = beam_r0 + u * beam_spread;
	float k = exp(-(dist * dist) / (r * r) * 1.6);
	float fall = pow(clamp(1.0 - u / beam_len, 0.0, 1.0), 1.4);
	float glare = pow(max(dot(-v, a), 0.0), 6.0);
	return beam_power * k * fall * (1.0 + 2.5 * glare);
}

float halo_light(vec3 o, vec3 v, float scene_dist) {
	float sum = 0.0;
	for (int i = 0; i < 3; i++) {
		vec3 p = halo[i].xyz;
		float R = halo[i].w;
		float s = dot(p - o, v);
		if (s <= 0.0 || s > scene_dist + 0.6 || R <= 0.0) {
			continue;
		}
		vec3 c = o + s * v - p;
		sum += halo_power[i] * exp(-dot(c, c) / (R * R));
	}
	return sum;
}

float smoke_density(vec3 o, vec3 v, float scene_dist) {
	float den = 0.0;
	for (int i = 0; i < 8; i++) {
		float R = puffs[i].w;
		if (R <= 0.0) {
			continue;
		}
		vec3 c = puffs[i].xyz;
		float s = dot(c - o, v);
		if (s - R > scene_dist) {
			continue;
		}
		vec3 q = o + s * v - c;
		float d2 = dot(q, q) / (R * R);
		if (d2 >= 1.0) {
			continue;
		}
		// Ränder ausfransen: Rauschen über die Lage im Bällchen
		float n = sky_noise(q.xy / R * 2.2 + vec2(float(i) * 3.7, onebit_time * 0.4));
		den += puff_alpha[i] * sqrt(1.0 - d2) * (0.55 + 0.9 * n);
	}
	return clamp(den, 0.0, 1.0);
}

// Gemeinsamer Ablauf. nr_ok: Normalen-/ID-Linien verfügbar (Forward+).
void onebit(vec2 uv, vec2 fragcoord, vec2 viewport, mat4 inv_proj, mat4 inv_view, vec3 cam,
		out float bit, out float tone, out float sky_px, out vec3 wc, out float zc, out float line_sil) {
	float d = depth_at(uv);
	sky_px = step(d, 0.0000001);
	vec3 vp = view_pos(uv, d, inv_proj);
	zc = -vp.z;
	vec3 dir_v = normalize(view_pos(uv, 1.0, inv_proj));
	vec3 dir = normalize(mat3(inv_view) * dir_v);
	wc = (inv_view * vec4(vp, 1.0)).xyz;
	float dist = sky_px > 0.5 ? 1e9 : length(vp);

	float L;
	if (sky_px > 0.5) {
		L = sky_luminance(dir, onebit_time);
	} else {
		L = screen_lin(uv).r;
		float hz = smoothstep(haze_begin, haze_end, dist) * haze_max;
		L = mix(L, sky_luminance(normalize(vec3(dir.x, 0.0, dir.z)), onebit_time), hz);
	}
	L += beam_light(cam, dir, dist);
	L += halo_light(cam, dir, dist);
	float den = smoke_density(cam, dir, dist);
	L = mix(L, smoke_lum, den * 0.9);
	bool air = sky_px > 0.5 || den > 0.3;

	tone = pow(clamp(L * exposure, 0.0, 1.0), gamma);
	tone = mix(tone, tone * tone * (3.0 - 2.0 * tone), contrast);
	ivec2 cell = dither_cell(dir, fragcoord, viewport);
	bit = step(threshold_at(cell, air), tone);

	// Sterne: einzelne Papierpixel an festen Stellen der Himmelskugel, wenige funkeln
	if (sky_px > 0.5 && stars > 0.5 && dir.y > 0.075 && tone < 0.4 && pattern_mode != 4) {
		float h = sky_hash(vec2(cell) * 0.7317 + vec2(13.1, 7.7));
		float tw = step(0.0, sin(onebit_time * 2.7 + h * 977.0));
		if (h > 0.9965 && (h < 0.9992 || tw > 0.5)) {
			bit = 1.0;
		}
	}

	// Silhouetten aus der Tiefe (alle Renderer)
	line_sil = 0.0;
	if (sky_px < 0.5 && lines > 0.5) {
		vec2 px = 1.0 / viewport;
		float izc = 1.0 / zc;
		float e = 0.0;
		e = max(e, depth_edge(uv, vec2(px.x, 0.0), izc, inv_proj));
		e = max(e, depth_edge(uv, vec2(-px.x, 0.0), izc, inv_proj));
		e = max(e, depth_edge(uv, vec2(0.0, px.y), izc, inv_proj));
		e = max(e, depth_edge(uv, vec2(0.0, -px.y), izc, inv_proj));
		line_sil = e * step(zc, line_fade_end);
	}
}


void vertex() {
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}

void fragment() {
	float bit;
	float tone;
	float sky_px;
	vec3 wc;
	float zc;
	float e;
	onebit(SCREEN_UV, FRAGCOORD.xy, VIEWPORT_SIZE, INV_PROJECTION_MATRIX, INV_VIEW_MATRIX, CAMERA_POSITION_WORLD,
		bit, tone, sky_px, wc, zc, e);
	vec2 px = 1.0 / VIEWPORT_SIZE;
	int ic = sky_px < 0.5 ? id_at(SCREEN_UV) : -1;
	bool fig = is_figure(ic);
	bool fig_far = fig && zc > figure_detail_end;
	if (ic == 9) {
		e = 0.0;   // leuchtendes Glas (Fenster, Laterne, Leuchtfeuer) bleibt frei, sonst füllen Linien die kleinen Scheiben
	}
	if (fig_far && figure_outline > 0.5) {
		e = 0.0;   // keine inneren Silhouetten der Figur in der Ferne
		bit = step(0.5, tone);
	}
	// Knick- und Materiallinien: nur zur rechten und unteren Seite prüfen (sonst doppelt breit); Nachbarn,
	// die deutlich weiter hinten liegen, gehören zur Silhouette. Auf dem Wasser (ID 15) keine Knicklinien.
	if (sky_px < 0.5 && lines > 0.5 && zc < id_fade_end && !fig_far && ic != 9) {
		vec3 nc = normal_at(SCREEN_UV, px, INV_PROJECTION_MATRIX);
		vec2 offs[2] = {vec2(px.x, 0.0), vec2(0.0, px.y)};
		for (int k = 0; k < 2; k++) {
			vec2 uv = SCREEN_UV + offs[k];
			float dn = depth_at(uv);
			if (dn <= 0.0000001) {
				continue;
			}
			float zn = -view_pos(uv, dn, INV_PROJECTION_MATRIX).z;
			if (abs(zn - zc) > 0.08 * zc) {
				continue;
			}
			int in_id = id_at(uv);
			if (zc < crease_fade_end && ic != 15 && in_id != 15) {
				e = max(e, step(normal_threshold, 1.0 - dot(nc, normal_at(uv, px, INV_PROJECTION_MATRIX))));
			}
			if (id_lines > 0.5 && in_id != ic) {
				e = 1.0;
			}
		}
	}
	// Figurenrand in der Ferne: innen Tinte, außen Papier
	int edge = 0;   // 1 innen (Figur am Rand), 2 außen (Grund neben der Figur, die davor steht)
	if (figure_outline > 0.5 && lines > 0.5) {
		vec2 offs4[4] = {vec2(px.x, 0.0), vec2(-px.x, 0.0), vec2(0.0, px.y), vec2(0.0, -px.y)};
		for (int k = 0; k < 4; k++) {
			vec2 uv = SCREEN_UV + offs4[k];
			float dn = depth_at(uv);
			bool fn = dn > 0.0000001 && is_figure(id_at(uv));
			if (fig_far && !fn) {
				edge = 1;
			}
			if (!fig && fn) {
				float zn = -view_pos(uv, dn, INV_PROJECTION_MATRIX).z;
				if (zn > figure_detail_end && (sky_px > 0.5 || zn < zc)) {
					edge = max(edge, 2);
				}
			}
		}
	}
	if (pattern_mode == 4) {
		ALBEDO = vec3(pow(tone, 2.2));   // Ausgabe wird nach sRGB gewandelt: so zeigt die Vorschau p selbst
	} else if (pattern_mode == 5) {
		ALBEDO = vec3(float(max(ic, 0)) / 15.0);   // Prüfung: Material-ID (linear, Ausgabe in sRGB)
	} else {
		if (e > 0.5) {
			bit = tone > 0.5 ? 0.0 : 1.0;
		}
		if (edge == 1) {
			bit = 0.0;
		} else if (edge == 2) {
			bit = 1.0;
		}
		ALBEDO = vec3(bit);
	}
}
