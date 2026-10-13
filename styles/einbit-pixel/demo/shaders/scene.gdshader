// Hafenszene in 1 Bit: liest die Tonkarte (R = Stufe·15, G = Musterfamilie·85, B = Bereich·30, siehe
// scripts/build_bg.py) und setzt jedes Pixel über die Schwellenmatrix seiner Familie auf Schwarz oder Weiß.
// Licht ist hier keine Farbe, sondern eine höhere Stufe (dichteres Weißmuster) oder ein Musterwechsel;
// der Blitz des Leuchtfeuers kehrt eine Kreisfläche um.
shader_type canvas_item;
render_mode unshaded, blend_disabled;

uniform sampler2D pattern_tex : filter_nearest;   // 16×24: Bayer (Zeilen 0–7), LINES (8–15), DASH (16–23)
uniform float t = 0.0;
uniform float horizon = 109.0;
uniform float quay_top = 154.0;

// Leuchtfeuer: Strahl als Keil (Richtung ±1, sichtbare Länge), Blitz als umgekehrter Kreis
uniform vec2 lamp_pos = vec2(365.0, 54.5);
uniform float beam_side = -1.0;
uniform float beam_len = 0.0;
uniform float flash_r = 0.0;
// Laterne: Flackerstärke 0..1
uniform vec2 lantern_pos = vec2(116.0, 89.0);
uniform float lantern_i = 1.0;
// Rauch: Wölkchen (x, y, Radius, Dichte 0..1)
uniform vec4 puffs[10];
uniform int puff_count = 0;
// Schalter für Messungen: 0 = alles, 1 = ohne Licht und Rauch (nur Tonkarte und Wasser)
uniform int fx_mode = 0;

const int SKY = 1;
const int WATER = 2;
const int GROUND = 3;
const int GLASS = 4;
const int STAR = 5;
const int LAMP = 6;

int pmod(int a, int m) { return ((a % m) + m) % m; }

float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }

bool pattern_white(int fam, int lev, int x, int y) {
	if (lev <= 0) return false;
	if (lev >= 16) return true;
	int thr = int(round(texelFetch(pattern_tex, ivec2(pmod(x, 16), fam * 8 + pmod(y, 8)), 0).r * 255.0));
	return thr < lev * 8;
}

void fragment() {
	ivec2 p = ivec2(floor(UV * vec2(textureSize(TEXTURE, 0))));
	vec4 tv = texelFetch(TEXTURE, p, 0);
	int lev = int(round(tv.r * 255.0 / 15.0));
	int fam = int(round(tv.g * 255.0 / 85.0));
	int reg = int(round(tv.b * 255.0 / 30.0));
	vec2 fp = vec2(p) + 0.5;
	int x = p.x;

	// Wasser: jede Doppelzeile wandert in ganzen Pixeln, nah schneller, Richtung wechselnd
	if (fam == 2) {
		int band = p.y >> 1;
		float depth = clamp((fp.y - horizon) / 45.0, 0.0, 1.0);
		float v = (1.5 + 3.0 * hash(vec2(float(band), 3.1)) + 5.0 * depth) * ((band & 1) == 0 ? 1.0 : -1.0);
		x += int(floor(t * v + 16.0 * hash(vec2(float(band), 7.7))));
	}

	if (fx_mode == 0) {
		// Sterne funkeln: einzelne Sterne für 1/6 s dunkel
		if (reg == STAR && hash(vec2(float(p.x * 7 + p.y), floor(t * 6.0))) < 0.07) lev = 1;

		// Strahl des Leuchtfeuers über dem Himmel: Musterwechsel (Zeilenraster → Bayer) und höhere Stufe
		if (reg == SKY || reg == STAR) {
			vec2 v = fp - lamp_pos;
			float along = v.x * beam_side;
			if (along > 3.0 && along < beam_len) {
				float centre = 0.10 * along;                    // leicht abwärts
				float half_w = 1.0 + 0.035 * along;
				if (abs(v.y - centre) < half_w) {
					float k = along / max(beam_len, 1.0);
					int boost = k < 0.35 ? 8 : (k < 0.7 ? 5 : 3);
					lev = min(16, max(lev, 2) + boost);
					fam = 0;
				}
			}
		}
		// Lichthof um die Lampe
		float dl = length(fp - lamp_pos);
		if (dl < 6.0 && reg != LAMP) lev = min(16, lev + (dl < 4.0 ? 6 : 3));

		// Laterne: Glas weiß, bei Böen halb (Schachbrett) oder dunkel; Lichthof in ganzen Pixelringen nur auf
		// Himmel, Sternen und Wasser, damit Rahmen, Kappe und Haken des Laternenkopfs schwarz bleiben
		if (reg == GLASS) {
			lev = lantern_i > 0.42 ? 16 : (lantern_i > 0.2 ? 8 : 0);
		} else if (reg == SKY || reg == STAR || reg == WATER) {
			float d = length((fp - lantern_pos) * vec2(1.0, 1.1));
			float r1 = floor(5.0 + 4.0 * lantern_i);
			float r2 = floor(9.0 + 7.0 * lantern_i);
			if (d < r1) { lev = min(16, lev + 5); if (fam == 1) fam = 0; }
			else if (d < r2) { lev = min(16, lev + 2); if (fam == 1) fam = 0; }
		}
		// Lichtkegel der Laterne auf dem Kai
		if (reg == GROUND) {
			vec2 q = (fp - vec2(lantern_pos.x, quay_top + 13.0)) / vec2(30.0 + 12.0 * lantern_i, 10.0 + 3.0 * lantern_i);
			float e = dot(q, q);
			if (e < 0.45) lev = min(16, lev + 4);
			else if (e < 1.0) lev = min(16, lev + 2);
		}
		// Rauch: helle, nach außen ausdünnende Wölkchen vor dem Himmel
		if (reg == SKY || reg == STAR) {
			for (int i = 0; i < puff_count; i++) {
				vec4 pf = puffs[i];
				float d = length(fp - pf.xy) / pf.z;
				if (d < 1.0) {
					int sl = int(round(pf.w * (d < 0.6 ? 12.0 : 6.0)));
					if (sl > lev || fam == 1) { lev = max(lev, sl); fam = 0; }
				}
			}
		}
	}

	bool w = pattern_white(fam, lev, x, p.y);
	// Blitz zur Kamera: Kreis um die Lampe umgekehrt
	if (fx_mode == 0 && flash_r > 0.5 && length(fp - lamp_pos) < flash_r) w = !w;
	COLOR = vec4(vec3(w ? 1.0 : 0.0), 1.0);
}
