shader_type canvas_item;
// Wind im gemalten Gras: verschiebt die Hintergrund-Textur waagerecht, nur wo die Maske hell ist.
// Maske als L/RGB-Textur (nicht im Alphakanal, Godot überschreibt sonst die Farbe transparenter Pixel).
// Die Verschiebung ist oben in einem Grasbüschel größer (Maske in build_orte.py nach oben verstärkt).

uniform sampler2D mask : filter_linear;
uniform float amp_px = 2.0;
uniform vec2 screen_px = vec2(1280.0, 720.0);
uniform float t = 0.0;

void fragment() {
	float m = texture(mask, UV).r;
	float wave = sin(t * 2.1 + UV.x * 23.0 + UV.y * 9.0) * 0.6 + sin(t * 3.7 + UV.x * 41.0 - UV.y * 5.0) * 0.4;
	float gust = 0.65 + 0.35 * sin(t * 0.9 - UV.x * 6.0);
	vec2 off = vec2(amp_px * m * wave * gust / screen_px.x, 0.0);
	COLOR = texture(TEXTURE, UV + off);
}
