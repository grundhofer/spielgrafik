shader_type spatial;
// Kaipflaster: eigene ebene Fläche 12 mm über den modellierten Platten aus shared/3d, darauf
// Granit-Kopfsteinpflaster (Poly Haven, CC0) mit
//  - Parallax Occlusion Mapping aus der Höhenkarte (Steine stehen aus der Fläche heraus,
//    verdecken sich bei flachem Blick gegenseitig),
//  - Nässe: Fugen und Mulden halten Wasser (Höhe unter einem Pegel, der großflächig schwankt),
//    dort Rauheit fast 0 und Normale flach -> Pfützen spiegeln Laterne, Fenster und Himmel (SSR),
//    der Rest ist feucht (dunkler, glatter).
// Abbildung: uv = Welt-xz / Kachelgröße. Normalenkarte (OpenGL): Bild rechts = +x, Bild oben = -z.
render_mode cull_back, depth_draw_opaque;

uniform sampler2D tex_a : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tex_n : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tex_orm : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tex_h : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D puddle_noise : hint_default_black, filter_linear_mipmap, repeat_enable;
uniform float tile_m = 2.0;
uniform float depth_m = 0.035;          // Tiefe der Fugen für die Parallaxe
uniform int pom_min_layers = 10;
uniform int pom_max_layers = 40;
uniform bool use_pom = true;
uniform float wet_level = 0.30;         // Höhenpegel, unter dem Wasser steht (0..1 der Höhenkarte)
uniform float wet_level_var = 0.28;     // großflächige Schwankung des Pegels
uniform float puddle_scale_m = 6.0;
uniform float damp = 0.55;              // allgemeine Feuchte 0..1
uniform vec3 tint : source_color = vec3(1.0);
uniform float macro_amount = 0.22;      // großflächige Helligkeits- und Feuchteschwankung gegen Kachelmuster
uniform float macro_scale_m = 9.0;
uniform float albedo_gain = 1.0;

varying vec3 v_wpos;

void vertex() {
	v_wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

vec3 unpack_n(vec4 t) {
	vec2 xy = t.xy * 2.0 - 1.0;
	return vec3(xy, sqrt(max(1.0 - dot(xy, xy), 0.0)));
}

void fragment() {
	vec2 uv = v_wpos.xz / tile_m;
	vec2 gx = dFdx(uv);
	vec2 gy = dFdy(uv);
	vec3 V = normalize(CAMERA_POSITION_WORLD - v_wpos);   // zur Kamera
	float h_at = 1.0;
	if (use_pom) {
		// Steep Parallax mit linearer Verfeinerung; Schritte nach Blickwinkel
		float vy = max(V.y, 0.08);
		vec2 shift = -V.xz / vy * (depth_m / tile_m);   // uv-Versatz für volle Tiefe
		float layers = mix(float(pom_max_layers), float(pom_min_layers), clamp(V.y, 0.0, 1.0));
		float step_d = 1.0 / layers;
		float cur_d = 0.0;
		vec2 cur_uv = uv;
		float cur_h = textureGrad(tex_h, cur_uv, gx, gy).r;
		float prev_h = cur_h;
		vec2 prev_uv = cur_uv;
		float prev_d = 0.0;
		for (int i = 0; i < 64; i++) {
			if (float(i) >= layers || (1.0 - cur_h) <= cur_d) break;
			prev_uv = cur_uv; prev_h = cur_h; prev_d = cur_d;
			cur_d += step_d;
			cur_uv = uv + shift * cur_d;
			cur_h = textureGrad(tex_h, cur_uv, gx, gy).r;
		}
		// Schnitt zwischen den letzten beiden Schritten
		float after = (1.0 - cur_h) - cur_d;
		float before = (1.0 - prev_h) - prev_d;
		float wgt = after / (after - before + 1e-5);
		uv = mix(cur_uv, prev_uv, clamp(wgt, 0.0, 1.0));
		h_at = textureGrad(tex_h, uv, gx, gy).r;
	} else {
		h_at = textureGrad(tex_h, uv, gx, gy).r;
	}

	vec3 a = textureGrad(tex_a, uv, gx, gy).rgb * tint * albedo_gain;
	vec3 tn = unpack_n(textureGrad(tex_n, uv, gx, gy));
	vec3 orm = textureGrad(tex_orm, uv, gx, gy).rgb;
	vec3 nw = normalize(vec3(tn.x, tn.z, -tn.y));

	// Pfützen: Pegel schwankt großflächig (Rauschtextur), Wasser füllt zuerst die Fugen
	float pn = textureGrad(puddle_noise, v_wpos.xz / puddle_scale_m, gx * tile_m / puddle_scale_m, gy * tile_m / puddle_scale_m).r;
	float level = wet_level + wet_level_var * (pn - 0.5) * 2.0;
	float water = smoothstep(level + 0.02, level - 0.06, h_at);
	float wet_edge = smoothstep(level + 0.18, level, h_at);   // feuchter Rand um die Pfütze

	// großflächig: hellere und dunklere, feuchtere Bereiche (bricht die 2-m-Wiederholung)
	float mac = textureGrad(puddle_noise, v_wpos.xz / macro_scale_m + vec2(0.37, 0.71), gx * tile_m / macro_scale_m, gy * tile_m / macro_scale_m).r;
	float mac2 = textureGrad(puddle_noise, v_wpos.zx / (macro_scale_m * 0.43) + vec2(0.11, 0.53), gx.yx * tile_m / (macro_scale_m * 0.43), gy.yx * tile_m / (macro_scale_m * 0.43)).r;
	a *= 1.0 + macro_amount * ((mac - 0.5) * 1.6 + (mac2 - 0.5) * 0.8);
	float rough = orm.g;
	// allgemeine Feuchte
	a *= mix(1.0, 0.7, damp);
	rough = mix(rough, rough * 0.5, damp);
	// Rand und Pfütze
	a *= mix(1.0, 0.65, wet_edge);
	rough = mix(rough, 0.12, wet_edge);
	a = mix(a, a * 0.55, water);
	rough = mix(rough, 0.015, water);
	nw = normalize(mix(nw, vec3(0.0, 1.0, 0.0), water * 0.97));

	ALBEDO = a;
	ROUGHNESS = rough;
	METALLIC = 0.0;
	SPECULAR = mix(0.5, 0.3, water);
	AO = mix(orm.r, 1.0, water);
	AO_LIGHT_AFFECT = 0.25;
	NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
}
