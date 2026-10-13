// Vignette und leichte Farbgebung über dem 3D-Bild (unter der Oberfläche).
// Liest das fertige Bild (hint_screen_texture), dunkelt die Ränder ab und zieht sie ins Blauviolette,
// hebt die Mitte minimal an. Rand in Bildschirmprozent, damit es bei jeder Auflösung gleich wirkt.
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_linear;
uniform float strength = 0.5;
uniform float inner = 0.35;
uniform float outer = 0.95;
uniform vec3 edge_tint : source_color = vec3(0.42, 0.36, 0.52);

void fragment() {
	vec3 c = texture(screen_tex, SCREEN_UV).rgb;
	vec2 p = (SCREEN_UV - 0.5) * vec2(1.0, 0.75) * 2.0;
	float r = length(p);
	float v = smoothstep(inner, outer, r);
	c = mix(c, c * edge_tint * 2.0, v * 0.18);
	c *= 1.0 - strength * v * v;
	COLOR = vec4(c, 1.0);
}
