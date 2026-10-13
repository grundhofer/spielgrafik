// Zeichengenerator einer Videotextseite (nach SAA5050): 40 × 25 Zellen à 20 × 28 Bildpunkte.
// Je Zelle liefert der Decoder (main.gd) ein RGBA8-Texel:
//   R = Zeichencode 0x20–0x7F (Text) bzw. Mosaikmuster 0–63
//   G = Vordergrund (Bit 0–2) | Hintergrund (Bit 3–5), Farben nach Videotext-Nummer (Bits B G R)
//   B = Art (Bit 0–1: 0 leer, 1 Text, 2 Mosaik) | getrennt (Bit 2) | Flash (Bit 3) | Hälfte (Bit 4–5: 0 normal,
//       1 obere, 2 untere Hälfte doppelter Höhe)
shader_type canvas_item;

uniform sampler2D cells : filter_nearest;
uniform sampler2D atlas : filter_nearest;
uniform bool flash_on = true;

const vec3 PAL[8] = vec3[8](vec3(0.0, 0.0, 0.0), vec3(1.0, 0.0, 0.0), vec3(0.0, 1.0, 0.0), vec3(1.0, 1.0, 0.0),
                            vec3(0.0, 0.0, 1.0), vec3(1.0, 0.0, 1.0), vec3(0.0, 1.0, 1.0), vec3(1.0, 1.0, 1.0));

void fragment() {
	ivec2 p = ivec2(floor(UV * vec2(800.0, 700.0)));
	ivec2 cell = p / ivec2(20, 28);
	ivec2 lp = p - cell * ivec2(20, 28);
	vec4 c = texelFetch(cells, cell, 0);
	int code = int(round(c.r * 255.0));
	int colors = int(round(c.g * 255.0));
	int flags = int(round(c.b * 255.0));
	int fg = colors & 7;
	int bg = (colors >> 3) & 7;
	int kind = flags & 3;
	bool sep = (flags & 4) != 0;
	bool fl = (flags & 8) != 0;
	int part = (flags >> 4) & 3;
	// Glyphe vor allen Verzweigungen holen (Atlas: 16 Zeichen je Zeile, Blöcke für normal/oben/unten)
	int gi = clamp(code - 32, 0, 95);
	ivec2 ap = ivec2((gi % 16) * 20 + lp.x, (gi / 16) * 28 + lp.y + part * 168);
	float glyph = texelFetch(atlas, ap, 0).r;
	float cov = 0.0;
	if (kind == 1) {
		cov = glyph;
	} else if (kind == 2) {
		int k = part == 0 ? 1 : 2;                 // doppelte Höhe: Sechstel doppelt so hoch
		int y = part == 2 ? lp.y + 28 : lp.y;
		int sy = y < 8 * k ? 0 : (y < 20 * k ? 1 : 2);
		int y1 = sy == 0 ? 8 * k : (sy == 1 ? 20 * k : 28 * k);
		int sx = lp.x < 10 ? 0 : 1;
		int x1 = sx * 10 + 10;
		bool on = ((code >> (sy * 2 + sx)) & 1) == 1;
		if (sep && (lp.x >= x1 - 3 || y >= y1 - 3 * k)) {
			on = false;                            // getrennte Mosaike: 3 px Lücke rechts und unten
		}
		cov = on ? 1.0 : 0.0;
	}
	if (fl && !flash_on) {
		cov = 0.0;                                 // Flash: in der Aus-Phase nur Hintergrund
	}
	COLOR = vec4(mix(PAL[bg], PAL[fg], cov), 1.0);
}
