shader_type canvas_item;
// Ortsserie, Stil painterly-digital: lebendes Standbild (Kinemagramm) eines Orts von Lornholm.
// Ein gemaltes KI-Bild, belebt nur durch Masken und diesen Shader (ein Durchgang):
// Himmel pendelt, Wasser wellt sich und glitzert, Sterne funkeln, Lichter flackern (Maske x Faktor),
// Lichtschein wandert über die Wände (Linse) oder flackert (Kamin), Flammen über Glut und Kerze,
// Gras wiegt sich im Wind, Leuchtturmstrahl vor dem Himmel, Möwen, Nebelbänder treiben, Lichtteilchen
// schweben, weiche Lichthöfe und eine leichte Vignette (Glühen und Dunst wie im Stil painterly-digital).
// Alle Zeiten kommen als Uniform aus ort.gd (aus dem Bildzähler), Zufall nur über den Hash ohne sin.

uniform sampler2D plate : filter_linear, repeat_disable;
uniform sampler2D mask_a : filter_linear, repeat_disable;   // R Wasser, G Himmel, B Sterne
uniform sampler2D mask_b : filter_linear, repeat_disable;   // R fire (Linse/Glut), G small (Kerze/Fenster), B lamp
uniform sampler2D mask_c : filter_linear, repeat_disable;   // R Gras, G Lichtempfänger, B Strahl sichtbar
uniform sampler2D noise_tex : filter_linear, repeat_enable; // drei kachelbare Rauschkanäle

uniform float t = 0.0;
uniform vec2 size = vec2(1280.0, 720.0);
uniform float horizon_y = 270.0;
uniform float water_bottom = 600.0;

// Himmel (reine Verschiebung, pendelt) und Wasser
uniform float sky_amp = 10.0;
uniform float sky_period = 70.0;
uniform float water_amp = 2.0;
uniform float water_speed = 0.06;
uniform float sparkle_k = 0.45;
uniform float glint_lo = 0.30;           // Glitzern erst ab dieser Helligkeit des Wassers
// Lichter: Flackern je Kanal (fire, small, lamp) und Lichtschein auf den Empfängerflächen
uniform vec3 flick = vec3(1.0);
uniform float receiver_k = 0.0;          // Stärke, mit der die Empfängerflächen dem fire-Flackern folgen
// Linse (Leuchtturm): heller senkrechter Streifen wandert über die Linse, Lichtfleck wandert über die Wände
uniform vec4 lens_rect = vec4(-1.0);     // x0, y0, x1, y1
uniform float lens_phase = 0.0;          // 0..1 je Umdrehung
uniform float lens_k = 0.0;
uniform float sweep_x = -9999.0;         // Mitte des Lichtflecks auf der Wand (px)
uniform float sweep_w = 160.0;
uniform float sweep_k = 0.0;
uniform vec3 sweep_col = vec3(1.0, 0.78, 0.48);
// Flammen (Kamin, Kerze): x, Basis-y, Breite, Höhe; k = Stärke
uniform vec4 flame[2];
uniform float flame_k[2];
// Leuchtturmstrahl
uniform vec2 lamp_pos = vec2(-9999.0);
uniform float beam_phi = 0.0;
uniform float beam_len = 0.0;
uniform float beam_k = 0.0;
uniform vec3 beam_col = vec3(1.0, 0.86, 0.62);
// Gras
uniform float grass_amp = 0.0;
// Möwen
uniform vec2 gull_pos[2];
uniform float gull_size[2];
uniform vec3 gull_col = vec3(0.10, 0.13, 0.16);
// Nebelbänder: (y, halbe Höhe, Dichte, Tempo px/s) und (Bereich, Maßstab px, Aufhellung, -)
// Bereich: 0 überall, 1 Himmel+Wasser, 2 nur Wasser, 3 Raum (nicht Himmel/Wasser)
uniform vec4 fog_band[4];
uniform vec4 fog_mode[4];
uniform vec3 fog_col = vec3(0.42, 0.52, 0.56);
// Lichtteilchen: Rechteck, Anzahl, Farbe
uniform vec4 mote_rect = vec4(0.0);
uniform int mote_n = 0;
uniform vec3 mote_col = vec3(1.0, 0.82, 0.55);
uniform float mote_k = 0.0;
uniform vec2 mote_light = vec2(-9999.0);  // Teilchen nahe dieser Stelle leuchten stärker
// Lichthöfe (additiv)
uniform vec2 glow_pos[6];
uniform vec4 glow_col[6];
uniform float glow_r[6];
uniform float vignette = 0.22;

float nz(vec2 p, int c) {
	vec4 n = texture(noise_tex, p);
	return c == 0 ? n.r : (c == 1 ? n.g : n.b);
}

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash1(float x) {
	x = fract(x * 0.1031);
	x *= x + 33.33;
	x *= x + x;
	return fract(x);
}

