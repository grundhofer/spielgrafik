shader_type canvas_item;
// Zusammensetzen des Neonbilds aus dem ID-Puffer (id.gdshader) in einem einzigen Bildschirmdurchgang:
//   Himmel mit Streifensonne, Sterne und Wolkenbändern  (Kennung 0)
//   Wasser mit Spiegelbild aus der Spiegelkamera       (Kennung 1)
//   Kai-Pflaster als perspektivisches Neonraster       (Kennung 2)
//   alle anderen Flächen: dunkle Füllung + Neonröhre an Umriss, Materialgrenze und Knick
// Der ID-Puffer ist doppelt so groß wie das Bild (2×2 Unterabtastung): Röhren und Kanten werden je
// Unterpixel bestimmt und gemittelt, so sind sie geglättet, ohne MSAA im ID-Puffer.
// Lichtkegel des Leuchtturms und Lichthöfe sind tiefengeprüft (Gegenstände davor verdecken sie).

#include "res://shaders/sky.gdshaderinc"

uniform sampler2D id_tex : filter_nearest, repeat_disable;
uniform sampler2D refl_tex : filter_nearest, repeat_disable;
uniform int ss = 2;                     // Unterabtastung des ID-Puffers je Achse
uniform vec2 out_size = vec2(1280.0, 720.0);

uniform mat4 cam_xform;                  // globale Transformation der Kamera
uniform mat4 view_mat;                   // Inverse davon
uniform float tan_half_fov = 0.383864;   // tan(21°)
uniform float aspect = 1.7777778;

uniform vec4 neon[64];                   // rgb = Röhrenfarbe (linear, HDR), a = cos(Knickwinkel) oder -2 = keine Knicklinien
uniform vec4 fill[64];                   // rgb = Füllfarbe (linear), a: +1 Linie auch an Materialgrenzen gleicher Tiefe, +2 durchsichtig (Himmel)

uniform float line_gain = 0.85;          // Helligkeit aller Röhren
uniform float core_white = 0.18;         // Weißanteil in der Röhrenmitte
uniform float line_w = 2.4;              // halbe Röhrenbreite in Unterpixeln
uniform float depth_tol = 0.035;         // Tiefensprung (relativ, 1/z) für Umrisse innerhalb einer Fläche
uniform float water_y = -0.8;

uniform float t = 0.0;                   // aufsummierte Zeit aus main.gd

// Raster auf dem Kai
uniform vec3 grid_col = vec3(2.0, 0.12, 1.2);
uniform float grid_cell = 1.0;
uniform vec3 pave_col = vec3(0.010, 0.004, 0.022);

// Leuchtturmstrahl
uniform vec3 lamp_pos = vec3(10.2, 12.58, -25.6);
uniform vec3 beam_dir = vec3(-1.0, -0.05, 0.0);
uniform vec3 beam_col = vec3(0.5, 1.6, 2.0);
uniform float beam_tan = 0.045;          // Öffnung des Strahls (tan des halben Winkels)
uniform float beam_len = 55.0;

// Lichthöfe (Position in Welt, Farbe, Radius in px)
uniform vec3 halo_pos[4];
uniform vec4 halo_col[4];                // rgb, a = Radius in Bildpunkten
uniform int halo_count = 0;

uniform float floor_depth = 4.0;         // Messkamera von unten: Tiefe des Bodens
uniform int debug_view = 0;              // 1 = Kennungen in Falschfarben, 2 = Maske (alles außer Himmel weiß)

const ivec2 DIRS[8] = ivec2[](ivec2(1, 0), ivec2(-1, 0), ivec2(0, 1), ivec2(0, -1),
		ivec2(1, 1), ivec2(-1, 1), ivec2(1, -1), ivec2(-1, -1));

vec3 cam_ray(vec2 uv) {
	return vec3((uv.x * 2.0 - 1.0) * tan_half_fov * aspect, (1.0 - uv.y * 2.0) * tan_half_fov, -1.0);
}

vec3 world_dir(vec2 uv) {
	return normalize(mat3(cam_xform) * cam_ray(uv));
}

vec2 project(vec3 p) {
	vec3 c = (view_mat * vec4(p, 1.0)).xyz;
	vec2 ndc = vec2(c.x / (-c.z * tan_half_fov * aspect), c.y / (-c.z * tan_half_fov));
	return vec2(ndc.x * 0.5 + 0.5, 0.5 - ndc.y * 0.5) * out_size;
}

