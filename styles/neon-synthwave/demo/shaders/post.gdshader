shader_type canvas_item;
// Bildschirm nach dem Glow (CanvasLayer 2 liegt über background_canvas_max_layer 1):
// Rasterzeilen, leichte Farbverschiebung zum Rand, Vignette.
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float scan_strength = 0.18;
uniform float scan_period = 3.0;      // Bildpunkte je Rasterzeile
uniform float ca_px = 0.5;            // Farbverschiebung am Bildrand in Bildpunkten
uniform float vignette = 0.32;
uniform int enabled = 1;

void fragment() {
	vec2 uv = SCREEN_UV;
	if (enabled == 0) {
		COLOR = vec4(textureLod(screen_tex, uv, 0.0).rgb, 1.0);
	} else {
		vec2 px = 1.0 / vec2(textureSize(screen_tex, 0));
		vec2 dc = uv - 0.5;
		float r2 = dot(dc * vec2(1.6, 1.0), dc * vec2(1.6, 1.0));
		vec2 ca = dc * r2 * 2.0 * ca_px * px * 4.0;
		vec3 c;
		c.r = textureLod(screen_tex, uv + ca, 0.0).r;
		c.g = textureLod(screen_tex, uv, 0.0).g;
		c.b = textureLod(screen_tex, uv - ca, 0.0).b;
		float y = uv.y / px.y;
		float s = 0.5 + 0.5 * cos(6.2831853 * y / scan_period);
		c *= 1.0 - scan_strength * s;
		c *= 1.0 - vignette * smoothstep(0.15, 0.75, r2);
		COLOR = vec4(c, 1.0);
	}
}
