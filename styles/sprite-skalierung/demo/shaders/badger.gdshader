shader_type canvas_item;
render_mode unshaded;
// Seitenneigung in Kurven per Zeilenversatz: Jede Texelzeile wird um eine ganze Zahl Texel verschoben,
// oben um "lean", an der Fußzeile um 0 (Scherung ohne Drehung, die Pixel bleiben auf dem Raster).
uniform float lean = 0.0;      // Versatz der obersten Zeile in Texeln (+ = nach rechts)
uniform vec2 tex_size = vec2(56.0, 64.0);
uniform float pad = 6.0;       // freie Spalten links und rechts im Bild

void fragment() {
	float row = floor(UV.y * tex_size.y);
	float k = 1.0 - (row + 0.5) / tex_size.y;
	float shift = floor(lean * k + 0.5);
	vec2 uv = vec2(UV.x - shift / tex_size.x, UV.y);
	vec4 c = texture(TEXTURE, uv);
	if (uv.x < 0.0 || uv.x > 1.0 || c.a < 0.5) {
		discard;
	}
	COLOR = vec4(c.rgb, 1.0);
}
