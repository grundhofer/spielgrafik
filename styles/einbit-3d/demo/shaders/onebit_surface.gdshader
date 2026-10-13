// Oberflächen für den 1-Bit-Look: nur ein Grauwert je Material (die Farbe entscheidet erst die
// Nachbearbeitung), Licht von Godot (Lambert, kein Glanz, alle Lichter weiß).
// Rotkanal = beleuchtete Helligkeit (Albedo nur in Rot), Blaukanal = Material-ID als Eigenleuchten
// ((ID + 0,5) / 16, unbeleuchtet, weil die Albedo dort 0 ist). So kennt die Nachbearbeitung die IDs in jedem
// Renderer, auch ohne Normalen-/Rauheitspuffer (Mobile, Compatibility).
shader_type spatial;
render_mode diffuse_lambert, specular_disabled, cull_back;

uniform float value : hint_range(0.0, 1.0) = 0.5;   // Grauwert (linear)
uniform float emission = 0.0;                        // Eigenleuchten (Glas)
uniform int material_id = 0;                         // 0..15

void fragment() {
	ALBEDO = vec3(value, 0.0, 0.0);
	EMISSION = vec3(emission, 0.0, (float(material_id) + 0.5) / 16.0);
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
	METALLIC = 0.0;
}
