// Mischt zwei Orte (je eine SubViewport) zum Bildschirm. Vorher bekommt jeder Ort seine Farb-LUT
// (Abgleich auf die Palette des Stilankers, 32^3 als 1024x32-Streifen). Dann einer von drei Übergängen:
//   mode 0: nur "from" (kein Übergang)
//   mode 1: nasse Überblendung: Rauschmaske läuft von links ein, dunkler Trockenrand an der Front
//   mode 2: Seitenumblättern: die alte Seite rollt sich als Zylinder von rechts unten nach links oben auf,
//           Rückseite ist Papier mit durchscheinendem Bild, Schatten auf der neuen Seite
//   mode 3: Dither- und Pixelauflösung: Blockgröße (1, 2, 4, 8 px) wächst bis zur Mitte und schrumpft wieder,
//           Wechsel je Block nach 8x8-Bayer-Schwelle
shader_type canvas_item;

uniform sampler2D from_tex : filter_linear, repeat_disable;
uniform sampler2D to_tex : filter_linear, repeat_disable;
uniform sampler2D from_lut : filter_linear, repeat_disable;
uniform sampler2D to_lut : filter_linear, repeat_disable;
uniform sampler2D noise_tex : filter_linear, repeat_enable;
uniform sampler2D paper_tex : filter_linear, repeat_enable;
uniform float progress = 0.0;
uniform int mode = 0;
uniform float lut_amount = 1.0;
uniform vec2 screen_size = vec2(1280.0, 720.0);
uniform float curl_radius = 64.0;
uniform vec2 curl_dir = vec2(1.0, 0.3);
// Die umgeschlagene Klappe hebt sich beim Blättern vom Papier ab; in der Draufsicht wirkt sie verkürzt.
uniform float flap_squash = 0.45;

const float N = 32.0;

vec3 lut(sampler2D L, vec3 c) {
	c = clamp(c, 0.0, 1.0);
	float b = c.b * (N - 1.0);
	float b0 = floor(b);
	float b1 = min(b0 + 1.0, N - 1.0);
	float f = b - b0;
	vec2 uv = vec2((c.r * (N - 1.0) + 0.5) / (N * N), (c.g * (N - 1.0) + 0.5) / N);
	vec3 s0 = texture(L, uv + vec2(b0 / N, 0.0)).rgb;
	vec3 s1 = texture(L, uv + vec2(b1 / N, 0.0)).rgb;
	return mix(c, mix(s0, s1, f), lut_amount);
}

vec3 from_col(vec2 uv) { return lut(from_lut, texture(from_tex, uv).rgb); }
vec3 to_col(vec2 uv) { return lut(to_lut, texture(to_tex, uv).rgb); }

int m2(int x, int y) { return 2 * ((x ^ y) & 1) + (y & 1); }
float bayer8(ivec2 p) {
	int x = p.x & 7;
	int y = p.y & 7;
	int v = 16 * m2(x & 1, y & 1) + 4 * m2((x >> 1) & 1, (y >> 1) & 1) + m2((x >> 2) & 1, (y >> 2) & 1);
	return (float(v) + 0.5) / 64.0;
}

bool in_page(vec2 p) { return p.x >= 0.0 && p.y >= 0.0 && p.x <= screen_size.x && p.y <= screen_size.y; }

vec3 page_back(vec2 p, float shade) {
	vec3 paper = texture(paper_tex, p / screen_size).rgb;
	vec3 through = from_col(vec2(p.x, p.y) / screen_size);
	float lum = dot(through, vec3(0.3, 0.55, 0.15));
	// durchscheinendes Bild: nur leicht, gespiegelt ergibt sich von selbst durch die Abtastung am Ursprungsort
	vec3 c = paper * mix(1.0, 0.72 + 0.28 * lum, 0.35);
	return c * shade;
}

