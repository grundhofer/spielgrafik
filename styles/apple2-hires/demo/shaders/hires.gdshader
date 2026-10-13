// Farbmodell der Hi-Res-Grafik eines 8-Bit-Heimcomputers am NTSC-Farbfernseher (Katalogeintrag apple2-hires).
//
// mem_tex: 40 × 192 Bytes, wie der Bildspeicher: Bit 0–6 = 7 Bildpunkte (Bit 0 links), Bit 7 = Farbgruppe.
// Jeder Bildpunkt sind zwei Halbpunkte des 560er-Signals; bei Bit 7 = 1 kommen sie einen Halbpunkt später,
// die Lücke am Byte-Anfang hält den letzten Halbpunkt des Byte davor. Die Farbe ergibt sich aus dem Fenster von
// 4 Halbpunkten um den Bildpunkt (eine Periode des Farbträgers): gesetzte Phasen 0–3 -> Index in PAL.
//   model 0 "fringe": Fenster für jeden Bildpunkt (auch dunkle Säume neben Linien)
//   model 1 "crisp":  Fenster nur für gesetzte Punkte und Lücken zwischen zwei gesetzten, sonst Schwarz
//   model 2 "ideal":  nur die sechs Farben, ohne Säume
// Ergebnis bei allen: Einzelpunkt farbig je nach Spalte und Gruppe, Nachbarn weiß, 1010 = volle Farbfläche.
// text_mono 1: Prüfschalter, nur die Textzeilen 160–191 einfarbig (gesetzt = Weiß), wie am Monochrom-Monitor;
//   bewusste Abweichung für die Lesbarkeit, die Demo zeigt standardmäßig das Farbmodell auch im Text.
shader_type canvas_item;
render_mode unshaded;

uniform sampler2D mem_tex : filter_nearest;
uniform int model = 1;
uniform int text_mono = 0;

const vec3 PAL[16] = vec3[16](
	vec3(0.0, 0.0, 0.0),
	vec3(144.0, 23.0, 64.0) / 255.0,
	vec3(64.0, 44.0, 165.0) / 255.0,
	vec3(208.0, 67.0, 229.0) / 255.0,
	vec3(0.0, 105.0, 64.0) / 255.0,
	vec3(128.0, 128.0, 128.0) / 255.0,
	vec3(47.0, 149.0, 229.0) / 255.0,
	vec3(191.0, 171.0, 255.0) / 255.0,
	vec3(64.0, 84.0, 0.0) / 255.0,
	vec3(208.0, 106.0, 26.0) / 255.0,
	vec3(128.0, 128.0, 128.0) / 255.0,
	vec3(255.0, 150.0, 191.0) / 255.0,
	vec3(47.0, 188.0, 26.0) / 255.0,
	vec3(191.0, 211.0, 90.0) / 255.0,
	vec3(111.0, 232.0, 191.0) / 255.0,
	vec3(1.0, 1.0, 1.0)
);

int byte_at(int b, int y) {
	if (b < 0 || b > 39) {
		return 0;
	}
	return int(texelFetch(mem_tex, ivec2(b, y), 0).r * 255.0 + 0.5);
}

int bit_at(int x, int y) {
	if (x < 0 || x > 279) {
		return 0;
	}
	return (byte_at(x / 7, y) >> (x % 7)) & 1;
}

int dot_at(int d, int y) {
	if (d < 0 || d > 559) {
		return 0;
	}
	int b = d / 14;
	int v = byte_at(b, y);
	if ((v & 128) == 0) {
		return (v >> (d / 2 - 7 * b)) & 1;
	}
	if (d == 14 * b) {
		return bit_at(7 * b - 1, y);
	}
	return (v >> ((d - 1) / 2 - 7 * b)) & 1;
}

int group_colour(int x, int h) {
	if (h == 1) {
		return (x % 2 == 0) ? 6 : 9;
	}
	return (x % 2 == 0) ? 3 : 12;
}

void fragment() {
	ivec2 p = ivec2(floor(UV * vec2(280.0, 192.0)));
	int x = clamp(p.x, 0, 279);
	int y = clamp(p.y, 0, 191);
	int v = byte_at(x / 7, y);
	int h = (v >> 7) & 1;
	int on = (v >> (x % 7)) & 1;
	int l = bit_at(x - 1, y);
	int r = bit_at(x + 1, y);
	int nib = 0;
	if (model == 2) {
		if (on == 1) {
			nib = (l == 1 || r == 1) ? 15 : group_colour(x, h);
		} else if (l == 1 && r == 1) {
			nib = group_colour(x - 1, (byte_at((x - 1) / 7, y) >> 7) & 1);
		}
	} else {
		int s = 2 * x + h - 1;
		for (int k = 0; k < 4; k++) {
			int dd = s + k;
			if (dot_at(dd, y) == 1) {
				nib |= 1 << ((dd + 4) % 4);
			}
		}
		if (model == 1 && on == 0 && !(l == 1 && r == 1)) {
			nib = 0;
		}
	}
	if (text_mono == 1 && y >= 160) {
		nib = (on == 1) ? 15 : 0;
	}
	COLOR = vec4(PAL[nib], 1.0);
}
