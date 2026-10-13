// Wasser für Pixel-3D (Ersatz für das glTF-Material "Water" am Mesh "Sea").
// - Spiegelung des Himmels in denselben harten Farbbändern wie p3d_sky: Die Höhe des gespiegelten
//   Strahls bestimmt das Band; Kräuselwellen verbiegen die Bandgrenzen zu Wellenstrichen.
// - Mischung mit der Wasserfarbe nach Fresnel, in Stufen.
// - Glitzern unter Laterne, Fenster und Leuchtfeuer (Spiegelung der Lampen an der Wellennormale).
// - Schaumkante, wo das Wasser Kai, Steg, Boote und Felsen berührt (Tiefenpuffer: Dicke des
//   Wassers entlang des Sehstrahls), dazu ein Schaumring, der nach außen wandert.
// - Gestufter Nebel wie p3d_post.
// Durchsichtig gerendert (ALPHA = 1), damit der Tiefenpuffer der deckenden Geometrie lesbar ist.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_always, cull_back, fog_disabled, shadows_disabled;

#include "res://shaders/p3d_common.gdshaderinc"

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest, repeat_disable;

uniform vec4 deep : source_color = vec4(0.10, 0.15, 0.27, 1.0);
uniform vec4 mid : source_color = vec4(0.16, 0.24, 0.38, 1.0);
uniform vec4 foam : source_color = vec4(0.96, 0.84, 0.74, 1.0);
uniform vec4 glint : source_color = vec4(1.0, 0.86, 0.52, 1.0);
// Himmelsbänder (dieselben Werte wie p3d_sky; main.gd kopiert sie)
uniform vec4 c0 : source_color = vec4(1.0, 0.80, 0.45, 1.0);
uniform vec4 c1 : source_color = vec4(0.97, 0.60, 0.34, 1.0);
uniform vec4 c2 : source_color = vec4(0.87, 0.42, 0.38, 1.0);
uniform vec4 c3 : source_color = vec4(0.66, 0.31, 0.44, 1.0);
uniform vec4 c4 : source_color = vec4(0.43, 0.25, 0.43, 1.0);
uniform vec4 c5 : source_color = vec4(0.27, 0.20, 0.38, 1.0);
uniform vec4 c6 : source_color = vec4(0.16, 0.14, 0.28, 1.0);
uniform vec4 bands_deg = vec4(1.6, 4.2, 8.0, 13.0);
uniform vec2 bands_deg2 = vec2(19.0, 27.0);

uniform float swell_height = 0.05;
uniform vec2 harbor_center = vec2(0.0, -12.0);
uniform float swell_radius = 40.0;
uniform float ripple_strength = 5.0;     // Grad Verbiegung der Bänder
uniform float ripple_fade = 70.0;        // m
uniform float foam_width = 0.22;         // m Wasserdicke für die Schaumkante
uniform float ring_period = 2.6;         // s
uniform float ring_dist = 0.75;          // m, so weit wandert der Ring
uniform vec3 lamp0 = vec3(4.1, 1.79, -0.12);     // Laterne
uniform vec3 lamp1 = vec3(-9.2, 1.45, 0.52);     // Fenster
uniform vec3 lamp2 = vec3(10.2, 12.58, -25.6);   // Leuchtfeuer
uniform vec3 lamp_size = vec3(0.06, 0.05, 0.05); // Schwelle 1 - cos
uniform float lamp0_gain = 1.0;
uniform float lamp2_gain = 1.0;

varying vec3 world_pos;

vec3 wave(vec2 p, vec2 dir, float len, float amp, float speed) {
	float k = 6.2831853 / len;
	vec2 d = normalize(dir);
	float ph = k * (dot(d, p) - speed * p3d_time);
	return vec3(amp * sin(ph), amp * k * cos(ph) * d);
}

vec3 swell(vec2 p) {
	return wave(p, vec2(0.3, 1.0), 11.0, 1.0, 1.3)
		+ wave(p, vec2(-0.6, 1.0), 17.0, 0.7, 1.7)
		+ wave(p, vec2(1.0, 0.4), 7.0, 0.35, 1.0);
}

