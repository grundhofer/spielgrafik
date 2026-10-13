// Wolken aus großen Quadern (MultiMesh), unbeleuchtet: Farbe je Flächenrichtung wie bei Voxelwolken,
// Unterseite von der untergegangenen Sonne angestrahlt, Oberseite kühl. Nebel gilt (Ferne).
shader_type spatial;
render_mode unshaded, cull_back, shadows_disabled;

uniform vec3 top_col : source_color = vec3(0.55, 0.45, 0.70);
uniform vec3 side_col : source_color = vec3(0.68, 0.48, 0.62);
uniform vec3 front_col : source_color = vec3(0.80, 0.55, 0.60);
uniform vec3 bottom_col : source_color = vec3(1.0, 0.66, 0.45);

varying vec3 n_world;

void vertex() {
	n_world = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec3 n = n_world;
	vec3 c = side_col;
	if (n.y > 0.5) c = top_col;
	else if (n.y < -0.5) c = bottom_col;
	else if (n.z > 0.5) c = front_col;
	else if (n.x < -0.5) c = mix(side_col, bottom_col, 0.35);
	ALBEDO = c;
}
