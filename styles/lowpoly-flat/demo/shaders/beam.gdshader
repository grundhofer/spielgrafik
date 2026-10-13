shader_type spatial;
// Lichtkegel des Leuchtturms als grober Kegel (6 Seiten): additiv, ohne Nebel. Jede Seitenfläche
// hat eine eigene Helligkeit (flache Normale gegen Blickrichtung), so bleibt der Kegel facettiert.
// Länge in Metern entlang der lokalen y-Achse des CylinderMesh (Mitte bei 0).
render_mode unshaded, blend_add, depth_draw_never, cull_back, fog_disabled;

uniform vec3 color : source_color = vec3(1.0, 0.88, 0.62);
uniform float intensity = 0.55;
uniform float length_m = 26.0;

varying float along;

void vertex() {
	along = clamp(0.5 + VERTEX.y / length_m, 0.0, 1.0);   // 0 an der Lampe (-y), 1 am Ende (+y)
}

void fragment() {
	vec3 fn = normalize(cross(dFdx(VERTEX), dFdy(VERTEX)));
	float facing = abs(dot(fn, normalize(-VERTEX)));
	float f = (1.0 - smoothstep(0.25, 1.0, along)) * smoothstep(0.0, 0.04, along);
	ALBEDO = color * intensity * f * (0.45 + 0.55 * facing);
}
