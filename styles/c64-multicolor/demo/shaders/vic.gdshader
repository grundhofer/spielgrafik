// Videochip eines 8-Bit-Heimcomputers, vereinfacht nachgebildet (Katalogeintrag c64-multicolor).
// Ein Bildpunkt je Fragment im 384x240-Bild (sichtbarer Rahmen 32 links/rechts, 20 oben/unten, Bild 320x200).
// Je Rasterzeile: Hintergrundfarbe ($D021), Rahmenfarbe ($D020), Modus (0 = Multicolor-Bitmap, 1 = Hires-Text).
// Multicolor-Bitmap: Bitpaar 00 = Zeilen-Hintergrund, 01 = Bildschirmspeicher oberes Halbbyte,
//                    10 = Bildschirmspeicher unteres Halbbyte, 11 = Farbspeicher (je 4x8-Zelle).
// Text: Zeichencode aus dem Bildschirmspeicher, Zeichenfarbe aus dem Farbspeicher, Papier = Zeilen-Hintergrund.
// Sprites: Tabelle mit bis zu 16 Einträgen (nach Hardware-Nummer sortiert, Multiplexer in main.gd):
//   Zeile 0: x, y (Koordinaten des Chips), Formnummer, Farbe; Zeile 1: Multicolor, X-Dehnung, Y-Dehnung,
//   Priorität hinter Vordergrund. Der Sprite mit der kleinsten Nummer, der an der Stelle deckt, entscheidet.
shader_type canvas_item;
render_mode unshaded;

uniform sampler2D bitmap_tex : filter_nearest;    // 160x200, L8: Bitpaar 0-3
uniform sampler2D cells_tex : filter_nearest;     // 40x25, RGBA8: R = Bildschirmspeicher, G = Farbspeicher
uniform sampler2D raster_tex : filter_nearest;    // 1x240, RGBA8: R = $D021, G = $D020, B = Modus
uniform sampler2D font_tex : filter_nearest;      // 8x2048, L8: 0/1
uniform sampler2D sprite_tex : filter_nearest;    // 24x(21*n), L8: 0-3 (hires 0/1)
uniform sampler2D sprite_regs : filter_nearest;   // 16x2, RGBAF
uniform sampler2D palette_tex : filter_nearest;   // 16x1, RGBA8
uniform int sprite_count = 0;
uniform int mc0 = 1;
uniform int mc1 = 11;
uniform int only_sprites = 0;                      // Prüfmodus: Hintergrund durch Farbe key_color ersetzen
uniform int no_sprites = 0;
uniform int key_color = 14;

int byte_at(sampler2D t, ivec2 p) {
	return int(texelFetch(t, p, 0).r * 255.0 + 0.5);
}

vec3 pal(int i) {
	return texelFetch(palette_tex, ivec2(i & 15, 0), 0).rgb;
}

void fragment() {
	ivec2 p = ivec2(floor(UV * vec2(384.0, 240.0)));
	vec4 rr = texelFetch(raster_tex, ivec2(0, p.y), 0);
	int bg = int(rr.r * 255.0 + 0.5);
	int border = int(rr.g * 255.0 + 0.5);
	int mode = int(rr.b * 255.0 + 0.5);
	int sx = p.x - 32;
	int sy = p.y - 20;
	int col = border;
	if (sx >= 0 && sx < 320 && sy >= 0 && sy < 200) {
		ivec2 cell = ivec2(sx / 8, sy / 8);
		vec4 cc = texelFetch(cells_tex, cell, 0);
		int scr = int(cc.r * 255.0 + 0.5);
		int cram = int(cc.g * 255.0 + 0.5) & 15;
		bool fg;
		if (mode == 0) {
			int v = byte_at(bitmap_tex, ivec2(sx / 2, sy));
			col = v == 0 ? bg : (v == 1 ? (scr >> 4) : (v == 2 ? (scr & 15) : cram));
			fg = v >= 2;
		} else {
			int bit = byte_at(font_tex, ivec2(sx & 7, scr * 8 + (sy & 7)));
			col = bit != 0 ? cram : bg;
			fg = bit != 0;
		}
		if (only_sprites != 0) {
			col = key_color;
			fg = false;
		}
		if (no_sprites == 0) {
			int cx = sx + 24;     // Sprite-Koordinaten des Chips: erstes sichtbares Pixel x = 24, y = 50
			int cy = sy + 50;
			for (int i = 0; i < 16; i++) {
				if (i >= sprite_count) {
					break;
				}
				vec4 a = texelFetch(sprite_regs, ivec2(i, 0), 0);
				vec4 f = texelFetch(sprite_regs, ivec2(i, 1), 0);
				int lx = cx - int(a.x);
				int ly = cy - int(a.y);
				int w = f.y > 0.5 ? 48 : 24;
				int h = f.z > 0.5 ? 42 : 21;
				if (lx < 0 || lx >= w || ly < 0 || ly >= h) {
					continue;
				}
				if (f.y > 0.5) { lx /= 2; }
				if (f.z > 0.5) { ly /= 2; }
				int v = byte_at(sprite_tex, ivec2(lx, int(a.z) * 21 + ly));
				if (v == 0) {
					continue;
				}
				int sc = int(a.w);
				if (f.x > 0.5) {
					sc = v == 1 ? mc0 : (v == 2 ? int(a.w) : mc1);
				}
				if (!(f.w > 0.5 && fg)) {
					col = sc;
				}
				break;
			}
		}
	}
	COLOR = vec4(pal(col), 1.0);
}
