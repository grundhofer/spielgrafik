// 1-Bit-Nachbearbeitung für Forward+: Normalen für die Knicklinien aus dem Normalenpuffer (USE_NR), sonst wie
// onebit_post_depth.gdshader. Ablauf in onebit_common.gdshaderinc. main.gd wählt je Renderer den Shader.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, depth_test_disabled, cull_disabled, fog_disabled, shadows_disabled;

#define USE_NR
#include "res://shaders/onebit_common.gdshaderinc"
