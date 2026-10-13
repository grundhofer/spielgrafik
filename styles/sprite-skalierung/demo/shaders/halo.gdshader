shader_type canvas_item;
render_mode unshaded, blend_add;
// Lichthof der Laternen als aufhellendes Sprite (additiv), gestufte Ringe ohne Verlauf.
// Wird wie die Requisiten skaliert und an der Kuppe abgeschnitten.
uniform float clip_y = 100000.0;
uniform float gain = 1.0;
varying float wy;

void vertex() {
	wy = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).y;
}

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	if (wy >= clip_y || c.a < 0.5) {
		discard;
	}
	COLOR = vec4(c.rgb * gain, 1.0);
}
