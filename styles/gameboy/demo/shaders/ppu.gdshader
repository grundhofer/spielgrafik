shader_type canvas_item;
render_mode unshaded;
// Bildaufbau wie die Grafikeinheit des Handhelds (DMG), Pixel für Pixel aus dem Videospeicher:
//   Kacheln 8x8 mit 2 Bit je Pixel (384 Plätze), Hintergrund- und Window-Karte je 32x32 Kacheln,
//   40 Sprite-Einträge (OAM) im 8x16-Modus, Register je Bildzeile (SCX, SCY, Window-Zeile).
// GDScript schreibt diese Speicher jedes Bild neu (wie das Spiel im VBlank); der Shader rechnet nur nach.

uniform sampler2D vram : filter_nearest;      // 128x192, R8: Farbnummer 0..3, 16 Kacheln je Zeile
uniform sampler2D bg_map : filter_nearest;    // 32x32, R8: Kachelnummer
uniform sampler2D win_map : filter_nearest;   // 32x32, R8: Kachelnummer
uniform sampler2D oam : filter_nearest;       // 40x1, RGBA8: Y+16, X+8, Kachel, Attribute
uniform sampler2D lines : filter_nearest;     // 144x1, RGBA8: SCX, SCY, Window-Zeile (255 = aus), Flags
uniform int bgp = 228;                        // Paletten-Register (0xE4: Farbe n -> Ton n)
uniform int obp0 = 228;
uniform int obp1 = 228;
uniform int wx = 7;                           // Window-Spalte + 7 wie im Register WX
uniform vec3 shade0 : source_color = vec3(0.608, 0.737, 0.059);   // 9bbc0f (hellster Ton)
uniform vec3 shade1 : source_color = vec3(0.545, 0.675, 0.059);   // 8bac0f
uniform vec3 shade2 : source_color = vec3(0.188, 0.384, 0.188);   // 306230
uniform vec3 shade3 : source_color = vec3(0.059, 0.220, 0.059);   // 0f380f (dunkelster Ton)

int byte_of(float v) {
	return int(round(v * 255.0));
}

int tile_px(int slot, int x, int y) {
	ivec2 p = ivec2((slot % 16) * 8 + x, (slot / 16) * 8 + y);
	return byte_of(texelFetch(vram, p, 0).r);
}

// Hintergrund und Window adressieren wie LCDC.4 = 0: Nummer 0..127 -> Platz 256..383, 128..255 -> 128..255
int bg_slot(int id) {
	return id < 128 ? 256 + id : id;
}

vec3 shade(int s) {
	if (s == 0) return shade0;
	if (s == 1) return shade1;
	if (s == 2) return shade2;
	return shade3;
}

void fragment() {
	int lx = int(floor(UV.x * 160.0));
	int ly = int(floor(UV.y * 144.0));
	vec4 reg = texelFetch(lines, ivec2(ly, 0), 0);
	int scx = byte_of(reg.r);
	int scy = byte_of(reg.g);
	int wline = byte_of(reg.b);
	int flags = byte_of(reg.a);

	int col = 0;
	if (wline != 255 && lx >= wx - 7) {
		int wxp = lx - (wx - 7);
		int id = byte_of(texelFetch(win_map, ivec2(wxp / 8, wline / 8), 0).r);
		col = tile_px(bg_slot(id), wxp % 8, wline % 8);
	} else if ((flags & 1) != 0) {
		int bx = (lx + scx) & 255;
		int by = (ly + scy) & 255;
		int id = byte_of(texelFetch(bg_map, ivec2(bx / 8, by / 8), 0).r);
		col = tile_px(bg_slot(id), bx % 8, by % 8);
	}
	int s = (bgp >> (col * 2)) & 3;

	if ((flags & 2) != 0) {
		// Sprites: die ersten 10 Einträge der OAM, die diese Zeile treffen (Hardwaregrenze).
		// Vorrang wie beim DMG: kleineres X gewinnt, bei gleichem X der frühere Eintrag;
		// Farbe 0 ist durchsichtig und lässt den nächsten Sprite durch.
		int count = 0;
		int best_x = 999;
		int best_c = 0;
		int best_attr = 0;
		for (int i = 0; i < 40; i++) {
			vec4 o = texelFetch(oam, ivec2(i, 0), 0);
			int sy = byte_of(o.r) - 16;
			if (ly < sy || ly >= sy + 16) {
				continue;
			}
			count += 1;
			if (count > 10) {
				break;
			}
			int ox = byte_of(o.g);
			int sx = ox - 8;
			if (lx < sx || lx >= sx + 8 || ox >= best_x) {
				continue;
			}
			int attr = byte_of(o.a);
			int ty = ly - sy;
			if ((attr & 64) != 0) ty = 15 - ty;
			int tx = lx - sx;
			if ((attr & 32) != 0) tx = 7 - tx;
			int t = (byte_of(o.b) & 254) + ty / 8;
			int c = tile_px(t, tx, ty % 8);
			if (c == 0) {
				continue;
			}
			best_x = ox;
			best_c = c;
			best_attr = attr;
		}
		if (best_c != 0 && ((best_attr & 128) == 0 || col == 0)) {
			int pal = (best_attr & 16) != 0 ? obp1 : obp0;
			s = (pal >> (best_c * 2)) & 3;
		}
	}
	COLOR = vec4(shade(s), 1.0);
}
