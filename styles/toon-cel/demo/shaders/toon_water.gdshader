// Toon-Wasser für das Mesh "Sea" (Ersatz für das glTF-Material "Water").
// - Dünung als Verschiebung in Weltkoordinaten (wie shared/3d), Zeit aus dem Skript (toon_time).
// - Farbe in harten Stufen: flaches Türkis nahe an Mauern und Strand, tiefes Blau, in der Ferne
//   gestufte Spiegelung des Abendhimmels (gleiche Farben wie der Himmel, globale Uniforms).
// - Schaumlinien: Schaumkante, wo das Wasser auf Geometrie trifft (Tiefenpuffer, Abstand entlang
//   des Sehstrahls), dazu ein abgelöster zweiter Ring, der nach außen wandert und schmaler wird.
// - Wellenlinien: Kanten eines Voronoi-Musters (F2 − F1), verzerrt und treibend.
// - Glitzern: Spiegelung der Lampen (Leuchtfeuer, Laterne) an den Wellennormalen, hart gestuft.
// Durchsichtig gerendert (ALPHA), damit der Tiefenpuffer der deckenden Geometrie lesbar ist.
shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_back, unshaded, shadows_disabled;

global uniform float toon_time;
global uniform vec4 sky_top : source_color;
global uniform vec4 sky_mid : source_color;
global uniform vec4 sky_low : source_color;
global uniform vec4 sky_glow : source_color;

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest, repeat_disable;

uniform vec4 shallow : source_color = vec4(0.22, 0.64, 0.72, 1.0);
uniform vec4 deep : source_color = vec4(0.14, 0.29, 0.55, 1.0);
uniform vec4 line_col : source_color = vec4(0.5, 0.84, 0.9, 1.0);
uniform vec4 foam_col : source_color = vec4(1.0, 0.95, 0.9, 1.0);
uniform vec4 glint_col : source_color = vec4(1.0, 0.86, 0.55, 1.0);
uniform float swell_height = 0.05;
uniform vec2 harbor_center = vec2(0.0, -12.0);
uniform float swell_radius = 40.0;
uniform float shallow_depth = 1.6;      // m entlang des Sehstrahls
uniform float foam_width = 0.32;
uniform float ring_period = 2.4;        // s
uniform float lines_scale = 2.6;        // m je Zelle
uniform float lines_fade = 70.0;        // m Abstand: Wellenlinien blenden aus
uniform vec3 lamp_a = vec3(10.2, 12.58, -25.6);   // Leuchtfeuer
uniform vec3 lamp_b = vec3(4.10, 1.79, -0.12);    // Laterne
uniform float lamp_a_power = 1.0;
uniform float lamp_b_power = 1.0;

varying vec3 world_pos;

vec3 wave(vec2 p, vec2 dir, float len, float amp, float speed) {
	float k = 6.2831853 / len;
	vec2 d = normalize(dir);
	float ph = k * (dot(d, p) - speed * toon_time);
	return vec3(amp * sin(ph), amp * k * cos(ph) * d);
}

vec3 swell(vec2 p) {
	return wave(p, vec2(0.3, 1.0), 11.0, 1.0, 1.3)
		+ wave(p, vec2(-0.6, 1.0), 17.0, 0.7, 1.7)
		+ wave(p, vec2(1.0, 0.4), 7.0, 0.35, 1.0);
}

vec2 hash2(vec2 p) {
	p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
	return fract(sin(p) * 43758.5453);
}

// Voronoi: x = F1, y = F2
vec2 voronoi(vec2 p, float t) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	float f1 = 8.0;
	float f2 = 8.0;
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 g = vec2(float(x), float(y));
			vec2 o = hash2(i + g);
			o = 0.5 + 0.38 * sin(t + 6.2831853 * o);
			float d = length(g + o - f);
			if (d < f1) {
				f2 = f1;
				f1 = d;
			} else if (d < f2) {
				f2 = d;
			}
		}
	}
	return vec2(f1, f2);
}

vec3 sky_color(float e) {
	// e = Höhe über dem Horizont (sin); gleiche Stufen wie toon_sky.gdshader
	vec3 c = sky_glow.rgb;
	c = mix(c, sky_low.rgb, smoothstep(0.012, 0.045, e));
	c = mix(c, sky_mid.rgb, smoothstep(0.06, 0.16, e));
	c = mix(c, sky_top.rgb, smoothstep(0.17, 0.36, e));
	return c;
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(world_pos.xz - harbor_center));
	vec3 s = swell(world_pos.xz) * swell_height * fade;
	VERTEX.y += s.x;
	world_pos.y += s.x;
}

