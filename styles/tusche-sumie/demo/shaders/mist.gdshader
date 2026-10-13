// Ziehender Nebel: kachelbare Nebelmaske (Alpha) wird waagerecht verschoben und oben und unten weich begrenzt;
// gezeigt wird das Papier selbst (per Bildschirmkoordinate), also leeres Papier, in dem die Tusche verschwindet.
shader_type canvas_item;

uniform sampler2D paper : filter_linear;
uniform float offset = 0.0;      // Verschiebung in UV der Maske
uniform float amount = 1.0;
uniform float repeat_x = 1.0;
uniform float soft_top = 0.35;
uniform float soft_bottom = 0.35;

void fragment() {
	vec2 uv = vec2(fract(UV.x * repeat_x + offset), UV.y);
	float m = texture(TEXTURE, uv).a;
	float b = smoothstep(0.0, soft_top, UV.y) * smoothstep(1.0, 1.0 - soft_bottom, UV.y);
	vec3 p = texture(paper, SCREEN_UV).rgb;
	COLOR = vec4(p, clamp(m * b * amount, 0.0, 1.0));
}
