shader_type spatial;
// ID-Durchgang: Jede Fläche schreibt statt einer Farbe drei Zahlen in den HDR-Puffer (RGBA16F):
//   R = Kennung (ganze Zahl, Bruchteil = Helligkeit 0..0,9 für verblassende Teile wie Rauch)
//   G = lineare Tiefe in Metern (Abstand entlang der Blickachse)
//   B = Normale in Weltkoordinaten, oktaedrisch, je Achse 5 Bit (0..1023)
// neon.gdshader liest daraus Umrisse, Flächen, Raster und Spiegelung. Kein Licht, kein Nebel.
render_mode unshaded, cull_disabled, fog_disabled, specular_disabled, shadows_disabled, ambient_light_disabled;

uniform float obj_id = 1.0;
uniform float alt_id = 0.0;     // > 0: Oberseiten auf Kaihöhe bekommen diese Kennung (Pflaster des Kais)
uniform float fade = 0.0;       // Bruchteil der Kennung: 0 = volle Helligkeit, 0,9 = fast aus
uniform float water_y = -0.8;
uniform bool flat_normals = false;  // Flächennormale aus Ableitungen (Gitterlinien auf Gelände)

varying vec3 wpos;
varying vec3 wnrm;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec2 oct_encode(vec3 n) {
	n /= (abs(n.x) + abs(n.y) + abs(n.z));
	vec2 e = n.y >= 0.0 ? n.xz : (1.0 - abs(n.zx)) * vec2(n.x >= 0.0 ? 1.0 : -1.0, n.z >= 0.0 ? 1.0 : -1.0);
	return e * 0.5 + 0.5;
}

void fragment() {
	// Spiegelkamera (unter der Wasserfläche): alles unter dem Wasser abschneiden, auch das Meer selbst.
	if (CAMERA_POSITION_WORLD.y < water_y && wpos.y < water_y + 0.01) {
		discard;
	}
	vec3 n = flat_normals ? normalize(cross(dFdy(wpos), dFdx(wpos))) : normalize(wnrm);
	// Doppelseitige Flächen: Normale zur Kamera drehen, sonst springt sie an Rückseiten.
	if (dot(n, CAMERA_POSITION_WORLD - wpos) < 0.0) {
		n = -n;
	}
	float id = obj_id;
	// Pflaster: alles zwischen Fugenfläche (-0,05) und Oberkante; Kantensteine (bis 0,10) bleiben Kaimauer
	if (alt_id > 0.0 && wpos.y > -0.07 && wpos.y < 0.03) {
		id = alt_id;
	}
	vec2 o = floor(clamp(oct_encode(n), 0.0, 1.0) * 31.0 + 0.5);
	ALBEDO = vec3(id + fade, -VERTEX.z, o.x * 32.0 + o.y);
}
