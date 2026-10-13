// Schrift mit senkrechtem Verlauf aus Palettenfarben (eine Farbe je Bildzeile ab der Oberkante der
// Großbuchstaben), harte Kanten (Schrift ohne Kantenglättung).
shader_type canvas_item;

uniform sampler2D grad : filter_nearest;
uniform float top_y = 0.0;

void fragment() {
	float a = COLOR.a;
	int n = textureSize(grad, 0).y;
	int row = clamp(int(floor(FRAGCOORD.y) - top_y), 0, n - 1);
	COLOR = vec4(texelFetch(grad, ivec2(0, row), 0).rgb, step(0.5, a));
}