vec3 curl(vec2 uv) {
	vec2 pos = uv * screen_size;
	vec2 n = normalize(curl_dir);
	float R = curl_radius;
	float pmax = max(max(dot(vec2(screen_size.x, 0.0), n), dot(vec2(0.0, screen_size.y), n)), dot(screen_size, n));
	float pmin = min(min(dot(vec2(screen_size.x, 0.0), n), dot(vec2(0.0, screen_size.y), n)), 0.0);
	float e = smoothstep(0.0, 1.0, progress);
	float L = mix(pmax + 2.0, pmin - R - 2.0, e);
	float x = dot(pos, n) - L;                 // > 0: aufgerollte Seite, < 0: noch flach
	const float PI_ = 3.14159265;
	if (x < 0.0) {
		// Rückseite (Klappe), verkürzt um flap_squash, falls dort Material der alten Seite liegt
		float sx = -x / flap_squash;           // Abstand auf der Klappe, entzerrt
		vec2 o = pos + n * (PI_ * R + sx - x);
		if (in_page(o)) {
			float edge = smoothstep(0.0, 10.0, -x);
			return page_back(o, mix(0.86, 0.97, edge) * mix(1.0, 0.9, smoothstep(0.0, 400.0, sx)));
		}
		// alte Seite flach; weicher Schatten der abgehobenen Klappe neben ihrem Rand.
		// Abstand zum Klappenrand: Strahl A - n*u in das Seitenrechteck (Slab-Verfahren), d = u * flap_squash
		vec3 c = from_col(uv);
		vec2 A = o;
		vec2 dir = -n;
		vec2 t1 = (vec2(0.0) - A) / dir;
		vec2 t2 = (screen_size - A) / dir;
		vec2 tmin = min(t1, t2);
		vec2 tmax = max(t1, t2);
		float t_in = max(tmin.x, tmin.y);
		float t_out = min(tmax.x, tmax.y);
		if (t_in <= t_out && t_out >= 0.0) {
			float d = max(t_in, 0.0) * flap_squash;
			c *= 1.0 - 0.38 * exp(-d / 14.0);
		}
		return c;
	}
	if (x <= R) {
		float a = asin(clamp(x / R, 0.0, 1.0));
		// obere Lage: Rückseite auf dem Rückweg des Zylinders
		float s2 = (PI_ - a) * R;
		vec2 o2 = pos + n * (s2 - x);
		if (in_page(o2)) {
			float shade = mix(1.02, 0.78, pow(x / R, 2.0));
			return page_back(o2, shade);
		}
		float s1 = a * R;
		vec2 o1 = pos + n * (s1 - x);
		if (in_page(o1)) {
			float shade = mix(1.0, 0.62, pow(x / R, 1.5));
			return from_col(o1 / screen_size) * shade;
		}
		return to_col(uv);
	}
	// neue Seite mit Schlagschatten der Rolle (nur wo die Rolle Material hat)
	vec3 c = to_col(uv);
	vec2 top = pos - n * x + n * (PI_ * R * 0.5);
	if (in_page(top)) {
		c *= 1.0 - 0.42 * exp(-(x - R) / (0.55 * R));
	}
	return c;
}

vec3 wet(vec2 uv) {
	float nz = texture(noise_tex, uv).r;
	float field = 0.62 * nz + 0.38 * uv.x;   // links (Lichtseite) zuerst, Lesrichtung
	float w = 0.035;
	float p = progress * (1.0 + 2.0 * w) - w;
	float reveal = 1.0 - smoothstep(p - w, p + w, field);
	// Trockenrand: dünne Linie (etwa 3 px) genau an der Front, Breite über fwidth im Bildschirmraum
	float fw = max(fwidth(field), 1e-4);
	float front = exp(-pow((field - p) / (fw * 2.5), 2.0));
	float halo = exp(-pow((field - p) / (w * 0.8), 2.0));
	vec2 wob = (vec2(texture(noise_tex, uv * 3.0).r, texture(noise_tex, uv * 3.0 + 0.37).r) - 0.5) * 0.005 * halo;
	vec3 c = mix(from_col(uv + wob), to_col(uv + wob), reveal);
	// Pigment sammelt sich am Trockenrand: Linie dunkler, davor ein Hauch heller (ausgewaschen)
	c *= 1.0 - 0.28 * front;
	c = mix(c, c * 1.06 + 0.02, 0.5 * halo * (1.0 - reveal));
	return c;
}

vec3 dither(vec2 uv) {
	vec2 pos = uv * screen_size;
	float k = sin(3.14159265 * clamp(progress, 0.0, 1.0));
	float b = exp2(floor(k * 3.0 + 0.5));      // 1, 2, 4, 8 px
	vec2 cell = floor(pos / b);
	vec2 c_uv = (cell + 0.5) * b / screen_size;
	float th = bayer8(ivec2(cell));
	return progress > th ? to_col(c_uv) : from_col(c_uv);
}

void fragment() {
	vec2 uv = UV;
	vec3 c;
	if (mode == 1) {
		c = wet(uv);
	} else if (mode == 2) {
		c = curl(uv);
	} else if (mode == 3) {
		c = dither(uv);
	} else {
		c = from_col(uv);
	}
	COLOR = vec4(c, 1.0);
}
