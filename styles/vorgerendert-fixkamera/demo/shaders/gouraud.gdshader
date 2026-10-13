// Figur: Licht nur je Eckpunkt (Gouraud), wie bei Echtzeitfiguren vor vorgerenderten Hintergründen
// um 1997–2000. Godots eigenes SHADING_MODE_PER_VERTEX änderte in 4.7 nichts am Bild (gemessen), deshalb
// rechnet dieser Shader das Licht selbst: Grundlicht + 2 Richtungslichter + 3 Punktlichter, Werte setzt
// main.gd jedes Bild aus den Lichtknoten der Szene (linear). Dazwischen nur lineare Interpolation.
shader_type spatial;
render_mode unshaded, cull_back, shadows_disabled, fog_disabled;

uniform vec3 albedo = vec3(1.0);                 // linear
uniform vec3 ambient = vec3(0.1);
uniform vec3 dir_dir[2];                          // Ausbreitungsrichtung (Welt)
uniform vec3 dir_col[2];
uniform vec3 pt_pos[3];
uniform vec3 pt_col[3];
uniform vec2 pt_range[3];                         // Reichweite, Abfall (omni_attenuation)
uniform float per_pixel = 0.0;                    // Vergleich: 1 = gleiche Rechnung je Pixel

varying vec3 v_light;
varying vec3 v_pos;
varying vec3 v_nrm;

vec3 light_at(vec3 p, vec3 n) {
	vec3 c = ambient;
	for (int i = 0; i < 2; i++) {
		c += dir_col[i] * max(dot(n, -dir_dir[i]), 0.0);
	}
	for (int i = 0; i < 3; i++) {
		vec3 l = pt_pos[i] - p;
		float d = max(length(l), 0.0001);
		float nd = d / pt_range[i].x;
		nd *= nd;
		nd *= nd;
		nd = max(1.0 - nd, 0.0);
		float att = nd * nd * pow(d, -pt_range[i].y);
		c += pt_col[i] * att * max(dot(n, l / d), 0.0);
	}
	return c;
}

void vertex() {
	v_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_nrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	v_light = light_at(v_pos, v_nrm);
}

void fragment() {
	vec3 l = per_pixel > 0.5 ? light_at(v_pos, normalize(v_nrm)) : v_light;
	vec3 c = albedo * l;
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
	// Kompatibilitäts-Renderer gibt unbeleuchtete Farben ohne Umrechnung aus (gemessen): selbst nach sRGB
	c = mix(c * 12.92, 1.055 * pow(max(c, vec3(0.0)), vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), c));
#endif
	ALBEDO = c;
}
