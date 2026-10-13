// Spiegelbild eines Boots im Wasser: gespiegeltes Sprite (scale.y = -1), in Bändern von 2 px um ganze
// Pixel versetzt und unregelmäßig unterbrochen (Wellen), nach unten ausblendend.
shader_type canvas_item;

uniform float t = 0.0;
uniform vec2 tex_size = vec2(160.0, 220.0);
uniform float strength = 0.45;

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

void fragment() {
	vec2 p = UV * tex_size;
	float dist = tex_size.y - p.y;   // Abstand zum Kiel (gespiegelt)
	float row = floor(p.y / 2.0);
	float tick = floor(t * 4.0);
	float off = floor((hash12(vec2(row, tick)) - 0.5) * (2.0 + 6.0 * dist / tex_size.y) + 0.5);
	float a = texture(TEXTURE, (p + vec2(off, 0.0)) / tex_size).a;
	float fadeout = 1.0 - smoothstep(0.0, tex_size.y * 0.6, dist);
	float gap = step(0.22 + 0.4 * dist / tex_size.y, hash12(vec2(row + 17.0, floor(t * 2.0))));
	COLOR = vec4(COLOR.rgb, a * strength * fadeout * gap);
}
