shader_type canvas_item;
// Dachs als lebendes Standbild: ein einziges gemaltes Bild, zerlegt in Körper, Schalende und Lider.
// Atmen (Streckung ab den Füßen im vertex()), leichtes Gewichtverlagern (Scherung ab den Füßen),
// Schal weht (Verschiebung des Schalendes über dem aufgefüllten Körper, quer zur Schalachse vom Ansatz zur
// Spitze; hängt der Schal, ist die Achse senkrecht und die Auslenkung waagerecht), Blinzeln (Lider-Ebene),
// warmes Kantenlicht der Laterne (flackert mit).
// TEXTURE = badger_body.png. Der Ursprung des Sprites liegt an den Füßen (offset im Skript).

uniform sampler2D scarf_tex : filter_linear, repeat_disable;
uniform sampler2D lid_tex : filter_linear, repeat_disable;
uniform float t = 0.0;
uniform float breath = 0.0;           // relative Streckung (z. B. 0.012)
uniform float sway = 0.0;             // Scherung: px seitlich je px Höhe über den Füßen
uniform float blink = 0.0;            // 0 offen, 1 zu
uniform vec2 tail_root = vec2(0.5, 0.35);   // Ansatz des Schalendes (UV), dort keine Bewegung
uniform vec2 tail_tip = vec2(0.5, 0.6);     // Spitze des Schalendes (UV), dort volle Auslenkung
uniform float scarf_amp = 5.0;        // px an der Spitze
uniform float gust = 1.0;             // Windstärke (Böen aus dem Skript)
uniform vec2 tex_size = vec2(160.0, 240.0);
uniform vec3 tint = vec3(1.0);
uniform vec2 light_dir = vec2(-1.0, -0.3);   // Richtung zur Laterne (Bildschirm)
uniform vec3 rim_col = vec3(1.0, 0.62, 0.30);
uniform float rim_k = 0.0;

varying vec4 vcol;

void vertex() {
	vcol = COLOR;
	// Füße liegen bei y = 0, nach oben negativ: Brustkorb hebt Kopf und Schultern
	VERTEX.y *= 1.0 + breath;
	VERTEX.x *= 1.0 + breath * 0.35;
	VERTEX.x += sway * -VERTEX.y;
}

void fragment() {
	vec2 uv = UV;
	vec4 body = texture(TEXTURE, uv);

	// Schalende: Auslenkung wächst vom Ansatz zur Spitze, Welle läuft zur Spitze hin
	vec2 ax = (tail_tip - tail_root) * tex_size;           // Achse in px
	float alen = max(length(ax), 1.0);
	vec2 dir = ax / alen;
	vec2 perp = vec2(dir.y, -dir.x);                       // senkrechte Achse -> nach rechts
	float s = dot(uv * tex_size - tail_root * tex_size, dir);
	float w = clamp(s / alen, 0.0, 1.2);
	float wave = sin(t * 5.1 - s * 0.075) * 0.65 + sin(t * 8.3 - s * 0.12 + 1.3) * 0.35;
	float side = pow(w, 1.4) * scarf_amp * gust * (0.55 + 0.45 * wave);
	float pull = -pow(w, 2.0) * scarf_amp * 0.25 * gust;   // Zug entlang der Achse (Wind strafft den Schal)
	vec2 d = perp * side + dir * pull;
	vec4 sc = texture(scarf_tex, uv - d / tex_size);

	vec3 col = mix(body.rgb, sc.rgb, sc.a);
	float a = sc.a + body.a * (1.0 - sc.a);

	vec4 lid = texture(lid_tex, uv);
	col = mix(col, lid.rgb, lid.a * blink);

	// Kantenlicht auf der Seite zur Laterne: dort, wo die ganze Figur (Körper und Schal) ein Stück weiter
	// Richtung Licht durchsichtig wird
	vec2 o = normalize(light_dir) * 3.0 / tex_size;
	float a_o = texture(TEXTURE, uv + o).a;
	float s_o = texture(scarf_tex, uv + o - d / tex_size).a;
	float edge = clamp(a - max(a_o, s_o), 0.0, 1.0);
	col = col * tint + rim_col * edge * rim_k;

	COLOR = vec4(col, a) * vcol;
}
