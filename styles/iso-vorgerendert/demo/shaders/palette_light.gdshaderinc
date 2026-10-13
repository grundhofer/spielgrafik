// Gemeinsame Teile von map.gdshader und badger.gdshader:
// Tiefenbild lesen, Kartenpixel + Tiefe -> Weltpunkt (Blender-Achsen, z oben), Lichtstufe aus Punktlichtern,
// Stufe mit 4x4-Bayer auf eine Zeile der Lichttabelle runden, Farbe = Lichttabelle[Stufe][Palettenindex].
// Jede ausgegebene Farbe ist damit eine der 256 Palettenfarben (wie die Lichttabellen der 8-Bit-Rollenspiele).

uniform sampler2D depth_tex : filter_nearest;
uniform sampler2D lut_tex : filter_nearest;
uniform vec3 cam_o;
uniform vec3 ax_r;
uniform vec3 ax_u;
uniform vec3 ax_d;
uniform float pxm = 30.85;
uniform vec2 map_size = vec2(640.0, 480.0);
uniform float d0 = 95.0;
uniform float d1 = 140.0;
uniform float levels[16];
uniform vec4 lights[6];
uniform float light_int[6];
uniform float ambient = 0.44;

const float BAYER4[16] = float[](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0,
                                 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);

float decode_depth(ivec2 p) {
	vec3 t = texelFetch(depth_tex, p, 0).rgb;
	float v = (round(t.r * 255.0) * 256.0 + round(t.g * 255.0)) / 65535.0;
	return d0 + v * (d1 - d0);
}

vec3 world_at(vec2 pc, float d) {
	return cam_o + (pc.x - map_size.x * 0.5) / pxm * ax_r - (pc.y - map_size.y * 0.5) / pxm * ax_u + d * ax_d;
}

// Tiefe der Bodenebene z = 0 am Kartenpunkt pc
float plane_depth(vec2 pc) {
	vec3 o = world_at(pc, 0.0);
	return -o.z / ax_d.z;
}

float light_at(vec3 w) {
	float l = ambient;
	for (int i = 0; i < 6; i++) {
		float r = lights[i].w;
		if (r <= 0.0) continue;
		float q = clamp(1.0 - dot(w - lights[i].xyz, w - lights[i].xyz) / (r * r), 0.0, 1.0);
		l += light_int[i] * q * q;
	}
	return l;
}

int row_for(float l, ivec2 p) {
	float r = 0.0;
	if (l <= levels[0]) {
		r = 0.0;
	} else if (l >= levels[15]) {
		r = 15.0;
	} else {
		for (int i = 0; i < 15; i++) {
			if (l >= levels[i] && l < levels[i + 1]) {
				r = float(i) + (l - levels[i]) / (levels[i + 1] - levels[i]);
			}
		}
	}
	float b = (BAYER4[(p.y & 3) * 4 + (p.x & 3)] + 0.5) / 16.0;
	return clamp(int(floor(r + b)), 0, 15);
}

vec3 lut_color(int idx, int row) {
	return texelFetch(lut_tex, ivec2(idx, row), 0).rgb;
}
