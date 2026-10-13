// Sichtbarer Lichtkegel des Leuchtturms: additiver, unbeleuchteter Kegel ohne Deckel.
// Das Mesh ist ein CylinderMesh, um -90° um X gedreht: lokales +Y zeigt vom Licht weg.
// Voxel-Anmutung: Helligkeit in Stufen (Abschnitte von 2 m entlang des Strahls, vier Stufen quer), der
// Kegel selbst bleibt glatt. Der Kegel beginnt start_m vor der Lampenmitte; wo er vor dem Lampenhaus liegt
// (Sichtstrahl näher als house_r an der Lampenmitte), wird er nicht gezeichnet: Zeigt der Strahl schräg zur
// Kamera, legte sein Anfang sonst einen hellen Schleier über Glas und Geländer.
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, fog_disabled, shadows_disabled;

uniform vec4 color : source_color = vec4(1.0, 0.86, 0.6, 1.0);
uniform float intensity = 0.25;
uniform float length_m = 30.0;
uniform float start_m = 1.1;
uniform float house_r = 1.5;          // Galerie mit Geländer: Radius 1,45–1,5 m

varying float along;   // 0 an der Lampe, 1 am Ende
varying vec3 axis;     // Kegelachse im Kameraraum
varying vec3 lamp;     // Lampenmitte im Kameraraum

void vertex() {
	along = clamp(VERTEX.y / length_m + 0.5, 0.0, 1.0);
	axis = normalize((MODELVIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
	lamp = (MODELVIEW_MATRIX * vec4(0.0, -0.5 * length_m - start_m, 0.0, 1.0)).xyz;
}

void fragment() {
	float side = abs(dot(normalize(NORMAL), VIEW));
	// Seitlich gesehen ist die Mitte am hellsten; von vorn gesehen leuchtet der ganze Kegel.
	float body = mix(side * side, 1.0, pow(abs(dot(normalize(axis), VIEW)), 4.0));
	body = ceil(body * 4.0) / 4.0;
	// clamp: mit MSAA wird along an Dreieckskanten extrapoliert; pow(negativ) ergäbe NaN (schwarze Punkte)
	float seg = floor(clamp(along, 0.0, 0.999) * length_m / 2.0) * 2.0 / length_m;
	float fall = pow(clamp(1.0 - seg, 0.0, 1.0), 1.6);
	vec3 ray = normalize(VERTEX);
	float off = length(lamp - dot(lamp, ray) * ray);
	ALBEDO = color.rgb * intensity * body * fall * step(house_r, off);
}
