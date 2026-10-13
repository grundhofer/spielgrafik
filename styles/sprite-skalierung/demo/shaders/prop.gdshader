shader_type canvas_item;
render_mode unshaded;
// Skalierte Sprites: Abtastung ohne Filter (Projekteinstellung Nearest), 1-Bit-Alpha.
// clip_y: Bildzeile, ab der die Straße davor liegt (Kuppe); Pixel darunter fallen weg.
// key*/key*_col: Palettenanimation – genau diese Farbe wird ersetzt (Laternenglas, Fenster, Leuchtfeuer).
uniform float clip_y = 100000.0;
uniform vec3 key1 = vec3(-1.0);
uniform vec3 key1_col = vec3(1.0);
uniform bool use_linear = false;   // Vergleichsschalter --smooth: lineare Filterung statt Nearest
uniform sampler2D lin_tex : filter_linear;
varying float wy;

void vertex() {
	wy = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).y;
}

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	if (use_linear) {
		c = texture(lin_tex, UV);
	}
	if (wy >= clip_y || c.a < 0.5) {
		discard;
	}
	if (distance(c.rgb, key1) < 0.006) {
		c.rgb = key1_col;
	}
	COLOR = vec4(c.rgb, use_linear ? c.a : 1.0);
}
