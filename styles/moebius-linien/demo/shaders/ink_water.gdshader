// Wasser als flache Pastellfläche mit Tuschestrichen: Grundfarbe nah türkis, zum Horizont heller
// (Himmel spiegelt sich), Schlagschatten von Booten, Steg und Kai in der Schattenstufe mit Schraffur
// wie ink.gdshader. Wellen als kurze waagerechte Striche, die in Weltkoordinaten liegen, auftauchen,
// sich strecken und wieder verschwinden; dazwischen helle Glanzstriche. Strichbreite in Pixeln
// (fwidth), deshalb gleich dünn in der Nähe und in der Ferne. Leichte Dünung als Verschiebung.
shader_type spatial;
render_mode cull_back, depth_draw_opaque, ambient_light_disabled;

global uniform float ink_time;
global uniform vec4 ink_color;   // linear (globale Farben werden nicht aus sRGB umgerechnet)
global uniform vec4 ink_shadow;   // linearer Faktor
global uniform float ink_hatch;
global uniform float ink_shade;

uniform vec4 albedo : source_color = vec4(0.55, 0.8, 0.78, 1.0);
uniform vec4 albedo_far : source_color = vec4(0.84, 0.9, 0.86, 1.0);
uniform vec4 glint : source_color = vec4(1.0, 0.97, 0.88, 1.0);
uniform float far_begin = 25.0;
uniform float far_end = 260.0;
uniform float swell = 0.05;
uniform int material_id = 15;
uniform float stroke_px = 1.3;
uniform float strokes_on = 1.0;

varying vec3 wpos;
varying flat vec2 anchor_px;
varying float hatch_line;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

void vertex() {
	vec3 w = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	// Dünung nur im Hafen; außen ist das Gitter grob (Zellen bis zu Hunderte Meter)
	float fade = 1.0 - smoothstep(18.0, 40.0, length(w.xz - vec2(2.0, -8.0)));
	float h = swell * fade * (0.6 * sin(w.x * 0.55 + ink_time * 1.3) + 0.4 * sin(w.z * 0.8 + w.x * 0.2 - ink_time * 1.1));
	VERTEX.y += h;
	wpos = w + vec3(0.0, h, 0.0);
	vec4 o = PROJECTION_MATRIX * (MODELVIEW_MATRIX * vec4(0.0, 0.0, 0.0, 1.0));
	anchor_px = (o.xy / o.w * 0.5 + 0.5) * VIEWPORT_SIZE;
}

// Wellenstriche einer Zellenreihe: Zelle cell_size (x, z), je Zelle ein Strich mit eigener Phase.
// Gibt die Deckung des Strichs zurück (0..1); kind = 0 dunkel, 1 hell.
float strokes(vec2 p, vec2 fw, vec2 cell_size, float period, float seed, float len_m, out float kind) {
	vec2 cell = floor(p / cell_size);
	float cov = 0.0;
	kind = 0.0;
	for (int dx = -1; dx <= 1; dx++) {
		vec2 c = cell + vec2(float(dx), 0.0);
		float r1 = hash(c + seed);
		float r2 = hash(c + seed + 17.3);
		float r3 = hash(c + seed + 41.9);
		vec2 center = (c + vec2(0.5 + 0.6 * (r1 - 0.5), 0.2 + 0.6 * r2)) * cell_size;
		center.x += 0.25 * ink_time * (r3 - 0.3);       // treibt langsam
		float life = fract(ink_time / period + r3);      // 0..1: auftauchen, strecken, verschwinden
		float grow = sin(3.14159 * life);
		float half_len = 0.5 * len_m * (0.5 + r1) * grow;
		if (half_len < 0.02) {
			continue;
		}
		float dz = abs(p.y - center.y);
		float dxm = max(abs(p.x - center.x) - half_len, 0.0);
		// Pixelabstände: z über fwidth(z), x über fwidth(x) (vor der Schleife bestimmt)
		float d_px = length(vec2(dxm / fw.x, dz / fw.y));
		float c_cov = 1.0 - smoothstep(stroke_px * 0.5 - 0.5, stroke_px * 0.5 + 0.5, d_px);
		if (c_cov > cov) {
			cov = c_cov;
			kind = step(0.72, r2);
		}
	}
	return cov;
}

void fragment() {
	float dist = length(wpos - CAMERA_POSITION_WORLD);
	vec3 base = mix(albedo.rgb, albedo_far.rgb, smoothstep(far_begin, far_end, dist));
	ALBEDO = base;
	METALLIC = 0.0;
	SPECULAR = 0.0;
	ROUGHNESS = (float(material_id) + 0.5) / 32.0;

	// Wellenstriche: zwei Zellenreihen (nah fein, fern grob), ausgeblendet, wo sie zu dicht würden
	float k1;
	float k2;
	vec2 fw = max(fwidth(wpos.xz), vec2(1e-5));
	float s1 = strokes(wpos.xz, fw, vec2(2.6, 0.9), 3.1, 3.0, 1.3, k1);
	float s2 = strokes(wpos.xz, fw, vec2(11.0, 4.0), 4.3, 9.0, 5.5, k2);
	// ausblenden, sobald ein Pixel mehr als etwa ein Achtel der Zellentiefe überdeckt (sonst Brei)
	float near_fade = 1.0 - smoothstep(0.08, 0.16, fw.y / 0.9);
	float far_fade = smoothstep(18.0, 40.0, dist) * (1.0 - smoothstep(0.08, 0.16, fw.y / 4.0));
	s1 *= near_fade * strokes_on;
	s2 *= far_fade * strokes_on;
	float dark = max(s1 * (1.0 - k1), s2 * (1.0 - k2));
	float light = max(s1 * k1, s2 * k2);
	ALBEDO = mix(ALBEDO, glint.rgb, light);
	ALBEDO = mix(ALBEDO, ink_color.rgb, dark * 0.9);

	vec2 p = FRAGCOORD.xy - anchor_px;
	float u = dot(p, vec2(sin(0.96), cos(0.96)));
	float d = abs(fract(u / 5.0) - 0.5) * 5.0;
	hatch_line = 1.0 - smoothstep(0.075, 1.075, d);
}

void light() {
	if (LIGHT_IS_DIRECTIONAL) {
		float lit = smoothstep(0.42, 0.58, ATTENUATION);
		lit = mix(1.0, lit, ink_shade);
		float h = hatch_line * 0.75 * ink_hatch;
		DIFFUSE_LIGHT += mix(ink_shadow.rgb * (1.0 - h), vec3(1.0), lit);
	}
}
