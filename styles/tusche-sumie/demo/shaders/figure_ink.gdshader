// Figur, zweiter Durchgang: RGB der Textur ist die Transmission von Tusche und Zinnober; multipliziert auf das,
// was darunter liegt (Papierfüllung der Figur oder, am ausgelaufenen Rand, der Hintergrund).
// progress 0..1: beim Szenenstart zieht die Tusche der Figur wie die des Hintergrunds ein (bg_ink.gdshader:
// helle Lasuren zuerst, satte Striche zuletzt, dasselbe Rauschen per Bildschirmkoordinate).
shader_type canvas_item;
render_mode blend_mul;

uniform float breathe = 0.0;
uniform float foot_y = 0.0;
uniform float progress = 1.0;
uniform sampler2D noise_tex : filter_linear, repeat_enable;

void vertex() {
	float k = (foot_y - VERTEX.y);
	VERTEX.y = foot_y - k * (1.0 + breathe);
}

void fragment() {
	float d = clamp(1.0 - dot(COLOR.rgb, vec3(1.0 / 3.0)), 0.0, 1.0);
	float n = texture(noise_tex, SCREEN_UV).r;
	float amt = clamp((progress * 1.2 - (d * 0.7 + n * 0.3)) / 0.14, 0.0, 1.0);
	COLOR = vec4(mix(vec3(1.0), COLOR.rgb, amt), 1.0);
}
