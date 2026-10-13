// Futter hinter der Puppe wie hinterlegtes Seidenpapier: die geschnittenen Löcher (Gesichtsstreifen,
// Kragen, Westenschlitze) zeigen einen warmen hellen Ton statt der Kulisse dahinter, damit das Gesicht
// auch vor Steg und Booten lesbar bleibt. Etwas Kulisse scheint durch (Bildschirm ohne Puppe).
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
uniform vec4 tissue : source_color = vec4(1.0, 0.84, 0.64, 1.0);
uniform float amount = 0.88;

void fragment() {
	float a = texture(TEXTURE, UV).a;
	vec3 bg = texture(screen_tex, SCREEN_UV).rgb;
	COLOR = vec4(mix(bg, tissue.rgb, amount), a);
}
