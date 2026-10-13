shader_type canvas_item;
// Schlussszene (SubViewport 320×180, ganzzahlig ×4) wischt von links über die Vergleichsansicht.
// Die Kante liegt auf ganzen Szenenpixeln, damit kein halbes Pixel stehen bleibt.

uniform float reveal = 0.0;      // 0 = nichts zu sehen, 1 = ganze Szene
uniform vec4 edge_col : source_color = vec4(0.96, 0.93, 0.86, 1.0);

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	float edge = floor(reveal * 322.0) - 1.0;      // in Szenenpixeln
	float px = floor(UV.x * 320.0);
	if (px > edge) {
		discard;
	}
	// die letzte Spalte vor der Kante hell (wie die Trennlinie der Vergleichsansicht)
	float on = step(edge - 0.5, px) * step(reveal, 0.999);
	COLOR = vec4(mix(c.rgb, edge_col.rgb, on), 1.0);
}
