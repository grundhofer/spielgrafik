// Gemeinsamer Teil der Pixel-3D-Shader: Zeit, Schwenk, ortsfestes Dithermuster, gestufter Nebel.
// p3d_pan ist der ganzzahlige Anteil der Kamerafahrt in Renderpixeln (main.gd). Dithermuster und
// Sterne werden mit FRAGCOORD + p3d_pan adressiert und wandern deshalb mit dem Bildinhalt, statt
// am Bildschirm zu kleben (sonst "Duschtür"-Effekt beim Schwenken).

global uniform float p3d_time;
global uniform vec2 p3d_pan;
global uniform vec4 p3d_fog_color : source_color;
global uniform vec3 p3d_fog_range;   // Beginn (m), Ende (m), höchster Anteil

const float P3D_BAYER[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0,
		3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);

// Schwelle 0..1 aus der Bayer-4×4-Matrix, ortsfest zum Bildinhalt
float p3d_bayer(vec2 frag) {
	vec2 p = mod(floor(frag) + p3d_pan, 4.0);
	return (P3D_BAYER[int(p.x) + int(p.y) * 4] + 0.5) / 16.0;
}

// Wert in `steps` harte Stufen teilen; nur im oberen Teil jeder Stufe (Breite `band`) wird zur
// nächsten Stufe gedithert, wie bei gepixelten Farbverläufen.
float p3d_steps(float v, float steps, float band, vec2 frag) {
	float x = clamp(v, 0.0, 1.0) * steps;
	float k = floor(x);
	float t = clamp((x - k - (1.0 - band)) / band, 0.0, 1.0);
	k += step(p3d_bayer(frag), t);
	return min(k, steps) / steps;
}

// Gestufter Tiefennebel (Anteil 0..p3d_fog_range.z)
float p3d_fog(float dist, vec2 frag) {
	float f = clamp((dist - p3d_fog_range.x) / (p3d_fog_range.y - p3d_fog_range.x), 0.0, 1.0);
	f = sqrt(f);
	return p3d_steps(f, 4.0, 0.35, frag) * p3d_fog_range.z;
}

// Tiefenpuffer je Renderer: Forward+/Mobile speichern umgekehrtes Z (Himmel = 0, NDC-z = Wert),
// Compatibility (OpenGL) normales Z (Himmel = 1, NDC-z = 2·Wert − 1).
bool p3d_is_sky(float d) {
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
	return d >= 0.9999999;
#else
	return d <= 0.0000001;
#endif
}

float p3d_ndc_z(float d) {
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
	return d * 2.0 - 1.0;
#else
	return d;
#endif
}
