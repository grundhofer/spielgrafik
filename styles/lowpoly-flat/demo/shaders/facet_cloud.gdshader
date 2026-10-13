shader_type spatial;
// Wolken und Rauch aus groben Kugeln (wenige Segmente): unbeleuchtet, Farbe je Facette aus ihrer
// Normale in Weltkoordinaten. Unterseite und Sonnenseite warm (Abendlicht von unten), Oberseite
// kühl. Ohne Nebel, weil die Wolken weit hinten stehen und sonst in der Himmelsfarbe verschwinden.
render_mode unshaded, cull_back, fog_disabled;

uniform vec3 top_color : source_color = vec3(0.62, 0.52, 0.78);
uniform vec3 side_color : source_color = vec3(0.92, 0.6, 0.7);
uniform vec3 bottom_color : source_color = vec3(1.0, 0.78, 0.62);
uniform vec3 sun_dir = vec3(-0.85, 0.1, 0.3);   // Richtung zur Sonne (Welt)
uniform float sun_amount = 0.25;
uniform float flat_shading = 1.0;

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec3 fn = normalize(cross(dFdx(wpos), dFdy(wpos)));
	vec3 to_cam = CAMERA_POSITION_WORLD - wpos;
	if (dot(fn, to_cam) < 0.0) {
		fn = -fn;
	}
	vec3 sn = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
	vec3 n = normalize(mix(sn, fn, flat_shading));
	float up = n.y;
	vec3 c = up > 0.0 ? mix(side_color, top_color, smoothstep(0.0, 0.85, up))
	                  : mix(side_color, bottom_color, smoothstep(0.0, 0.7, -up));
	float s = max(dot(n, normalize(sun_dir)), 0.0);
	c = mix(c, bottom_color, s * sun_amount);
	ALBEDO = c;
}
