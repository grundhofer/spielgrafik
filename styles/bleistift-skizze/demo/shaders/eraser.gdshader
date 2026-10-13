// Radierer: Striche, die das Papier an derselben Bildschirmstelle zurückholen (mit Karo, das ist gedruckt und
// geht nicht weg). In den Tälern des Papierzahns bleibt etwas Grafit hängen, wie bei echtem Radieren.
// Für das Glitzern auf dem Wasser: Lichter, die aus dem Grafit herausradiert sind.
shader_type canvas_item;

uniform sampler2D paper_tex : filter_linear;
uniform sampler2D tooth_tex : repeat_enable, filter_linear;
uniform vec2 screen_size = vec2(1280.0, 720.0);

varying vec2 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	vec3 paper = texture(paper_tex, world_pos / screen_size).rgb;
	float t = texture(tooth_tex, world_pos / 256.0).r;
	COLOR = vec4(paper, COLOR.a * mix(0.5, 1.0, smoothstep(0.2, 0.6, t)));
}
