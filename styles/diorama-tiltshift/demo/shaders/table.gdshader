// Tischtuch unter dem Sockel: dunkler Filz, der nach außen abdunkelt (Lichtkegel der Studiolampe).
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

#include "res://shaders/dio_noise.gdshaderinc"

uniform vec4 albedo : source_color = vec4(0.16, 0.15, 0.2, 1.0);
uniform vec3 center = vec3(1.0, 0.0, -13.5);
uniform float pool_r = 26.0;
uniform float pool_soft = 30.0;
uniform float outside = 0.25;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	float d = length((world_pos.xz - center.xz) * vec2(1.0, 0.85));
	float pool = mix(outside, 1.0, 1.0 - smoothstep(pool_r, pool_r + pool_soft, d));
	float fib = dio_vnoise(world_pos * vec3(9.0, 1.0, 9.0)) * 0.5 + dio_vnoise(world_pos.zyx * vec3(11.0, 1.0, 7.0)) * 0.5;
	ALBEDO = albedo.rgb * pool * (0.85 + 0.3 * fib);
	ROUGHNESS = 1.0;
	SPECULAR = 0.1;
}
