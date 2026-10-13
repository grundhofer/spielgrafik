// Cel-Shading für Hafen, Figur, Rauch: Stufenlicht statt weicher Verläufe.
// Sonne (DirectionalLight3D): drei Töne – Schatten (nur Umgebungslicht), Mittelton, Spitzlicht –
// mit harter Kante; Schlagschatten aus der Shadow-Map ebenfalls hart abgeschnitten.
// Punktlichter (Laterne, Fenster, Leuchtfeuer): zwei harte Ringe statt Abfall.
// Rim-Light: harte Lichtkante an der Silhouette (Fresnel-Schwelle), ausgenommen die Seite, die vom
// Abendhimmel abgewandt ist (globale Uniforms toon_rim_dir/toon_rim_color, Stärke je Material).
// Material-ID in ROUGHNESS: outline_post.gdshader zieht an ID-Grenzen eine Linie (Farbgrenzen).
shader_type spatial;
render_mode cull_back, depth_draw_opaque;

global uniform vec3 toon_rim_dir;
global uniform vec4 toon_rim_color : source_color;

uniform vec4 albedo : source_color = vec4(1.0);
uniform vec4 emission : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform float emission_energy = 0.0;
uniform float band_shadow = 0.02;      // N·L-Schwelle Schatten -> Mittelton
uniform float band_high = 0.55;        // N·L-Schwelle Mittelton -> Spitzlicht
uniform float mid_level = 0.55;        // Anteil des Sonnenlichts im Mittelton
uniform float rim_strength = 0.0;
uniform float rim_width = 0.5;         // Schwelle auf 1 - N·V
uniform float spec_strength = 0.0;
uniform float spec_size = 0.96;        // Schwelle auf N·H
uniform float point_band_lo = 0.10;    // Punktlicht: äußerer Ring
uniform float point_band_hi = 0.32;    // Punktlicht: innerer Ring
uniform int material_id = 0;           // 0..15, für Linien an Farbgrenzen
uniform float smooth_shading = 0.0;    // Vergleichsschalter --no-toon: weiches Lambert statt Stufen

const float AA = 0.012;

void fragment() {
	ALBEDO = albedo.rgb;
	METALLIC = 0.0;
	SPECULAR = 0.0;
	ROUGHNESS = (float(material_id) + 0.5) / 16.0;
	vec3 n_world = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
	float fres = 1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	float side = dot(n_world, normalize(toon_rim_dir));
	float rim = smoothstep(rim_width - 0.02, rim_width + 0.02, fres) * smoothstep(-0.35, -0.1, side);
	vec3 rim_col = toon_rim_color.rgb * (0.55 + 0.45 * albedo.rgb);
	EMISSION = emission.rgb * emission_energy + rim_col * rim * rim_strength;
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	if (LIGHT_IS_DIRECTIONAL) {
		float shadow = smoothstep(0.4, 0.6, ATTENUATION);
		float mid = smoothstep(band_shadow - AA, band_shadow + AA, ndl) * shadow;
		float high = smoothstep(band_high - AA, band_high + AA, ndl) * shadow;
		float stepped = mid * mid_level + high * (1.0 - mid_level);
		float soft = max(ndl, 0.0) * ATTENUATION;
		DIFFUSE_LIGHT += LIGHT_COLOR / PI * mix(stepped, soft, smooth_shading);
		vec3 h = normalize(LIGHT + VIEW);
		float s = smoothstep(spec_size - 0.004, spec_size + 0.004, dot(NORMAL, h)) * shadow;
		SPECULAR_LIGHT += LIGHT_COLOR / PI * s * spec_strength;
	} else {
		float a = ATTENUATION * clamp(ndl * 1.5 + 0.2, 0.0, 1.0);
		float b = smoothstep(point_band_lo - 0.01, point_band_lo + 0.01, a) * 0.5
			+ smoothstep(point_band_hi - 0.01, point_band_hi + 0.01, a) * 0.5;
		DIFFUSE_LIGHT += LIGHT_COLOR / PI * mix(b, ATTENUATION * max(ndl, 0.0), smooth_shading);
	}
}
