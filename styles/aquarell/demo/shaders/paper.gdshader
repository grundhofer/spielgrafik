shader_type canvas_item;
// Papierkorn über dem ganzen Bild: Prägung des kaltgepressten Papiers (Licht von links oben),
// Granulation (Pigment setzt sich in die Täler, je mehr Farbe, desto stärker) und leichte Zahnung.
uniform sampler2D screen_tex : hint_screen_texture, filter_linear;
uniform sampler2D paper_tex : repeat_enable, filter_linear;
uniform vec3 paper_col = vec3(0.957, 0.937, 0.894);
uniform float emboss = 0.07;
uniform float granulation = 0.22;
uniform float tooth = 0.035;
uniform float tile_px = 512.0;

void fragment() {
	vec3 c = texture(screen_tex, SCREEN_UV).rgb;
	vec2 p = FRAGCOORD.xy;
	float h = texture(paper_tex, p / tile_px).r;
	float hl = texture(paper_tex, (p + vec2(-1.0, -1.0)) / tile_px).r;
	float hr = texture(paper_tex, (p + vec2(1.0, 1.0)) / tile_px).r;
	float light = 1.0 + emboss * (hl - hr);
	float pig = clamp(1.0 - dot(c, vec3(0.299, 0.587, 0.114)) / dot(paper_col, vec3(0.299, 0.587, 0.114)), 0.0, 1.0);
	c *= 1.0 - granulation * pig * (1.0 - h) * (1.0 - pig * 0.5);
	c *= 1.0 - tooth * (1.0 - h);
	c *= light;
	COLOR = vec4(c, 1.0);
}
