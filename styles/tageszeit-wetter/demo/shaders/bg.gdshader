// Hintergrund: ein KI-Gemälde (Tag, neutrales Licht) in jedem Zustand.
// Reihenfolge: Wasser bewegen -> Schnee/Nässe auf das Grundbild -> LUT des Zustands -> Lichtbild (Fenster,
// Laterne, Leuchtfeuer) -> Himmel neu färben -> Nebel nach Tiefe -> Strahl, Lichthöfe, Blitz.
shader_type canvas_item;

#include "res://shaders/common.gdshaderinc"

uniform sampler2D plate_tex : filter_linear, repeat_disable;  // Himmel unter Objekten fortgesetzt
uniform sampler2D data_a : filter_linear, repeat_disable;     // R Himmel, G Wasser, B Tiefe (nah = 1)
uniform sampler2D data_b : filter_linear, repeat_disable;     // Anteil Fenster / Laterne / Leuchtfeuer
uniform sampler2D data_c : filter_linear, repeat_disable;     // R Wolken, G Boote, B Schnee-Alpha
uniform sampler2D snow_tex : filter_linear, repeat_disable;   // Farbe der Schneeschicht
uniform sampler2D light_tex : filter_linear, repeat_disable;  // Lichtbild aus dem Nachtschlüssel
uniform sampler2D noise_tex : filter_linear, repeat_enable;   // 3 kachelbare Rauschkanäle

uniform vec2 size = vec2(1280.0, 720.0);
uniform float horizon_y = 347.5;
// Himmel
uniform float sky_orig = 1.0;          // 1 = gemalter Taghimmel unverändert
uniform vec3 sky_top = vec3(0.3, 0.55, 0.9);
uniform vec3 sky_hor = vec3(0.7, 0.8, 0.95);
uniform vec3 cloud_lit = vec3(1.0);
uniform vec3 cloud_shade = vec3(0.8);
uniform float cloud_vis = 1.0;
uniform float glow = 0.0;              // Abendrot am Horizont
uniform vec3 glow_col = vec3(1.0, 0.55, 0.25);
uniform float stars = 0.0;
uniform float overcast = 0.0;          // geschlossene, ziehende Wolkendecke
uniform vec3 overcast_col = vec3(0.5);
uniform float cloud_drift = 0.0;       // px
// Lichter
uniform vec3 light_mul = vec3(0.0);    // Fenster, Laterne, Leuchtfeuer (mit Flackern)
uniform vec2 window_pos = vec2(162.0, 382.6);
uniform vec2 lantern_pos = vec2(379.4, 293.3);
uniform vec2 lamp_pos = vec2(1119.5, 131.2);
uniform float beam = 0.0;
uniform float beam_phi = 0.0;
uniform float beam_len = 950.0;
// Wetter
uniform float wet = 0.0;
uniform float ripple = 0.0;
uniform float snow_cover = 0.0;
uniform float sparkle = 0.0;
uniform vec3 water_tint = vec3(1.0);   // Wasser je Zustand abdunkeln/umfärben (vor der LUT)

const vec3 WARM = vec3(1.0, 0.72, 0.38);

float noise1(vec2 uv) { return texture(noise_tex, uv).r; }

