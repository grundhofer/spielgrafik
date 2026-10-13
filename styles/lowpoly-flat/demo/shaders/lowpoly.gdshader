shader_type spatial;
// Low-Poly mit Flat-Shading: eine Normale je Facette (aus den Ableitungen der Position, unabhängig von
// den Normalen im Mesh), eine flache Farbe je Material, keine Texturen. Eine kleine Abweichung je
// Facette (Helligkeit und Farbton) kommt als Vertexfarbe aus blender/build_lowpoly.py (R, G).
// Licht: Lambert ohne Glanz; Schatten- und Umgebungsfarbe kommen aus Himmel und Fülllicht.
render_mode diffuse_lambert, specular_disabled, cull_back;

uniform vec3 albedo : source_color = vec3(1.0);
uniform float jitter_value = 0.09;   // ± Helligkeit je Facette
uniform float jitter_hue = 0.035;    // ± warm/kalt je Facette
uniform float use_jitter = 1.0;      // 0 für Meshes ohne Vertexfarbe (Dachs) und Vergleichsschalter
uniform float flat_shading = 1.0;    // 0 = Normalen aus dem Mesh (Vergleichsschalter --smooth)
uniform vec3 emission : source_color = vec3(0.0);
uniform float emission_energy = 0.0;

varying vec3 vcol;

void vertex() {
	vcol = COLOR.rgb;
}

void fragment() {
	// Flächennormale im Kameraraum; zur Kamera gedreht (gilt dann auch für doppelseitige Flächen)
	vec3 fn = normalize(cross(dFdx(VERTEX), dFdy(VERTEX)));
	if (dot(fn, VERTEX) > 0.0) {
		fn = -fn;
	}
	NORMAL = normalize(mix(NORMAL, fn, flat_shading));
	float j = (vcol.r - 0.5) * 2.0 * jitter_value * use_jitter;
	float h = (vcol.g - 0.5) * 2.0 * jitter_hue * use_jitter;
	vec3 c = albedo * (1.0 + j);
	c *= vec3(1.0 + h, 1.0, 1.0 - h);
	ALBEDO = clamp(c, 0.0, 1.0);
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
	AO = 1.0;
	AO_LIGHT_AFFECT = 0.0;
	EMISSION = emission * emission_energy;
}
