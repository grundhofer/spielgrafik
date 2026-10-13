// Mode 7 wie in der PPU der 16-Bit-Konsole: eine einzige Ebene aus einer 128×128-Kachelkarte mit höchstens
// 256 Kacheln à 8×8 Texel (8 Bit = CGRAM-Index je Texel). Je Bildzeile setzt die HDMA-Tabelle (224×1,
// RGBA = A, B, C, D als 8.8-Festkomma) eine eigene Matrix; daraus entsteht die Perspektive. Gerechnet wird
// ganzzahlig wie in der Hardware (bsnes ppu-fast mode7.cpp): Ursprung je Zeile mit abgeschnittenen
// unteren 6 Bit, dann je Pixel + A bzw. + C, Texel = Wert >> 8, Abtastung ohne Filter und ohne Mipmaps.
// Außerhalb der 1024×1024-Karte gilt Kachel 0 (M7SEL = 11). Danach Farbmathematik wie per HDMA: zur
// CGRAM-Farbe wird je Zeile eine feste Farbe addiert (Dunst zum Horizont), Ergebnis auf 5 Bit begrenzt.
shader_type canvas_item;
render_mode unshaded, blend_disabled;

uniform sampler2D tilemap : filter_nearest, repeat_disable;   // 128×128, L8: Kachelnummer
uniform sampler2D tiles : filter_nearest, repeat_disable;     // 128×128, L8: 16×16 Kacheln
uniform sampler2D cgram : filter_nearest, repeat_disable;     // 256×1, RGB (5-Bit-Werte ×255/31)
uniform sampler2D hdma : filter_nearest, repeat_disable;      // 224×1, RGBAF: A, B, C, D
uniform sampler2D fixcol : filter_nearest, repeat_disable;    // 224×1, RGBF: Farbmathematik-Addend (0..31)
uniform int x0;
uniform int y0;
uniform int hofs;
uniform int vofs;
uniform int row0;      // erste Bildzeile dieses Rechtecks
uniform int rows;      // Höhe des Rechtecks in Zeilen

int clip13(int n) {
	return (n & 0x2000) != 0 ? (n | ~1023) : (n & 1023);
}

void fragment() {
	int x = int(floor(UV.x * 256.0));
	int y = row0 + int(floor(UV.y * float(rows)));
	vec4 m = texelFetch(hdma, ivec2(y, 0), 0);
	int a = int(round(m.r));
	int b = int(round(m.g));
	int c = int(round(m.b));
	int d = int(round(m.a));
	int ch = clip13(hofs - x0);
	int cv = clip13(vofs - y0);
	int ox = ((a * ch) & ~63) + ((b * cv) & ~63) + ((b * y) & ~63) + (x0 << 8);
	int oy = ((c * ch) & ~63) + ((d * cv) & ~63) + ((d * y) & ~63) + (y0 << 8);
	int px = (ox + a * x) >> 8;
	int py = (oy + c * x) >> 8;
	bool oob = ((px | py) & ~1023) != 0;
	int tile = int(round(texelFetch(tilemap, ivec2((px >> 3) & 127, (py >> 3) & 127), 0).r * 255.0));
	tile = oob ? 0 : tile;
	ivec2 tp = ivec2((tile & 15) * 8 + (px & 7), (tile >> 4) * 8 + (py & 7));
	int idx = int(round(texelFetch(tiles, tp, 0).r * 255.0));
	vec3 col = texelFetch(cgram, ivec2(idx, 0), 0).rgb;
	// Farbmathematik: Addition einer festen Farbe je Zeile, Sättigung bei 31 (5 Bit)
	vec3 c5 = round(col * 31.0);
	vec3 add = texelFetch(fixcol, ivec2(y, 0), 0).rgb;
	c5 = min(c5 + add, vec3(31.0));
	// genau k/255 ausgeben: Compatibility rundet beim Schreiben ab, Forward+ zur nächsten Stufe
	COLOR = vec4(round(c5 * 255.0 / 31.0) / 255.0, 1.0);
}
