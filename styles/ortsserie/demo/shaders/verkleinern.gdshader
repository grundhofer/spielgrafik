shader_type canvas_item;
// Zeigt eine SubViewport-Textur (1280×720) verkleinert ohne Flimmern: Mittel über taps×taps bilineare
// Abtastungen im Fußabdruck des Bildschirmpixels (dFdx/dFdy). ViewportTexturen haben keine Mipmaps; eine einzelne
// Abtastung bei Faktor 0,29 würde zwei Drittel der Pixel überspringen (Pinselstriche und Pixelraster flimmern).
// Bei 1:1 (Fußabdruck höchstens 1 Texel) zählt nur die Mitte, damit Pixelstile scharf bleiben. Keine Verzweigung,
// alle Abtastungen laufen immer.
uniform int taps : hint_range(1, 6) = 4;

varying vec4 vcol;   // Vertexfarbe (modulate) für Überblendungen; COLOR enthält in fragment() schon die Textur

void vertex() {
	vcol = COLOR;
}

void fragment() {
	vec2 dx = dFdx(UV);
	vec2 dy = dFdy(UV);
	vec2 tex_px = vec2(textureSize(TEXTURE, 0));
	float foot = max(length(dx * tex_px), length(dy * tex_px));
	vec4 center = texture(TEXTURE, UV);
	vec4 acc = vec4(0.0);
	for (int j = 0; j < taps; j++) {
		for (int i = 0; i < taps; i++) {
			vec2 o = (vec2(float(i), float(j)) + 0.5) / float(taps) - 0.5;
			acc += texture(TEXTURE, UV + o.x * dx + o.y * dy);
		}
	}
	acc /= float(taps * taps);
	vec3 rgb = mix(center.rgb, acc.rgb, step(1.01, foot));
	COLOR = vec4(rgb, 1.0) * vcol;
}
