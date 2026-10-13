shader_type canvas_item;
// Hintergrund: Wasser bewegt sich nur innerhalb der Wassermaske (R von bg_mask.png).
// Zeilen werden um ganze Pixel verschoben (keine Unschärfe der Konturen), gelesen wird nur aus Wasserpixeln.
// Dazu kurze helle Glanzstriche wie in gezeichneten Adventures und die flackernde Spiegelung der Laterne.

uniform sampler2D mask_tex : filter_nearest;
uniform float t = 0.0;
uniform float horizon_y = 345.0;
uniform float quay_y = 544.0;
uniform vec2 lantern = vec2(892.0, 325.0);
uniform float lantern_amount = 1.0;

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

void fragment() {
	vec2 size = vec2(1280.0, 720.0);
	vec2 px = floor(UV * size) + 0.5;
	float d = clamp((px.y - horizon_y) / (quay_y - horizon_y), 0.0, 1.0);   // 0 Horizont, 1 vorn
	float row = floor(px.y / (1.0 + 2.0 * d));
	float sh = sin(row * 0.9 + t * 1.6) * 0.8 + sin(row * 0.37 - t * 1.1 + 1.3) * 0.7;
	float dx = floor(sh * (0.5 + 2.0 * d) + 0.5);
	vec2 uv2 = (px + vec2(dx, 0.0)) / size;
	vec4 base = texture(TEXTURE, UV);
	vec4 moved = texture(TEXTURE, uv2);
	float w = texture(mask_tex, UV).r;
	float w2 = texture(mask_tex, uv2).r;
	vec3 col = mix(base.rgb, moved.rgb, step(0.5, w) * step(0.5, w2));

	// Glanzstriche: kurze waagerechte Striche in Zellen, die einzeln aufblitzen; nach vorn länger
	vec2 cell_size = vec2(16.0 + 30.0 * d, 3.0 + 3.0 * d);
	vec2 cell = floor(px / cell_size);
	vec2 f = px / cell_size - cell;
	float h = hash12(cell + 17.0);
	float ph = hash12(cell * 1.7 + 3.1) * 6.2831;
	float blink = pow(max(0.0, sin(t * (1.1 + 1.5 * h) + ph)), 8.0);
	float dash = step(0.18, f.x) * step(f.x, 0.82) * step(0.34, f.y) * step(f.y, 0.66);
	float glint = blink * dash * step(0.80, h) * (0.45 + 0.55 * d);
	vec3 gcol = mix(vec3(0.78, 0.86, 0.98), vec3(1.0, 0.80, 0.52), smoothstep(170.0, 20.0, abs(px.x - lantern.x)));

	// Spiegelung der Laterne: senkrechte Säule aus flackernden Bändern
	float colw = 6.0 + 18.0 * d;
	float refl = exp(-pow((px.x - lantern.x) / colw, 2.0));
	float band = step(0.42, hash12(vec2(floor(px.y / (2.0 + 2.0 * d)), floor(t * 6.0))));
	refl *= band * smoothstep(horizon_y + 4.0, horizon_y + 36.0, px.y) * lantern_amount;

	col += w * (glint * 0.34 * gcol + refl * 0.30 * vec3(1.0, 0.72, 0.42));
	COLOR = vec4(col, base.a);
}
