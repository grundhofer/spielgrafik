// Fahne: Stoffsimulation aus Blender als Vertex Animation Texture (VAT) abspielen.
// vat_pos: Versatz zur Ruhelage (Godot-Achsen, lokal), vat_nrm: Normale; Spalte = Punkt, Zeile = Bild.
// Der Punktindex steht in UV2.x = (i + 0,5) / N (Blender-Skript blender/build_vat.py). texelFetch liest
// die Texel ohne Filter; zwischen zwei Bildern wird linear gemischt.
shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform sampler2D vat_pos : filter_nearest, repeat_disable;
uniform sampler2D vat_nrm : filter_nearest, repeat_disable;
uniform float frame_pos = 0.0;          // abgespieltes Bild (0 .. Bildzahl), vom Skript gefaltet (t · 30 mod 120)

uniform vec3 field_color : source_color = vec3(0.16, 0.30, 0.20);
uniform vec3 band_color : source_color = vec3(0.68, 0.12, 0.10);
uniform vec3 trim_color : source_color = vec3(0.92, 0.86, 0.72);

void vertex() {
	ivec2 size = textureSize(vat_pos, 0);
	int col = clamp(int(UV2.x * float(size.x)), 0, size.x - 1);
	float f = max(frame_pos, 0.0);
	int r0 = int(floor(f)) % size.y;
	int r1 = (r0 + 1) % size.y;
	float w = fract(f);
	vec3 o = mix(texelFetch(vat_pos, ivec2(col, r0), 0).xyz, texelFetch(vat_pos, ivec2(col, r1), 0).xyz, w);
	vec3 n = mix(texelFetch(vat_nrm, ivec2(col, r0), 0).xyz, texelFetch(vat_nrm, ivec2(col, r1), 0).xyz, w);
	VERTEX += o;
	NORMAL = normalize(n);
}

// Kante ohne Treppen: Übergang über die Breite eines Bildpixels (fwidth)
float edge(float d) {
	float w = max(fwidth(d), 1e-4);
	return clamp(0.5 - d / w, 0.0, 1.0);
}

void fragment() {
	// Muster: Feld, Mittelband mit hellen Kanten, Schwalbenschwanz am freien Ende (UV: x vom Mast, y von oben)
	float y = abs(UV.y - 0.5);
	float notch = edge(y - (UV.x - 0.78) * 1.4) * step(0.78, UV.x);   // 1 im ausgeschnittenen Keil
	vec3 c = field_color;
	c = mix(c, trim_color, edge(y - 0.17));
	c = mix(c, band_color, edge(y - 0.12));
	c = mix(c, trim_color, edge(UV.x - 0.05));
	ALBEDO = c;
	ALPHA = 1.0 - notch;
	ALPHA_SCISSOR_THRESHOLD = 0.5;
	ALPHA_ANTIALIASING_EDGE = 0.3;      // Alpha-to-Coverage mit MSAA: glatte Kante am Schwalbenschwanz
	ROUGHNESS = 0.85;
	SPECULAR = 0.25;
	BACKLIGHT = c * 0.35;               // Stoff lässt etwas Licht durch
	if (!FRONT_FACING) {
		NORMAL = -NORMAL;
	}
}
