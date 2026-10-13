shader_type canvas_item;
// Art déco – Plakatbild mit Umgebungsanimationen. Alles in Bildpixeln des Plakats (1536x1024, Welt).
// Maske art/mask.png (filter_nearest, RGB-Codes): Himmel 0,0,1  Wolken 0,1,1  Sonne 1,1,0  Meer 0,1,0
// Boote 1,0,0  Fenster 1,.5,0  Laterne 1,0,1  Leuchtfeuer .5,0,1  Sterne 1,1,1  Rest 0,0,0.
// Effekte sind Plakatformen mit harten Kanten (Kantenglättung nur über fwidth, etwa 1 Pixel):
//   Sonnenstrahlen  abwechselnd hellere Keile im Himmel hinter den Wolken, drehen langsam
//   Leuchtfeuer     Strahl aus drei Stufen (Kern, Saum, drei Längenabschnitte), nur über Himmel/Wolken
//   Lichthöfe       konzentrische Stufenringe um Leuchtfeuer und Laterne; Aufblitzen als achtstrahliger Stern
//   Wasser          Spiegelungen als Säulen kurzer goldener Striche, springen 6-mal je Sekunde
//   Boote           schaukeln um ganze Pixel (Bootspixel versetzt, freie Stellen aus der Bootsplatte)

uniform sampler2D mask : filter_nearest;
uniform sampler2D plate : filter_linear;
uniform vec2 tex_size = vec2(1536.0, 1024.0);
uniform float t = 0.0;
uniform vec2 sun_c = vec2(575.6, 532.0);
uniform float horizon_y = 485.0;
uniform float quay_y = 712.0;
uniform vec2 lamp = vec2(1352.5, 112.1);
uniform vec2 lantern = vec2(1110.6, 555.3);
uniform float ray_rot = 0.0;          // Drehung der Sonnenstrahlen (Bogenmaß)
uniform float ray_gain = 1.0;
uniform float beam_dir = 1.0;         // -1 links, +1 rechts
uniform float beam_len = 0.0;         // sichtbare Länge in Pixeln (0 = zur Kamera oder weg)
uniform float lamp_gain = 1.0;
uniform float lamp_flash = 0.0;       // 0..1, Leuchtfeuer zeigt zur Kamera
uniform float lantern_gain = 1.0;
uniform float window_gain = 1.0;
uniform vec4 boat_a = vec4(805.0, 540.0, 965.0, 700.0);
uniform vec4 boat_b = vec4(1125.0, 525.0, 1320.0, 695.0);
uniform float bob_a = 0.0;            // ganze Pixel
uniform float bob_b = 0.0;
uniform float glint_step = 0.0;       // ganzzahliger Schritt für die Spiegelungen (6 je Sekunde)

const vec3 GOLD = vec3(0.98, 0.80, 0.46);
const vec3 PALE = vec3(1.0, 0.93, 0.74);

