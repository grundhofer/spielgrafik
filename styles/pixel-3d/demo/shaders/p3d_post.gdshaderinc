// Gemeinsamer Teil von p3d_post.gdshader (Forward+, mit Normalenpuffer: Konturen und Kantenlicht) und
// p3d_post_depth.gdshader (Mobile/Compatibility: nur Konturen aus dem Tiefenpuffer). Beschreibung dort.
// Mit P3D_NORMALS wird der Normalenpuffer gelesen (gibt es nur in Forward+).

#include "res://shaders/p3d_common.gdshaderinc"

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest, repeat_disable;
uniform sampler2D screen_tex : hint_screen_texture, filter_nearest, repeat_disable;
#ifdef P3D_NORMALS
uniform sampler2D nr_tex : hint_normal_roughness_texture, filter_nearest, repeat_disable;
#endif

uniform float outlines = 1.0;
uniform float highlights = 1.0;
uniform float fog = 1.0;
uniform float depth_threshold = 0.025;   // relativer Fehler der 1/z-Vorhersage
uniform float normal_threshold = 0.22;   // 1 - N·N
uniform vec4 ink : source_color = vec4(0.09, 0.05, 0.14, 1.0);
uniform float outline_keep = 0.3;        // Anteil der Objektfarbe in der Kontur
uniform float outline_ink = 0.55;        // Anteil Tinte
uniform float highlight_gain = 1.45;
uniform vec4 highlight_tint : source_color = vec4(1.0, 0.86, 0.66, 1.0);
uniform vec3 light_view = vec3(-0.6, 0.6, 0.5);  // Lichtrichtung im Kameraraum (main.gd setzt sie)
uniform float outline_fade = 80.0;       // m: Linien ab hier schwächer (Ferne bleibt ruhig)
uniform float debug_edges = 0.0;         // 1: Konturen rot, Kantenlicht grün (Prüfbild)

void vertex() {
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}

vec3 view_pos(vec2 uv, float d, mat4 ip) {
	vec4 v = ip * vec4(uv * 2.0 - 1.0, p3d_ndc_z(d), 1.0);
	return v.xyz / v.w;
}

void fragment() {
	vec2 px = 1.0 / VIEWPORT_SIZE;
	vec2 uv = SCREEN_UV;
	float dc = texture(depth_tex, uv).r;
	vec3 col = textureLod(screen_tex, uv, 0.0).rgb;
	if (p3d_is_sky(dc)) {
		// Himmel: unverändert durchreichen
		ALBEDO = col;
		ALPHA = 0.0;
	} else {
		vec3 vc = view_pos(uv, dc, INV_PROJECTION_MATRIX);
		float zc = -vc.z;
		float izc = 1.0 / zc;
#ifdef P3D_NORMALS
		vec3 nc = normalize(texture(nr_tex, uv).xyz * 2.0 - 1.0);
#endif
		vec2 dirs[4] = {vec2(1.0, 0.0), vec2(-1.0, 0.0), vec2(0.0, 1.0), vec2(0.0, -1.0)};
		float sil = 0.0;
		float hl = 0.0;
		for (int k = 0; k < 4; k++) {
			vec2 un = uv + dirs[k] * px;
			vec2 uo = uv - dirs[k] * px;
			float dn = texture(depth_tex, un).r;
			float dop = texture(depth_tex, uo).r;
			float izn = 0.0;
			vec3 vn = vec3(0.0);
			if (!p3d_is_sky(dn)) {
				vn = view_pos(un, dn, INV_PROJECTION_MATRIX);
				izn = 1.0 / -vn.z;
			}
			float izo = 0.0;
			if (!p3d_is_sky(dop)) {
				izo = 1.0 / -view_pos(uo, dop, INV_PROJECTION_MATRIX).z;
			}
			float pred = 2.0 * izc - izo;
			float err = (pred - izn) / izc;
			// Nachbar hinter der Vorhersage und hinter der Mitte: Mitte ist Außenkante
			if (izn < izc * 0.995 && err > depth_threshold) {
				sil = 1.0;
			}
#ifdef P3D_NORMALS
			else if (!p3d_is_sky(dn) && abs(izn - izc) < 0.08 * izc) {
				vec3 nn = normalize(texture(nr_tex, un).xyz * 2.0 - 1.0);
				if (1.0 - dot(nc, nn) > normal_threshold) {
					vec3 d = normalize(vn - vc);
					bool convex = dot(nc - nn, d) < -0.05;
					bool lit_side = dot(nc, light_view) > dot(nn, light_view);
					if (convex && lit_side) {
						hl = 1.0;
					}
				}
			}
#endif
		}
		float fade = 1.0 - 0.5 * step(outline_fade, zc);
		vec3 outc = mix(col * outline_keep, ink.rgb, outline_ink);
		vec3 hlc = col * highlight_gain * highlight_tint.rgb + highlight_tint.rgb * 0.03;
		vec3 c = col;
		if (sil * outlines > 0.5) {
			c = mix(col, outc, fade);
		} else if (hl * highlights > 0.5) {
			c = mix(col, hlc, fade);
		}
		if (debug_edges > 0.5) {
			c = col * 0.35 + vec3(sil, hl * (1.0 - sil), 0.0);
		}
		float f = p3d_fog(zc, FRAGCOORD.xy) * fog;
		c = mix(c, p3d_fog_color.rgb, f);
		ALBEDO = c;
		ALPHA = 1.0;
	}
}
