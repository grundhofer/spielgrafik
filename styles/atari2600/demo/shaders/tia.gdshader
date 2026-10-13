shader_type canvas_item;
render_mode unshaded;
// Bildaufbau wie der Videochip der zweiten Konsolengeneration (NTSC, 160 Pixel je Zeile, 192 Zeilen).
// Es gibt keinen Bildspeicher: Für jede Zeile liegen nur die Register vor, die das Programm („Kernel“,
// scripts/main.gd) in dieser Zeile gesetzt hat. Der Shader rechnet daraus jedes Pixel:
//   Playfield  40 Blöcke je 4 Pixel (40 Bit je Zeile), Farbe COLUPF (auf Wunsch ab Pixel SPLIT eine zweite,
//              wie ein Schreibzugriff mitten in der Zeile)
//   Spieler    2 x 8 Bit (GRP0/GRP1), eine Farbe je Zeile, NUSIZ: 1-3 Kopien oder 2-/4-fache Breite, Spiegelung
//   Missiles   2 Striche (1/2/4/8 Pixel) in der Farbe ihres Spielers, kopiert mit dem Spieler
//   Ball       1 Strich (1/2/4/8 Pixel) in der Playfield-Farbe
//   Vorrang    Spieler 0 > Spieler 1 > Playfield/Ball > Hintergrund (CTRLPF Bit 2 dreht Playfield nach vorn)
//   HMOVE      Zeilen mit HMOVE-Strobe: die ersten 8 Pixel schwarz (der bekannte Kamm am linken Rand)
// Das Textband (Zeilen mit TEXT-Flag) ist die einzige Ausnahme: dort liest der Shader eine Bitmap.

uniform sampler2D regs : filter_nearest;   // 192 x 6, RGBA8, eine Spalte je Zeile
uniform sampler2D pal : filter_nearest;    // 128 x 1, NTSC-Palette
uniform sampler2D text : filter_nearest;   // 160 x 56, R8: Textband-Bitmap
uniform int text_y0 = 136;
uniform bool probe = false;                // Messmodus: nur das Spielerbild 0 auf Magenta

int b(vec4 v, int c) {
	return int(round(v[c] * 255.0));
}

vec3 color_of(int reg) {
	return texelFetch(pal, ivec2((reg & 254) >> 1, 0), 0).rgb;
}

bool player_hit(int x, int px, int grp, int nusiz, bool refl) {
	int mode = nusiz & 7;
	int scale = mode == 5 ? 2 : (mode == 7 ? 4 : 1);
	int offs[3] = int[3](0, -1, -1);
	if (mode == 1) { offs = int[3](0, 16, -1); }
	else if (mode == 2) { offs = int[3](0, 32, -1); }
	else if (mode == 3) { offs = int[3](0, 16, 32); }
	else if (mode == 4) { offs = int[3](0, 64, -1); }
	else if (mode == 6) { offs = int[3](0, 32, 64); }
	for (int i = 0; i < 3; i++) {
		if (offs[i] < 0) continue;
		int d = (x - px - offs[i] + 320) % 160;
		if (d < 8 * scale) {
			int bit = d / scale;
			bit = refl ? bit : 7 - bit;
			if (((grp >> bit) & 1) != 0) return true;
		}
	}
	return false;
}

bool missile_hit(int x, int mx, bool en, int nusiz) {
	if (!en) return false;
	int w = 1 << ((nusiz >> 4) & 3);
	int mode = nusiz & 7;
	int offs[3] = int[3](0, -1, -1);
	if (mode == 1) { offs = int[3](0, 16, -1); }
	else if (mode == 2) { offs = int[3](0, 32, -1); }
	else if (mode == 3) { offs = int[3](0, 16, 32); }
	else if (mode == 4) { offs = int[3](0, 64, -1); }
	else if (mode == 6) { offs = int[3](0, 32, 64); }
	for (int i = 0; i < 3; i++) {
		if (offs[i] < 0) continue;
		if ((x - mx - offs[i] + 320) % 160 < w) return true;
	}
	return false;
}

vec3 pixel(int x, int y) {
	vec4 r0 = texelFetch(regs, ivec2(y, 0), 0);   // COLUBK, COLUPF, COLUP0, COLUP1
	vec4 r1 = texelFetch(regs, ivec2(y, 1), 0);   // PF-Blöcke 0-31
	vec4 r2 = texelFetch(regs, ivec2(y, 2), 0);   // PF-Blöcke 32-39, GRP0, GRP1, Flags
	vec4 r3 = texelFetch(regs, ivec2(y, 3), 0);   // P0X, P1X, M0X, M1X
	vec4 r4 = texelFetch(regs, ivec2(y, 4), 0);   // BLX, NUSIZ0, NUSIZ1, CTRLPF
	vec4 r5 = texelFetch(regs, ivec2(y, 5), 0);   // COLUPF rechts, SPLIT
	int colubk = b(r0, 0);
	int colupf = b(r0, 1);
	int colup0 = b(r0, 2);
	int colup1 = b(r0, 3);
	int flags = b(r2, 3);
	int ctrlpf = b(r4, 3);
	vec3 magenta = vec3(1.0, 0.0, 1.0);
	if ((flags & 64) != 0) {
		// Textband: Bitmap statt Registern (bewusster Regelbruch, siehe style.json)
		float on = texelFetch(text, ivec2(x, y - text_y0), 0).r;
		if (probe) return magenta;
		return on > 0.5 ? color_of(colupf) : color_of(colubk);
	}
	if ((flags & 32) != 0 && x < 8) {
		return probe ? magenta : vec3(0.0);
	}
	int blk = x / 4;
	int pfbyte = blk < 32 ? b(r1, blk / 8) : b(r2, 0);
	bool pf = ((pfbyte >> (blk % 8)) & 1) != 0;
	int split = b(r5, 1);
	int pfcol = x < split ? colupf : b(r5, 0);
	if ((ctrlpf & 2) != 0) {
		pfcol = x < 80 ? colup0 : colup1;      // Score-Modus
	}
	bool p0 = player_hit(x, b(r3, 0), b(r2, 1), b(r4, 1), (flags & 1) != 0)
		|| missile_hit(x, b(r3, 2), (flags & 4) != 0, b(r4, 1));
	bool p1 = player_hit(x, b(r3, 1), b(r2, 2), b(r4, 2), (flags & 2) != 0)
		|| missile_hit(x, b(r3, 3), (flags & 8) != 0, b(r4, 2));
	int bw = 1 << ((ctrlpf >> 4) & 3);
	bool bl = (flags & 16) != 0 && (x - b(r4, 0) + 320) % 160 < bw;
	if (probe) {
		// Messmodus: nur das Spielerbild 0 (ohne Missile), damit Fenster und Glitzern nicht mitzählen
		bool g0 = player_hit(x, b(r3, 0), b(r2, 1), b(r4, 1), (flags & 1) != 0);
		return g0 ? color_of(colup0) : magenta;
	}
	vec3 c = color_of(colubk);
	if ((ctrlpf & 4) != 0) {
		if (p1) c = color_of(colup1);
		if (p0) c = color_of(colup0);
		if (pf || bl) c = color_of(pfcol);
	} else {
		if (pf || bl) c = color_of(pfcol);
		if (p1) c = color_of(colup1);
		if (p0) c = color_of(colup0);
	}
	return c;
}

void fragment() {
	int x = clamp(int(floor(UV.x * 160.0)), 0, 159);
	int y = clamp(int(floor(UV.y * 192.0)), 0, 191);
	COLOR = vec4(pixel(x, y), 1.0);
}