vec3 raw(sampler2D tex, ivec2 p, ivec2 sz) {
	return texelFetch(tex, clamp(p, ivec2(0), sz - 1), 0).rgb;
}

int sid(vec3 s) {
	return int(floor(s.r + 0.01));
}

float sdepth(vec3 s) {
	return sid(s) == 0 ? 1.0e6 : s.g;
}

vec3 dec_n(float b) {
	float ox = floor(b / 32.0 + 0.001);
	float oy = b - ox * 32.0;
	vec2 e = vec2(ox, oy) / 31.0 * 2.0 - 1.0;
	vec3 n = vec3(e.x, 1.0 - abs(e.x) - abs(e.y), e.y);
	if (n.y < 0.0) {
		vec2 s = vec2(n.x >= 0.0 ? 1.0 : -1.0, n.z >= 0.0 ? 1.0 : -1.0);
		n.xz = (1.0 - abs(n.zx)) * s;
	}
	return normalize(n);
}

// Röhre am Unterpixel p: Stärke 0..1 und Kennung, deren Farbe die Röhre trägt.
// Regeln: Am Umriss zeichnet der vordere Gegenstand die Röhre auf beiden Seiten der Kante (innen und
// über dem Hintergrund). An Materialgrenzen gleicher Tiefe zeichnet jede Seite ihre eigene Farbe.
// Innerhalb einer Kennung: Tiefensprung gegen die ebene Vorhersage (1/z linear) oder Knick der Normalen.
vec2 tube(sampler2D tex, ivec2 p, ivec2 sz, vec3 c, float w_half) {
	int idc = sid(c);
	float dc = sdepth(c);
	vec3 nc = dec_n(c.b);
	float best = 0.0;
	float best_id = 0.0;
	int kmax = int(ceil(w_half + 0.5));
	for (int d = 0; d < 8; d++) {
		ivec2 o = DIRS[d];
		float step_len = d < 4 ? 1.0 : 1.41421;
		for (int k = 1; k <= kmax; k++) {
			float dist = float(k) * step_len - 0.5;
			float w = 1.0 - smoothstep(w_half - 0.75, w_half + 0.75, dist);
			if (w <= best) {
				break;
			}
			vec3 q = raw(tex, p + o * k, sz);
			int idq = sid(q);
			float dq = sdepth(q);
			int hit_id = -1;
			if (idq != idc) {
				if (dq < dc * 0.97 - 0.02) {
					hit_id = idq;                       // q liegt vorn: dessen Röhre reicht herüber
				} else if (dc < dq * 0.97 - 0.02 || mod(fill[idc].a, 2.0) > 0.5) {
					hit_id = idc;                       // p liegt vorn oder Materialgrenze
				}
			} else if (idc > 1) {
				vec3 q2 = raw(tex, p - o * k, sz);
				float inv_pred = sid(q2) == idc ? 2.0 / dc - 1.0 / sdepth(q2) : 1.0 / dc;
				float inv_q = 1.0 / dq;
				if (inv_q < inv_pred * (1.0 - depth_tol)) {
					hit_id = idc;                       // q liegt dahinter (gleiche Kennung)
				} else if (inv_q > inv_pred * (1.0 + depth_tol) * (1.0 + depth_tol)) {
					hit_id = idc;                       // q liegt davor
				} else if (neon[idc].a > -1.5 && dot(dec_n(q.b), nc) < neon[idc].a) {
					hit_id = idc;                       // Knick
				}
			}
			if (hit_id > 1 && dot(neon[hit_id].rgb, vec3(1.0)) > 0.001) {
				best = w;
				best_id = float(hit_id);
				break;
			}
		}
	}
	return vec2(best, best_id);
}

vec3 haze(vec3 col, float depth) {
	float h = smoothstep(40.0, 420.0, depth);
	return mix(col, horizon_col() * 0.55, h * 0.75);
}

vec3 fill_color(vec3 s) {
	int id = sid(s);
	float fade = clamp(fract(s.r + 0.01) - 0.01, 0.0, 1.0);
	vec3 f = fill[id].rgb * (1.0 - fade);
	return haze(f, s.g);
}

vec3 tube_color(vec2 tb, float depth, float fade) {
	// Röhre in voller Stärke (gemischt wird mit tb.x): gesättigte Farbe, in der Mitte leicht zu Weiß
	vec3 n = neon[int(tb.y)].rgb * (1.0 - fade) * line_gain;
	float m = max(n.r, max(n.g, n.b));
	vec3 c = n + vec3(min(m, 1.0) * core_white * tb.x * tb.x);
	float h = smoothstep(40.0, 420.0, depth);
	return c * (1.0 - h * 0.7);
}


