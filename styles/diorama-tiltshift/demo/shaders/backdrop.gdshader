// Gemalter Himmelsprospekt hinter dem Sockel (wie bei Modellbahn-Hintergründen): eine Hohlkehle, die
// vom Tischtuch aus nach oben biegt, darauf Abendverlauf, weiche Wolkenbänder und ein paar Sterne.
// Unten trägt die Kehle Farbe und Licht des Tischtuchs (gleiche Rechnung wie table.gdshader), damit keine
// Kante zwischen Tisch und Karte entsteht; nach oben übernimmt der gemalte Himmel als Emission.
// UV.x läuft um den Bogen (0..1), UV.y entlang des Profils (0 auf dem Tisch, 1 oben).
shader_type spatial;
render_mode blend_mix, cull_disabled, fog_disabled, diffuse_burley;

#include "res://shaders/dio_noise.gdshaderinc"

uniform vec4 table_albedo : source_color = vec4(0.16, 0.15, 0.2, 1.0);
uniform vec3 center = vec3(1.0, 0.0, -13.5);
uniform float pool_r = 26.0;
uniform float pool_soft = 30.0;
uniform float outside = 0.25;
uniform vec4 c_low : source_color = vec4(1.0, 0.62, 0.36, 1.0);
uniform vec4 c_mid : source_color = vec4(0.88, 0.45, 0.52, 1.0);
uniform vec4 c_high : source_color = vec4(0.36, 0.27, 0.55, 1.0);
uniform vec4 c_top : source_color = vec4(0.12, 0.13, 0.32, 1.0);
uniform vec4 c_cloud : source_color = vec4(0.62, 0.34, 0.5, 1.0);
uniform vec4 c_cloud_lit : source_color = vec4(1.0, 0.7, 0.5, 1.0);
uniform float aspect = 6.0;           // Breite / Höhe des Profils
uniform float sky_from = 0.16;        // ab hier beginnt der gemalte Himmel (Profilanteil)
uniform float brightness = 1.0;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 uv = vec2(UV.x * aspect, UV.y);
	float h = clamp((UV.y - sky_from) / (1.0 - sky_from), 0.0, 1.0);
	vec3 col = mix(c_low.rgb, c_mid.rgb, smoothstep(0.04, 0.25, h));
	col = mix(col, c_high.rgb, smoothstep(0.2, 0.55, h));
	col = mix(col, c_top.rgb, smoothstep(0.5, 0.95, h));
	float band = smoothstep(0.1, 0.18, h) * (1.0 - smoothstep(0.4, 0.55, h));
	float cl = dio_fbm2(vec2(uv.x * 0.9, h * 7.0));
	float cloud = smoothstep(0.55, 0.68, cl) * band;
	float lit = smoothstep(0.62, 0.5, dio_fbm2(vec2(uv.x * 0.9, (h - 0.012) * 7.0)));
	col = mix(col, mix(c_cloud.rgb, c_cloud_lit.rgb, lit * 0.8), cloud * 0.75);
	vec2 sc = floor(uv * 70.0);
	float star = step(0.985, dio_hash12(sc)) * smoothstep(0.55, 0.8, h);
	col += vec3(1.0, 0.95, 0.85) * star * (1.0 - smoothstep(0.05, 0.2, length(fract(uv * 70.0) - 0.5))) * 0.9;
	col *= 0.96 + 0.08 * dio_vnoise2(uv * vec2(12.0, 40.0));

	// Übergang vom Tischtuch: unten beleuchtetes Tuch, darüber der Himmel als Emission
	float sky = smoothstep(sky_from - 0.1, sky_from + 0.08, UV.y);
	sky *= smoothstep(0.0, 0.25, UV.x) * smoothstep(1.0, 0.7, UV.x);    // Enden des Bogens laufen ins Tuch aus
	float d = length((world_pos.xz - center.xz) * vec2(1.0, 0.85));
	float pool = mix(outside, 1.0, 1.0 - smoothstep(pool_r, pool_r + pool_soft, d));
	float fib = dio_vnoise(world_pos * vec3(9.0, 1.0, 9.0)) * 0.5 + dio_vnoise(world_pos.zyx * vec3(11.0, 1.0, 7.0)) * 0.5;
	ALBEDO = table_albedo.rgb * pool * (0.85 + 0.3 * fib) * (1.0 - sky);
	EMISSION = col * brightness * sky;
	ROUGHNESS = 1.0;
	SPECULAR = 0.1;
}
