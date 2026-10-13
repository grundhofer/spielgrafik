// Striche, die Godot zeichnet (Rauch, Leuchtturmstrahl, Laternenschein, Möwen, Schatten): Deckung auf dem
// Papierzahn derselben Bildschirmstelle, damit sie wie Grafit oder Buntstift körnig sind und nicht wie Vektorlinien.
shader_type canvas_item;

uniform sampler2D tooth_tex : repeat_enable, filter_linear;
uniform float grain = 0.7;

varying vec2 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	float t = texture(tooth_tex, world_pos / 256.0).r;
	COLOR.a *= mix(1.0, clamp(smoothstep(0.12, 0.7, t) * 1.25, 0.0, 1.0), grain);
}