vec3 plate_at(vec2 p) {
	return texture(plate, clamp(p, vec2(0.5), size - 0.5) / size).rgb;
}

vec3 plate_mirror(vec2 p) {
	vec2 q = abs(p);
	q = size - abs(size - q);
	return texture(plate, clamp(q, vec2(0.5), size - 0.5) / size).rgb;
}

float flame_at(vec2 p, vec4 f, float seed) {
	// Flamme als Tropfen, dessen Rand von aufsteigendem Rauschen zerfasert wird
	vec2 q = p - f.xy;
	float v = -q.y / max(f.w, 1.0);                     // 0 an der Basis, 1 oben
	if (v < -0.15 || v > 1.3 || abs(q.x) > f.z) {
		return 0.0;
	}
	// Rauschen grob abtasten (Kachel 256 Texel auf mindestens 600 px) und nur die glatten Kanäle r (1/f)
	// und g (1/f^1,6) nehmen; Kanal b (1/f^0,7) ist fast weiß und macht die Flammenränder körnig
	float S = max(f.z * 8.0, 600.0);
	float sway = (nz(vec2(seed * 0.37 + t * 0.15, 0.21), 0) - 0.5) * 0.9 * v * v;
	float u = q.x / max(f.z * 0.5, 1.0) - sway * 2.0;
	float n = nz(vec2(p.x / S + seed, (p.y + t * f.w * 1.8) / S), 1);
	float n2 = nz(vec2(p.x / (S * 0.5) - seed, (p.y + t * f.w * 2.6) / (S * 0.5)), 1);
	float width = (1.0 - smoothstep(0.0, 1.0, v)) * (0.55 + 0.45 * smoothstep(-0.15, 0.25, v));
	float edge = width - abs(u) + (n - 0.5) * 0.7 + (n2 - 0.5) * 0.35;
	return smoothstep(0.0, 0.25, edge) * smoothstep(-0.15, 0.05, v);
}

