// Zeigt eine Zwischenstufe unverändert an (Vergleichsschalter --raw, --show-ctrl, --show=<Durchgang>).
shader_type canvas_item;

uniform sampler2D src : filter_nearest, repeat_disable;

void fragment() {
	COLOR = vec4(texture(src, UV).rgb, 1.0);
}
