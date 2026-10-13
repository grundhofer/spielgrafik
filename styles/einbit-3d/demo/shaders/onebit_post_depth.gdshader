// 1-Bit-Nachbearbeitung für Mobile und Compatibility (kein Normalenpuffer): Normalen für die Knicklinien aus der
// Tiefe rekonstruiert. Ablauf in onebit_common.gdshaderinc; main.gd setzt diesen Shader außerhalb von Forward+.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, depth_test_disabled, cull_disabled, fog_disabled, shadows_disabled;

#include "res://shaders/onebit_common.gdshaderinc"
