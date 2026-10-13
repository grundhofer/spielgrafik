// Kantenrichtung aus dem geglätteten Strukturtensor (r = gx·gx, g = gx·gy, b = gy·gy).
// xy = Richtung entlang der Kanten (Einheitsvektor, Pixelraum mit y nach unten), z = Anisotropie 0..1.
vec3 flow_from_tensor(vec3 tf) {
	float Txx = tf.r;
	float Txy = tf.g;
	float Tyy = tf.b;
	float root = sqrt(max((Txx - Tyy) * (Txx - Tyy) + 4.0 * Txy * Txy, 0.0));
	float l1 = 0.5 * (Txx + Tyy + root);
	float l2 = 0.5 * (Txx + Tyy - root);
	vec2 g1 = vec2(Txy, l1 - Txx);
	vec2 g2 = vec2(l1 - Tyy, Txy);
	vec2 g = dot(g1, g1) > dot(g2, g2) ? g1 : g2;
	float gl = length(g);
	vec2 t = gl > 1e-8 ? vec2(-g.y, g.x) / gl : vec2(1.0, 0.0);
	float A = (l1 + l2) > 1e-8 ? (l1 - l2) / (l1 + l2) : 0.0;
	return vec3(t, A);
}
