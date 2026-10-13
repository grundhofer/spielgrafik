// Requisiten tanzen im Takt (Rubber-Hose-Merkmal): Biegen und Stauchen um den Standpunkt.
// Die Textur hat seitlich und oben einen durchsichtigen Rand; der Fuß (anchor) bleibt fest.
// Vorwärtsabbildung (auch in main.gd für Merkpunkte wie Schornstein und Lampe):
//   h = -q.y / height,  p.x = q.x * sx + bend * h^2,  p.y = q.y * sy   (q, p relativ zum Anker, y nach unten)
// Der Shader tastet umgekehrt ab. Boote: alles unterhalb der Wasserlinie (Weltkoordinate) wird verworfen.
shader_type canvas_item;

uniform vec2 anchor = vec2(0.0);     // Standpunkt in Texturpixeln
uniform float height = 100.0;        // Höhe des Inhalts über dem Anker in Texturpixeln
uniform float bend = 0.0;            // seitlicher Versatz der Oberkante in Pixeln
uniform float sx = 1.0;
uniform float sy = 1.0;
uniform float waterline = 100000.0;  // Weltkoordinate y; darunter durchsichtig (nur Boote)

varying vec4 vcol;
varying vec2 world;

void vertex() {
	vcol = COLOR;
	world = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	vec2 ts = 1.0 / TEXTURE_PIXEL_SIZE;
	vec2 p = UV * ts - anchor;
	float qy = p.y / sy;
	float h = clamp(-qy / height, 0.0, 1.6);
	float qx = (p.x - bend * h * h) / sx;
	vec2 uv = (vec2(qx, qy) + anchor) / ts;
	vec4 c = texture(TEXTURE, uv);
	float inside = step(0.0, uv.x) * step(uv.x, 1.0) * step(0.0, uv.y) * step(uv.y, 1.0);
	float above = step(world.y, waterline);
	COLOR = c * vcol * vec4(1.0, 1.0, 1.0, inside * above);
}
