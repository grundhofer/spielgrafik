// Ersatz für p3d_post.gdshader in Mobile und Compatibility (dort gibt es keinen Normalenpuffer):
// nur Pixelkonturen aus dem Tiefenpuffer und gestufter Nebel, kein Kantenlicht. main.gd wählt den
// Shader nach RenderingServer.get_current_rendering_method().
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, depth_test_disabled, cull_disabled, fog_disabled, shadows_disabled;

#include "res://shaders/p3d_post.gdshaderinc"
