// Weicher additiver Lichtschein (Laterne, Fenster): Stärke über die Knotenfarbe (modulate) gesteuert.
shader_type canvas_item;
render_mode blend_add;

uniform float falloff = 2.2;

void fragment() {
	float r = length(UV - 0.5) * 2.0;
	float a = pow(clamp(1.0 - r, 0.0, 1.0), falloff);
	COLOR = vec4(COLOR.rgb * a * COLOR.a, 1.0);
}
