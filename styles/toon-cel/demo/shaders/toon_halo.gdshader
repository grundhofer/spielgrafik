// Lichthof als Billboard: zwei harte Ringe (Kern, Saum) statt weichem Glühen, additiv.
// main.gd skaliert ihn mit dem Flackern der Laterne bzw. dem Aufblitzen des Leuchtfeuers.
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, fog_disabled, shadows_disabled;

uniform vec4 color : source_color = vec4(1.0, 0.78, 0.4, 1.0);
uniform float intensity = 0.5;
uniform float inner = 0.42;     // Radius des Kerns (0..1 des Quads)
uniform float outer = 0.95;

void vertex() {
	// zur Kamera drehen, Größe aus der Modellskalierung
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	MODELVIEW_MATRIX = MODELVIEW_MATRIX * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0),
		vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0), vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0),
		vec4(0.0, 0.0, 0.0, 1.0));
}

void fragment() {
	float r = length(UV * 2.0 - 1.0);
	float ring_in = 1.0 - smoothstep(inner - 0.02, inner + 0.02, r);
	float ring_out = 1.0 - smoothstep(outer - 0.03, outer, r);
	ALBEDO = color.rgb * intensity * (0.35 * ring_out + 0.65 * ring_in);
}
