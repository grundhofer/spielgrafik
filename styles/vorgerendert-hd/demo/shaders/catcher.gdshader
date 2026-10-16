// Only direct-light shadow opacity appears over the plate; the receiver itself stays transparent.
shader_type spatial;
render_mode shadow_to_opacity, depth_draw_never, cull_disabled, specular_disabled;
void fragment() {
    ALBEDO = vec3(1.0);
    METALLIC = 1.0;
    RADIANCE = vec4(0.0, 0.0, 0.0, 1.0);
    ROUGHNESS = 1.0;
    ALPHA = 0.55;
}
