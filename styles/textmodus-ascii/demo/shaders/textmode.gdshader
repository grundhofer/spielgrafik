// Zeichengenerator des PC-Textmodus: 80×25 Zellen à 8×14 Pixel (640×350).
// vram: 80×25, R = Zeichencode (CP437), G = Attribut (Bit 0–3 Vordergrund, 4–6 Hintergrund, 7 Blinken).
// font: Zeichensatz-ROM als 16×16-Atlas (128×224), Alpha = Pixel gesetzt.
shader_type canvas_item;

uniform sampler2D font_tex : filter_nearest;
uniform sampler2D vram : filter_nearest;
uniform bool blink_on = true;      // Phase des Zeichenblinkens (aus: blinkende Zeichen zeigen nur Hintergrund)
uniform bool cursor_on = false;    // Phase des Cursors
uniform ivec2 cursor = ivec2(-1, -1);

const vec3 PAL[16] = vec3[16](
	vec3(0.0, 0.0, 0.0), vec3(0.0, 0.0, 0.6667), vec3(0.0, 0.6667, 0.0), vec3(0.0, 0.6667, 0.6667),
	vec3(0.6667, 0.0, 0.0), vec3(0.6667, 0.0, 0.6667), vec3(0.6667, 0.3333, 0.0), vec3(0.6667, 0.6667, 0.6667),
	vec3(0.3333, 0.3333, 0.3333), vec3(0.3333, 0.3333, 1.0), vec3(0.3333, 1.0, 0.3333), vec3(0.3333, 1.0, 1.0),
	vec3(1.0, 0.3333, 0.3333), vec3(1.0, 0.3333, 1.0), vec3(1.0, 1.0, 0.3333), vec3(1.0, 1.0, 1.0)
);

void fragment() {
	ivec2 p = ivec2(floor(UV * vec2(640.0, 350.0)));
	p = clamp(p, ivec2(0), ivec2(639, 349));
	ivec2 cell = ivec2(p.x / 8, p.y / 14);
	ivec2 g = ivec2(p.x % 8, p.y % 14);
	vec4 v = texelFetch(vram, cell, 0);
	int ch = int(v.r * 255.0 + 0.5);
	int at = int(v.g * 255.0 + 0.5);
	int fg = at & 15;
	int bg = (at >> 4) & 7;
	bool lit = texelFetch(font_tex, ivec2((ch % 16) * 8 + g.x, (ch / 16) * 14 + g.y), 0).a > 0.5;
	if ((at & 128) != 0 && !blink_on) {
		lit = false;
	}
	if (cursor_on && cell == cursor && g.y >= 12) {   // Unterstrich-Cursor: Zeilen 12–13 der Zelle
		lit = true;
	}
	COLOR = vec4(lit ? PAL[fg] : PAL[bg], 1.0);
}
