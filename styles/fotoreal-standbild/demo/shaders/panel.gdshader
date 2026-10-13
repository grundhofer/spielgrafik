shader_type canvas_item;
// Textfeld als Milchglas: das Bild dahinter weichgezeichnet (photo_blur, gleiche Lage) und abgedunkelt, darüber eine
// feine helle Kante oben. Weiche Ecken (Radius in px). Größe aus rect_size (main.gd).
uniform sampler2D blur_tex : filter_linear, repeat_disable;   // weichgezeichnetes Foto 1280x720
uniform vec2 rect_pos = vec2(0.0);
uniform vec2 rect_size = vec2(520.0, 184.0);
uniform vec2 screen_size = vec2(1280.0, 720.0);
uniform float radius = 6.0;
uniform float darken = 0.42;
uniform vec3 tint = vec3(0.05, 0.065, 0.09);
uniform float tint_k = 0.55;
uniform float fade = 1.0;

void fragment() {
	vec2 p = UV * rect_size;
	vec3 bg = texture(blur_tex, (rect_pos + p) / screen_size).rgb;
	vec3 c = mix(bg * darken, tint, tint_k);
	// Abstand zum abgerundeten Rechteck
	// Distanzfunktion abgerundetes Rechteck nach Inigo Quilez – Copyright (c) Inigo Quilez, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt), https://iquilezles.org/articles/distfunctions2d/
	vec2 q = abs(p - rect_size * 0.5) - (rect_size * 0.5 - radius);
	float dist = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - radius;
	float a = 1.0 - smoothstep(-1.0, 0.5, dist);
	// feine Lichtkante oben und dezente Linie innen
	float top = (1.0 - smoothstep(0.0, 1.2, p.y)) * 0.35;
	float inner = (1.0 - smoothstep(0.0, 1.0, abs(dist + 1.0))) * 0.10;
	c += vec3(1.0, 0.95, 0.88) * (top + inner);
	COLOR = vec4(c, a * 0.92 * fade);
}
