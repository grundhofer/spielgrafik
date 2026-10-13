// Möwen: gebackener Flügelschlag (VAT aus Blender) auf einer MultiMeshInstance3D.
// Jede Instanz bekommt über INSTANCE_CUSTOM eigene Werte: x = Stelle im Flügelschlag (0..1; das Skript
// rechnet (Phase + t · Schläge pro Sekunde) mod 1 in doppelter Genauigkeit), y = Schläge pro Sekunde,
// z = Ausschlag (0 = Gleiten mit gestreckten Flügeln = Ruhelage, 1 = voller Schlag). Ein Draw-Call für den
// ganzen Schwarm; das Skript setzt je Bild nur Transformation und Custom-Daten der Instanzen.
shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform sampler2D vat_pos : filter_nearest, repeat_disable;
uniform sampler2D vat_nrm : filter_nearest, repeat_disable;
uniform vec3 under_color : source_color = vec3(0.86, 0.87, 0.86);

varying vec3 base_color;

void vertex() {
	ivec2 size = textureSize(vat_pos, 0);
	int col = clamp(int(UV2.x * float(size.x)), 0, size.x - 1);
	float f = fract(INSTANCE_CUSTOM.x) * float(size.y);
	int r0 = int(floor(f)) % size.y;
	int r1 = (r0 + 1) % size.y;
	float w = fract(f);
	vec3 o = mix(texelFetch(vat_pos, ivec2(col, r0), 0).xyz, texelFetch(vat_pos, ivec2(col, r1), 0).xyz, w);
	vec3 n = mix(texelFetch(vat_nrm, ivec2(col, r0), 0).xyz, texelFetch(vat_nrm, ivec2(col, r1), 0).xyz, w);
	float amp = INSTANCE_CUSTOM.z;
	VERTEX += o * amp;
	NORMAL = normalize(mix(NORMAL, n, amp));
	base_color = COLOR.rgb;
}

void fragment() {
	vec3 c = base_color;
	if (!FRONT_FACING) {
		NORMAL = -NORMAL;
		// Unterseite der Flügel hell (Oberseite grau, Spitzen schwarz bleiben schwarz)
		c = mix(c, under_color, step(0.2, c.r) * step(c.r, 0.7));
	}
	ALBEDO = c;
	ROUGHNESS = 0.8;
	SPECULAR = 0.3;
}
