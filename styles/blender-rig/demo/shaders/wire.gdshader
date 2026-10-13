// Drahtgitter des geriggten Dachses als Überlagerung.
// Das Mesh baut wire_mesh.gd (aufgerufen aus main.gd) aus den Flächen der Figur: jedes Dreieck mit eigenen
// Eckpunkten, in COLOR.rgb die baryzentrischen Koordinaten. Diagonalen ebener Vierecke sind dort um +1
// angehoben und erscheinen nie,
// so zeigt das Gitter die Vierecke aus Blender statt der exportierten Dreiecke.
// Es hängt am selben Skelett und Skin wie die Figur und verformt sich deshalb mit.
shader_type spatial;
render_mode unshaded, blend_mix, cull_back, depth_draw_never, shadows_disabled, fog_disabled;

uniform vec4 line_color : source_color = vec4(0.80, 0.94, 1.0, 0.38);
uniform float amount : hint_range(0.0, 1.0) = 0.0;  // Einblenden (main.gd)
uniform float width_px = 0.9;                        // Linienbreite in Pixeln
uniform float pull_m = 0.004;                        // Richtung Kamera ziehen, gegen Z-Fighting mit der Figur

varying vec3 bary;

void vertex() {
	bary = COLOR.rgb;
	vec4 vp = MODELVIEW_MATRIX * vec4(VERTEX, 1.0);
	vp.xyz -= normalize(vp.xyz) * pull_m;
	POSITION = PROJECTION_MATRIX * vp;
}

void fragment() {
	vec3 d = bary / max(fwidth(bary), vec3(1e-5));
	float e = min(min(d.x, d.y), d.z);
	float line = 1.0 - smoothstep(width_px - 0.5, width_px + 0.5, e);
	ALBEDO = line_color.rgb;
	ALPHA = line * line_color.a * amount;
}
