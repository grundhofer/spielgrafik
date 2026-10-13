// Boots-Cel: alles unterhalb der Wasserlinie (in Bildschirmkoordinaten) wird weggelassen, damit der schaukelnde
// Rumpf nie unter dem Wasser hervorschaut. Darüber liegt ein 2–3 px hoher, wasserfarbener Streifen (flache
// Cel-Farbe) mit gestufter Oberkante, die sich je Tick seitlich versetzt: Er deckt die gerade Schnittkante des
// Rumpfs ab, damit das Boot im Wasser liegt statt darauf. Der Streifen gilt in Welt- und in Sprite-Koordinaten,
// damit die Kante auch bedeckt bleibt, wenn das Boot beim Schaukeln etwas aus dem Wasser hebt.
shader_type canvas_item;

uniform float waterline = 500.0;
uniform float tick = 0.0;
uniform vec4 water : source_color = vec4(0.12, 0.26, 0.46, 1.0);
uniform float stripe = 2.0;
varying vec2 world;
varying vec2 local;

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
	local = VERTEX;  // Sprite-Pixel; die Unterkante (Schnitt an der Wasserlinie) liegt bei y = 0
}

void fragment() {
	if (world.y > waterline) {
		discard;
	}
	float seg = floor((local.x + tick * 3.0) / 7.0);
	float h = stripe + mod(seg, 2.0);
	if (world.y > waterline - h - 1.0 || local.y > -h) {
		COLOR.rgb = water.rgb;
	}
}
