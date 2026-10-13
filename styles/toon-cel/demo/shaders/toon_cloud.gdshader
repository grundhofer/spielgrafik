// Wolken als 3D-Körper (Gruppen gestauchter Kugeln) mit harten Tönen. Die Normale für das Licht
// ist zum großen Teil die Normale eines Ellipsoids um die ganze Wolke (instance uniform), damit die
// Stufen der Form der Wolke folgen statt Streifen auf jeder Kugel zu bilden. Licht von unten
// hinten (Sonne unter dem Horizont): Unterseiten glühen orange, die Oberseiten liegen violett im
// Schatten. Unbeleuchtet und ohne Nebel, damit die Farben im Abendhimmel genau steuerbar bleiben.
shader_type spatial;
render_mode unshaded, cull_back, fog_disabled, shadows_disabled;

instance uniform vec3 cloud_center = vec3(0.0);
instance uniform vec3 cloud_radii = vec3(1.0);

uniform vec3 light_dir = vec3(-0.25, -0.55, -0.8);   // Richtung zum Licht (Welt)
uniform vec4 lit : source_color = vec4(1.0, 0.72, 0.5, 1.0);
uniform vec4 mid : source_color = vec4(0.86, 0.5, 0.62, 1.0);
uniform vec4 shade : source_color = vec4(0.4, 0.31, 0.6, 1.0);
uniform float band_a = -0.05;
uniform float band_b = 0.32;
uniform float own_normal = 0.3;   // Anteil der Kugelnormale (Beulen)
uniform int material_id = 14;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec3 n_puff = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
	vec3 n_shape = normalize((world_pos - cloud_center) / (cloud_radii * cloud_radii));
	vec3 n = normalize(mix(n_shape, n_puff, own_normal));
	float l = dot(n, normalize(light_dir));
	vec3 c = mix(shade.rgb, mid.rgb, smoothstep(band_a - 0.015, band_a + 0.015, l));
	c = mix(c, lit.rgb, smoothstep(band_b - 0.015, band_b + 0.015, l));
	ALBEDO = c;
	ROUGHNESS = (float(material_id) + 0.5) / 16.0;
}