// Neigung der Kräuselung (Ableitung nach x und z)
vec2 ripples(vec2 p) {
	vec3 r = wave(p, vec2(0.15, 1.0), 2.6, 0.06, 0.7)
		+ wave(p, vec2(-0.5, 1.0), 1.9, 0.05, 0.6)
		+ wave(p, vec2(0.7, 1.0), 1.3, 0.035, 0.5)
		+ wave(p, vec2(-0.2, -1.0), 3.4, 0.06, 0.8);
	return r.yz;
}

vec3 band_color(float e, float th) {
	float limits[6] = {bands_deg.x, bands_deg.y, bands_deg.z, bands_deg.w, bands_deg2.x, bands_deg2.y};
	int idx = 6;
	for (int i = 0; i < 6; i++) {
		if (e < limits[i]) {
			idx = i;
			break;
		}
	}
	if (idx <= 0) return c0.rgb;
	if (idx == 1) return c1.rgb;
	if (idx == 2) return c2.rgb;
	if (idx == 3) return c3.rgb;
	if (idx == 4) return c4.rgb;
	if (idx == 5) return c5.rgb;
	return c6.rgb;
}

float glint_at(vec3 wp, vec3 r, vec3 lamp, float size) {
	vec3 l = normalize(lamp - wp);
	return step(1.0 - size, dot(r, l));
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(world_pos.xz - harbor_center));
	vec3 s = swell(world_pos.xz) * swell_height * fade;
	VERTEX.y += s.x;
	world_pos.y += s.x;
}

void fragment() {
	vec2 frag = FRAGCOORD.xy;
	vec3 cam = CAMERA_POSITION_WORLD;
	vec3 to_eye = cam - world_pos;
	float dist = length(to_eye);
	vec3 v = to_eye / dist;

	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(world_pos.xz - harbor_center));
	vec2 g = swell(world_pos.xz).yz * swell_height * fade;
	float rf = 1.0 - smoothstep(ripple_fade * 0.4, ripple_fade, dist);
	g += ripples(world_pos.xz) * rf;
	vec3 n = normalize(vec3(-g.x, 1.0, -g.y));

	// Spiegelung: Höhe des gespiegelten Strahls in Grad
	vec3 r = reflect(-v, n);
	float e = degrees(asin(clamp(r.y, -1.0, 1.0)));
	float e_flat = degrees(asin(clamp(v.y, 0.0, 1.0)));
	// Kräuselung verbiegt die Bänder stärker als die physikalische Normale (Wellenstriche)
	e = e_flat + (e - e_flat) * ripple_strength * 0.2;
	vec3 refl = band_color(max(e, 0.0), 0.0);

	// Fresnel in drei Stufen: flach gesehen mehr Spiegelung
	float fres = pow(1.0 - clamp(v.y, 0.0, 1.0), 4.0);
	float fq = p3d_steps(fres, 3.0, 0.3, frag);
	vec3 water = mix(deep.rgb, mid.rgb, step(0.34, fq));
	vec3 col = mix(water, refl, 0.25 + 0.6 * fq);

	// Glitzern der Lampen: schmale Säulen aus Strichen
	float gl = glint_at(world_pos, r, lamp0, lamp_size.x) * lamp0_gain
		+ glint_at(world_pos, r, lamp1, lamp_size.y)
		+ glint_at(world_pos, r, lamp2, lamp_size.z) * lamp2_gain;
	col = mix(col, glint.rgb, step(0.5, gl) * rf);

	// Schaum aus dem Tiefenpuffer: Dicke des Wassers entlang des Sehstrahls
	float d = texture(depth_tex, SCREEN_UV).r;
	vec4 vb = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, p3d_ndc_z(d), 1.0);
	vb.xyz /= vb.w;
	float thick = p3d_is_sky(d) ? 1000.0 : length(vb.xyz - VERTEX);
	float ring_t = fract(p3d_time / ring_period);
	float ring_r = foam_width + ring_dist * ring_t;
	float ring = step(abs(thick - ring_r), 0.06 * (1.0 - ring_t)) * step(dist, 40.0);
	float edge = step(thick, foam_width) * step(dist, 120.0);
	col = mix(col, foam.rgb, max(edge, ring * 0.75));

	col = mix(col, p3d_fog_color.rgb, p3d_fog(dist, frag));
	ALBEDO = col;
	ALPHA = 1.0;
}