void fragment() {
	vec2 px = UV * size;
	vec4 da = texture(data_a, UV);
	float sky = da.r;
	float water = da.g;
	float depth = da.b;
	float below = px.y - horizon_y;
	// 0,3 am Horizont .. 1 am Kai (Wellen werden nach vorn größer)
	float persp = mix(0.3, 1.0, clamp(below / 250.0, 0.0, 1.0));

	// ---- Wasser: zeilenweise Verschiebung, nur innerhalb der Wasserfläche ----
	vec2 uvw = UV;
	if (water > 0.02) {
		float row = pow(max(below, 0.0), 0.75);
		float n = texture(noise_tex, vec2(px.x / (620.0 * persp) + time * 0.015, row / 9.0 - time * 0.05)).r - 0.5;
		float m = texture(noise_tex, vec2(px.x / (300.0 * persp) - time * 0.02, row / 5.0 + time * 0.07)).g - 0.5;
		vec2 d = vec2((n * 5.0 + m * 2.0) * persp, m * 1.2 * persp);
		vec2 cand = UV + d / size;
		float ok = smoothstep(0.6, 0.95, texture(data_a, cand).g) * smoothstep(0.6, 0.95, water);
		uvw = mix(UV, cand, ok);
	}
	vec3 base = texture(TEXTURE, uvw).rgb;
	base = mix(base, base * water_tint, water);

	// ---- Schnee: Schicht aus dem Schneeschlüssel, wächst fleckig ----
	vec4 dc = texture(data_c, UV);
	float sn = texture(noise_tex, px / 700.0 + vec2(0.31, 0.17)).g;
	float cov = dc.b * smoothstep(sn - 0.12, sn + 0.12, snow_cover * 1.35 - 0.17);
	base = mix(base, texture(snow_tex, UV).rgb, cov);

	// ---- Nässe auf dem Boden (Regen) ----
	float ground = (1.0 - sky) * (1.0 - water) * smoothstep(horizon_y + 60.0, horizon_y + 200.0, px.y);
	float gw = wet * ground * (1.0 - cov);
	base = mix(base, base * base * 1.15, gw * 0.6);

	// ---- Farbkorrektur des Zustands ----
	vec3 c = grade(base);

	// ---- Lichtbild: (Nachtschlüssel - Nacht-LUT), je Quelle skaliert ----
	vec3 lt = texture(light_tex, uvw).rgb;
	vec3 fr = texture(data_b, UV).rgb;
	float li = dot(fr, light_mul);
	c += lt * li * (1.0 + 0.5 * gw) * mix(1.0, 1.5, cov);

	// Spiegelung der Laterne auf nassem Kai: senkrechter, unruhiger Streifen unter dem Pfosten
	if (gw > 0.0) {
		float dx = (px.x - lantern_pos.x) / 16.0;
		float yy = (px.y - 560.0) / 150.0;
		float st = texture(noise_tex, vec2(px.x / 9.0, px.y / 70.0 - time * 0.4)).r;
		float refl = exp(-dx * dx) * smoothstep(0.0, 0.25, yy) * exp(-max(yy, 0.0)) * (0.35 + 1.1 * st);
		c += WARM * refl * gw * light_mul.y * 0.55;
	}

	// ---- Wasser: Glitzern am Tag, Abendrot gespiegelt, Regenringe ----
	if (water > 0.02) {
		float row = max(below, 0.0);
		float s1 = texture(noise_tex, vec2(px.x / (24.0 * persp) + time * 0.04, row / (6.0 * persp))).b;
		float s2 = texture(noise_tex, vec2(px.x / (15.0 * persp) - time * 0.06, row / (4.0 * persp) + 0.37)).g;
		float sp = smoothstep(0.80, 0.86, s1) * smoothstep(0.70, 0.80, s2) * sparkle * smoothstep(0.4, 0.8, persp);
		c += vec3(1.0, 0.98, 0.92) * sp * 0.55 * water;
		float wn = texture(noise_tex, vec2(px.x / 140.0, row / 6.0 - time * 0.06)).r;
		c += glow_col * glow * exp(-row / 55.0) * (0.25 + 0.9 * wn) * 0.55 * water;
		if (ripple > 0.0) {
			vec2 wq = vec2(px.x, row * 3.2) / (30.0 * persp);
			vec2 cell = floor(wq);
			vec2 f = fract(wq) - 0.5;
			float h = hash12(cell + 7.0);
			float ph = fract(time * 1.7 + h);
			vec2 o = (vec2(hash12(cell + 1.3), hash12(cell + 2.7)) - 0.5) * 0.35;
			float r = length(f - o);
			float ring = smoothstep(0.06, 0.0, abs(r - ph * 0.42)) * (1.0 - ph) * step(0.3, h);
			c += vec3(0.75, 0.82, 0.9) * ring * ripple * 0.16 * water;
		}
	}

	// ---- Himmel ----
	if (sky > 0.003) {
		vec2 suv = vec2(UV.x + cloud_drift / size.x, UV.y);
		suv.x = 1.0 - abs(1.0 - abs(suv.x));   // am Bildrand spiegeln statt die Randspalte zu strecken
		vec3 pl = texture(plate_tex, suv).rgb;
		float cl = texture(data_c, suv).r;
		float t = clamp(px.y / horizon_y, 0.0, 1.0);
		vec3 gr = mix(sky_top, sky_hor, pow(t, 1.5));
		float band = exp(-max(horizon_y - px.y, 0.0) / 70.0);
		gr += glow_col * glow * band;
		float sh = clamp((dot(pl, vec3(0.3333)) - 0.68) / 0.26, 0.0, 1.0);
		vec3 cc = mix(cloud_shade, cloud_lit, sh) + glow_col * glow * band * 0.5;
		vec3 skyc = mix(gr, cc, cl * cloud_vis);
		skyc = mix(skyc, pl, sky_orig);
		// Sterne: ein Pixel je 4×4-Zelle mit geringer Wahrscheinlichkeit, langsam funkelnd
		vec2 ip = floor(px);
		vec2 cell = floor(ip / 4.0);
		float h = hash12(cell);
		vec2 off = floor(vec2(hash12(cell + 3.1), hash12(cell + 5.7)) * 4.0);
		float isstar = step(0.986, h) * step(length(ip - cell * 4.0 - off), 0.5);
		float tw = 0.65 + 0.35 * sin(time * (2.0 + 3.0 * hash12(cell + 9.2)) + h * 40.0);
		float sb = isstar * (0.35 + 0.65 * fract(h * 71.0)) * tw;
		skyc += vec3(0.9, 0.94, 1.0) * sb * stars * (1.0 - cl * cloud_vis) * smoothstep(1.0, 0.55, t);
		// Wolkendecke (Regen, Nebel, Schnee): zwei Rauschlagen, die ziehen
		float o1 = texture(noise_tex, vec2(px.x / 900.0 + time * 0.030, px.y / 300.0)).g;
		float o2 = texture(noise_tex, vec2(px.x / 380.0 + time * 0.055, px.y / 130.0 + 0.5)).r;
		vec3 oc = overcast_col * (0.72 + 0.5 * o1 + 0.18 * o2) * mix(1.0, 1.12, t);
		skyc = mix(skyc, oc, overcast);
		c = mix(c, skyc, sky);
	}

	// ---- Nebel nach Tiefe, mit ziehenden Bänken ----
	if (fog > 0.0) {
		float fn = texture(noise_tex, vec2(px.x / 600.0 + time * 0.07, px.y / 170.0 + time * 0.012)).g;
		float fn2 = texture(noise_tex, vec2(px.x / 260.0 - time * 0.11, px.y / 70.0)).r;
		float ff = fog_amount(1.0 - depth, 0.45 + 0.9 * fn + 0.35 * fn2);
		// Schwaden: ziehende helle Bänder auch vorn (sonst wirkt der Nebel wie ein Standbild)
		float wisp = smoothstep(0.45, 0.85, fn * 0.7 + fn2 * 0.5) * fog * 0.4 * smoothstep(0.6, 1.0, fog_front);
		ff = ff + wisp * (1.0 - ff);
		c = mix(c, fog_col, clamp(ff, 0.0, 1.0));
	}

	// ---- Leuchtturmstrahl: dreht sich, auf dem Bild verkürzt; sichtbar vor Himmel und im Nebel ----
	if (beam > 0.0) {
		float cp = cos(beam_phi);
		float dirx = cp < 0.0 ? -1.0 : 1.0;
		vec2 v = px - lamp_pos;
		float along = v.x * dirx;
		float lp = beam_len * abs(cp);
		// im Nebel breiter, weicher und kürzer (Streuung), sonst schmal und klar
		float w = (3.0 + along * 0.085) * (1.0 + 0.9 * fog);
		float perp = abs(v.y - along * 0.02);
		float bn = texture(noise_tex, vec2(along / 260.0 - time * 0.08, perp / 30.0)).g;
		float bi = smoothstep(w, w * mix(0.25, 0.0, fog), perp) * step(0.0, along)
			* (1.0 - smoothstep(lp * 0.15, lp * (1.0 - 0.35 * fog), along));
		bi *= (0.65 + 0.5 * bn) * (0.6 + 0.4 * abs(cp));
		float vis = max(sky, fog * 0.9);
		c += vec3(1.0, 0.92, 0.7) * bi * beam * vis * (0.55 - 0.2 * fog);
		// Aufblitzen, wenn der Strahl zur Kamera zeigt
		float face = pow(max(sin(beam_phi), 0.0), 8.0);
		c += vec3(1.0, 0.9, 0.65) * face * beam * exp(-length(v) / (7.0 + 9.0 * fog)) * 1.0;
	}

	// ---- Lichthöfe (im Nebel größer) ----
	float hw = exp(-length((px - window_pos) * vec2(0.8, 1.0)) / (18.0 + 45.0 * fog));
	float hl = exp(-length(px - lantern_pos) / (13.0 + 45.0 * fog));
	float hm = exp(-length(px - lamp_pos) / (7.0 + 13.0 * fog));
	c += WARM * (hw * light_mul.x * 0.22 + hl * light_mul.y * 0.42 + hm * light_mul.z * 0.45) * (1.0 + 1.2 * fog);

	// ---- Blitz: kaltes, entsättigtes Licht auf dem Grundbild; der Himmel wird zur von innen
	// aufgehellten Wolkendecke (nicht zum gemalten blauen Taghimmel des Grundbilds) ----
	if (flash > 0.0) {
		float bl = dot(base, vec3(0.299, 0.587, 0.114));
		vec3 fb = mix(vec3(bl), base, 0.35) * vec3(0.86, 0.93, 1.10) * 1.1;
		float fq = texture(noise_tex, vec2(px.x / 500.0 + time * 0.03, px.y / 160.0)).g;
		vec3 fs = vec3(0.56, 0.60, 0.72) * (0.5 + 0.9 * fq);
		c = mix(c, mix(fb, fs, sky), flash * 0.6);
	}
	COLOR = vec4(c, 1.0);
}
