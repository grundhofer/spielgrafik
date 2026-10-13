// Jugendstil – Ornamentrahmen: die Goldflächen des Rahmens (art/frame_gold.png) schimmern. Ein schräger
// Lichtstreif läuft alle SWEEP Sekunden über den Rahmen und hellt nur Goldpixel zu Blassgold auf; dazu atmet das
// Gold leicht. COLOR enthält in fragment() schon die Texturfarbe.
shader_type canvas_item;

uniform sampler2D gold_mask : filter_nearest;
uniform float t = 0.0;
uniform float sweep_period = 3.0;
uniform vec3 pale_gold = vec3(1.0, 0.92, 0.66);

void fragment() {
	float g = texture(gold_mask, UV).r;
	vec2 p = UV * vec2(1280.0, 720.0);
	float span = 1280.0 + 720.0 * 0.6 + 400.0;
	float front = -200.0 + span * fract(t / sweep_period);
	float d = (p.x + p.y * 0.6) - front;
	float band = smoothstep(-70.0, -20.0, d) * (1.0 - smoothstep(10.0, 40.0, d));
	float breathe = 0.06 + 0.06 * sin(t * 1.4 + p.x * 0.004 - p.y * 0.003);
	vec4 c = COLOR;
	c.rgb = mix(c.rgb, pale_gold, g * clamp(band * 0.8 + breathe, 0.0, 1.0));
	COLOR = c;
}
