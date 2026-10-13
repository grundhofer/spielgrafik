shader_type canvas_item;
render_mode unshaded;
// Bildaufbau wie die Bildeinheit (PPU) einer 8-Bit-Heimkonsole, Pixel für Pixel aus ihrem Speicher:
//   Musterspeicher (CHR) in 1-KB-Bänken zu je 64 Kacheln 8x8 mit 2 Bit je Pixel, acht Bankfenster je Bildzeile
//   (0-3 Hintergrund, 4-7 Sprites; Umschalten wie mit einem Mapper-Baustein), zwei Namenstabellen 32x30
//   nebeneinander, Attribute je 16x16-Block (Palette 0-3), Paletten-RAM mit 32 Einträgen (Nummern der
//   festen Systempalette), 64 Sprite-Einträge (OAM) im 8x16-Modus, Scroll-Register je Bildzeile.
// Gezeigt werden die Zeilen 8-231 (256x224). GDScript beschreibt den Speicher jedes Bild; hier wird nur gerechnet.

uniform sampler2D chr : filter_nearest;      // 128 x (32*Bänke), R8: Farbnummer 0..3, 16 Kacheln je Zeile
uniform sampler2D nt : filter_nearest;       // 64x30, R8: Kachelnummer (Namenstabelle 0 links, 1 rechts)
uniform sampler2D attr : filter_nearest;     // 32x15, R8: Palette 0..3 je 16x16-Block
uniform sampler2D pal : filter_nearest;      // 32x1, R8: Paletten-RAM (Systemfarbnummern 0..63)
uniform sampler2D syspal : filter_nearest;   // 64x1, RGB: feste Systempalette
uniform sampler2D oam : filter_nearest;      // 64x1, RGBA8: Y, Kachel, Attribute, X
uniform sampler2D lines : filter_nearest;    // 224x3, RGBA8: Zeile 0 Scroll X lo, Namenstabelle, Scroll Y, Schalter
                                             //               Zeile 1/2 Bankfenster 0-3 / 4-7

int byte_at(sampler2D s, ivec2 p) {
	return int(round(texelFetch(s, p, 0).r * 255.0));
}

ivec4 bytes4(sampler2D s, ivec2 p) {
	return ivec4(round(texelFetch(s, p, 0) * 255.0));
}

// Pixel einer Kachel: tile 0..511 (0-255 Musterspeicher $0000, 256-511 $1000), über die Bankfenster der Zeile
int chr_px(int tile, int x, int y, ivec4 banks_lo, ivec4 banks_hi) {
	int slot = tile >> 6;
	int bank;
	if (slot == 0) bank = banks_lo.x;
	else if (slot == 1) bank = banks_lo.y;
	else if (slot == 2) bank = banks_lo.z;
	else if (slot == 3) bank = banks_lo.w;
	else if (slot == 4) bank = banks_hi.x;
	else if (slot == 5) bank = banks_hi.y;
	else if (slot == 6) bank = banks_hi.z;
	else bank = banks_hi.w;
	int g = bank * 64 + (tile & 63);
	return byte_at(chr, ivec2((g % 16) * 8 + x, (g / 16) * 8 + y));
}

void fragment() {
	int lx = int(floor(UV.x * 256.0));
	int ly = int(floor(UV.y * 224.0));
	int line = ly + 8;                       // Bildzeile der Konsole (0-239)
	ivec4 reg = bytes4(lines, ivec2(ly, 0));
	ivec4 banks_lo = bytes4(lines, ivec2(ly, 1));
	ivec4 banks_hi = bytes4(lines, ivec2(ly, 2));
	int flags = reg.w;

	// Hintergrund
	int bg_c = 0;
	int bg_p = 0;
	if ((flags & 1) != 0) {
		int sx = (lx + reg.x + reg.y * 256) & 511;
		int sy = (line + reg.z) % 240;
		int ntx = sx >> 3;
		int tile = byte_at(nt, ivec2(ntx, sy >> 3));
		bg_c = chr_px(tile, sx & 7, sy & 7, banks_lo, banks_hi);
		bg_p = byte_at(attr, ivec2(sx >> 4, sy >> 4));
	}
	int pal_index = bg_c == 0 ? 0 : bg_p * 4 + bg_c;

	// Sprites: nur die ersten 8 OAM-Einträge, die diese Zeile treffen, werden ausgewertet (Hardwaregrenze).
	// Der erste deckende Sprite in OAM-Reihenfolge gewinnt; liegt er hinter dem Hintergrund (Attribut-Bit 5),
	// verdeckt ihn jeder nicht durchsichtige Hintergrundpixel.
	if ((flags & 2) != 0) {
		int found = 0;
		for (int i = 0; i < 64; i++) {
			ivec4 o = bytes4(oam, ivec2(i, 0));
			int top = o.x + 1;               // Sprites erscheinen eine Zeile unter ihrem Y-Wert
			int dy = line - top;
			if (o.x >= 239 || dy < 0 || dy >= 16) {
				continue;
			}
			found += 1;
			if (found > 8) {
				break;
			}
			int dx = lx - o.w;
			if (dx < 0 || dx >= 8) {
				continue;
			}
			int at = o.z;
			if ((at & 64) != 0) dx = 7 - dx;
			if ((at & 128) != 0) dy = 15 - dy;
			int base = (o.y & 1) * 256 + (o.y & 254);
			int c = chr_px(base + dy / 8, dx, dy % 8, banks_lo, banks_hi);
			if (c == 0) {
				continue;
			}
			if ((at & 32) == 0 || bg_c == 0) {
				pal_index = 16 + (at & 3) * 4 + c;
			}
			break;
		}
	}
	int color = byte_at(pal, ivec2(pal_index, 0)) & 63;
	COLOR = vec4(texelFetch(syspal, ivec2(color, 0), 0).rgb, 1.0);
}