void fragment() {
	vec3 cam = CAMERA_POSITION_WORLD;
	float dist = length(world_pos - cam);
	vec3 v_world = normalize(cam - world_pos);

	// Wassertiefe entlang des Sehstrahls bis zur deckenden Geometrie dahinter
	float d = texture(depth_tex, SCREEN_UV).r;
	vec4 sv = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, d, 1.0);
	sv.xyz /= sv.w;
	float thick = length(sv.xyz) - length(VERTEX);
	if (d <= 0.0000001) {
		thick = 1000.0;
	}

	// Wellenlinien: Voronoi-Kanten, quer gestreckt (Striche liegen waagerecht im Bild), verzerrt,
	// treibend und durch ein zweites Muster in einzelne Striche zerlegt
	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(world_pos.xz - harbor_center));
	vec2 g = swell(world_pos.xz).yz * swell_height * fade;
	vec2 lp = world_pos.xz * vec2(0.42, 1.0) / lines_scale + vec2(0.04, 0.09) * toon_time;
	lp += 0.22 * vec2(sin(world_pos.z * 0.8 + toon_time * 0.9), cos(world_pos.x * 0.5 + toon_time * 0.7));
	vec2 vo = voronoi(lp, toon_time * 0.6);
	float edge = vo.y - vo.x;
	vec2 mp = world_pos.xz * vec2(0.25, 0.6) / lines_scale - vec2(0.03, 0.05) * toon_time;
	float mask = smoothstep(0.42, 0.5, voronoi(mp + 17.0, 1.3 + toon_time * 0.4).x);
	g += vec2(sin(lp.x * 6.0 + toon_time), cos(lp.y * 5.0 - toon_time)) * 0.06;
	vec3 n_world = normalize(vec3(-g.x, 1.0, -g.y));

	// Grundfarbe in Stufen
	float sh = 1.0 - smoothstep(shallow_depth - 0.03, shallow_depth + 0.03, thick);
	vec3 col = mix(deep.rgb, shallow.rgb, sh);

	// Himmelsspiegelung nur in der Ferne: Fresnel in zwei harten Stufen
	float ndv = max(dot(vec3(0.0, 1.0, 0.0), v_world), 0.0);
	float fr = pow(1.0 - ndv, 4.0);
	float refl = smoothstep(0.52, 0.54, fr) * 0.4 + smoothstep(0.8, 0.82, fr) * 0.45;
	vec3 r = reflect(-v_world, vec3(0.0, 1.0, 0.0));
	col = mix(col, sky_color(r.y), refl);

	// Wellenlinien (nur nah bis mittel)
	float lw = mix(0.06, 0.1, smoothstep(10.0, lines_fade, dist));
	float lines = 1.0 - smoothstep(lw - 0.012, lw + 0.012, edge);
	lines *= mask * (1.0 - smoothstep(lines_fade * 0.5, lines_fade, dist));
	col = mix(col, line_col.rgb, lines * 0.8);

	// Glitzern der Lampen
	vec3 rr = reflect(-v_world, n_world);
	float ga = dot(rr, normalize(lamp_a - world_pos));
	float gb = dot(rr, normalize(lamp_b - world_pos));
	float glint = smoothstep(0.9965, 0.9975, ga) * lamp_a_power + smoothstep(0.993, 0.995, gb) * lamp_b_power;
	col = mix(col, glint_col.rgb, clamp(glint, 0.0, 1.0));

	// Schaum: Kante + abgelöster Ring
	float wob = 0.07 * sin(world_pos.x * 2.3 + toon_time * 1.7) + 0.06 * sin(world_pos.z * 3.1 - toon_time * 1.3)
		+ 0.05 * (edge - 0.3);
	float foam = 1.0 - smoothstep(foam_width - 0.015, foam_width + 0.015, thick + wob);
	float ph = fract(toon_time / ring_period);
	float ring_pos = foam_width + 0.12 + ph * 0.75;
	float ring_w = 0.075 * (1.0 - ph);
	float ring = 1.0 - smoothstep(ring_w - 0.01, ring_w + 0.01, abs(thick + wob * 0.6 - ring_pos));
	ring *= step(0.02, ring_w);
	float near = 1.0 - smoothstep(60.0, 140.0, dist);
	col = mix(col, foam_col.rgb, clamp(foam + ring, 0.0, 1.0) * near);

	ALBEDO = col;
	ALPHA = 1.0;
}
