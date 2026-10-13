// Nachbearbeitung 2: anisotroper Kuwahara-Filter mit Polynomgewichten (Kyprianidis, Kang und
// Döllner 2009; Gewichte nach Kyprianidis 2010). Je Pixel eine Ellipse entlang der Kantenrichtung
// aus dem geglätteten Strukturtensor, in acht Sektoren geteilt; das Ergebnis mischt die Mittelwerte
// der Sektoren, ruhige Sektoren (kleine Varianz) zählen stärker. So entstehen flache Farbflächen mit
// gerichteten, pinselartigen Rändern, und Kanten bleiben scharf.
// Die Größe des Pinsels kommt je Pixel aus der Steuerkarte (R): Figur fein, Himmel grob.
shader_type canvas_item;

uniform sampler2D src : filter_nearest, repeat_disable;    // Farbbild (sRGB-Werte)
uniform sampler2D tfm : filter_nearest, repeat_disable;    // geglätteter Strukturtensor
uniform sampler2D ctrl : filter_nearest, repeat_disable;   // Steuerkarte
uniform float r_min = 2.5;          // Pinselradius in Pixeln bei Steuerwert 0
uniform float r_max = 9.0;          // bei Steuerwert 1
uniform float alpha = 1.0;          // wie stark die Ellipse gestreckt wird
uniform float q = 8.0;              // Schärfe der Sektorwahl
uniform float hardness = 8.0;
uniform float zero_cross = 0.58;
uniform float zeta_scale = 1.0;     // Überlappung der Sektoren (1 = 1/Radius wie Acerola)
uniform float radius_scale = 1.0;   // Vergleichsschalter: 0 = Filter aus

void fragment() {
	ivec2 sz = textureSize(src, 0);
	ivec2 p = ivec2(UV * vec2(sz));
	vec4 cs = texelFetch(ctrl, p, 0);
	float r = mix(r_min, r_max, clamp(cs.r, 0.0, 1.0)) * radius_scale;
	vec3 center = texelFetch(src, p, 0).rgb;
	if (r < 0.75) {
		COLOR = vec4(center, 1.0);
	} else {
		vec3 tf = texelFetch(tfm, p, 0).rgb;
		float Txx = tf.r;
		float Txy = tf.g;
		float Tyy = tf.b;
		float root = sqrt(max((Txx - Tyy) * (Txx - Tyy) + 4.0 * Txy * Txy, 0.0));
		float l1 = 0.5 * (Txx + Tyy + root);
		float l2 = 0.5 * (Txx + Tyy - root);
		// Gradientenrichtung (Eigenvektor zum großen Eigenwert), stabil gewählt
		vec2 g1 = vec2(Txy, l1 - Txx);
		vec2 g2 = vec2(l1 - Tyy, Txy);
		vec2 g = dot(g1, g1) > dot(g2, g2) ? g1 : g2;
		float gl = length(g);
		vec2 tn = gl > 1e-8 ? vec2(-g.y, g.x) / gl : vec2(1.0, 0.0);   // Kantenrichtung
		vec2 nn = vec2(-tn.y, tn.x);
		float A = (l1 + l2) > 1e-8 ? (l1 - l2) / (l1 + l2) : 0.0;
		float a = r * clamp((alpha + A) / alpha, 0.1, 2.0);
		float b = r * clamp(alpha / (alpha + A), 0.1, 2.0);
		int max_x = int(sqrt(a * a * tn.x * tn.x + b * b * nn.x * nn.x));
		int max_y = int(sqrt(a * a * tn.y * tn.y + b * b * nn.y * nn.y));
		float zeta = zeta_scale / r;
		float sz_ = sin(zero_cross);
		float eta = (zeta + cos(zero_cross)) / (sz_ * sz_);
		vec4 m[8];
		vec3 s[8];
		for (int k = 0; k < 8; k++) {
			m[k] = vec4(0.0);
			s[k] = vec3(0.0);
		}
		for (int j = -max_y; j <= max_y; j++) {
			for (int i = -max_x; i <= max_x; i++) {
				vec2 o = vec2(float(i), float(j));
				vec2 v = 0.5 * vec2(dot(o, tn) / a, dot(o, nn) / b);
				if (dot(v, v) <= 0.25) {
					vec3 c = clamp(texelFetch(src, clamp(p + ivec2(i, j), ivec2(0), sz - 1), 0).rgb, 0.0, 1.0);
					float w[8];
					float sum = 0.0;
					float vxx = zeta - eta * v.x * v.x;
					float vyy = zeta - eta * v.y * v.y;
					float z = max(0.0, v.y + vxx); w[0] = z * z; sum += w[0];
					z = max(0.0, -v.x + vyy); w[2] = z * z; sum += w[2];
					z = max(0.0, -v.y + vxx); w[4] = z * z; sum += w[4];
					z = max(0.0, v.x + vyy); w[6] = z * z; sum += w[6];
					vec2 v2 = 0.70710678 * vec2(v.x - v.y, v.x + v.y);
					vxx = zeta - eta * v2.x * v2.x;
					vyy = zeta - eta * v2.y * v2.y;
					z = max(0.0, v2.y + vxx); w[1] = z * z; sum += w[1];
					z = max(0.0, -v2.x + vyy); w[3] = z * z; sum += w[3];
					z = max(0.0, -v2.y + vxx); w[5] = z * z; sum += w[5];
					z = max(0.0, v2.x + vyy); w[7] = z * z; sum += w[7];
					float gw = exp(-3.125 * dot(v2, v2)) / max(sum, 1e-6);
					for (int k = 0; k < 8; k++) {
						float wk = w[k] * gw;
						m[k] += vec4(c * wk, wk);
						s[k] += c * c * wk;
					}
				}
			}
		}
		vec4 o = vec4(0.0);
		for (int k = 0; k < 8; k++) {
			if (m[k].w > 1e-6) {
				vec3 mean = m[k].rgb / m[k].w;
				vec3 var = abs(s[k] / m[k].w - mean * mean);
				float sigma2 = var.r + var.g + var.b;
				float wk = 1.0 / (1.0 + pow(hardness * 1000.0 * sigma2, 0.5 * q));
				o += vec4(mean * wk, wk);
			}
		}
		COLOR = vec4(o.w > 1e-6 ? o.rgb / o.w : center, 1.0);
	}
}
