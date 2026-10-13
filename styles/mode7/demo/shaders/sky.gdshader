// Oberer Bildteil in Mode 1: Hintergrundfarbe je Zeile (HDMA schreibt CGRAM 0 je Zeile = Himmelsverlauf),
// darüber BG2 (Wolken, Palette 1) und BG1 (Felsnase, Leuchtturm, Inseln; Paletten 2/3). Beide Ebenen sind
// 512 px breit und laufen waagrecht um; HOFS folgt dem Kurs der Kamera (ganze Pixel), die Wolken treiben
// zusätzlich langsam. Index % 16 == 0 ist durchsichtig.
shader_type canvas_item;
render_mode unshaded, blend_disabled;

uniform sampler2D bg1 : filter_nearest, repeat_disable;
uniform sampler2D bg2 : filter_nearest, repeat_disable;
uniform sampler2D cgram : filter_nearest, repeat_disable;
uniform sampler2D skycol : filter_nearest, repeat_disable;   // H×1: Hintergrundfarbe je Zeile
uniform int hofs1;
uniform int hofs2;
uniform int rows;

void fragment() {
	int x = int(floor(UV.x * 256.0));
	int y = int(floor(UV.y * float(rows)));
	int x1 = ((x + hofs1) % 512 + 512) % 512;
	int x2 = ((x + hofs2) % 512 + 512) % 512;
	int i1 = int(round(texelFetch(bg1, ivec2(x1, y), 0).r * 255.0));
	int i2 = int(round(texelFetch(bg2, ivec2(x2, y), 0).r * 255.0));
	vec3 c1 = texelFetch(cgram, ivec2(i1, 0), 0).rgb;
	vec3 c2 = texelFetch(cgram, ivec2(i2, 0), 0).rgb;
	vec3 c0 = texelFetch(skycol, ivec2(y, 0), 0).rgb;
	vec3 col = (i1 % 16 != 0) ? c1 : ((i2 % 16 != 0) ? c2 : c0);
	COLOR = vec4(col, 1.0);
}
