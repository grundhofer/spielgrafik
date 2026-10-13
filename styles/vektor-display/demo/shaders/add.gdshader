// Nachleuchten, Schritt 2: das frische Strahlbild kommt additiv dazu.
shader_type canvas_item;
render_mode blend_add, unshaded;

void fragment() {
	COLOR = vec4(texture(TEXTURE, UV).rgb, 1.0);
}
