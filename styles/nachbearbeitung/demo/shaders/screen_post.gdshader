// Bildschirm-Nachbearbeitung: liegt auf dem fertigen Bild (Welt + Oberfläche) und wirkt auf alles.
// Look CRT: gewölbte Röhre (Krümmung), 240 Zeilen mit Strahlprofil (Scanlines), Lochmaske aus RGB-Leuchtpunkten,
// leichter Nachleuchtschein, Abschattung zu den Rändern, abgerundete Ecken, schwarze Einfassung.
// crt = 0 gibt das Bild unverändert aus.
shader_type canvas_item;
render_mode unshaded;

// Quellbild (Viewport-Textur, setzt main.gd): TEXTURE ist in eigenen Funktionen nicht verfügbar.
uniform sampler2D src_tex : filter_linear, repeat_disable;

uniform float crt = 0.0;
uniform float lines = 240.0;              // Zeilen des Röhrenbilds (3 px je Zeile bei 720 px)
uniform vec2 curvature = vec2(0.045, 0.06);
uniform float mask_dark = 0.62;
uniform float mask_light = 1.32;
uniform float mask_row = 0.78;
uniform float glow = 0.22;
uniform float time_s = 0.0;

vec3 src(vec2 uv) {
	return textureLod(src_tex, uv, 0.0).rgb;
}

vec2 warp(vec2 uv) {
	vec2 c = uv * 2.0 - 1.0;
	c *= vec2(1.0 + c.y * c.y * curvature.x, 1.0 + c.x * c.x * curvature.y);
	return c * 0.5 + 0.5;
}

// Eine Röhrenzeile: Mittel über ihre 3 Quellzeilen, waagerecht leicht verwaschen (begrenzte Bandbreite)
vec3 scan_line(float x, float n, vec2 ps) {
	float v = (n + 0.5) / lines;
	float h = 1.0 / lines;
	vec3 s = vec3(0.0);
	for (int i = -1; i <= 1; i++) {
		float y = v + float(i) * h / 3.0;
		s += 0.5 * src(vec2(x - 0.6 * ps.x, y)) + 0.5 * src(vec2(x + 0.6 * ps.x, y));
	}
	return s / 3.0;
}

// Strahlprofil: helle Zeilen werden breiter (wie beim echten Elektronenstrahl)
vec3 beam(float d, vec3 c) {
	vec3 w = 0.22 + 0.2 * pow(c, vec3(1.5));
	vec3 x = d / w;
	return exp(-x * x * 0.5);
}

// Lochmaske: RGB-Leuchtpunkte je 1 px (Tripel 3 px); jede zweite Pixelzeile dunkel, je Tripelpaar um
// eine Zeile versetzt. So entstehen versetzte Punktreihen wie bei einer Lochmaske (nach dem bekannten
// Schattenmasken-Muster aus quelloffenen CRT-Shadern nachgebaut).
vec3 shadow_mask(vec2 p) {
	float odd = fract(p.x / 6.0) < 0.5 ? 1.0 : 0.0;
	float row = fract((p.y + odd) / 2.0) < 0.5 ? mask_row : 1.0;
	float k = fract(p.x / 3.0);
	vec3 m = vec3(mask_dark);
	if (k < 0.333) {
		m.r = mask_light;
	} else if (k < 0.666) {
		m.g = mask_light;
	} else {
		m.b = mask_light;
	}
	return m * row;
}

void fragment() {
	vec2 ps = TEXTURE_PIXEL_SIZE;
	vec3 plain = src(UV);
	vec3 col = plain;
	if (crt > 0.5) {
		vec2 uv = warp(UV);
		float y = uv.y * lines - 0.5;
		float n0 = floor(y);
		float f = y - n0;
		vec3 a = scan_line(uv.x, n0, ps);
		vec3 b = scan_line(uv.x, n0 + 1.0, ps);
		vec3 c = a * beam(f, a) + b * beam(1.0 - f, b);
		// Nachleuchten: grobe Unschärfe des Bildes dazu
		vec3 halo = vec3(0.0);
		for (int i = 0; i < 8; i++) {
			float ang = float(i) * 0.785398;
			halo += src(uv + vec2(cos(ang), sin(ang)) * vec2(9.0, 7.0) * ps);
		}
		c += glow * halo / 8.0 * 0.55;
		c *= shadow_mask(floor(UV / ps));
		c *= 1.5;
		// Abschattung zum Rand der Röhre und abgerundete Ecken
		vec2 e = uv * (1.0 - uv.yx);
		float vig = pow(clamp(e.x * e.y * 16.0, 0.0, 1.0), 0.22);
		c *= vig;
		vec2 cd = abs(uv * 2.0 - 1.0);
		vec2 ar = vec2(1280.0 / 720.0, 1.0);
		vec2 corner = max(cd * ar - (ar - 0.07), 0.0);
		float edge = 1.0 - smoothstep(0.065, 0.072, length(corner));
		edge *= step(0.0, uv.x) * step(uv.x, 1.0) * step(0.0, uv.y) * step(uv.y, 1.0);
		// leichtes Flimmern der Zeilenhelligkeit (50-Hz-Gefühl), deterministisch über time_s
		c *= 1.0 + 0.015 * sin(time_s * 61.0 + uv.y * 3.0);
		vec3 bezel = vec3(0.012, 0.012, 0.014);
		col = mix(bezel, c, edge);
	}
	COLOR = vec4(col, 1.0);
}
