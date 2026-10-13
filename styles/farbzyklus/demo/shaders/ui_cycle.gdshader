// Titelschrift mit Farbzyklus: Jedes Schriftpixel nimmt einen Eintrag der Goldrampe (Palette 4..9) nach seiner
// Lage auf dem Bildschirmraster; cycler.gd rotiert die Rampe, dadurch läuft ein Glanz schräg durch die Schrift.
// Die Schrift ist ohne Kantenglättung gesetzt, die Deckkraft ist also 0 oder 1.
shader_type canvas_item;
render_mode unshaded;

uniform sampler2D palette_tex : filter_nearest, repeat_disable;
uniform int ramp_start = 4;
uniform int ramp_len = 6;

void fragment() {
	ivec2 p = ivec2(floor(FRAGCOORD.xy));
	int k = ((p.x + p.y) / 2) % ramp_len;
	vec4 c = texelFetch(palette_tex, ivec2(ramp_start + k, 0), 0);
	COLOR = vec4(c.rgb, COLOR.a > 0.5 ? 1.0 : 0.0);
}
