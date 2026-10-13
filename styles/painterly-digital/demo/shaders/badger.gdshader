// Figur: Umgebungstönung + zwei Lichtkanten (warmes Gegenlicht vom Abendhimmel oben, Laternenlicht seitlich).
// Kante = deckend hier, durchsichtig ein paar Texel Richtung Licht.
// COLOR enthält in fragment() bereits die Texturfarbe; die Vertexfarbe (modulate) kommt über ein varying.
shader_type canvas_item;

uniform vec3 ambient = vec3(0.86, 0.9, 0.98);
uniform vec2 back_dir = vec2(0.25, -1.0);
uniform vec3 back_color = vec3(1.0, 0.78, 0.55);
uniform float back_strength = 0.35;
uniform vec2 lamp_dir = vec2(1.0, -0.3);
uniform vec3 lamp_color = vec3(1.3, 0.8, 0.4);
uniform float lamp_strength = 0.0;
uniform float rim_px = 2.5;
// Unterhalb von rim_cut (UV.y) keine Lichtkanten: Dort endet der Rumpf an der gezackten Schnittkante über den
// Beinen. Ohne diese Grenze bekamen die Zackenflanken Laternenlicht und zeichneten eine helle gepunktete Linie.
uniform float rim_cut = 2.0;

varying vec4 vcol;

void vertex() {
	vcol = COLOR;
}

void fragment() {
	vec4 tex = texture(TEXTURE, UV);
	vec2 db = normalize(back_dir) * TEXTURE_PIXEL_SIZE * rim_px;
	vec2 dl = normalize(lamp_dir) * TEXTURE_PIXEL_SIZE * rim_px;
	float rb = clamp(1.0 - 0.5 * (texture(TEXTURE, UV + db).a + texture(TEXTURE, UV + db * 0.5).a), 0.0, 1.0);
	float rl = clamp(1.0 - 0.5 * (texture(TEXTURE, UV + dl).a + texture(TEXTURE, UV + dl * 0.5).a), 0.0, 1.0);
	float keep = 1.0 - smoothstep(rim_cut - 4.0 * TEXTURE_PIXEL_SIZE.y, rim_cut, UV.y);
	rb *= keep;
	rl *= keep;
	float lum = dot(tex.rgb, vec3(0.3, 0.55, 0.15));
	vec3 c = tex.rgb * ambient * vcol.rgb;
	c += back_color * back_strength * rb * (0.6 + 0.4 * lum) * vcol.rgb;
	c += lamp_color * lamp_strength * rl * (0.5 + 0.5 * lum) * vcol.rgb;
	COLOR = vec4(c, tex.a * vcol.a);
}
