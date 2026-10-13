// Spiegelung der Figur auf dem nassen Pflaster: dasselbe Sprite gespiegelt (main.gd), additiv, nach unten
// ausblendend und vom Regen waagerecht gekräuselt.
shader_type canvas_item;
render_mode blend_add;

uniform float t = 0.0;
uniform float feet_y = 645.0;
uniform float refl_gain = 0.3;
uniform float refl_len = 110.0;

varying vec2 world;

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	float d = world.y - feet_y;
	float fade = clamp(1.0 - d / refl_len, 0.0, 1.0);
	fade *= fade;
	vec2 uv = UV + vec2((sin(world.y * 0.9 + t * 6.0) + 0.5 * sin(world.y * 2.1 - t * 9.0)) * 0.0035, 0.0);
	vec4 r = texture(TEXTURE, uv);
	COLOR = vec4(r.rgb * r.a * refl_gain * fade, 1.0);
}
