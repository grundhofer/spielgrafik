// Billboard-Sprites wie in den Sektor-Engines: senkrecht, immer parallel zur Bildebene (die Kamera
// neigt sich nie), 1-Bit-Transparenz (Index 255), Licht des Sektors, in dem das Ding steht, nach
// Maßstab; Vollhell-Bilder (Lampen) nutzen Farbtabelle 0.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque, specular_disabled, shadows_disabled, fog_disabled;

#include "res://shaders/rc_common.gdshaderinc"

uniform sampler2D atlas : filter_nearest;
instance uniform vec4 frame_rect = vec4(0.0, 0.0, 1.0, 1.0);   // Texel: x, y, Breite, Höhe
instance uniform float light = 176.0;
instance uniform float fullbright = 0.0;

void vertex() {
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(
		vec4(normalize(cross(vec3(0.0, 1.0, 0.0), INV_VIEW_MATRIX[2].xyz)), 0.0),
		vec4(0.0, 1.0, 0.0, 0.0),
		vec4(normalize(cross(INV_VIEW_MATRIX[0].xyz, vec3(0.0, 1.0, 0.0))), 0.0),
		MODEL_MATRIX[3]);
	MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
}

void fragment() {
	vec2 t = clamp(floor(UV * frame_rect.zw), vec2(0.0), frame_rect.zw - 1.0) + frame_rect.xy;
	int idx = int(texelFetch(atlas, ivec2(t), 0).r * 255.0 + 0.5);
	if (idx == 255) {
		discard;
	}
	int level = fullbright > 0.5 ? 0 : rc_level(light, 0, -VERTEX.z, false);
	ALBEDO = rc_out(rc_shade(idx, level));
}
