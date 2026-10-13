// Hintergrund: RGB = Transmission der Tusche, A = Reihenfolge des Einziehens (Dichte). Ergebnis = Papier * T.
// progress 0..1: beim Szenenstart zieht die Tusche ins Papier, helle Lasuren zuerst, satte Striche zuletzt,
// mit wolkigem Rauschen, damit es nicht wie eine Überblendung aussieht.
shader_type canvas_item;

uniform sampler2D paper : filter_linear;
uniform sampler2D noise_tex : filter_linear, repeat_enable;
uniform float progress = 1.0;
const float ALPHA_FLOOR = 21.0 / 255.0;   // siehe tools/inkutil.py

void fragment() {
	vec4 ink = texture(TEXTURE, UV);
	float n = texture(noise_tex, UV * vec2(1.0, 1.0)).r;
	float order = clamp((ink.a - ALPHA_FLOOR) / (1.0 - ALPHA_FLOOR), 0.0, 1.0);
	float key = order * 0.7 + n * 0.3;
	float amt = clamp((progress * 1.2 - key) / 0.14, 0.0, 1.0);
	vec3 p = texture(paper, SCREEN_UV).rgb;
	COLOR = vec4(p * mix(vec3(1.0), ink.rgb, amt), 1.0);
}
