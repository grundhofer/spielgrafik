// Gemalter Himmel: das KI-Bild sky.png als Himmelskuppel (Abbildung in hp_sky_map.gdshaderinc).
shader_type sky;
render_mode use_debanding;

#include "res://shaders/hp_sky_map.gdshaderinc"

uniform float exposure = 1.0;

void sky() {
	COLOR = sky_color(normalize(EYEDIR)) * exposure;
}
