shader_type canvas_item;
// Boot (und sein Spiegelbild) an der Wasserlinie derselben Wellenfunktion abgeschnitten.
uniform vec4 w0;
uniform vec4 w1;
uniform vec4 w2;
uniform vec3 ph;
uniform float t;
uniform float horizon = 369.1;
uniform float F = 500.0;
uniform float D = 1000.0;
uniform float CX = 640.0;
uniform float boat_z = 10.0;
uniform float is_reflection = 0.0;
uniform vec3 tint : source_color = vec3(0.84, 0.83, 0.94);
uniform vec3 water_col : source_color = vec3(0.26, 0.47, 0.55);
varying vec2 wpos;
varying vec4 vcol;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
	vcol = COLOR;
}

float surf_y(float sx) {
	float X = (sx - CX) * boat_z / F;
	vec2 xz = vec2(X, boat_z);
	float h = w0.w * sin(w0.x * xz.x + w0.y * xz.y - w0.z * t + ph.x)
		+ w1.w * sin(w1.x * xz.x + w1.y * xz.y - w1.z * t + ph.y)
		+ w2.w * sin(w2.x * xz.x + w2.y * xz.y - w2.z * t + ph.z);
	return horizon + D / boat_z - F * h / boat_z;
}

void fragment() {
	float ys = surf_y(wpos.x);
	float wob = sin(wpos.y * 0.9 + t * 2.4) * 1.4 * TEXTURE_PIXEL_SIZE.x / 0.71;
	vec4 straight = texture(TEXTURE, UV) * vcol;
	vec4 wobbly = texture(TEXTURE, UV + vec2(wob, 0.0)) * vcol;
	// Boot: oberhalb der Oberfläche, schmaler heller Saum an der Wasserlinie
	vec4 b = straight;
	b.rgb *= tint;
	float above = 1.0 - smoothstep(ys - 0.6, ys + 0.6, wpos.y);
	float foam = smoothstep(ys - 2.4, ys - 0.5, wpos.y) * above;
	b.rgb = mix(b.rgb, vec3(0.82, 0.88, 0.93), foam * 0.55);
	b.a *= above;
	// Spiegelbild: nur unterhalb, gedämpft, zur Wasserfarbe gezogen, nach unten ausgeblendet
	vec4 r = wobbly;
	r.rgb = mix(water_col, r.rgb * tint, 0.42);
	float below = smoothstep(ys - 0.5, ys + 1.0, wpos.y);
	r.a *= below * 0.55 * exp(-max(wpos.y - ys, 0.0) / 34.0);
	COLOR = mix(b, r, is_reflection);
}
