// Bewegte Figur im N64-Look: Materialfarbe ohne Textur, Licht je Eckpunkt aus Umgebungslicht, Abendsonne,
// einem kühlen Gegenlicht von hinten oben (Kante), Fenster und Laterne; Nebel je Eckpunkt. Wie Figuren der
// Zeit: Licht nur über Normalen und wenige Richtungslichter, keine Schatten.
shader_type spatial;
render_mode unshaded, cull_back, specular_disabled;

#include "res://shaders/n64_common.gdshaderinc"

uniform vec4 albedo : source_color = vec4(1.0);
uniform vec3 rim_dir = vec3(0.3, -0.35, 0.88);     // Richtung, in die das Kantenlicht scheint
uniform vec4 rim_color : source_color = vec4(0.35, 0.4, 0.65, 1.0);
uniform float ambient = 1.0;
uniform float shine = 0.0;                          // Glanzpunkt je Eckpunkt (Augen, Nase, Messing)

varying vec3 v_light;
varying float v_fog;

void vertex() {
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 wn = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	float sun = max(dot(wn, -n64_sun_dir), 0.0);
	float rim = max(dot(wn, -normalize(rim_dir)), 0.0);
	vec3 l = n64_hemi(wn) * ambient
		+ n64_sun_color.rgb * n64_sun_energy * sun
		+ rim_color.rgb * rim
		+ n64_window_color.rgb * 1.6 * n64_point(wp, wn, n64_window_pos, 6.0)
		+ n64_lantern(wp, wn);
	vec3 vdir = normalize((INV_VIEW_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz - wp);
	vec3 h = normalize(vdir - n64_sun_dir);
	l += shine * pow(max(dot(wn, h), 0.0), 12.0) * n64_sun_color.rgb;
	v_light = l;
	float depth = -(VIEW_MATRIX * vec4(wp, 1.0)).z;
	v_fog = n64_fog(depth);
}

void fragment() {
	ALBEDO = mix(albedo.rgb * v_light, n64_fog_color.rgb, v_fog);
}