// Wasser: Spiegelbild aus der Spiegelkamera (Bild senkrecht gespiegelt), mit Kräuselung verschoben und in
// waagerechte Streifen gebrochen; Himmel im Spiegelbild aus der gespiegelten Richtung.
uniform vec3 water_col = vec3(0.004, 0.003, 0.02);
uniform float refl_gain = 0.8;

vec3 water(vec3 rd, vec3 ro, vec2 uv) {
	float tw = (water_y - ro.y) / min(rd.y, -1.0e-4);
	vec3 wp = ro + rd * tw;
	float w1 = sin(wp.x * 0.9 + wp.z * 2.3 + t * 1.7) + 0.6 * sin(-wp.x * 1.7 + wp.z * 3.9 - t * 2.3)
			+ 0.35 * sin(wp.z * 7.3 + wp.x * 0.5 + t * 3.1);
	float amp = 30.0 / max(tw, 4.0);
	vec2 off = vec2(w1 * amp * 0.55, w1 * amp * 0.3);
	ivec2 rsz = textureSize(refl_tex, 0);
	vec2 rscale = vec2(rsz) / out_size;
	vec2 rpx = (vec2(uv.x, 1.0 - uv.y) * out_size + off) * rscale;
	ivec2 rp = ivec2(floor(rpx));
	vec3 s = raw(refl_tex, rp, rsz);
	vec3 c;
	if (sid(s) == 0) {
		vec3 rdir = normalize(vec3(rd.x + w1 * 0.0025, -rd.y, rd.z));
		c = sky(rdir, t, true);
	} else {
		c = fill_color(s);
		vec2 tb = tube(refl_tex, rp, rsz, s, 1.3);
		if (tb.x > 0.0) {
			c = mix(c, tube_color(tb, s.g, 0.0), tb.x);
		}
	}
	// waagerechte Brüche: dunkle Fugen zwischen Wellenbändern, nach hinten dichter
	float band = sin(wp.z * 3.4 + w1 * 1.1 + t * 0.7) + 0.5 * sin(wp.z * 9.1 - wp.x * 0.3 + t * 1.3);
	float br = 0.2 + 0.8 * smoothstep(-0.6, 0.4, band);
	float fres = mix(0.55, 1.0, smoothstep(10.0, 120.0, tw));
	return water_col + c * refl_gain * br * fres;
}

float beam(vec3 ro, vec3 rd, float max_t) {
	// kleinster Abstand zwischen Sehstrahl und Strahlachse
	vec3 a = normalize(beam_dir);
	vec3 w0 = ro - lamp_pos;
	float b = dot(rd, a);
	float d = dot(rd, w0);
	float e = dot(a, w0);
	float den = 1.0 - b * b;
	if (den < 1.0e-5) {
		return 0.0;
	}
	float sr = (b * e - d) / den;          // entlang des Sehstrahls
	float sa = (e - b * d) / den;          // entlang der Strahlachse
	if (sa < 0.0 || sr < 0.0 || sr > max_t) {
		return 0.0;
	}
	vec3 pr = ro + rd * sr;
	vec3 pa = lamp_pos + a * sa;
	float dist = length(pr - pa);
	float radius = 0.25 + sa * beam_tan;
	float x = dist / radius;
	float core = exp(-x * x * 2.2);
	float edge = exp(-pow((x - 0.92) * 9.0, 2.0)) * 0.6;   // Neonkanten des Kegels
	float along = exp(-sa / beam_len) * smoothstep(0.0, 2.0, sa);
	return (core * 0.42 + edge) * along;
}

