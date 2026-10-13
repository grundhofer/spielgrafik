// Bildröhre: frisches Strahlbild + Nachleuchten. Das Nachleuchten (Puffer minus frisches Bild) wird erst
// oberhalb einer Schwelle sichtbar: helle, schnelle Linien (Leuchtfeuer, Strahl, Möwenflügel) ziehen eine
// Spur, schwache Linien und die Figur bleiben scharf. Leichte Abdunklung zu den Ecken (gewölbtes Glas).
// Keine Scanlines und kein Pixelraster: Ein Vektorbildschirm hat keine Zeilen.
shader_type canvas_item;

uniform sampler2D beam_tex : filter_nearest;
uniform float trail_floor = 0.3;
uniform float trail_gain = 1.0;
uniform float vignette = 0.22;

void fragment() {
	vec3 acc = texture(TEXTURE, UV).rgb;
	vec3 now = texture(beam_tex, UV).rgb;
	vec3 trail = max(acc - now - vec3(trail_floor), vec3(0.0)) * trail_gain;
	vec3 c = now + trail;
	vec2 d = UV - 0.5;
	float v = 1.0 - vignette * dot(d, d) * 2.2;
	COLOR = vec4(c * v, 1.0);
}
