// Wände und Böden der Sektorkarte: Texel = Palettenindex, Licht über die Farbtabelle (keine Filterung,
// keine Mipmaps, kein Nebel). UV2 = (Sektornummer, Art): Art −1/0/+1 = Wand mit Richtungskontrast,
// 8 = Boden (Lichttabelle nach Entfernung statt nach Maßstab).
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque, specular_disabled, shadows_disabled, fog_disabled;

#include "res://shaders/rc_common.gdshaderinc"

uniform sampler2D tex : filter_nearest, repeat_enable;
uniform sampler2D sector_light : filter_nearest;   // 256 x 1, Lichtstufe je Sektor (0–255)

varying flat vec2 sec;

void vertex() {
	sec = UV2;
}

void fragment() {
	int idx = int(texture(tex, UV).r * 255.0 + 0.5);
	float light = texelFetch(sector_light, ivec2(int(sec.x + 0.5), 0), 0).r * 255.0;
	bool flat_ = sec.y > 4.0;
	int level = rc_level(light, flat_ ? 0 : int(round(sec.y)), -VERTEX.z, flat_);
	ALBEDO = rc_out(rc_shade(idx, level));
}
