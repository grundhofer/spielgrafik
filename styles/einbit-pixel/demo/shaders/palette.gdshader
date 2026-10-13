// Letzte Ebene: macht aus dem fertigen Bild genau zwei Farben (Schwelle 0,5). Tinte und Papier sind
// austauschbar wie die Farbe eines 1-Bit-Bildschirms.
shader_type canvas_item;
render_mode unshaded, blend_disabled;

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
uniform vec3 ink = vec3(0.106, 0.098, 0.086);    // #1B1916
uniform vec3 paper = vec3(0.914, 0.890, 0.827);  // #E9E3D3

void fragment() {
	vec3 c = texture(screen_tex, SCREEN_UV).rgb;
	COLOR = vec4(dot(c, vec3(0.299, 0.587, 0.114)) > 0.5 ? paper : ink, 1.0);
}
