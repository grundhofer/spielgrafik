shader_type canvas_item;
// Boot: alles unterhalb der (waagerechten) Wasserlinie ausblenden. Die Linie bleibt waagerecht, auch wenn das
// Boot schaukelt, weil in Weltkoordinaten verglichen wird.

uniform float water_y = 500.0;
varying vec2 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	COLOR.a *= 1.0 - smoothstep(water_y - 0.6, water_y + 0.6, world_pos.y);
}