void fragment() {
	vec2 p = UV * size;
	vec4 ma = texture(mask_a, UV);
	vec4 mb = texture(mask_b, UV);
	vec4 mc = texture(mask_c, UV);
	float water = ma.r, sky = ma.g, stars = ma.b;
	float grass = mc.r, recv = mc.g, beam_vis = mc.b;

	// --- Gras im Wind: waagerechtes Versetzen innerhalb der Grasfläche, Böen wandern von links nach rechts
	vec2 sp = p;
	if (grass_amp > 0.0) {
		float gust = nz(vec2(p.x / 900.0 - t * 0.05, 0.37), 0);
		float wv = nz(vec2(p.x / 600.0 - t * 0.12, p.y / 420.0), 1) - 0.5;
		float g = texture(mask_c, (p + vec2(3.0, 0.0)) / size).r * texture(mask_c, (p - vec2(3.0, 0.0)) / size).r;
		sp.x += grass_amp * (0.4 + 1.2 * gust) * wv * 2.0 * g * grass;
	}
	vec3 still = texture(TEXTURE, sp / size).rgb;

	// --- Himmel: langsames Pendeln als reine Verschiebung, Sterne funkeln an Ort und Stelle
	float sky_off = sky_amp * sin(6.2831853 * (t - 4.0) / sky_period);
	vec3 skyc = plate_mirror(p + vec2(sky_off, 0.0));
	skyc *= 1.0 + (nz((p + vec2(sky_off * 1.3 + t * 0.4, 0.0)) / vec2(820.0, 520.0), 0) - 0.5) * 0.08;
	float tw = nz(p / 256.0 + vec2(t * 0.12, t * 0.07), 1);
	skyc = mix(skyc, still * (0.5 + 1.0 * smoothstep(0.35, 0.7, tw)), stars);

	// --- Wasser: Zeilenwellen, vorn stärker; Glitzern nur auf hellen Stellen
	float depth = clamp((p.y - horizon_y) / max(water_bottom - horizon_y, 1.0), 0.0, 1.0);
	float persp = mix(0.25, 1.0, depth);
	vec2 q = vec2(p.x / (600.0 * persp), p.y / (40.0 * persp));
	float n1 = nz(q + vec2(t * water_speed, -t * water_speed * 0.6), 0) - 0.5;
	float n2 = nz(q * 2.1 + vec2(-t * water_speed * 1.4, t * water_speed * 0.4), 1) - 0.5;
	vec2 wd = vec2(n1 * 2.0 + n2, (n2 - n1) * 0.35) * water_amp * persp * 1.6;
	vec3 wc = plate_at(p + wd);
	float lum = dot(wc, vec3(0.299, 0.587, 0.114));
	float hz = max(p.y - horizon_y, 0.0);
	float kf = 160.0 / (hz + 160.0);
	vec2 wpl = vec2((p.x - size.x * 0.5) * kf / 3.0, 160.0 * log((hz + 160.0) / 160.0)) / 256.0;
	float g1 = nz(wpl + vec2(t * 0.012, t * 0.004), 2);
	float g2 = nz(wpl * vec2(0.83, 1.0) + vec2(0.43 - t * 0.010, 0.71 + t * 0.006), 0);
	float glint = smoothstep(0.36, 0.47, g1 * g2) * smoothstep(glint_lo, glint_lo + 0.2, lum);
	wc += glint * sparkle_k * vec3(1.0, 0.84, 0.6) * (0.4 + 0.6 * depth);

	vec3 col = still;
	col = mix(col, skyc, sky);
	col = mix(col, wc, water);

	// --- Lichter flackern (Leuchtfläche und gemalter Schein), Empfängerflächen folgen dem fire-Kanal
	col *= 1.0 + mb.r * (flick.x - 1.0) + mb.g * (flick.y - 1.0) + mb.b * (flick.z - 1.0);
	col *= 1.0 + recv * receiver_k * (flick.x - 1.0);

	// --- Linse: ein heller senkrechter Streifen (Brennpunkt der drehenden Linse) läuft über die Glasringe
	if (lens_k > 0.0 && p.x > lens_rect.x && p.x < lens_rect.z && p.y > lens_rect.y && p.y < lens_rect.w) {
		float lx = (p.x - lens_rect.x) / (lens_rect.z - lens_rect.x);
		float c = fract(lens_phase) * 1.6 - 0.3;
		float band = exp(-pow((lx - c) / 0.11, 2.0));
		float rings = 0.75 + 0.25 * nz(vec2(lx * 0.4, p.y / 600.0), 1);
		col += vec3(1.0, 0.86, 0.6) * band * rings * lens_k * mb.r;
	}
	// --- Lichtfleck der Linse wandert über Wände und Boden (nur Empfängerflächen außerhalb der Fenster)
	if (sweep_k > 0.0) {
		float dx = (p.x - sweep_x) / sweep_w;
		float spot = exp(-dx * dx) * (0.35 + 0.65 * recv) * (1.0 - sky) * (1.0 - water);
		col += sweep_col * spot * sweep_k * (0.6 + 0.4 * nz(vec2(p.x / 700.0, p.y / 500.0 + t * 0.02), 0));
	}

	// --- Flammen (additiv, über der gemalten Glut bzw. dem Docht)
	for (int i = 0; i < 2; i++) {
		if (flame_k[i] <= 0.0) {
			continue;
		}
		float f = flame_at(p, flame[i], float(i) * 3.1 + 1.7);
		float v = clamp(-(p.y - flame[i].y) / max(flame[i].w, 1.0), 0.0, 1.0);
		vec3 fc = mix(vec3(1.0, 0.78, 0.38), vec3(0.95, 0.38, 0.12), v);
		col += fc * f * flame_k[i] * (0.75 + 0.25 * (i == 0 ? flick.x : flick.y));   // 0 Feuer, 1 Kerze
	}

	// --- Leuchtturmstrahl (additiv, nur vor dem Himmel)
	if (beam_k > 0.0) {
		float side = cos(beam_phi);
		float toward = sin(beam_phi);
		vec2 dv = p - lamp_pos;
		float dirx = side >= 0.0 ? 1.0 : -1.0;
		vec2 bdir = normalize(vec2(dirx, 0.03));
		float along = dot(dv, bdir);
		float across = abs(dv.x * bdir.y - dv.y * bdir.x);
		float Lb = beam_len * abs(side);
		float hw = 1.5 + max(along, 0.0) * (0.07 + 0.09 * max(toward, 0.0));
		float cone = smoothstep(hw, hw * 0.25, across) * smoothstep(0.0, 8.0, along) * (1.0 - smoothstep(Lb * 0.25, Lb, along));
		float rel = (dv.x * bdir.y - dv.y * bdir.x) / max(hw, 1.0);
		float haze = (0.7 + 0.6 * nz(p / 1100.0 + vec2(t * 0.01, 0.0), 0)) * (0.65 + 0.7 * nz(vec2(rel * 0.45 + 0.13, along / 1400.0 - t * 0.012), 2));
		float facing = mix(0.35, 1.0, clamp(toward * 0.5 + 0.5, 0.0, 1.0));
		col += beam_col * cone * haze * facing * beam_k * beam_vis;
	}

	// --- Möwen
	for (int i = 0; i < 2; i++) {
		if (gull_size[i] <= 0.0) {
			continue;
		}
		vec2 g = (p - gull_pos[i]) / gull_size[i];
		float ph = t * (i == 0 ? 7.5 : 6.3) + float(i);
		float flap = mix(0.18, sin(ph) * 0.55, smoothstep(0.2, 0.6, sin(t * 0.7 + float(i) * 1.7) * 0.5 + 0.5));
		float ax = abs(g.x);
		float yc = -flap * ax + 0.35 * ax * ax - 0.10;
		float th = 0.16 * (1.0 - ax) + 0.05;
		float wing = (1.0 - smoothstep(th * 0.6, th, abs(g.y - yc))) * (1.0 - smoothstep(0.92, 1.0, ax));
		float body = 1.0 - smoothstep(0.10, 0.18, length(g * vec2(0.9, 1.6)));
		col = mix(col, gull_col, clamp(max(wing, body), 0.0, 1.0) * 0.85 * sky);
	}

	// --- Lichthöfe (additiv, weich); ihre Summe färbt auch den Nebel
	vec3 glow = vec3(0.0);
	for (int i = 0; i < 6; i++) {
		float d = length(p - glow_pos[i]) / max(glow_r[i], 1.0);
		glow += glow_col[i].rgb * glow_col[i].a * exp(-d * d * 2.2);
	}

	// --- Nebelbänder: zwei Rauschlagen treiben gegeneinander, weich nach oben und unten
	for (int i = 0; i < 4; i++) {
		vec4 b = fog_band[i];
		if (b.z <= 0.0) {
			continue;
		}
		vec4 m = fog_mode[i];
		float region = m.x < 0.5 ? 1.0 : (m.x < 1.5 ? max(sky, water) : (m.x < 2.5 ? water : (1.0 - max(sky, water))));
		float prof = exp(-pow((p.y - b.x) / max(b.y, 1.0), 2.0));
		// Kacheln mindestens 256 px hoch und breit (1 px je Texel oder gröber)
		vec2 fp = p / max(m.y, 256.0);
		float f = nz(fp * vec2(0.5, 0.9) + vec2(t * b.w / max(m.y, 256.0) * 0.5, float(i) * 0.31), 0) * 0.6
			+ nz(fp * vec2(0.8, 1.0) + vec2(-t * b.w / max(m.y, 256.0) * 0.8, 0.53 + float(i) * 0.17), 1) * 0.4;
		float a = smoothstep(0.32, 0.72, f) * prof * b.z * region;
		vec3 fc = fog_col * (1.0 + m.z) + glow * 1.6;
		col = mix(col, fc, clamp(a, 0.0, 1.0));
	}

	// --- Lichtteilchen: schweben langsam, leuchten nahe der Lichtquelle stärker
	if (mote_n > 0 && p.x > mote_rect.x - 6.0 && p.x < mote_rect.z + 6.0 && p.y > mote_rect.y - 6.0 && p.y < mote_rect.w + 6.0) {
		vec2 ext = mote_rect.zw - mote_rect.xy;
		for (int i = 0; i < 64; i++) {
			if (i >= mote_n) {
				break;
			}
			float fi = float(i);
			float r1 = hash1(fi * 1.37 + 0.5), r2 = hash1(fi * 2.71 + 3.1), r3 = hash1(fi * 5.13 + 7.7), r4 = hash1(fi * 0.91 + 11.3);
			float rise = 4.0 + 9.0 * r3;
			float yy = mote_rect.w - fract(r2 + t * rise / ext.y) * ext.y;
			float xx = mote_rect.x + fract(r1 + 0.02 * sin(t * (0.3 + 0.4 * r4) + fi)) * ext.x;
			xx += 9.0 * sin(t * (0.5 + 0.6 * r3) + fi * 2.0);
			vec2 d = p - vec2(xx, yy);
			float rad = 1.2 + 1.6 * r4;
			float a = exp(-dot(d, d) / (rad * rad));
			if (a < 0.003) {
				continue;
			}
			float edge = smoothstep(0.0, 0.15, (yy - mote_rect.y) / ext.y) * smoothstep(0.0, 0.15, (mote_rect.w - yy) / ext.y);
			float tw2 = 0.55 + 0.45 * sin(t * (1.3 + 2.0 * r1) + fi * 4.0);
			float near = 0.35 + 0.65 * exp(-pow(length(vec2(xx, yy) - mote_light) / 320.0, 2.0));
			col += mote_col * a * edge * tw2 * near * mote_k;
		}
	}

	col += glow;
	// Vignette: Ränder leicht abdunkeln (Luftperspektive, Blick zur Mitte)
	vec2 vc = UV - 0.5;
	col *= 1.0 - vignette * smoothstep(0.25, 0.75, length(vc * vec2(1.0, 0.8)) * 1.25);
	COLOR = vec4(col, 1.0);
}
