// Gießharz-Wasser des Dioramas: Oberfläche (Sea) und Schnittkanten (SectionWater) mit demselben Shader.
// Durchsichtig mit Farbaufnahme nach der Strecke im Harz (Tiefenpuffer): Kaimauer, Bootsrümpfe und Grund
// scheinen in flachen Bereichen durch, tiefes Wasser wird dunkel-türkis. Hochglanz kommt aus dem normalen
// Licht (ALBEDO schwarz, Farbe als EMISSION aus dem Bild dahinter), Kräuselung nur in der Normale.
// depth_draw_always: Das Harz steht im Tiefenpuffer, damit die Tiefenunschärfe es richtig einordnet.
shader_type spatial;
render_mode blend_mix, depth_draw_always, cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap, repeat_disable;
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest, repeat_disable;

uniform bool side = false;                        // Schnittkante statt Oberfläche
uniform vec3 absorb = vec3(2.2, 0.75, 0.55);      // je m Harz (rot wird zuerst geschluckt)
uniform vec4 shallow : source_color = vec4(0.36, 0.72, 0.70, 1.0);
uniform vec4 deep : source_color = vec4(0.04, 0.17, 0.26, 1.0);
uniform float scatter = 0.6;                      // Helligkeit des Streulichts im Harz
uniform float water_y = -0.8;
uniform float floor_y = -2.6;
uniform float ripple = 0.06;
uniform float refract_px = 10.0;
uniform float roughness : hint_range(0.0, 1.0) = 0.1;
uniform vec4 meniscus : source_color = vec4(0.85, 0.95, 0.92, 1.0);

global uniform float dio_time;

varying vec3 world_pos;

vec2 wave_grad(vec2 p, vec2 dir, float len, float amp, float speed) {
	float k = 6.2831853 / len;
	vec2 d = normalize(dir);
	float ph = k * (dot(d, p) - speed * dio_time);
	return amp * k * cos(ph) * d;
}

// Tiefenpuffer -> Ansichtsraum. Compatibility (OpenGL) speichert z in -1..1, Forward+/Mobile in 0..1.
vec3 view_pos(vec2 suv, float dz, mat4 inv_proj) {
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
	vec4 vp = inv_proj * vec4(vec3(suv, dz) * 2.0 - 1.0, 1.0);
#else
	vec4 vp = inv_proj * vec4(suv * 2.0 - 1.0, dz, 1.0);
#endif
	return vp.xyz / vp.w;
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec3 n_world = vec3(0.0, 1.0, 0.0);
	if (!side) {
		vec2 p = world_pos.xz;
		vec2 g = wave_grad(p, vec2(0.3, 1.0), 2.6, 0.05, 0.35)
			+ wave_grad(p, vec2(-0.7, 0.6), 1.7, 0.035, 0.28)
			+ wave_grad(p, vec2(0.9, -0.2), 1.1, 0.02, 0.22)
			+ wave_grad(p, vec2(-0.2, -1.0), 3.7, 0.06, 0.4);
		n_world = normalize(vec3(-g.x * ripple * 4.0, 1.0, -g.y * ripple * 4.0));
		NORMAL = normalize((VIEW_MATRIX * vec4(n_world, 0.0)).xyz);
	}

	// Strecke im Harz bis zur Geometrie dahinter
	vec2 off = (NORMAL.xy) * refract_px / VIEWPORT_SIZE;
	vec2 suv = clamp(SCREEN_UV + (side ? vec2(0.0) : off), vec2(0.001), vec2(0.999));
	float dz = texture(depth_tex, suv).r;
	float dz0 = texture(depth_tex, SCREEN_UV).r;
	float thick = max(length(view_pos(suv, dz, INV_PROJECTION_MATRIX)) - length(VERTEX), 0.0);
	if (thick < 0.02) {          // Versatz zeigt auf Geometrie vor dem Wasser: ohne Versatz lesen
		suv = SCREEN_UV;
		thick = max(length(view_pos(suv, dz0, INV_PROJECTION_MATRIX)) - length(VERTEX), 0.0);
	}
	thick = min(thick, 12.0);
	vec3 behind = textureLod(screen_tex, suv, 0.0).rgb;
	vec3 trans = exp(-absorb * thick);

	// Streulicht: oben hell-türkis, zum Grund hin dunkel
	float depth01 = clamp((water_y - world_pos.y) / (water_y - floor_y), 0.0, 1.0);
	vec3 body = mix(shallow.rgb, deep.rgb, side ? smoothstep(0.0, 1.0, depth01) : smoothstep(0.0, 6.0, thick)) * scatter;
	vec3 col = behind * trans + body * (1.0 - trans);

	if (side) {
		// heller Meniskus an der Oberkante und leichte Schlieren im Harz
		float top = smoothstep(0.06, 0.0, water_y - world_pos.y);
		col = mix(col, meniscus.rgb * 0.9, top * 0.7);
	}

	ALBEDO = vec3(0.0);
	EMISSION = col;
	ROUGHNESS = roughness;
	SPECULAR = 0.5;
	METALLIC = 0.0;
	ALPHA = 1.0;
}