void fragment() {
	ivec2 sz = textureSize(id_tex, 0);
	ivec2 base = ivec2(floor(UV * out_size)) * ss;
	vec3 ro = cam_xform[3].xyz;
	vec3 rd = world_dir(UV);

	// Pixelweise (nicht je Unterpixel): Himmel, Wasser, Raster
	bool need_sky = false;
	bool need_water = false;
	bool need_pave = false;
	vec3 subs[4];
	int n_sub = ss * ss;
	float min_depth = 1.0e6;
	for (int i = 0; i < n_sub; i++) {
		subs[i] = raw(id_tex, base + ivec2(i % ss, i / ss), sz);
		int id = sid(subs[i]);
		need_sky = need_sky || id == 0 || fill[id].a > 1.5;
		need_water = need_water || id == 1;
		need_pave = need_pave || id == 2;
		min_depth = min(min_depth, sdepth(subs[i]));
	}

	vec3 sky_c = vec3(0.0);
	if (need_sky) {
		sky_c = sky(rd, t, false);
	}

	vec3 water_c = vec3(0.0);
	if (need_water) {
		water_c = water(rd, ro, UV);
	}

	vec3 pave_c = vec3(0.0);
	// Raster: Strahl mit der Kaiebene schneiden (y = 0); fwidth braucht stetige Werte, deshalb immer rechnen
	float tp = (0.004 - ro.y) / min(rd.y, -1.0e-4);
	vec3 pp = ro + rd * tp;
	vec2 g = pp.xz / grid_cell;
	vec2 fw = max(fwidth(g), vec2(1.0e-4));
	if (need_pave) {
		vec2 gd = abs(fract(g - 0.5) - 0.5) / fw;
		float lx = 1.0 - smoothstep(0.35, 1.35, gd.x);
		float lz = 1.0 - smoothstep(0.35, 1.35, gd.y);
		float fade_far = 1.0 - smoothstep(0.08, 0.32, max(fw.x, fw.y));
		float pulse = 0.65 + 0.35 * smoothstep(0.75, 1.0, sin(pp.z * 0.55 + t * 2.4) * 0.5 + 0.5);
		float gl = max(lx, lz) * pulse;
		pave_c = pave_col + grid_col * gl * mix(0.12, 1.0, fade_far);
	}

	vec3 acc = vec3(0.0);
	for (int i = 0; i < n_sub; i++) {
		vec3 s = subs[i];
		int id = sid(s);
		vec3 c;
		if (id == 0) {
			c = sky_c;
		} else if (id == 1) {
			c = water_c;
		} else if (id == 2) {
			c = pave_c;
		} else if (fill[id].a > 1.5) {
			c = sky_c;
		} else {
			c = fill_color(s);
		}
		vec2 tb = tube(id_tex, base + ivec2(i % ss, i / ss), sz, s, line_w);
		if (tb.x > 0.0) {
			// Kennung und Verblassen der Röhre kommen vom zeichnenden Gegenstand
			float fade = 0.0;
			float dd = s.g;
			if (int(tb.y) != id) {
				// Röhre eines vorderen Nachbarn: dessen Tiefe ist unbekannt, nimm die kleinste im Pixel
				dd = min_depth;
			} else {
				fade = clamp(fract(s.r + 0.01) - 0.01, 0.0, 1.0);
			}
			vec3 lc = tube_color(tb, dd, fade);
			c = mix(c, lc, tb.x);
		}
		acc += c;
	}
	vec3 col = acc / float(n_sub);

	// Leuchtturmstrahl (tiefengeprüft gegen die Mitte des Pixels)
	float depth_c = sdepth(subs[0]);
	float max_t = depth_c / max(dot(rd, -mat3(cam_xform)[2]), 1.0e-3);
	col += beam_col * beam(ro, rd, max_t);

	// Lichthöfe
	vec2 px = UV * out_size;
	for (int i = 0; i < halo_count; i++) {
		vec2 hp = project(halo_pos[i]);
		vec3 hc = (view_mat * vec4(halo_pos[i], 1.0)).xyz;
		float hd = -hc.z;
		float r = length(px - hp) / halo_col[i].a;
		float vis = depth_c > hd - 0.6 ? 1.0 : 0.25;
		col += halo_col[i].rgb * exp(-r * r * 2.5) * vis;
	}

	if (debug_view == 3) {
		// Messung von unten: R = Bodenkontakt (Tiefe bis 1,2 cm über dem Boden), G = ganze Figur
		float m = 0.0;
		float g = 0.0;
		for (int i = 0; i < n_sub; i++) {
			int id = sid(subs[i]);
			g += id != 0 ? 1.0 : 0.0;
			m += (id != 0 && subs[i].g < floor_depth + 0.012) ? 1.0 : 0.0;
		}
		col = vec3(m, g, 0.0) / float(n_sub);
	}
	if (debug_view == 2) {
		float m = 0.0;
		for (int i = 0; i < n_sub; i++) {
			m += sid(subs[i]) != 0 ? 1.0 : 0.0;
		}
		col = vec3(m / float(n_sub));
	}
	if (debug_view == 1) {
		vec3 s0 = subs[0];
		float idf = float(sid(s0));
		col = (fract(idf * vec3(0.137, 0.731, 0.413)) * 0.8 + 0.1) * (1.0 - smoothstep(0.0, 60.0, s0.g) * 0.5);
	}
	COLOR = vec4(col, 1.0);
}
