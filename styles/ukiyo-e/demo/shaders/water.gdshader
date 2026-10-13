// Hafenwasser des Druckbilds: Die gedruckten Wellenlinien wiegen sich, indem jedes Wasserpixel aus einem um ganze
// Pixel versetzten Wasserpixel gelesen wird (waagerecht in Bändern von etwa 60 px Höhe, senkrecht in Bändern von
// etwa 300 px Breite, zum Kai hin stärker). Gelesen wird nur aus Wasser (um 3 px geschrumpfte Maske, G), verändert
// nur Wasser (R); Boote, Steg, Felsen und ihre Konturen bleiben stehen. Ganze Pixel, damit die feinen Linien scharf
// bleiben. Zeit kommt von außen, schon auf 10 Bilder/s gestuft. In der Nahaufnahme (bg_close.png, px_scale 1,6)
// laufen Phasen in Druckkoordinaten und die Ausschläge wachsen mit, damit sich dieselben Linien gleich bewegen.
shader_type canvas_item;

uniform sampler2D water_mask : filter_nearest;
uniform float time_q = 0.0;
uniform vec2 tex_size = vec2(1264.0, 704.0);
uniform float horizon_y = 256.0;
uniform float quay_y = 436.0;
uniform float px_scale = 1.0;
uniform vec2 view = vec2(0.0);                     // Druckkoordinate der linken oberen Ecke (Nahaufnahme)

void fragment() {
	vec2 px = UV * tex_size;                       // Pixelmitte: i + 0.5
	float d = clamp((px.y - horizon_y) / (quay_y - horizon_y), 0.0, 1.0);
	vec2 pw = view + px / px_scale;                // Druckkoordinaten
	float ax = mix(1.0, 4.0, d) * px_scale;
	float ay = mix(0.0, 1.6, d) * px_scale;
	float dx = round(ax * sin(time_q * 2.0944 + pw.y * 0.105));
	float dy = round(ay * sin(time_q * 1.3963 + pw.x * 0.021 + 1.0));
	vec2 suv = (px + vec2(dx, dy)) / tex_size;
	vec4 here = texture(water_mask, UV);
	vec4 there = texture(water_mask, suv);
	vec4 moved = texture(TEXTURE, suv);
	float use = step(0.5, here.r) * step(0.5, there.g);
	COLOR = mix(COLOR, moved, use);
}
