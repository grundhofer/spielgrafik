shader_type canvas_item;
// Rauchwolke mit zwei harten Tönen: Rot der Textur = Lichtanteil (1 Licht, 0 Schatten).
uniform vec3 lit_color = vec3(0.98, 0.80, 0.78);
uniform vec3 shade_color = vec3(0.55, 0.52, 0.72);
varying vec4 vcol;
void vertex() { vcol = COLOR; }
void fragment() {
	vec4 t = texture(TEXTURE, UV);
	vec3 c = mix(shade_color, lit_color, t.r);
	COLOR = vec4(c, t.a) * vcol;
}