float code(vec3 m, vec3 c) {
	return step(length(m - c), 0.3);
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

// harte Kante mit etwa 1 Pixel Glättung
float edge(float d) {
	float w = max(fwidth(d), 1e-4);
	return clamp(0.5 - d / w, 0.0, 1.0);
}

void fragment() {
	vec2 p = UV * tex_size;
	// alle Abtastungen vor den Verzweigungen
	vec3 m = texture(mask, UV).rgb;
	vec2 oa = vec2(0.0, bob_a);
	vec2 ob = vec2(0.0, bob_b);
	vec3 ma = texture(mask, (p - oa) / tex_size).rgb;
	vec3 mb = texture(mask, (p - ob) / tex_size).rgb;
	vec4 ca = texture(TEXTURE, (p - oa) / tex_size);
	vec4 cb = texture(TEXTURE, (p - ob) / tex_size);
	vec4 pl = texture(plate, UV);
	vec3 col = COLOR.rgb;

	float sky = code(m, vec3(0.0, 0.0, 1.0));
	float cloud = code(m, vec3(0.0, 1.0, 1.0));
	float sea = code(m, vec3(0.0, 1.0, 0.0));
	float boat = code(m, vec3(1.0, 0.0, 0.0));
	float win = code(m, vec3(1.0, 0.5, 0.0));
	float lant = code(m, vec3(1.0, 0.0, 1.0));
	float lmp = code(m, vec3(0.5, 0.0, 1.0));
	float star = code(m, vec3(1.0, 1.0, 1.0));

	// --- Boote schaukeln (nur in ihren Kästen, nur über Meer und Boot) ---
	float in_a = step(boat_a.x, p.x) * step(p.x, boat_a.z) * step(boat_a.y - 4.0, p.y) * step(p.y, boat_a.w);
	float in_b = step(boat_b.x, p.x) * step(p.x, boat_b.z) * step(boat_b.y - 4.0, p.y) * step(p.y, boat_b.w);
	float water_or_boat = max(sea, boat);
	float hit_a = in_a * water_or_boat * code(ma, vec3(1.0, 0.0, 0.0));
	float hit_b = in_b * water_or_boat * code(mb, vec3(1.0, 0.0, 0.0));
	float vacated = (in_a + in_b) * boat * (1.0 - max(hit_a, hit_b));
	col = mix(col, pl.rgb, clamp(vacated, 0.0, 1.0));
	col = mix(col, ca.rgb, hit_a);
	col = mix(col, cb.rgb, hit_b);
	// das versetzte Boot gilt als Boot, nicht als Wasser (keine Spiegelstriche darüber)
	sea *= 1.0 - max(hit_a, hit_b);

	// --- Sonnenstrahlen: Keile um die Sonnenmitte, nur im freien Himmel ---
	vec2 d = p - sun_c;
	float ang = atan(d.x, -d.y) + ray_rot;
	float n_rays = 30.0;
	float a01 = ang / 6.2831853 * n_rays;
	float tri = abs(fract(a01) - 0.5) - 0.25;   // <0 innerhalb des hellen Keils
	float ray = edge(tri * 6.2831853 / n_rays * length(d));
	float r = length(d);
	float fall = smoothstep(1100.0, 180.0, r) * step(p.y, horizon_y);
	// jeder zweite helle Keil etwas kräftiger (zwei Stufen wie im Druck)
	float strong = step(0.5, fract(floor(a01) * 0.5));
	float ray_amt = ray * fall * mix(0.075, 0.13, strong) * ray_gain;
	col = mix(col, GOLD, ray_amt * sky);

	// --- Sterne funkeln ---
	float tw = 0.75 + 0.45 * sin(t * (2.0 + 2.5 * hash(floor(p / 12.0))) + 6.2831853 * hash(floor(p / 12.0) + 3.1));
	col = mix(col, col * tw, star);

	// --- Leuchtfeuer: Strahl in Stufen ---
	vec2 q = p - lamp;
	float along = q.x * beam_dir;
	float tilt = 0.035;
	float across = abs(q.y - along * tilt);
	float spread = 0.075;
	float halfw = 4.0 + along * spread;
	float in_len = edge(-along) * edge(along - beam_len);
	float outer = edge(across - halfw) * in_len;
	float core = edge(across - halfw * 0.42) * in_len;
	float seg = floor(clamp(along / max(beam_len, 1.0), 0.0, 0.999) * 3.0);
	float seg_gain = 1.0 - seg * 0.28;
	float beam_amt = (outer * 0.20 + core * 0.26) * seg_gain;
	col = mix(col, PALE, clamp(beam_amt, 0.0, 0.8) * max(sky, max(cloud, star)));

	// --- Lichthöfe: Stufenringe ---
	float rl = length(p - lamp);
	float halo_l = 0.0;
	halo_l += edge(rl - 34.0) * 0.07;
	halo_l += edge(rl - 24.0) * 0.09;
	halo_l += edge(rl - 15.0) * 0.12;
	col = mix(col, GOLD, halo_l * lamp_gain * max(sky, cloud));
	// Aufblitzen: Stern aus acht spitzen Strahlen um das Leuchtfeuer
	float fa = atan(q.x, -q.y);
	float sp = abs(fract(fa / 6.2831853 * 8.0 + 0.5) - 0.5) * 6.2831853 / 8.0 * rl;
	float sp_len = 18.0 + 70.0 * lamp_flash;
	float sp_w = 3.2 * (1.0 - clamp(rl / sp_len, 0.0, 1.0));
	float spoke = edge(sp - sp_w) * edge(rl - sp_len) * step(0.02, lamp_flash);
	col = mix(col, PALE, spoke * 0.75 * lamp_flash * max(sky, max(cloud, star)));
	float rn = length(p - lantern);
	float halo_n = 0.0;
	halo_n += edge(rn - 58.0 * (0.94 + 0.06 * lantern_gain)) * 0.06;
	halo_n += edge(rn - 42.0 * (0.94 + 0.06 * lantern_gain)) * 0.08;
	halo_n += edge(rn - 28.0 * (0.94 + 0.06 * lantern_gain)) * 0.11;
	col = mix(col, GOLD, halo_n * lantern_gain * (1.0 - lant));

	// --- Lichter ---
	col = mix(col, min(col * lamp_gain + vec3(0.06, 0.04, 0.0) * (lamp_gain - 1.0), vec3(1.0)), lmp);
	col = mix(col, min(col * lantern_gain, vec3(1.0)), lant);
	col = mix(col, min(col * window_gain, vec3(1.0)), win);

	// --- Spiegelungen im Wasser: Säulen kurzer Striche ---
	float v = p.y - horizon_y;
	float rows = sqrt(max(v, 0.0)) * 2.2;          // Zeilen werden zum Betrachter hin breiter (2 -> 14 px)
	float row = floor(rows);
	float in_row = edge(fract(rows) - 0.45) * step(0.0, v);
	float h1 = hash(vec2(row, glint_step));
	float h2 = hash(vec2(row + 17.0, glint_step));
	float depth = clamp(v / (quay_y - horizon_y), 0.0, 1.0);
	// Sonne: breite Säule unter der Sonnenscheibe
	float hl_s = mix(118.0, 44.0, depth) * (0.25 + 0.75 * h1);
	float cx_s = sun_c.x + (h2 - 0.5) * mix(30.0, 70.0, depth);
	float dash_s = edge(abs(p.x - cx_s) - hl_s) * in_row;
	float sun_amt = dash_s * mix(0.55, 0.26, depth);
	// Leuchtfeuer und Laterne: schmale Säulen
	float hl_l = mix(5.0, 16.0, depth) * (0.3 + 0.7 * h2);
	float dash_l = edge(abs(p.x - lamp.x - (h1 - 0.5) * 8.0) - hl_l) * in_row * step(515.0, p.y);
	float hl_n = mix(4.0, 12.0, depth) * (0.3 + 0.7 * hash(vec2(row + 41.0, glint_step)));
	float dash_n = edge(abs(p.x - lantern.x - (h2 - 0.5) * 6.0) - hl_n) * in_row * step(lantern.y + 30.0, p.y);
	float refl = sun_amt + dash_l * 0.30 * lamp_gain + dash_n * 0.34 * lantern_gain;
	col = mix(col, GOLD, clamp(refl, 0.0, 0.8) * sea);

	COLOR = vec4(col, COLOR.a);
}
