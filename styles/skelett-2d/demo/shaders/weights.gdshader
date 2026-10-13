shader_type canvas_item;
// Rig-Ansicht: Textur gedämpft, darüber die Gewichtsfarbe des Gitterpunkts (Polygon2D.vertex_colors),
// nur dort, wo die Textur deckt – wie die Gewichtsansicht eines Animationseditors.
varying vec4 vcol;

void vertex() {
	vcol = COLOR;
}

void fragment() {
	vec4 tex = texture(TEXTURE, UV);
	COLOR = vec4(mix(tex.rgb * 0.8, vcol.rgb, 0.40), tex.a);
}
