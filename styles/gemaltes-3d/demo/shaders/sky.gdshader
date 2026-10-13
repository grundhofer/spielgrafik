// Himmel der Bildkamera (Funktionen in sky_common.gdshaderinc).
shader_type sky;
render_mode use_debanding;

#include "res://shaders/paint_common.gdshaderinc"
#include "res://shaders/sky_common.gdshaderinc"

void sky() {
	COLOR = sky_color(normalize(EYEDIR));
}
