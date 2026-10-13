shader_type canvas_item;
render_mode unshaded;
// Himmel als Farbe je Bildzeile (Rasterfarben), Tabelle 1×224 aus main.gd in 5-Bit-Stufen.
uniform sampler2D sky : filter_nearest;
varying vec2 px;

void vertex() {
	px = VERTEX;
}

void fragment() {
	COLOR = vec4(texelFetch(sky, ivec2(0, int(floor(px.y))), 0).rgb, 1.0);
}
