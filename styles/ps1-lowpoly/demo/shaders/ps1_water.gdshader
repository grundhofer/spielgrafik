// PS1-Wasser für das Mesh "Sea": Dünung als Verschiebung der Gitterpunkte (Gitter 1,5 m im Hafen),
// Licht und Glanz je Eckpunkt, eine 64×64-Wassertextur, die über die Fläche wandert (UV-Verschiebung),
// affin und auf Pixel gerundet wie alles andere, Depth Cueing über Vertexfarben. Zeit kommt aus main.gd
// (ps1_time). In der Sortierung liegt das Meer ganz hinten (ot_bias): Alles, was darüber liegt, wird
// darüber gemalt; was das Wasser verdecken soll, ist in harbor_ps1.glb abgeschnitten.
shader_type spatial;
render_mode unshaded, cull_back, depth_draw_opaque, fog_disabled, shadows_disabled;

#include "res://shaders/ps1_common.gdshaderinc"

uniform sampler2D tex : source_color, filter_nearest, repeat_enable;
uniform sampler2D tex_mip : source_color, filter_nearest_mipmap, repeat_enable;   // nur Vergleich (ps1_mip)
uniform float tex_meters = 5.0;              // eine Kachel je 5 m
uniform vec2 scroll = vec2(0.035, 0.06);     // Kacheln pro Sekunde
uniform float swell_height = 0.07;
uniform vec2 harbor_center = vec2(0.0, -12.0);
uniform float swell_radius = 40.0;
uniform vec3 glint_color : source_color = vec3(1.0, 0.75, 0.45);
uniform float ot_bias = 1000.0;

varying vec3 v_mul;
varying vec3 v_add;
varying vec3 v_mul_w;                    // mal w, im Fragment geteilt: Gouraud linear im Bildraum
varying vec3 v_add_w;
varying vec3 v_affine;
varying vec2 v_uv;
varying float v_ot;

vec3 wave(vec2 p, vec2 dir, float len, float amp, float speed) {
	float k = 6.2831853 / len;
	float ph = k * (dot(normalize(dir), p) - speed * ps1_time);
	return vec3(amp * sin(ph), amp * k * cos(ph) * normalize(dir));
}

void vertex() {
	vec3 wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(wpos.xz - harbor_center));
	vec3 s = (wave(wpos.xz, vec2(0.3, 1.0), 9.0, 1.0, 1.3)
		+ wave(wpos.xz, vec2(-0.7, 1.0), 5.0, 0.6, 1.1)
		+ wave(wpos.xz, vec2(1.0, 0.3), 3.3, 0.35, 0.9)) * swell_height * fade;
	VERTEX.y += s.x;
	wpos.y += s.x;
	vec3 wn = normalize(vec3(-s.y * 3.0, 1.0, -s.z * 3.0));
	vec3 light = ps1_light(wpos, wn, 1.0);
	// Glanz je Eckpunkt: Abendhimmel spiegelt sich, stärker wo die Welle zur Kamera kippt
	vec3 to_cam = normalize(CAMERA_POSITION_WORLD - wpos);
	float glint = pow(clamp(dot(reflect(-to_cam, wn), normalize(vec3(0.15, 0.12, -1.0))), 0.0, 1.0), 12.0);
	light += glint_color * glint * 1.4 * fade;
	vec4 view = MODELVIEW_MATRIX * vec4(VERTEX, 1.0);
	float cue = ps1_fog(-view.z);        // Depth Cueing je Eckpunkt: zwei Vertexfarben
	v_mul = light * (1.0 - cue);
	v_add = ps1_fog_color.rgb * cue;
	v_ot = -view.z + ot_bias;
	vec4 clip = ps1_snap(PROJECTION_MATRIX * view);
	POSITION = clip;
	v_mul_w = v_mul * clip.w;
	v_add_w = v_add * clip.w;
	vec2 uv = wpos.xz / tex_meters + scroll * ps1_time;
	v_affine = vec3(uv * clip.w, clip.w);
	v_uv = uv;
}

void fragment() {
	vec2 uv = mix(v_uv, v_affine.xy / v_affine.z, ps1_affine);
	vec3 t = ps1_mip > 0.5 ? texture(tex_mip, uv).rgb : texture(tex, uv).rgb;
	vec3 mul = mix(v_mul, v_mul_w / v_affine.z, ps1_affine_vc);
	vec3 add = mix(v_add, v_add_w / v_affine.z, ps1_affine_vc);
	ALBEDO = t * mul + add;
	DEPTH = ps1_ot > 0.5 ? ps1_ot_depth(v_ot, PROJECTION_MATRIX) : FRAGCOORD.z;
}
