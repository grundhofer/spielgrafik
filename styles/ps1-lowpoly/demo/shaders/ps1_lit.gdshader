// PS1-Material für Hafen und Dachs: Vertex-Snapping, Gouraud-Licht je Eckpunkt mit vorberechneten
// Vertexfarben, Depth Cueing über Vertexfarben, affine Texturen (64×64, Nearest, ohne Mipmaps),
// Sortierung nach Polygonen statt Z-Puffer. Ersetzt die glTF-Materialien per Name (main.gd).
shader_type spatial;
render_mode unshaded, cull_back, depth_draw_opaque, fog_disabled, shadows_disabled;

#include "res://shaders/ps1_common.gdshaderinc"

uniform vec4 albedo : source_color = vec4(1.0);
uniform sampler2D tex : source_color, filter_nearest, repeat_enable;
uniform sampler2D tex_mip : source_color, filter_nearest_mipmap, repeat_enable;   // nur Vergleich (ps1_mip)
uniform bool use_tex = false;
uniform bool cutout = false;             // Texel mit Alpha 0 sind durchsichtig (wie Farbe 0 auf der Konsole)
uniform vec2 uv_scale = vec2(1.0);       // UVs sind in Metern; 0.5 = eine Kachel je 2 m
uniform vec3 emission : source_color = vec3(0.0);
uniform float emit_scale = 0.0;          // leuchtende Teile (Glas); main.gd lässt flackern
uniform float lit = 1.0;                 // 0 = unbeleuchtet (Glas)
uniform vec3 light_boost = vec3(0.0);    // eigenes Zusatzlicht je Objekt (Figur), wie eigene Lichtmatrix
uniform float ot_bias = 0.0;             // Versatz in der Sortierung (m), siehe main.gd -> OT_BIAS
uniform bool ot_per_pixel = false;       // Kaiboden: Tiefe je Pixel (+ ot_bias) statt je Polygon

varying vec3 v_mul;                      // Vertexfarbe 1: moduliert die Textur (Licht × (1 − Nebel))
varying vec3 v_add;                      // Vertexfarbe 2: Ferne-Farbe × Nebel + Leuchten
varying vec3 v_mul_w;                    // beide mal w: im Fragment durch w geteilt = linear im Bildraum
varying vec3 v_add_w;
varying vec3 v_affine;
varying vec2 v_uv;
varying flat float v_ot;                 // Sortiertiefe des ganzen Dreiecks
varying float v_dist;                    // Tiefe je Pixel (nur Kaiboden)

void vertex() {
	vec3 wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 wn = normalize(MODEL_NORMAL_MATRIX * NORMAL);
	vec3 light = mix(vec3(1.0), ps1_light(wpos, wn, COLOR.r) + light_boost, lit);
	vec4 view = MODELVIEW_MATRIX * vec4(VERTEX, 1.0);
	float cue = ps1_fog(-view.z);        // Depth Cueing je Eckpunkt: zwei Vertexfarben
	v_mul = light * (1.0 - cue);
	v_add = ps1_fog_color.rgb * cue + emission * emit_scale * (1.0 - cue);
	// Mittelpunkt des Dreiecks = Eckpunkt + Versatz (CUSTOM0, beim Laden berechnet)
	v_ot = -(MODELVIEW_MATRIX * vec4(VERTEX + CUSTOM0.xyz, 1.0)).z + ot_bias;
	v_dist = -view.z + ot_bias;
	vec4 clip = ps1_snap(PROJECTION_MATRIX * view);
	POSITION = clip;
	v_mul_w = v_mul * clip.w;
	v_add_w = v_add * clip.w;
	v_affine = vec3(UV * uv_scale * clip.w, clip.w);
	v_uv = UV * uv_scale;
}

void fragment() {
	vec3 base = albedo.rgb;
	if (use_tex) {
		vec2 uv = mix(v_uv, v_affine.xy / v_affine.z, ps1_affine);
		vec4 t = ps1_mip > 0.5 ? texture(tex_mip, uv) : texture(tex, uv);
		if (cutout && t.a < 0.5) {
			discard;
		}
		base = t.rgb;
	}
	vec3 mul = mix(v_mul, v_mul_w / v_affine.z, ps1_affine_vc);
	vec3 add = mix(v_add, v_add_w / v_affine.z, ps1_affine_vc);
	ALBEDO = base * mul + add;
	DEPTH = ps1_ot > 0.5 ? ps1_ot_depth(ot_per_pixel ? v_dist : v_ot, PROJECTION_MATRIX) : FRAGCOORD.z;
}
