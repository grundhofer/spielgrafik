// Vorgerenderter Dachs: Palettenindex (R), Tiefe relativ zum Ankerpunkt (G, 0 = leer), Schatten (B, zeichnet
// map.gdshader). Verdeckung je Pixel gegen das mitgerenderte Tiefenbild der Karte (Häuschen, Fässer ...),
// Licht wie die Karte über die Lichttabelle.
shader_type canvas_item;
render_mode blend_disabled, unshaded;

#include "res://shaders/palette_light.gdshaderinc"

uniform ivec2 map_origin;
uniform ivec2 sheet_origin;
uniform float d_anchor = 110.0;
uniform float zrange = 2.56;
uniform float z_bias = 0.03;
uniform bool occlusion_on = true;

void fragment() {
	ivec2 t = ivec2(floor(UV * vec2(textureSize(TEXTURE, 0))));
	vec4 s = texelFetch(TEXTURE, t, 0);
	if (s.g < 0.5 / 255.0) {
		discard;
	}
	ivec2 p = map_origin + (t - sheet_origin);
	float db = d_anchor + (round(s.g * 255.0) / 255.0 - 0.5) * zrange;
	if (occlusion_on && decode_depth(p) < db - z_bias) {
		discard;
	}
	float l = light_at(world_at(vec2(p) + 0.5, db));
	int row = row_for(l, p);
	COLOR = vec4(lut_color(int(round(s.r * 255.0)), row), 1.0);
}
