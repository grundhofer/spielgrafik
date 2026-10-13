// Statische Hafengeometrie im N64-Look: Textur (32×32, 3-Punkt-Filter) mal Licht je Eckpunkt.
// Das Licht kommt aus den gebackenen Vertexfarben von harbor_n64.glb (R = Umgebungsverdeckung,
// G = Abendsonne mit Schatten, B = Fensterlicht) und der flackernden Laterne, die je Eckpunkt dazukommt.
// Nebel je Eckpunkt. Alles wird im vertex() gerechnet und nur interpoliert (Gouraud).
shader_type spatial;
render_mode unshaded, cull_back, specular_disabled;

#include "res://shaders/n64_common.gdshaderinc"

uniform sampler2D tex : source_color, filter_nearest_mipmap, repeat_enable;
uniform float use_tex = 1.0;
uniform vec2 uv_scale = vec2(1.0);          // Kacheln je Meter (UVs in Metern)
uniform vec4 tint : source_color = vec4(1.0);
uniform vec3 emission = vec3(0.0);          // leuchtende Teile (Glas)
uniform float emission_fog = 0.35;          // wie stark Nebel das Leuchten schluckt
uniform float light_boost = 1.0;

varying vec3 v_light;
varying float v_fog;

void vertex() {
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 wn = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	vec3 bake = n64_vc_on > 0.5 ? COLOR.rgb : vec3(1.0, max(dot(wn, -n64_sun_dir), 0.0), 0.0);
	vec3 l = n64_hemi(wn) * bake.r
		+ n64_sun_color.rgb * n64_sun_energy * bake.g
		+ n64_window_color.rgb * bake.b
		+ n64_lantern(wp, wn);
	v_light = l * light_boost;
	if (n64_debug > 0.5) {
		v_light = vec3(n64_debug < 1.5 ? bake.r : (n64_debug < 2.5 ? bake.g : bake.b));
	}
	float depth = -(VIEW_MATRIX * vec4(wp, 1.0)).z;
	v_fog = n64_fog(depth);
}

void fragment() {
	vec3 albedo = tint.rgb;
	if (use_tex > 0.5 && n64_debug < 0.5) {
		albedo *= n64_tex(tex, UV * uv_scale).rgb;
	}
	vec3 c = albedo * v_light + emission;
	float f = length(emission) > 0.0 ? v_fog * emission_fog : v_fog;
	ALBEDO = mix(c, n64_fog_color.rgb, f);
}
