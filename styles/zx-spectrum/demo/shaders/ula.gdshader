// Videologik des Spectrum (ULA) als Shader: liest den Bildschirmspeicher wie die Hardware.
// bitmap_tex: 6144 Bytes Bitmap in Speicherreihenfolge (32×192 Texel, ein Byte je Texel),
// attr_tex: 768 Attributbytes (32×24), border_tex: Rahmenfarbe je Bildzeile (1×240, nur Farben 0–7).
// Attributbyte: Bit 7 FLASH, Bit 6 BRIGHT, Bits 5–3 PAPER, Bits 2–0 INK.
shader_type canvas_item;
render_mode unshaded;

uniform sampler2D bitmap_tex : filter_nearest, repeat_disable;
uniform sampler2D attr_tex : filter_nearest, repeat_disable;
uniform sampler2D border_tex : filter_nearest, repeat_disable;
uniform bool flash_phase = false;

const vec3 PAL[16] = vec3[16](
	vec3(0.0), vec3(0.0, 0.0, 0.843), vec3(0.843, 0.0, 0.0), vec3(0.843, 0.0, 0.843),
	vec3(0.0, 0.843, 0.0), vec3(0.0, 0.843, 0.843), vec3(0.843, 0.843, 0.0), vec3(0.843),
	vec3(0.0), vec3(0.0, 0.0, 1.0), vec3(1.0, 0.0, 0.0), vec3(1.0, 0.0, 1.0),
	vec3(0.0, 1.0, 0.0), vec3(0.0, 1.0, 1.0), vec3(1.0, 1.0, 0.0), vec3(1.0));

int byte_at(sampler2D tex, ivec2 p) {
	return int(texelFetch(tex, p, 0).r * 255.0 + 0.5);
}

void fragment() {
	ivec2 p = ivec2(floor(UV * vec2(320.0, 240.0)));
	int x = p.x - 32;
	int y = p.y - 24;
	int border = byte_at(border_tex, ivec2(0, p.y)) & 7;
	int bmp_addr = ((clamp(y, 0, 191) & 0xC0) << 5) | ((clamp(y, 0, 191) & 7) << 8)
		| ((clamp(y, 0, 191) & 0x38) << 2) | (clamp(x, 0, 255) >> 3);
	int bits = byte_at(bitmap_tex, ivec2(bmp_addr & 31, bmp_addr >> 5));
	int attr = byte_at(attr_tex, ivec2(clamp(x, 0, 255) >> 3, clamp(y, 0, 191) >> 3));
	vec3 col;
	if (x < 0 || x >= 256 || y < 0 || y >= 192) {
		col = PAL[border];
	} else {
		int ink = attr & 7;
		int paper = (attr >> 3) & 7;
		if ((attr & 0x80) != 0 && flash_phase) {
			int tmp = ink;
			ink = paper;
			paper = tmp;
		}
		int bit = (bits >> (7 - (x & 7))) & 1;
		col = PAL[(bit == 1 ? ink : paper) + ((attr >> 6) & 1) * 8];
	}
	COLOR = vec4(col, 1.0);
}
