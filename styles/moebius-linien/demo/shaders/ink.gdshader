// Flächen wie in einer kolorierten Tuschezeichnung: eine flache Farbe je Material, genau eine
// Schattenstufe (Eigen- und Schlagschatten der Sonne, harte Kante) und im Schatten eine Schraffur aus
// parallelen Tuschestrichen. Kein Verlauf, kein Glanz, kein Umgebungslicht.
// Die Schraffur liegt im Bildraum, ist aber am Bildpunkt des Objekt-Ursprungs verankert: Bewegt sich
// ein Objekt (Dachs, Boote), wandern seine Striche mit, statt über die Fläche zu rutschen.
// Material-ID in ROUGHNESS: ink_lines.gdshader zieht an ID-Grenzen eine Linie (Farbgrenzen).
shader_type spatial;
render_mode cull_back, depth_draw_opaque, ambient_light_disabled;

global uniform vec4 ink_shadow;   // Schattenstufe als linearer Faktor auf die Farbe
global uniform float ink_hatch;                  // 0 = Schraffur aus (Vergleichsschalter)
global uniform float ink_shade;                  // 0 = keine Schattenstufe (Vergleichsschalter)

uniform vec4 albedo : source_color = vec4(1.0);
uniform vec3 shade_mul = vec3(1.0);   // Feinabstimmung der Schattenfarbe je Material
uniform float glow = 0.0;             // 1 = leuchtet unbeleuchtet in seiner Farbe (Glas)
uniform int material_id = 0;          // 0..31, Linien an Farbgrenzen (Figur ab 16: Faltenlinien)
uniform float hatch_strength = 0.82;  // 0..1, wie dunkel die Striche im Schatten sind
uniform float hatch_spacing = 5.0;    // Abstand der Striche in Pixeln
uniform float hatch_width = 1.15;     // Strichbreite in Pixeln
uniform float hatch_angle = 0.96;     // Richtung im Bild (Bogenmaß, 0 = waagerecht)
uniform float terminator = 0.0;       // N·L-Schwelle zwischen Licht und Schatten

varying flat vec2 anchor_px;
varying float hatch_line;

void vertex() {
	vec4 o = PROJECTION_MATRIX * (MODELVIEW_MATRIX * vec4(0.0, 0.0, 0.0, 1.0));
	anchor_px = (o.xy / o.w * 0.5 + 0.5) * VIEWPORT_SIZE;
}

void fragment() {
	ALBEDO = albedo.rgb;
	METALLIC = 0.0;
	SPECULAR = 0.0;
	ROUGHNESS = (float(material_id) + 0.5) / 32.0;
	// Abstand zum nächsten Strich in Pixeln, Kante 1 px weich (SMAA glättet den Rest)
	vec2 p = FRAGCOORD.xy - anchor_px;
	float u = dot(p, vec2(sin(hatch_angle), cos(hatch_angle)));
	float d = abs(fract(u / hatch_spacing) - 0.5) * hatch_spacing;
	hatch_line = 1.0 - smoothstep(hatch_width * 0.5 - 0.5, hatch_width * 0.5 + 0.5, d);
	if (glow > 0.5) {
		EMISSION = albedo.rgb;
		ALBEDO = vec3(0.0);
	}
}

void light() {
	if (LIGHT_IS_DIRECTIONAL) {
		float ndl = dot(NORMAL, LIGHT);
		float lit = smoothstep(terminator - 0.015, terminator + 0.015, ndl) * smoothstep(0.42, 0.58, ATTENUATION);
		lit = mix(1.0, lit, ink_shade);
		float h = hatch_line * hatch_strength * ink_hatch;
		vec3 shadowed = ink_shadow.rgb * shade_mul * (1.0 - h);
		DIFFUSE_LIGHT += mix(shadowed, vec3(1.0), lit);
	}
}
