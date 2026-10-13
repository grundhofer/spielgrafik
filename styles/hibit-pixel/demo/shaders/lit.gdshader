// Beleuchtete Pixel-Ebenen (Hafen nah/fern, Dachs): 2D-Licht mit Normal Map aus der CanvasTexture.
// Das Licht wird in Stufen gerechnet (bands) und nur an den Stufengrenzen geordnet gedithert, damit es auf
// dem 640×360-Raster wie gepixelt wirkt statt wie ein weicher Filter. Glanz (Spekular) nur, wo die
// Spekular-Textur es erlaubt (nasser Kai, Metall).
shader_type canvas_item;

uniform float bands = 6.0;
uniform float band_width = 0.3;    // Breite des Dither-Übergangs an einer Stufengrenze (0..1)
uniform bool banded = true;
uniform float spec_gain = 1.0;

float bayer4(vec2 p) {
	int x = int(mod(floor(p.x), 4.0));
	int y = int(mod(floor(p.y), 4.0));
	int i = x + y * 4;
	float m[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
	return (m[i] + 0.5) / 16.0;
}

float quant(float v, vec2 frag) {
	float s = v * bands;
	float b = floor(s);
	float t = clamp((fract(s) - 0.5) / band_width + 0.5, 0.0, 1.0);
	return (b + (t > bayer4(frag) ? 1.0 : 0.0)) / bands;
}

void light() {
	float ndl = max(0.0, dot(NORMAL, LIGHT_DIRECTION));
	vec3 l = LIGHT_COLOR.rgb * LIGHT_ENERGY * ndl;
	// Glanz: Halbvektor zur Kamera (0,0,1)
	vec3 h = normalize(LIGHT_DIRECTION + vec3(0.0, 0.0, 1.0));
	float sp = pow(max(dot(NORMAL, h), 0.0), max(SPECULAR_SHININESS.a * 64.0, 1.0)) * spec_gain;
	vec3 s = LIGHT_COLOR.rgb * LIGHT_ENERGY * SPECULAR_SHININESS.rgb * sp;
	vec3 tot = l * COLOR.rgb + s;
	if (banded) {
		float m = max(tot.r, max(tot.g, tot.b));
		float q = quant(m, FRAGCOORD.xy);
		tot *= q / max(m, 0.0001);
	}
	LIGHT = vec4(tot, LIGHT_COLOR.a);
}
