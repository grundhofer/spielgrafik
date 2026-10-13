// Figur: auf dasselbe Blatt gezeichnet wie der Hintergrund. Innerhalb der Silhouette deckt das Papier (Papier-
// textur an derselben Bildschirmstelle, mit Karo), darauf Grafit und Buntstift der Figur. Line-Boil wie die
// Zeichnung, aber im Bildraster des Bogens verankert (die Verzerrung wandert nicht mit, wenn die Figur läuft).
// TEXTURE: Bogen badger.png, eine Reihe, Bildbreite frame_w (scripts/build_badger.py); Papier = Weiß.
shader_type canvas_item;
#include "res://shaders/boil.gdshaderinc"

uniform sampler2D paper_tex : filter_linear;
uniform vec2 screen_size = vec2(1280.0, 720.0);
uniform vec2 sheet_size = vec2(1617.0, 245.0);
uniform float frame_w = 147.0;
uniform float ink_gain = 1.15;     // Figur etwas kräftiger als im Bogen, damit sie neben der Zeichnung trägt
uniform float ink_gamma = 0.9;

varying vec2 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	vec2 p = UV * sheet_size;
	float fx = floor(p.x / frame_w) * frame_w;
	vec2 lp = p - vec2(fx, 0.0);
	float pressure;
	ivec2 ip = ivec2(floor(p)) + boil_offset(lp, pressure);
	ip.x = clamp(ip.x, int(fx), int(fx + frame_w) - 1);
	ip.y = clamp(ip.y, 0, int(sheet_size.y) - 1);
	vec4 s = texelFetch(TEXTURE, ip, 0);
	vec3 ink = min(pow(1.0 - s.rgb, vec3(ink_gamma)) * ink_gain, vec3(0.86));
	ink = on_tooth(ink * pressure, world_pos);
	vec3 paper = texture(paper_tex, world_pos / screen_size).rgb;
	COLOR = vec4(paper * (1.0 - clamp(ink, 0.0, 1.0)), s.a);
}
