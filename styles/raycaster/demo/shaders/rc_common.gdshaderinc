// Gemeinsame Regeln der Sektor-Engines: Lichtstufe aus Sektorlicht und Entfernung, Farbtabelle.
// Ergebnis ist immer eine Palettenfarbe (Zeile 0 von palette.png). shaders/screen.gdshader rastet die
// Ausgabe zusätzlich auf die Palette ein (gleicht Rundung in Mobile/Compatibility aus) und setzt den
// Himmel dort ein, wo nichts gezeichnet wurde (Alpha 0).

uniform sampler2D colormap : filter_nearest;            // 256 x 32, Wert = Palettenindex
uniform sampler2D palette : source_color, filter_nearest;
const float RC_UNITS_PER_M = 32.0;                      // eine Karteneinheit = ein Texel = 1/32 m

vec3 rc_out(float index) {
	return texelFetch(palette, ivec2(int(index), 0), 0).rgb;
}

// Lichtstufe 0 (hell) … 31 (dunkel). light 0–255, contrast −1/0/+1 (Wandrichtung),
// is_flat = Boden (Tabelle nach Entfernung) statt Wand/Sprite (Tabelle nach Maßstab).
int rc_level(float light, int contrast, float depth_m, bool is_flat) {
	int lightnum = clamp((int(light + 0.5) >> 4) + contrast, 0, 15);
	int startmap = (15 - lightnum) * 4;
	float units = max(depth_m * RC_UNITS_PER_M, 1.0);
	int sub;
	if (is_flat) {
		int j = min(int(units / 16.0), 127);
		sub = (160 / (j + 1)) / 2;
	} else {
		sub = min(int(2560.0 / units), 47) / 2;
	}
	return clamp(startmap - sub, 0, 31);
}

float rc_shade(int index, int level) {
	return floor(texelFetch(colormap, ivec2(index, level), 0).r * 255.0 + 0.5);
}
