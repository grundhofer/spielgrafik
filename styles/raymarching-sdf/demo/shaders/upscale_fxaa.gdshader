// Hochskalieren 640×360 -> 1280×720: bilinear, vorher FXAA (vereinfachte Fassung nach T. Lottes)
// auf dem Raster der internen Auflösung, damit die Treppen an Kanten weicher werden.
shader_type canvas_item;

uniform bool fxaa = true;

float luma(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }

void fragment() {
	vec2 px = TEXTURE_PIXEL_SIZE;
	vec2 uv = UV;
	vec3 rgb_m = texture(TEXTURE, uv).rgb;
	if (!fxaa) {
		COLOR = vec4(rgb_m, 1.0);
	} else {
		vec3 nw = texture(TEXTURE, uv + vec2(-0.5, -0.5) * px).rgb;
		vec3 ne = texture(TEXTURE, uv + vec2(0.5, -0.5) * px).rgb;
		vec3 sw = texture(TEXTURE, uv + vec2(-0.5, 0.5) * px).rgb;
		vec3 se = texture(TEXTURE, uv + vec2(0.5, 0.5) * px).rgb;
		float l_nw = luma(nw);
		float l_ne = luma(ne);
		float l_sw = luma(sw);
		float l_se = luma(se);
		float l_m = luma(rgb_m);
		float l_min = min(l_m, min(min(l_nw, l_ne), min(l_sw, l_se)));
		float l_max = max(l_m, max(max(l_nw, l_ne), max(l_sw, l_se)));
		vec2 dir = vec2(-((l_nw + l_ne) - (l_sw + l_se)), (l_nw + l_sw) - (l_ne + l_se));
		float reduce = max((l_nw + l_ne + l_sw + l_se) * 0.25 * (1.0 / 8.0), 1.0 / 128.0);
		float rcp = 1.0 / (min(abs(dir.x), abs(dir.y)) + reduce);
		dir = clamp(dir * rcp, vec2(-6.0), vec2(6.0)) * px;
		vec3 a = 0.5 * (texture(TEXTURE, uv + dir * (1.0 / 3.0 - 0.5)).rgb + texture(TEXTURE, uv + dir * (2.0 / 3.0 - 0.5)).rgb);
		vec3 b = a * 0.5 + 0.25 * (texture(TEXTURE, uv - dir * 0.5).rgb + texture(TEXTURE, uv + dir * 0.5).rgb);
		float l_b = luma(b);
		COLOR = vec4((l_b < l_min || l_b > l_max) ? a : b, 1.0);
	}
}
