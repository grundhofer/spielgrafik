// Sichtbarer Lichtkegel des Leuchtturms (übernommen aus shared/3d/demo/shaders/beam.gdshader):
// additiver, unbeleuchteter Kegel ohne Deckel; ergänzt den Strahl im volumetrischen Nebel, der nur bis
// 70 m vor der Kamera reicht.
// Das Mesh ist ein CylinderMesh, um -90° um X gedreht: lokales +Y zeigt vom Licht weg.
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, fog_disabled, shadows_disabled;

uniform vec4 color : source_color = vec4(1.0, 0.86, 0.6, 1.0);
uniform float intensity = 0.25;
uniform float length_m = 30.0;

varying float along;   // 0 an der Lampe, 1 am Ende
varying vec3 axis;     // Kegelachse im Kameraraum

void vertex() {
	along = clamp(VERTEX.y / length_m + 0.5, 0.0, 1.0);
	axis = normalize((MODELVIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
}

void fragment() {
	float side = abs(dot(normalize(NORMAL), VIEW));
	// Seitlich gesehen ist die Mitte am hellsten; von vorn gesehen leuchtet der ganze Kegel.
	float body = mix(side * side, 1.0, pow(abs(dot(normalize(axis), VIEW)), 4.0));
	// clamp: mit MSAA wird along an Dreieckskanten extrapoliert; pow(negativ) ergäbe NaN (schwarze Punkte)
	float fall = pow(clamp(1.0 - along, 0.0, 1.0), 1.6);
	ALBEDO = color.rgb * intensity * body * fall;
}
