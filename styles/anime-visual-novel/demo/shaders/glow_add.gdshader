shader_type canvas_item;
render_mode blend_add;
// Additives Licht (Lichthöfe, Strahl, Funkeln). Farbe und Stärke über modulate.
void fragment() {
	COLOR.rgb *= COLOR.a;
	COLOR.a = 1.0;
}
