shader_type canvas_item;
render_mode unshaded;
// Rasterstraße: Jede Bildzeile ist eine Zeile der Tabelle "lines" (5 Texel breit, 224 hoch), die main.gd
// je Bild neu schreibt. Der Shader liest nur seine Zeile und entscheidet je Pixel nach dem Abstand zur
// Straßenmitte: Straße, Kantenstein, Seitenfläche (Gras oder Wasser). Hell/Dunkel nach Weltposition s.
//   Texel 0: Mitte x (px), halbe Straßenbreite (px), Kantensteinbreite (px), Art (0 leer, 1 Straße, 2 Meer)
//   Texel 1: s (m), z (m), Material links, Material rechts (0 Wasser, 1 Gras)
//   Texel 2: Belag (0 Pflaster, 1 Planken), Pixel je Meter, -, -
//   Texel 3/4: Wasserfarbe hell/dunkel dieser Zeile (5-Bit-Werte, Spiegelung des Himmels nach Entfernung)

uniform sampler2D lines : filter_nearest;
uniform sampler2D pal : filter_nearest;     // 16×1, Farben in 5-Bit-Stufen
uniform float wave = 0.0;                   // Wellenphase in Metern (Wasserstreifen laufen schneller)
uniform int tick = 0;                       // Bildzähler für das Glitzern (15 Hz)
uniform bool stripes = true;                // Vergleichsschalter --nostripes

varying vec2 px;

void vertex() {
	px = VERTEX;
}

vec3 P(int i) {
	return texelFetch(pal, ivec2(i, 0), 0).rgb;
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void fragment() {
	int row = int(floor(px.y));
	vec4 a = texelFetch(lines, ivec2(0, row), 0);
	vec4 b = texelFetch(lines, ivec2(1, row), 0);
	vec4 c = texelFetch(lines, ivec2(2, row), 0);
	vec3 wa = texelFetch(lines, ivec2(3, row), 0).rgb;
	vec3 wb = texelFetch(lines, ivec2(4, row), 0).rgb;
	float kind = a.w;
	if (kind < 0.5) {
		discard;
	}
	float x = floor(px.x) + 0.5;
	float s = b.x;
	float ppm = c.y;
	// Wasser: Streifen 2,5 m, laufen mit eigener Phase (Wellen kommen auf die Kamera zu)
	float wpar = mod(floor((s + wave) / 2.5), 2.0);
	vec3 water = (wpar < 0.5 || !stripes) ? wa : wb;
	// Glitzern: einzelne helle Pixel in fernen Wasserzeilen, wechseln mit 15 Hz
	float gl = hash(vec2(floor(x / 2.0), float(row) + float(tick) * 17.0));
	float far = clamp((b.y - 25.0) / 120.0, 0.0, 1.0);
	if (gl > 1.0 - 0.035 * far) {
		water = P(12);
	}
	vec3 col = water;
	if (kind < 1.5) {
		float dx = x - a.x;
		float ad = abs(dx);
		float hw = a.y;
		float kw = max(a.z, 1.0);
		if (ad < hw) {
			if (c.x < 0.5) {
				// Pflaster: Bänder 2 m hell/dunkel, Steinreihen alle 0,5 m mit Fuge (nur wo sie mindestens
				// 1 px breit wären), Mittelrinne aus hellem Granit nur in den hellen Bändern
				float p = mod(floor(s / 2.0), 2.0);
				col = (p < 0.5 || !stripes) ? P(0) : P(1);
				float rowq = s / 0.5;
				if (stripes && ppm > 9.0 && fract(rowq) < 0.12) {
					col = P(p < 0.5 ? 15 : 3);
				}
				float u = dx / ppm + 0.25 * mod(floor(rowq), 2.0);
				if (stripes && ppm > 18.0 && fract(u / 0.5) < 0.06) {
					col = P(p < 0.5 ? 15 : 3);
				}
				if (ad < max(0.6, 0.09 * ppm) && p < 0.5) {
					col = P(11);
				}
			} else {
				// Planken: 0,4 m, dunkle Fuge am Anfang jeder Planke
				float q = s / 0.4;
				float p = mod(floor(q), 2.0);
				col = (p < 0.5 || !stripes) ? P(8) : P(9);
				if (fract(q) < 0.14 && stripes) {
					col = P(10);
				}
			}
		} else if (ad < hw + kw) {
			// Kantensteine: 1 m hell/dunkel (bei Planken: Randbalken)
			float p = mod(floor(s / 1.0), 2.0);
			if (c.x < 0.5) {
				col = (p < 0.5 || !stripes) ? P(2) : P(3);
			} else {
				col = P(13);
			}
		} else {
			float m = dx < 0.0 ? b.z : b.w;
			if (m > 0.5) {
				float p = mod(floor(s / 3.0), 2.0);
				col = (p < 0.5 || !stripes) ? P(4) : P(5);
			} else {
				// schmaler Schattenstreifen an der Kaimauer
				if (ad < hw + kw + max(1.0, 0.25 * ppm) && c.x < 0.5) {
					col = P(14);
				}
			}
		}
	}
	COLOR = vec4(col, 1.0);
}
