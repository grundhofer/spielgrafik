// Dämmerungstönung plus warmes Laternenlicht nach Abstand im Bildschirmraum (Weltkoordinaten, keine Kamera).
// COLOR enthält in fragment() schon Texturfarbe x modulate.
shader_type canvas_item;

uniform vec3 tint = vec3(0.8, 0.78, 0.9);
uniform vec2 lamp_pos = vec2(854.0, 382.0);
uniform float lamp_r = 300.0;
uniform float lamp_k = 0.0;
uniform vec3 lamp_col = vec3(1.0, 0.7, 0.36);
uniform vec2 win_pos = vec2(310.0, 420.0);
uniform float win_r = 0.0;
uniform float win_k = 0.0;

varying vec2 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	float d = length((wpos - lamp_pos) * vec2(1.0, 1.25));
	float f = lamp_k * pow(clamp(1.0 - d / lamp_r, 0.0, 1.0), 1.7);
	float dw = length(wpos - win_pos);
	float fw = win_r > 0.0 ? win_k * pow(clamp(1.0 - dw / win_r, 0.0, 1.0), 2.0) : 0.0;
	COLOR.rgb *= tint + lamp_col * (f + fw);
}
