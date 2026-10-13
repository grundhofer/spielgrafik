// Schlagschatten: jede Schicht eines Stacks als Fläche, um ihre Höhe entlang der Sonne versetzt auf eine Ebene
// gelegt. Pixel, unter denen das Gelände nicht auf Höhe der Ebene liegt, entfallen (Schatten fällt nicht ins Leere).
shader_type canvas_item;
render_mode unshaded;

uniform sampler2D world_map : filter_nearest, repeat_disable;   // water.png: B = Geländehöhe * 8
uniform vec4 world_rect = vec4(-64.0, -184.0, 576.0, 576.0);   // Weltlage der Karte
uniform vec3 tint = vec3(0.52, 0.50, 0.74);

uniform float plane_h = 0.0;              // Schichtindex der Fläche, auf die der Schatten fällt (-1 = Wasser)

global uniform vec2 cam_cs;
global uniform vec2 cam_pivot;
global uniform vec2 cam_center;

varying vec2 v_canvas;

vec2 rot(vec2 v, vec2 cs) { return vec2(cs.x * v.x - cs.y * v.y, cs.y * v.x + cs.x * v.y); }

void vertex() {
	v_canvas = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	if (texture(TEXTURE, UV).a < 0.5) {
		discard;
	}
	vec2 ground = v_canvas + vec2(0.0, max(plane_h, 0.0));
	vec2 w = cam_pivot + rot(ground - cam_center, vec2(cam_cs.x, -cam_cs.y));
	vec2 uv = (w - world_rect.xy) / world_rect.zw;
	float h = texture(world_map, uv).b * 255.0 / 8.0;      // Höhe = Anzahl belegter Schichten
	if (abs(h - (plane_h + 1.0)) > 0.5) {
		discard;
	}
	COLOR = vec4(tint, 1.0);
}
